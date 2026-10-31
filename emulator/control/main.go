//go:build windows

package main

import (
	"context"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"sectorv-virtualcar-control/p2audit"
	"strings"
	"syscall"
	"time"
	"unsafe"
)

const (
	HKEY_LOCAL_MACHINE  = uintptr(0x80000002)
	KEY_READ            = 0x20019
	KEY_WRITE           = 0x20006
	KEY_WOW64_32KEY     = 0x0200
	REG_SZ              = 1
	REG_DWORD           = 4
	WM_CREATE           = 1
	WM_DESTROY          = 2
	WM_COMMAND          = 0x111
	WM_APP_DONE         = 0x8001
	WS_OVERLAPPEDWINDOW = 0x00CF0000
	WS_VISIBLE          = 0x10000000
	WS_CHILD            = 0x40000000
	SW_SHOW             = 5
	COLOR_WINDOW        = 5
)

var (
	user32        = syscall.NewLazyDLL("user32.dll")
	kernel32      = syscall.NewLazyDLL("kernel32.dll")
	advapi32      = syscall.NewLazyDLL("advapi32.dll")
	regClass      = user32.NewProc("RegisterClassExW")
	createWindow  = user32.NewProc("CreateWindowExW")
	defWindow     = user32.NewProc("DefWindowProcW")
	getMessage    = user32.NewProc("GetMessageW")
	translate     = user32.NewProc("TranslateMessage")
	dispatch      = user32.NewProc("DispatchMessageW")
	showWindow    = user32.NewProc("ShowWindow")
	updateWindow  = user32.NewProc("UpdateWindow")
	msgBox        = user32.NewProc("MessageBoxW")
	setText       = user32.NewProc("SetWindowTextW")
	postQuit      = user32.NewProc("PostQuitMessage")
	postMessage   = user32.NewProc("PostMessageW")
	enableWindow  = user32.NewProc("EnableWindow")
	getModule     = kernel32.NewProc("GetModuleHandleW")
	regCreate     = advapi32.NewProc("RegCreateKeyExW")
	regOpen       = advapi32.NewProc("RegOpenKeyExW")
	regSet        = advapi32.NewProc("RegSetValueExW")
	regQuery      = advapi32.NewProc("RegQueryValueExW")
	regDelete     = advapi32.NewProc("RegDeleteTreeW")
	regClose      = advapi32.NewProc("RegCloseKey")
	baseDir       string
	mainWin       uintptr
	statusWnd     uintptr
	activeAction  int
	activeCancel  context.CancelFunc
	actionResults = make(chan actionResult, 1)
	actionButtons []uintptr
)

const subkey = `SOFTWARE\PassThruSupport.04.04\SectorV Virtual Car`

func ptr(s string) *uint16 { return syscall.StringToUTF16Ptr(s) }
func alert(title, msg string) {
	msgBox.Call(mainWin, uintptr(unsafe.Pointer(ptr(msg))), uintptr(unsafe.Pointer(ptr(title))), 0x40)
}
func regSetStr(key uintptr, name, value string) error {
	data := syscall.StringToUTF16(value)
	r, _, _ := regSet.Call(key, uintptr(unsafe.Pointer(ptr(name))), 0, REG_SZ, uintptr(unsafe.Pointer(&data[0])), uintptr(len(data)*2))
	runtime.KeepAlive(data)
	if r != 0 {
		return fmt.Errorf("RegSetValueExW %s: %d", name, r)
	}
	return nil
}
func regSetDword(key uintptr, name string, value uint32) error {
	r, _, _ := regSet.Call(key, uintptr(unsafe.Pointer(ptr(name))), 0, REG_DWORD, uintptr(unsafe.Pointer(&value)), 4)
	if r != 0 {
		return fmt.Errorf("RegSetValueExW %s: %d", name, r)
	}
	return nil
}
func currentDLL() (string, error) {
	if baseDir == "" {
		return "", errors.New("каталог приложения не определён")
	}
	return filepath.Abs(filepath.Join(baseDir, "VirtualCarJ2534.dll"))
}

// Inspect a DLL's PE machine field without loading native code.
func peMachine(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()
	var header [64]byte
	if _, err = io.ReadFull(f, header[:]); err != nil {
		return "", err
	}
	if string(header[:2]) != "MZ" {
		return "", errors.New("DLL не является PE-файлом")
	}
	off := int64(binary.LittleEndian.Uint32(header[0x3c:0x40]))
	if off < 64 || off > 1024*1024 {
		return "", errors.New("неверный PE offset")
	}
	var signature [6]byte
	if _, err = f.ReadAt(signature[:], off); err != nil {
		return "", err
	}
	if string(signature[:4]) != "PE\x00\x00" {
		return "", errors.New("отсутствует подпись PE")
	}
	switch binary.LittleEndian.Uint16(signature[4:6]) {
	case 0x014c:
		return "x86", nil
	case 0x8664:
		return "x64", nil
	case 0xAA64:
		return "ARM64", nil
	default:
		return "другая архитектура", nil
	}
}

func regGetString(key uintptr, name string) (string, error) {
	var kind, size uint32
	r, _, _ := regQuery.Call(key, uintptr(unsafe.Pointer(ptr(name))), 0, uintptr(unsafe.Pointer(&kind)), 0, uintptr(unsafe.Pointer(&size)))
	if r != 0 {
		return "", fmt.Errorf("RegQueryValueExW %s: %d", name, r)
	}
	if kind != REG_SZ {
		return "", fmt.Errorf("RegQueryValueExW %s: тип не REG_SZ", name)
	}
	if size < 2 || size > 65536 || size%2 != 0 {
		return "", fmt.Errorf("RegQueryValueExW %s: неверный размер", name)
	}
	buf := make([]uint16, size/2)
	r, _, _ = regQuery.Call(key, uintptr(unsafe.Pointer(ptr(name))), 0, uintptr(unsafe.Pointer(&kind)), uintptr(unsafe.Pointer(&buf[0])), uintptr(unsafe.Pointer(&size)))
	if r != 0 {
		return "", fmt.Errorf("RegQueryValueExW %s: %d", name, r)
	}
	return syscall.UTF16ToString(buf), nil
}

func registeredDLL() (string, error) {
	var k uintptr
	r, _, _ := regOpen.Call(HKEY_LOCAL_MACHINE, uintptr(unsafe.Pointer(ptr(subkey))), 0, KEY_READ|KEY_WOW64_32KEY, uintptr(unsafe.Pointer(&k)))
	if r != 0 {
		return "", fmt.Errorf("адаптер не найден в Registry32 (код %d)", r)
	}
	defer regClose.Call(k)
	return regGetString(k, "FunctionLibrary")
}

func registrationProblem() error {
	expected, err := currentDLL()
	if err != nil {
		return err
	}
	actual, err := registeredDLL()
	if err != nil {
		return err
	}
	if !filepath.IsAbs(actual) {
		return fmt.Errorf("путь FunctionLibrary не абсолютный: %q", actual)
	}
	if !strings.EqualFold(filepath.Clean(actual), filepath.Clean(expected)) {
		return fmt.Errorf("адаптер указывает на другой каталог: %s", actual)
	}
	arch, err := peMachine(actual)
	if err != nil {
		return fmt.Errorf("библиотека недоступна: %w", err)
	}
	if arch != "x86" {
		return fmt.Errorf("для этой сборки требуется x86 DLL; обнаружена %s", arch)
	}
	return nil
}

func diagnosticReport() (string, error) {
	expected, err := currentDLL()
	if err != nil {
		return "", err
	}
	actual, lookupErr := registeredDLL()
	report := "Диагностика J2534 v04.04 (Registry32)\n" +
		"Ключ: HKLM\\" + subkey + "\n" +
		"DLL в папке приложения: " + expected + "\n"
	if arch, e := peMachine(expected); e == nil {
		report += "Архитектура DLL: " + arch + "\n"
	} else {
		report += "Проблема с DLL: " + e.Error() + "\n"
	}
	if lookupErr != nil {
		report += "Состояние реестра: " + lookupErr.Error() + "\n"
	} else {
		report += "FunctionLibrary: " + actual + "\n"
	}
	profile := filepath.Join(baseDir, "virtualcar.ini")
	report += "Профиль рядом с EXE: " + profile + "\n"
	if blob, e := os.ReadFile(profile); e == nil {
		section := ""
		found := map[string]bool{}
		for _, raw := range strings.Split(string(blob), "\n") {
			line := strings.TrimSpace(raw)
			if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
				section = strings.ToUpper(strings.TrimSpace(line[1 : len(line)-1]))
				continue
			}
			if section == "ECU1" {
				for _, key := range []string{"DIDF1B0Hex", "DIDF1A3Hex"} {
					if strings.HasPrefix(strings.ToUpper(line), strings.ToUpper(key)+"=") {
						value := strings.TrimSpace(strings.SplitN(line, "=", 2)[1])
						found[key] = value != "" && !strings.HasPrefix(value, ";")
					}
				}
			}
		}
		for _, key := range []string{"DIDF1B0Hex", "DIDF1A3Hex"} {
			status := "пусто (ответ не настроен)"
			if found[key] {
				status = "задано (структура НЕ проверена)"
			}
			report += key + ": " + status + "\n"
		}
	} else {
		report += "Ошибка чтения INI: " + e.Error() + "\n"
	}
	if actual != "" && !strings.EqualFold(filepath.Clean(actual), filepath.Clean(expected)) {
		report += "ВНИМАНИЕ: SectorV загрузит конфигурацию рядом с зарегистрированной DLL, а не рядом с этим EXE.\n"
	}
	if e := registrationProblem(); e != nil {
		report += "\nОшибка: " + e.Error() + "\nРешение: запустите от администратора и нажмите «Установить адаптер»."
	} else {
		report += "\nПроверка регистрации пройдена. Если SectorV не показывает адаптер, проверьте разрядность SectorV и поддержку J2534 v04.04."
	}
	return report, nil
}

// switchLabProfile is explicit and opt-in. Preserve the previous custom INI
// before switching, as the synthetic fixture values are NOT real Volvo IDs.
func switchLabProfile(mode string) (string, error) {
	var src string
	switch mode {
	case "experimental":
		src = "virtualcar-experimental.ini"
	case "vdash":
		src = "virtualcar-vdash-lab.ini"
	case "p2":
		src = "virtualcar-p2.ini"
	case "p2demo":
		// Prefer the private XC90 fixture if the user extracted private-P2.
		// The public lab profile has an unrelated synthetic VIN and must not
		// silently replace a user's read-only test fixture.
		privateSource := filepath.Join("private-P2", "virtualcar-p2-b9fb-lab-vin.ini")
		if _, err := os.Stat(filepath.Join(baseDir, privateSource)); err == nil {
			src = privateSource
		} else if !os.IsNotExist(err) {
			return "", fmt.Errorf("проверка личного P2 профиля: %w", err)
		} else {
			src = "virtualcar-p2-b9fb-lab-vin.ini"
		}
	case "default":
		src = "virtualcar-default.ini"
	default:
		return "", fmt.Errorf("неизвестный профиль: %s", mode)
	}
	sourcePath := filepath.Join(baseDir, src)
	destPath := filepath.Join(baseDir, "virtualcar.ini")
	blob, err := os.ReadFile(sourcePath)
	if err != nil {
		return "", fmt.Errorf("не удалось прочитать %s: %w", src, err)
	}
	if ((mode == "p2" || mode == "p2demo") && (!strings.Contains(string(blob), "[P2]") || !strings.Contains(string(blob), "[D2_50]"))) || (mode != "p2" && mode != "p2demo" && (!strings.Contains(string(blob), "[ECU1]") || !strings.Contains(string(blob), "DIDF1B0Hex=") || !strings.Contains(string(blob), "DIDF1A3Hex="))) {
		return "", fmt.Errorf("файл %s не содержит ожидаемые настройки CEM", src)
	}
	if mode == "p2demo" {
		pf := p2audit.ReadProfile(string(blob))
		validFB := false
		for _, fixture := range pf.Fixtures {
			if fixture.Name == "D2_50" && fixture.Count == 13 && fixture.Valid {
				validFB = true
			}
		}
		if !validFB {
			return "", fmt.Errorf("P2 B9FB профиль не прошёл проверку 13 кадров и VIN; virtualcar.ini не изменён")
		}
	}
	previous, err := os.ReadFile(destPath)
	if err != nil && !os.IsNotExist(err) {
		return "", err
	}
	if err == nil {
		if string(previous) == string(blob) {
			return "Профиль уже выбран: " + mode + ". Для SectorV нужен полный перезапуск, чтобы он заново загрузил INI.", nil
		}
		stamp := time.Now().Format("20060102-150405.000")
		backup := filepath.Join(baseDir, "virtualcar-backup-"+stamp+".ini")
		if e := os.WriteFile(backup, previous, 0644); e != nil {
			return "", fmt.Errorf("резервная копия профиля не создана, изменения отменены: %w", e)
		}
	}
	tmp := destPath + ".new"
	if e := os.WriteFile(tmp, blob, 0644); e != nil {
		return "", e
	}
	// SectorV must be closed before switching profiles: DLL reads INI at Open.
	if e := os.Rename(tmp, destPath); e != nil {
		os.Remove(tmp)
		return "", fmt.Errorf("не удалось заменить virtualcar.ini (закройте SectorV): %w", e)
	}
	result := "Выбран " + mode + " профиль; virtualcar.ini обновлён. Предыдущий профиль сохранён в резервной копии.\n"
	result += "Полностью закройте и повторно запустите SectorV: работающая DLL не перечитает INI автоматически.\n"
	if mode == "experimental" {
		result += "F1B0/F1A3 содержат только SIM-байты. Это не реальные идентификаторы CEM и не гарантия VIN."
	}
	if mode == "p2" {
		result += "P2 2005-2014: включены D2 запросы CEM B9F0/B9FB/B9FC. Ответы разрешены только для загруженных и проверенных CAN-трасс. Без них VIN не появится."
	}
	if mode == "p2demo" {
		result += "Активировано из: " + src + "\n"
		if strings.Contains(string(blob), "FixtureProvenance = historical_public_2005_fixture_with_private_VIN") {
			result += "P2 B9FB: локальный частный профиль с VIN владельца; остальные поля из исторической записи 2005 года. Не публикуйте INI, полноценная идентификация не гарантирована."
		} else {
			result += "P2 B9FB: 13 кадров из опубликованного D2 лога, исходный VIN заменён синтетическим. Остальные исторические поля НЕ соответствуют XC90: идентификация не гарантирована."
		}
	}
	if mode == "vdash" {
		result += "VDASH LAB: включён синтетический CAN 0x555 и ISO15765 RxStart. Это диагностический A/B тест, не зажигание Volvo."
	}
	return result, nil
}

func install() error {
	dll, err := currentDLL()
	if err != nil {
		return err
	}
	arch, err := peMachine(dll)
	if err != nil {
		return fmt.Errorf("DLL не найдена или повреждена: %w", err)
	}
	if arch != "x86" {
		return fmt.Errorf("ожидалась DLL x86; обнаружено: %s", arch)
	}
	var key uintptr
	var disposition uint32
	r, _, _ := regCreate.Call(HKEY_LOCAL_MACHINE, uintptr(unsafe.Pointer(ptr(subkey))), 0, 0, 0, KEY_WRITE|KEY_WOW64_32KEY, 0, uintptr(unsafe.Pointer(&key)), uintptr(unsafe.Pointer(&disposition)))
	if r != 0 {
		return fmt.Errorf("RegCreateKeyExW: %d (start as Administrator)", r)
	}
	defer regClose.Call(key)
	for _, kv := range [][2]string{{"Vendor", "SectorV Virtual Lab"}, {"Name", "SectorV Virtual Car (J2534)"}, {"FunctionLibrary", dll}, {"ConfigApplication", ""}} {
		if err := regSetStr(key, kv[0], kv[1]); err != nil {
			return err
		}
	}
	for _, v := range [][2]interface{}{{"CAN", uint32(1)}, {"ISO15765", uint32(1)}, {"MessageVersion", uint32(0x404)}} {
		if err := regSetDword(key, v[0].(string), v[1].(uint32)); err != nil {
			return err
		}
	}
	// A key existing in HKLM is not enough: verify its DLL location and PE architecture.
	if err := registrationProblem(); err != nil {
		return fmt.Errorf("регистрация записана, но проверка не пройдена: %w", err)
	}
	return nil
}
func uninstall() error {
	parent := `SOFTWARE\PassThruSupport.04.04`
	var k uintptr
	r, _, _ := regOpen.Call(HKEY_LOCAL_MACHINE, uintptr(unsafe.Pointer(ptr(parent))), 0, KEY_WRITE|KEY_WOW64_32KEY, uintptr(unsafe.Pointer(&k)))
	if r != 0 {
		return fmt.Errorf("RegOpenKeyExW: %d (start as Administrator)", r)
	}
	defer regClose.Call(k)
	r, _, _ = regDelete.Call(k, uintptr(unsafe.Pointer(ptr("SectorV Virtual Car"))))
	if r != 0 {
		return fmt.Errorf("RegDeleteTreeW: %d", r)
	}
	return nil
}

type msg struct {
	ProtocolID, RxStatus, TxFlags, Timestamp, DataSize, ExtraDataIndex uint32
	Data                                                               [4128]byte
}

func call(dll *syscall.DLL, name string, args ...uintptr) (uintptr, error) {
	proc, e := dll.FindProc(name)
	if e != nil {
		return 0, e
	}
	ret, _, _ := proc.Call(args...)
	if ret != 0 {
		return ret, fmt.Errorf("%s returned 0x%X", name, ret)
	}
	return ret, nil
}
func selfTest() (string, error) {
	path := filepath.Join(baseDir, "VirtualCarJ2534.dll")
	dll, e := syscall.LoadDLL(path)
	if e != nil {
		return "", e
	}
	defer dll.Release()
	var dev uint32
	if _, e = call(dll, "PassThruOpen", 0, uintptr(unsafe.Pointer(&dev))); e != nil {
		return "", e
	}
	defer call(dll, "PassThruClose", uintptr(dev))
	var chanID uint32
	if _, e = call(dll, "PassThruConnect", uintptr(dev), 6, 0, 500000, uintptr(unsafe.Pointer(&chanID))); e != nil {
		return "", e
	}
	defer call(dll, "PassThruDisconnect", uintptr(chanID))
	var out msg
	out.ProtocolID = 6
	out.DataSize = 7
	copy(out.Data[:], []byte{0, 0, 7, 0xE0, 0x22, 0xF1, 0x90})
	count := uint32(1)
	if _, e = call(dll, "PassThruWriteMsgs", uintptr(chanID), uintptr(unsafe.Pointer(&out)), uintptr(unsafe.Pointer(&count)), 500); e != nil {
		return "", e
	}
	var in msg
	count = 1
	if _, e = call(dll, "PassThruReadMsgs", uintptr(chanID), uintptr(unsafe.Pointer(&in)), uintptr(unsafe.Pointer(&count)), 500); e != nil {
		return "", e
	}
	if in.DataSize < 24 || in.Data[4] != 0x62 || in.Data[5] != 0xF1 || in.Data[6] != 0x90 {
		return "", errors.New("unexpected VIN response")
	}
	vin := string(in.Data[7:24])
	if len(vin) != 17 {
		return "", errors.New("invalid VIN length")
	}
	return fmt.Sprintf("J2534 Open/Connect/Write/Read: OK\nVIN: %s\nОтвет ECU, CAN ID: %02X%02X%02X%02X", vin, in.Data[0], in.Data[1], in.Data[2], in.Data[3]), nil
}

// A read-only protocol probe. It tests the emulator, not SectorV itself.
func cemSelfTest() (string, error) {
	path := filepath.Join(baseDir, "VirtualCarJ2534.dll")
	dll, e := syscall.LoadDLL(path)
	if e != nil {
		return "", e
	}
	defer dll.Release()
	var dev uint32
	if _, e = call(dll, "PassThruOpen", 0, uintptr(unsafe.Pointer(&dev))); e != nil {
		return "", e
	}
	defer call(dll, "PassThruClose", uintptr(dev))
	var cid uint32
	if _, e = call(dll, "PassThruConnect", uintptr(dev), 5, 0, 500000, uintptr(unsafe.Pointer(&cid))); e != nil {
		return "", e
	}
	var out msg
	out.ProtocolID = 5
	out.DataSize = 12
	copy(out.Data[:], []byte{0, 0, 7, 0x26, 0x03, 0x22, 0xF1, 0x14, 0, 0, 0, 0})
	n := uint32(1)
	if _, e = call(dll, "PassThruWriteMsgs", uintptr(cid), uintptr(unsafe.Pointer(&out)), uintptr(unsafe.Pointer(&n)), 100); e != nil {
		return "", e
	}
	var in msg
	n = 1
	if _, e = call(dll, "PassThruReadMsgs", uintptr(cid), uintptr(unsafe.Pointer(&in)), uintptr(unsafe.Pointer(&n)), 100); e != nil {
		return "", e
	}
	if in.DataSize != 12 || in.Data[2] != 0x07 || in.Data[3] != 0x2E || in.Data[4] != 0x10 || in.Data[5] != 0x14 || in.Data[6] != 0x62 || in.Data[7] != 0xF1 || in.Data[8] != 0x14 {
		return "", errors.New("P3 CEM F114: ожидался первый кадр ISO-TP с положительным ответом")
	}
	// In the raw CAN channel the adapter must wait for FlowControl from 0x726.
	out = msg{}
	out.ProtocolID = 5
	out.DataSize = 12
	copy(out.Data[:], []byte{0, 0, 7, 0x26, 0x30, 0, 0, 0, 0, 0, 0, 0})
	n = 1
	if _, e = call(dll, "PassThruWriteMsgs", uintptr(cid), uintptr(unsafe.Pointer(&out)), uintptr(unsafe.Pointer(&n)), 100); e != nil {
		return "", e
	}
	assembled := append([]byte{}, in.Data[6:12]...)
	for i := 0; i < 2; i++ {
		in = msg{}
		n = 1
		if _, e = call(dll, "PassThruReadMsgs", uintptr(cid), uintptr(unsafe.Pointer(&in)), uintptr(unsafe.Pointer(&n)), 100); e != nil {
			return "", fmt.Errorf("P3 CEM F114 ISO-TP CF%d: %w", i+1, e)
		}
		if in.DataSize != 12 || in.Data[4] != byte(0x21+i) {
			return "", fmt.Errorf("P3 CEM F114: неверный последовательный кадр %d", i+1)
		}
		assembled = append(assembled, in.Data[5:12]...)
	}
	if len(assembled) < 20 || assembled[0] != 0x62 || assembled[1] != 0xF1 || assembled[2] != 0x14 {
		return "", errors.New("P3 CEM F114: ошибка восстановления VIN")
	}
	vin := string(assembled[3:20])
	if len(vin) != 17 {
		return "", errors.New("P3 CEM F114: VIN не имеет длину 17")
	}
	call(dll, "PassThruDisconnect", uintptr(cid))
	if _, e = call(dll, "PassThruConnect", uintptr(dev), 5, 0x100, 500000, uintptr(unsafe.Pointer(&cid))); e != nil {
		return "", e
	}
	defer call(dll, "PassThruDisconnect", uintptr(cid))
	result := fmt.Sprintf("P3 CEM (0x726 / 0x72E): F114 VIN = %s (синтетический тест).\n", vin)
	for _, target := range []byte{0x40, 0x50} {
		out = msg{}
		out.ProtocolID = 5
		out.TxFlags = 0x100
		out.DataSize = 12
		copy(out.Data[:], []byte{0, 0x0F, 0xFF, 0xFE, 0xCB, target, 0xB9, 0xFB, 0, 0, 0, 0})
		n = 1
		if _, e = call(dll, "PassThruWriteMsgs", uintptr(cid), uintptr(unsafe.Pointer(&out)), uintptr(unsafe.Pointer(&n)), 100); e != nil {
			return "", e
		}
		in = msg{}
		n = 1
		rc, readErr := call(dll, "PassThruReadMsgs", uintptr(cid), uintptr(unsafe.Pointer(&in)), uintptr(unsafe.Pointer(&n)), 0)
		if readErr == nil && in.DataSize >= 12 {
			result += fmt.Sprintf("D2 CEM 0x%02X: получен воспроизведённый кадр.\n", target)
		} else if rc == 0x10 || rc == 0x09 {
			result += fmt.Sprintf("D2 CEM 0x%02X: профиль ответа не задан.\n", target)
		} else {
			return "", readErr
		}
	}
	result += "Это проверка адаптера, а не успешное подключение SectorV."
	return result, nil
}

// A dedicated read-only P2 test: confirms DLL wiring and whether any recorded
// CEM data was loaded. Never tries security access, coding or programming.
func p2SelfTest() (string, error) {
	dll, err := syscall.LoadDLL(filepath.Join(baseDir, "VirtualCarJ2534.dll"))
	if err != nil {
		return "", err
	}
	defer dll.Release()
	var dev uint32
	if _, err = call(dll, "PassThruOpen", 0, uintptr(unsafe.Pointer(&dev))); err != nil {
		return "", err
	}
	defer call(dll, "PassThruClose", uintptr(dev))
	var cid uint32
	if _, err = call(dll, "PassThruConnect", uintptr(dev), 5, 0x100, 500000, uintptr(unsafe.Pointer(&cid))); err != nil {
		return "", err
	}
	defer call(dll, "PassThruDisconnect", uintptr(cid))
	result := "Volvo P2 D2 read-only | 500 kbit/s | 29-bit CAN\n"
	for _, op := range []byte{0xF0, 0xFB, 0xFC} {
		var out msg
		out.ProtocolID = 5
		out.TxFlags = 0x100
		out.DataSize = 12
		copy(out.Data[:], []byte{0x00, 0x0F, 0xFF, 0xFE, 0xCB, 0x50, 0xB9, op, 0, 0, 0, 0})
		count := uint32(1)
		if _, err = call(dll, "PassThruWriteMsgs", uintptr(cid), uintptr(unsafe.Pointer(&out)), uintptr(unsafe.Pointer(&count)), 100); err != nil {
			return "", err
		}
		nframes := 0
		var responseID uint32
		for nframes < 64 {
			var in msg
			count = 1
			rc, _ := call(dll, "PassThruReadMsgs", uintptr(cid), uintptr(unsafe.Pointer(&in)), uintptr(unsafe.Pointer(&count)), 35)
			if rc == 9 || rc == 16 {
				break
			}
			if rc != 0 {
				return "", fmt.Errorf("B9%02X: PassThruReadMsgs code %d", op, rc)
			}
			if in.DataSize < 12 {
				return "", errors.New("P2 D2: short CAN frame")
			}
			if nframes == 0 {
				responseID = binary.BigEndian.Uint32(in.Data[:4])
			}
			if binary.BigEndian.Uint32(in.Data[:4]) != responseID {
				return "", errors.New("P2 D2: response CAN ID changed during replay")
			}
			nframes++
		}
		result += fmt.Sprintf("CEM 0x50 B9%02X: %d frames, response ID 0x%08X\n", op, nframes, responseID)
	}
	return result + "0 frames = fixture missing. This is not proof of vehicle identification.", nil
}

// markSession adds an append-only boundary without truncating an active client's log.
// SectorV and VirtualCarControl may have distinct processes and therefore must
// not share a process-local session counter.
const traceMarker = "=== SECTORV VIRTUALCAR SESSION "

func markSession() (string, error) {
	path := filepath.Join(os.TempDir(), "SectorVVirtualCar.log")
	tag := time.Now().Format("20060102-150405")
	f, err := os.OpenFile(path, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0644)
	if err != nil {
		return "", err
	}
	_, writeErr := fmt.Fprintf(f, "\r\n%s%s ===\r\n", traceMarker, tag)
	closeErr := f.Close()
	if writeErr != nil {
		return "", writeErr
	}
	if closeErr != nil {
		return "", closeErr
	}
	return "Сессия " + tag + " начата. Запустите SectorV и выберите P2. После попытки определения откройте 8. Анализ журнала.", nil
}

// Analyze only the latest marked attempt, keeping the raw SectorV lines for
// post-mortem analysis. No claim is made that delivered CAN frames were accepted.
func analyzeLog() (string, error) {
	path := filepath.Join(os.TempDir(), "SectorVVirtualCar.log")
	blob, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	allLines := strings.Split(strings.ReplaceAll(string(blob), "\r\n", "\n"), "\n")
	lines := allLines
	tag := "unmarked"
	for i, line := range allLines {
		if strings.HasPrefix(line, traceMarker) {
			lines = allLines[i+1:]
			tag = strings.TrimSuffix(strings.TrimPrefix(line, traceMarker), " ===")
			tag = strings.TrimSpace(tag)
		}
	}
	var sector []string
	for _, line := range lines {
		if strings.HasPrefix(line, "[PID=") && strings.Contains(strings.ToLower(line), " sectorv.exe]") {
			sector = append(sector, line)
		}
	}
	// Without a session marker the log may contain weeks of previous builds.
	// Analyze only the latest SectorV PID instead of combining incompatible runs.
	if tag == "unmarked" && len(sector) > 0 {
		latest := sector[len(sector)-1][5:13]
		filtered := make([]string, 0, len(sector))
		for _, line := range sector {
			if strings.HasPrefix(line, "[PID="+latest+" SectorV.exe]") {
				filtered = append(filtered, line)
			}
		}
		sector = filtered
	}
	predicates := []struct{ name, pattern string }{
		{"Открытие адаптера", "PassThruOpen ->"},
		{"Подключение CAN", "PassThruConnect protocol"},
		{"Вызов READ_VBATT", "PassThruIoctl READ_VBATT"},
		{"Запрос VIN P3 F114", "TX (app request) 00 00 07 26 03 22 F1 14"},
		{"Отправлен VIN P3", "P3 CEM F114 VIN reply"},
		{"Доставлены RX-кадры 0x72E", "PassThruReadMsgs -> delivered 00 00 07 2E"},
		{"Запрос CEM F1B0", "TX (app request) 00 00 07 26 03 22 F1 B0"},
		{"Ответ F1B0", "F1B0 configured lab fixture"},
		{"Запрос CEM F1A3", "TX (app request) 00 00 07 26 03 22 F1 A3"},
		{"Ответ F1A3", "F1A3 configured lab fixture"},
		{"P2 D2 B9F0/B9FB запрошен", "TX (app request) 00 0F FF FE CB"},
		{"P2 D2 запись воспроизведена", "P2 D2 read-only recorded frames staged"},
		{"P2 D2 нет записи", "P2 D2 read command: no validated response fixture"},
		{"P2 D2 RX 0x01200003", "PassThruReadMsgs -> delivered 01 20 00 03"},
		{"Команда P2 FF C8 (сброс ECU)", "TX (app request) 00 0F FF FE FF C8"},
		{"Функциональный сброс 11 81", "TX (app request) 00 00 07 DF 02 11 81"},
		{"Таймауты J2534", "PassThruReadMsgs timeout:"},
	}
	out := fmt.Sprintf("Сессия: %s\nВсего строк в сессии: %d\nСтрок SectorV.exe: %d\n", tag, len(lines), len(sector))
	out += "Передача RX в J2534 не доказывает, что SectorV принял VIN.\n\n"
	for _, p := range predicates {
		count := 0
		for _, s := range sector {
			if strings.Contains(s, p.pattern) {
				count++
			}
		}
		out += fmt.Sprintf("%s: %d\n", p.name, count)
	}
	out += "\n" + p2audit.SummarizeLog(strings.Join(sector, "\n")).Report() + "\n"
	out += "\nПоследние обращения SectorV (до 16):\n"
	relevant := []string{}
	for _, line := range sector {
		if strings.Contains(line, "TX (app request)") || strings.Contains(line, "Active INI:") ||
			strings.Contains(line, "PassThruIoctl READ_VBATT") || strings.Contains(line, "fixture lengths") ||
			strings.Contains(line, "F1B0 configured") || strings.Contains(line, "F1A3 configured") ||
			strings.Contains(line, "P2 D2") || strings.Contains(line, "P2 fixture") ||
			strings.Contains(line, "PassThruReadMsgs timeout") {
			relevant = append(relevant, line)
		}
	}
	if len(relevant) > 16 {
		relevant = relevant[len(relevant)-16:]
	}
	out += strings.Join(relevant, "\n") + "\n"
	if len(sector) == 0 {
		out += "\nНет вызовов SectorV. После начала захвата надо повторить подключение.\n"
	}
	tracePath := filepath.Join(os.TempDir(), "SectorVVirtualCar-session-"+tag+".txt")
	reportPath := filepath.Join(os.TempDir(), "SectorVVirtualCar-report-"+tag+".txt")
	if err := os.WriteFile(tracePath, []byte(strings.Join(sector, "\r\n")+"\r\n"), 0644); err != nil {
		return "", err
	}
	if err := os.WriteFile(reportPath, []byte(out), 0644); err != nil {
		return "", err
	}
	out += "\nПолная трасса SectorV: " + tracePath + "\nСводка: " + reportPath
	return out, nil
}

// p2Audit inspects the actual local INI and last captured SectorV session.
// It is entirely read-only: no J2534 calls or ECU commands are made.
func p2Audit() (string, error) {
	profileFile := filepath.Join(baseDir, "virtualcar.ini")
	profileData, err := os.ReadFile(profileFile)
	if err != nil {
		return "", fmt.Errorf("открыть профиль P2: %w", err)
	}
	dllWarning := ""
	if registered, regErr := registeredDLL(); regErr == nil {
		if expected, exeErr := currentDLL(); exeErr == nil && !strings.EqualFold(filepath.Clean(registered), filepath.Clean(expected)) {
			dllWarning = "\nВНИМАНИЕ: зарегистрированный J2534 адаптер ссылается на другую DLL: " + registered + "\n" +
				"SectorV читает INI рядом с ЭТОЙ DLL, а не рядом с VirtualCarControl.exe. Выполните кнопку 1 (установка адаптера), закройте и заново откройте SectorV.\n"
		}
	}
	parsedProfile := p2audit.ReadProfile(string(profileData))
	report := "АКТИВНЫЙ INI: " + profileFile + "\n" + parsedProfile.Report() + dllWarning
	has50 := false
	for _, fixture := range parsedProfile.Fixtures {
		if fixture.Name == "D2_50" && fixture.Count > 0 && fixture.Valid {
			has50 = true
		}
	}
	if !has50 {
		report += "\nОШИБКА ПРОФИЛЯ: ответ CEM 0x50 B9FB отключён или невалиден.\n"
		private := filepath.Join(baseDir, "private-P2", "virtualcar-p2-b9fb-lab-vin.ini")
		if _, e := os.Stat(private); e == nil {
			report += "Личный P2 найден: закройте SectorV и нажмите кнопку 15 для активации.\n"
		} else {
			report += "Личный P2 не найден: распакуйте отдельный архив XC90V8-private-profile внутрь папки приложения (папка private-P2), затем нажмите кнопку 15.\n"
		}
		report += "Не используйте кнопку 13 для теста VIN: базовый P2 намеренно без записанных ответов.\n"
	} else {
		report += "\nCEM 0x50 B9FB: ответ настроен. Для загрузки изменений в DLL полностью перезапустите SectorV.\n"
	}
	logFile := filepath.Join(os.TempDir(), "SectorVVirtualCar.log")
	logData, logErr := os.ReadFile(logFile)
	if logErr == nil {
		report += "\n" + p2audit.SummarizeLog(string(logData)).Report()
	} else if !os.IsNotExist(logErr) {
		report += "\nЖурнал не прочитан: " + logErr.Error() + "\n"
	} else {
		report += "\nЖурнала пока нет. После запуска SectorV нажмите 9, затем 16.\n"
	}
	report += "\nНет подтверждения, что SectorV принял VIN или активировал функции автомобиля.\n"
	path := filepath.Join(os.TempDir(), "SectorVVirtualCar-P2-audit.txt")
	if err := os.WriteFile(path, []byte(report), 0644); err != nil {
		return "", err
	}
	report += "\nОтчёт сохранён: " + path
	return report, nil
}

// Run potentially untrusted/hanging J2534 DLL calls in a *separate process*.
// A goroutine alone would leave a stuck native call alive; CommandContext can
// terminate the process after its deadline without freezing this Win32 window.
type actionResult struct {
	id     int
	output string
	err    error
}

func runCLI(action string) int {
	var output string
	var err error
	switch action {
	case "--self-test":
		output, err = selfTest()
	case "--cem-test":
		output, err = cemSelfTest()
	case "--install":
		err = install()
		output = "Виртуальный адаптер зарегистрирован. Перезапустите SectorV."
	case "--uninstall":
		err = uninstall()
		output = "Удалена только запись SectorV Virtual Car в реестре."
	case "--diagnose":
		output, err = diagnosticReport()
	case "--analyze-log":
		output, err = analyzeLog()
	case "--mark-session":
		output, err = markSession()
	case "--profile-experimental":
		output, err = switchLabProfile("experimental")
	case "--profile-default":
		output, err = switchLabProfile("default")
	case "--profile-vdash":
		output, err = switchLabProfile("vdash")
	case "--profile-p2":
		output, err = switchLabProfile("p2")
	case "--profile-p2-demo":
		output, err = switchLabProfile("p2demo")
	case "--p2-test":
		output, err = p2SelfTest()
	case "--p2-audit":
		output, err = p2Audit()
	default:
		fmt.Fprintln(os.Stderr, "Unknown action:", action)
		return 2
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, "Ошибка:", err)
		return 1
	}
	fmt.Println(output)
	return 0
}

func setStatus(s string) {
	if statusWnd != 0 {
		setText.Call(statusWnd, uintptr(unsafe.Pointer(ptr(s))))
	}
}

func startAction(id int) {
	if activeAction != 0 {
		return
	}
	commands := map[int]string{101: "--install", 102: "--self-test", 105: "--uninstall", 106: "--cem-test", 107: "--diagnose", 108: "--analyze-log", 109: "--mark-session", 110: "--profile-experimental", 111: "--profile-default", 112: "--profile-vdash", 113: "--profile-p2", 114: "--p2-test", 115: "--profile-p2-demo", 116: "--p2-audit"}
	descriptions := map[int]string{101: "Установка адаптера", 102: "Самопроверка", 105: "Удаление адаптера", 106: "Проверка CEM P3 / D2", 107: "Диагностика регистрации", 108: "Анализ журнала SectorV", 109: "Новая сессия P2/P3", 110: "Тестовый профиль", 111: "Базовый профиль", 112: "VDASH LAB профиль", 113: "P2 без B9FB", 114: "Проверка P2 D2", 115: "P2 VIN (личный или лабораторный)", 116: "Аудит P2 профиля и журнала"}
	command := commands[id]
	if command == "" {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 8*time.Second)
	activeCancel = cancel
	activeAction = id
	for _, h := range actionButtons {
		enableWindow.Call(h, 0)
	}
	setStatus("Выполняется: " + descriptions[id] + " (таймаут 8 с)...")
	hwnd := mainWin
	go func() {
		defer cancel()
		exe, err := os.Executable()
		output := ""
		if err == nil {
			cmd := exec.CommandContext(ctx, exe, command)
			cmd.Dir = baseDir // The J2534 DLL always lives next to this executable.
			cmd.SysProcAttr = &syscall.SysProcAttr{HideWindow: true}
			bytes, cmdErr := cmd.CombinedOutput()
			output = strings.TrimSpace(string(bytes))
			err = cmdErr
		}
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			err = errors.New("Превышено 8 секунд. Зависшая проверка остановлена; окно управления продолжает работать")
		}
		actionResults <- actionResult{id: id, output: output, err: err}
		postMessage.Call(hwnd, WM_APP_DONE, 0, 0)
	}()
}

func finishAction() {
	var result actionResult
	select {
	case result = <-actionResults:
	default:
		return
	}
	if activeCancel != nil {
		activeCancel()
		activeCancel = nil
	}
	activeAction = 0
	for _, h := range actionButtons {
		enableWindow.Call(h, 1)
	}
	updateStatus()
	if result.err != nil {
		message := result.err.Error()
		if result.output != "" {
			message += "\n\n" + result.output
		}
		alert("Ошибка / таймаут", message)
		return
	}
	title := map[int]string{101: "Установлено", 102: "Самопроверка успешна", 105: "Удалено", 106: "Проверка CEM завершена", 107: "Диагностика J2534", 108: "Анализ журнала", 109: "Начало захвата", 110: "Тестовый профиль", 111: "Базовый профиль", 112: "VDASH LAB профиль", 113: "P2 без B9FB", 114: "Проверка P2 D2", 115: "P2 VIN (личный или лабораторный)", 116: "Аудит P2 профиля и журнала"}[result.id]
	alert(title, result.output)
}

func execNotepad(path string) error { return exec.Command("notepad.exe", path).Start() }
func updateStatus() {
	s := "Статус: требуется установка/исправление J2534 (кнопка 1)"
	if err := registrationProblem(); err == nil {
		s = "Статус: регистрация исправна (J2534 04.04, x86)"
	}
	if statusWnd != 0 {
		setText.Call(statusWnd, uintptr(unsafe.Pointer(ptr(s))))
	}
}
func mk(class, text string, x, y, w, h int32, id uintptr) uintptr {
	classPtr := ptr(class)
	namePtr := ptr(text)
	handle, _, _ := createWindow.Call(0, uintptr(unsafe.Pointer(classPtr)), uintptr(unsafe.Pointer(namePtr)), WS_VISIBLE|WS_CHILD, uintptr(x), uintptr(y), uintptr(w), uintptr(h), mainWin, id, 0, 0)
	return handle
}

type wcEx struct {
	size       uint32
	style      uint32
	wndProc    uintptr
	clsExtra   int32
	wndExtra   int32
	instance   uintptr
	icon       uintptr
	cursor     uintptr
	background uintptr
	menuName   *uint16
	className  *uint16
	iconSm     uintptr
}
type point struct{ x, y int32 }
type winMsg struct {
	hwnd           uintptr
	msg            uint32
	wParam, lParam uintptr
	time           uint32
	point          point
	private        uint32
}

func wndProc(hwnd uintptr, msg uint32, wp, lp uintptr) uintptr {
	switch msg {
	case WM_CREATE:
		mainWin = hwnd
		mk("STATIC", "Виртуальный автомобиль | J2534", 20, 18, 560, 26, 0)
		mk("STATIC", "Лабораторный эмулятор. Реальный автомобиль не требуется.", 20, 52, 580, 24, 0)
		statusWnd = mk("STATIC", "Проверка адаптера...", 20, 88, 580, 24, 0)
		actionButtons = []uintptr{
			mk("BUTTON", "1. Установить адаптер", 20, 130, 260, 40, 101),
			mk("BUTTON", "2. Проверить эмулятор", 300, 130, 260, 40, 102),
			mk("BUTTON", "5. Проверка CEM P3 / D2", 20, 236, 540, 40, 106),
			mk("BUTTON", "6. Удалить адаптер", 20, 289, 540, 40, 105),
		}
		mk("BUTTON", "3. Профиль автомобиля", 20, 183, 260, 40, 103)
		mk("BUTTON", "4. Журнал обмена", 300, 183, 260, 40, 104)
		/* The P2 replay self-test occupies the old noninteractive caption slot. */
		actionButtons = append(actionButtons, mk("BUTTON", "7. Диагностика J2534", 20, 340, 260, 40, 107),
			mk("BUTTON", "8. Анализ журнала", 300, 340, 260, 40, 108),
			mk("BUTTON", "9. Начать новую сессию", 300, 388, 260, 32, 109),
			mk("BUTTON", "14. Проверка P2 D2", 20, 388, 260, 32, 114),
			mk("BUTTON", "10. Тестовый профиль CEM", 20, 438, 260, 40, 110),
			mk("BUTTON", "11. Базовый профиль", 300, 438, 260, 40, 111),
			mk("BUTTON", "12. VDASH LAB", 20, 489, 260, 36, 112),
			mk("BUTTON", "13. P2 (без ответов B9FB)", 300, 489, 260, 36, 113),
			mk("BUTTON", "15. Личный P2 / тест VIN", 20, 533, 260, 32, 115),
			mk("BUTTON", "16. Аудит P2", 300, 533, 260, 32, 116))
		updateStatus()
		return 0
	case WM_COMMAND:
		id := wp & 0xFFFF
		switch id {
		case 101, 102, 105, 106, 107, 108, 109, 110, 111, 112, 113, 114, 115, 116:
			startAction(int(id))
		case 103:
			if err := execNotepad(filepath.Join(baseDir, "virtualcar.ini")); err != nil {
				alert("Ошибка", err.Error())
			}
		case 104:
			if err := execNotepad(filepath.Join(os.TempDir(), "SectorVVirtualCar.log")); err != nil {
				alert("Ошибка", err.Error())
			}
		}
		return 0
	case WM_APP_DONE:
		finishAction()
		return 0
	case WM_DESTROY:
		if activeCancel != nil {
			activeCancel()
		}
		postQuit.Call(0)
		return 0
	}
	r, _, _ := defWindow.Call(hwnd, uintptr(msg), wp, lp)
	return r
}
func main() {
	// Resolve the absolute location before GUI *or* CLI dispatch. v0.2.1
	// dispatched --install before setting baseDir, breaking child-process installs.
	exe, err := os.Executable()
	if err != nil {
		fmt.Fprintln(os.Stderr, "Cannot determine executable location:", err)
		return
	}
	baseDir = filepath.Dir(exe)
	if len(os.Args) == 2 && strings.HasPrefix(os.Args[1], "--") {
		os.Exit(runCLI(os.Args[1]))
	}
	// Window ownership and Win32 message pump must stay on the same OS thread.
	runtime.LockOSThread()
	defer runtime.UnlockOSThread()
	hInst, _, _ := getModule.Call(0)
	class := ptr("SectorVVirtualCarControl")
	wc := wcEx{size: uint32(unsafe.Sizeof(wcEx{})), wndProc: syscall.NewCallback(wndProc), instance: hInst, background: COLOR_WINDOW + 1, className: class}
	r, _, _ := regClass.Call(uintptr(unsafe.Pointer(&wc)))
	if r == 0 {
		alert("Error", "Could not register UI window class")
		return
	}
	name := ptr("SectorV Virtual Car 0.3.6.1 | Управление")
	hwnd, _, _ := createWindow.Call(0, uintptr(unsafe.Pointer(class)), uintptr(unsafe.Pointer(name)), WS_OVERLAPPEDWINDOW|WS_VISIBLE, 180, 150, 630, 640, 0, 0, hInst, 0)
	if hwnd == 0 {
		alert("Error", "Could not create UI window")
		return
	}
	mainWin = hwnd
	showWindow.Call(hwnd, SW_SHOW)
	updateWindow.Call(hwnd)
	var m winMsg
	for {
		r, _, _ := getMessage.Call(uintptr(unsafe.Pointer(&m)), 0, 0, 0)
		if int32(r) <= 0 {
			break
		}
		translate.Call(uintptr(unsafe.Pointer(&m)))
		dispatch.Call(uintptr(unsafe.Pointer(&m)))
	}
}
