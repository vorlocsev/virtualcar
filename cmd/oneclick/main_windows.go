//go:build windows

package main

import (
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"sync"
	"syscall"
	"time"
	"unsafe"
)

//go:embed assets/VirtualCarTrace32.dll assets/VirtualCarTraceAttribution-x86.exe assets/VirtualCarTraceSummary-x86.exe assets/VirtualCarIgnition-x86.exe
var embedded embed.FS

const (
	appTitle           = "Virtual Car · J2534 OneClick dev26"
	providerName       = "VirtualCar Trace VM dev26"
	providerKey        = `SOFTWARE\PassThruSupport.04.04\VirtualCar Trace VM dev26`
	wmDestroy          = 0x0002
	wmClose            = 0x0010
	wmCommand          = 0x0111
	wmSetFont          = 0x0030
	wmAppStatus        = 0x8001
	wmAppDone          = 0x8002
	wsOverlappedWindow = 0x00CF0000
	wsVisible          = 0x10000000
	wsChild            = 0x40000000
	wsBorder           = 0x00800000
	esAutoHScroll      = 0x0080
	bsPushButton       = 0x00000000
	swShow             = 5
	mbIconError        = 0x10
	mbIconInfo         = 0x40
	keyWow6432         = 0x0200
)

var (
	kernel32                                                  = syscall.NewLazyDLL("kernel32.dll")
	user32                                                    = syscall.NewLazyDLL("user32.dll")
	gdi32                                                     = syscall.NewLazyDLL("gdi32.dll")
	shell32                                                   = syscall.NewLazyDLL("shell32.dll")
	comdlg32                                                  = syscall.NewLazyDLL("comdlg32.dll")
	advapi32                                                  = syscall.NewLazyDLL("advapi32.dll")
	pCreateWindow                                             = user32.NewProc("CreateWindowExW")
	pRegisterClass                                            = user32.NewProc("RegisterClassExW")
	pDefWndProc                                               = user32.NewProc("DefWindowProcW")
	pSetText                                                  = user32.NewProc("SetWindowTextW")
	pGetText                                                  = user32.NewProc("GetWindowTextW")
	pGetMessage                                               = user32.NewProc("GetMessageW")
	pMessageBox                                               = user32.NewProc("MessageBoxW")
	pPostMessage                                              = user32.NewProc("PostMessageW")
	pSendMessage                                              = user32.NewProc("SendMessageW")
	pEnableWindow                                             = user32.NewProc("EnableWindow")
	pShellExecuteEx                                           = shell32.NewProc("ShellExecuteExW")
	pRegCreate                                                = advapi32.NewProc("RegCreateKeyExW")
	pRegSetValue                                              = advapi32.NewProc("RegSetValueExW")
	pRegDelete                                                = advapi32.NewProc("RegDeleteKeyExW")
	hwnd, hExeEdit, hDllEdit, hStatus, hRun, hOpen, hFindings uintptr
	running                                                   bool
	lastReport                                                string
	updateLock                                                sync.Mutex
	latestUpdate                                              string
	latestErr                                                 error
	latestAssessment                                          string
	font                                                      uintptr
)

type point struct{ X, Y int32 }
type winMessage struct {
	HWnd           uintptr
	Message        uint32
	WParam, LParam uintptr
	Time           uint32
	Pt             point
}
type wndClass struct {
	Size       uint32
	Style      uint32
	Proc       uintptr
	ClsExtra   int32
	WndExtra   int32
	Instance   uintptr
	Icon       uintptr
	Cursor     uintptr
	Background uintptr
	MenuName   *uint16
	ClassName  *uint16
	SmallIcon  uintptr
}
type openFileName struct {
	Size            uint32
	Owner           uintptr
	Instance        uintptr
	Filter          *uint16
	CustomFilter    *uint16
	MaxCustomFilter uint32
	FilterIndex     uint32
	File            *uint16
	MaxFile         uint32
	FileTitle       *uint16
	MaxFileTitle    uint32
	InitialDir      *uint16
	Title           *uint16
	Flags           uint32
	FileOffset      uint16
	FileExtension   uint16
	DefExt          *uint16
	CustData        uintptr
	Hook            uintptr
	TemplateName    *uint16
	Reserved        uintptr
	ReservedDword   uint32
	FlagsEx         uint32
}
type shellExecuteInfo struct {
	Size     uint32
	Mask     uint32
	Hwnd     uintptr
	Verb     *uint16
	File     *uint16
	Params   *uint16
	Dir      *uint16
	Show     int32
	InstApp  uintptr
	IDList   uintptr
	Class    *uint16
	KeyClass uintptr
	HotKey   uint32
	Icon     uintptr
	Process  uintptr
}

func w(s string) *uint16                                { p, _ := syscall.UTF16PtrFromString(s); return p }
func call(p *syscall.LazyProc, args ...uintptr) uintptr { r, _, _ := p.Call(args...); return r }
func messageBox(text string, flag uintptr) {
	call(pMessageBox, hwnd, uintptr(unsafe.Pointer(w(text))), uintptr(unsafe.Pointer(w(appTitle))), flag)
}
func setText(control uintptr, text string) { call(pSetText, control, uintptr(unsafe.Pointer(w(text)))) }
func getText(control uintptr) string {
	b := make([]uint16, 2048)
	call(pGetText, control, uintptr(unsafe.Pointer(&b[0])), uintptr(len(b)))
	return strings.TrimSpace(syscall.UTF16ToString(b))
}
func setStatus(text string) {
	updateLock.Lock()
	latestUpdate = text
	updateLock.Unlock()
	call(pPostMessage, hwnd, wmAppStatus, 0, 0)
}
func createControl(class, text string, style uintptr, x, y, width, height int32, id uintptr) uintptr {
	child := call(pCreateWindow, 0, uintptr(unsafe.Pointer(w(class))), uintptr(unsafe.Pointer(w(text))), style|wsChild|wsVisible, uintptr(x), uintptr(y), uintptr(width), uintptr(height), hwnd, id, 0, 0)
	if font != 0 {
		call(pSendMessage, child, wmSetFont, font, 1)
	}
	return child
}
func chooseFile(title, filter string) string {
	buf := make([]uint16, 2048)
	filter16 := syscall.StringToUTF16(filter)
	ofn := openFileName{Size: uint32(unsafe.Sizeof(openFileName{})), Owner: hwnd, Filter: &filter16[0], File: &buf[0], MaxFile: uint32(len(buf)), Title: w(title), Flags: 0x1000 | 0x800 | 0x8}
	if call(comdlg32.NewProc("GetOpenFileNameW"), uintptr(unsafe.Pointer(&ofn))) == 0 {
		return ""
	}
	return syscall.UTF16ToString(buf)
}
func wndProc(h uintptr, msg uint32, wp, lp uintptr) uintptr {
	switch msg {
	case wmCommand:
		id := wp & 0xffff
		switch id {
		case 101:
			if p := chooseFile("Выберите SectorV.exe", "Приложения (*.exe)\x00*.exe\x00Все файлы\x00*.*\x00\x00"); p != "" {
				setText(hExeEdit, p)
			}
		case 102:
			if p := chooseFile("Выберите исходную VirtualCarJ2534.dll", "DLL файлы (*.dll)\x00*.dll\x00Все файлы\x00*.*\x00\x00"); p != "" {
				setText(hDllEdit, p)
			}
		case 103:
			if !running {
				exe, dll := getText(hExeEdit), getText(hDllEdit)
				running = true
				updateLock.Lock()
				latestAssessment = ""
				lastReport = ""
				updateLock.Unlock()
				setText(hFindings, "Сбор данных…")
				call(pEnableWindow, hOpen, 0)
				call(pEnableWindow, hRun, 0)
				setStatus("Подготовка трассировки…")
				go runWorkflow(exe, dll)
			}
		case 104:
			updateLock.Lock()
			report := lastReport
			updateLock.Unlock()
			if report != "" {
				_ = exec.Command("explorer.exe", filepath.Dir(report)).Start()
			}
		case 105:
			if !running {
				go func() {
					if err := elevate("--unregister", ""); err != nil {
						setStatus("Не удалось удалить регистрацию: " + err.Error())
					} else {
						setStatus("Регистрация тестового J2534 удалена")
					}
				}()
			}
		}
		return 0
	case wmAppStatus:
		updateLock.Lock()
		v := latestUpdate
		updateLock.Unlock()
		setText(hStatus, v)
		return 0
	case wmAppDone:
		running = false
		call(pEnableWindow, hRun, 1)
		updateLock.Lock()
		e := latestErr
		resultText := latestAssessment
		updateLock.Unlock()
		if resultText != "" {
			setText(hFindings, resultText)
		}
		if e != nil {
			messageBox("Не удалось завершить цикл:\n"+e.Error(), mbIconError)
		} else {
			messageBox("Готово! Итоговый отчёт создан.\nНажмите «Открыть отчёт» или прикрепите j2534-diagnostics.json.", mbIconInfo)
		}
		updateLock.Lock()
		report := lastReport
		updateLock.Unlock()
		if report != "" {
			call(pEnableWindow, hOpen, 1)
		}
		return 0
	case wmClose:
		if running {
			messageBox("Сначала закройте SectorV и дождитесь обработки трассы. Это нужно для сохранения отчёта.", mbIconInfo)
			return 0
		}
		call(user32.NewProc("DestroyWindow"), h)
		return 0
	case wmDestroy:
		call(user32.NewProc("PostQuitMessage"), 0)
		return 0
	}
	return call(pDefWndProc, h, uintptr(msg), wp, lp)
}
func guiMain() {
	runtime.LockOSThread()
	call(user32.NewProc("SetProcessDPIAware"))
	klass := w("VirtualCarTraceOneClickWindow")
	wc := wndClass{Size: uint32(unsafe.Sizeof(wndClass{})), Proc: syscall.NewCallback(wndProc), ClassName: klass, Background: 6, Instance: call(kernel32.NewProc("GetModuleHandleW"), 0), Cursor: call(user32.NewProc("LoadCursorW"), 0, 32512)}
	if call(pRegisterClass, uintptr(unsafe.Pointer(&wc))) == 0 {
		messageBox("Не удалось создать класс окна", mbIconError)
		return
	}
	hwnd = call(pCreateWindow, 0, uintptr(unsafe.Pointer(klass)), uintptr(unsafe.Pointer(w(appTitle))), wsOverlappedWindow, 100, 100, 720, 546, 0, 0, wc.Instance, 0)
	if hwnd == 0 {
		return
	}
	font = call(gdi32.NewProc("GetStockObject"), 17) // DEFAULT_GUI_FONT
	createControl("STATIC", "Приложение SectorV (x86):", 0, 22, 18, 640, 20, 0)
	hExeEdit = createControl("EDIT", "", wsBorder|esAutoHScroll, 22, 40, 573, 26, 0)
	createControl("BUTTON", "Обзор…", bsPushButton, 603, 40, 90, 27, 101)
	createControl("STATIC", "Исходная VirtualCarJ2534.dll (x86):", 0, 22, 79, 640, 20, 0)
	hDllEdit = createControl("EDIT", "", wsBorder|esAutoHScroll, 22, 102, 573, 26, 0)
	createControl("BUTTON", "Обзор…", bsPushButton, 603, 102, 90, 27, 102)
	createControl("STATIC", "В SectorV выберите адаптер «VirtualCar Trace VM dev26» и выполните только чтение VIN / CEM.", 0, 22, 141, 675, 28, 0)
	hRun = createControl("BUTTON", "▶  ЗАПУСТИТЬ SECTORV И СОБРАТЬ ОТЧЁТ", bsPushButton, 22, 183, 671, 43, 103)
	hStatus = createControl("STATIC", "Готов к запуску. При первой регистрации J2534 Windows спросит разрешение UAC.", 0, 22, 236, 665, 33, 0)
	hFindings = createControl("STATIC", "Питание: ещё не проверено\r\nJ2534-2 PS: ещё не проверено\r\nD2 Ref 6660: ещё не проверен\r\nОбычный режим CEM: ещё не проверен\r\nНеизвестные D2: ещё не проверены\r\nЗажигание: не определено\r\nCEM: ещё не проверен", 0, 22, 274, 670, 176, 0)
	hOpen = createControl("BUTTON", "Открыть отчёт", bsPushButton, 22, 457, 195, 28, 104)
	call(pEnableWindow, hOpen, 0)
	createControl("BUTTON", "Удалить тестовый адаптер", bsPushButton, 465, 457, 228, 28, 105)
	home, _ := os.UserHomeDir()
	exe, dll := autoPaths(home)
	if dir, e := localDirectory(); e == nil {
		settingsPath := filepath.Join(dir, "settings.json")
		if _, statErr := os.Stat(settingsPath); os.IsNotExist(statErr) {
			settingsPath = filepath.Join(filepath.Dir(dir), "dev21", "settings.json")
			if _, oldErr := os.Stat(settingsPath); oldErr != nil {
				settingsPath = filepath.Join(filepath.Dir(dir), "dev20", "settings.json")
			}
			if _, statErr := os.Stat(settingsPath); os.IsNotExist(statErr) {
				settingsPath = filepath.Join(filepath.Dir(dir), "dev19", "settings.json")
				if _, statErr := os.Stat(settingsPath); os.IsNotExist(statErr) {
					settingsPath = filepath.Join(filepath.Dir(dir), "dev18", "settings.json")
				}
			}
		}
		if b, e := os.ReadFile(settingsPath); e == nil {
			var saved struct {
				SectorV string `json:"sectorv"`
				DLL     string `json:"dll"`
			}
			if json.Unmarshal(b, &saved) == nil {
				if fileExists(saved.SectorV) {
					exe = saved.SectorV
				}
				if fileExists(saved.DLL) {
					dll = saved.DLL
				}
			}
		}
	}
	setText(hExeEdit, exe)
	setText(hDllEdit, dll)
	// Show the most recent report without requiring another SectorV launch.
	prev := filepath.Join(home, "Desktop", "VirtualCar-Trace-Results", "j2534-diagnostics.json")
	if data, e := os.ReadFile(prev); e == nil {
		if assessment, e := readAssessmentFile(data); e == nil {
			setText(hFindings, conciseAssessment(assessment))
			updateLock.Lock()
			lastReport = prev
			updateLock.Unlock()
			call(pEnableWindow, hOpen, 1)
			setText(hStatus, "Загружен предыдущий отчёт. Для новой проверки нажмите кнопку запуска.")
		}
	}
	call(user32.NewProc("ShowWindow"), hwnd, swShow)
	call(user32.NewProc("UpdateWindow"), hwnd)
	var msg winMessage
	for {
		r := call(pGetMessage, uintptr(unsafe.Pointer(&msg)), 0, 0, 0)
		if r == 0 || r == ^uintptr(0) {
			break
		}
		call(user32.NewProc("TranslateMessage"), uintptr(unsafe.Pointer(&msg)))
		call(user32.NewProc("DispatchMessageW"), uintptr(unsafe.Pointer(&msg)))
	}
}
func localDirectory() (string, error) {
	p := os.Getenv("LOCALAPPDATA")
	if p == "" {
		home, e := os.UserHomeDir()
		if e != nil {
			return "", e
		}
		p = filepath.Join(home, "AppData", "Local")
	}
	return filepath.Join(p, "VirtualCar-Trace-OneClick", "dev26"), nil
}
func embeddedBytes(name string) ([]byte, error) { return embedded.ReadFile("assets/" + name) }
func extractFiles(dir string) (proxy, attribution, summary, ignition string, err error) {
	names := []string{"VirtualCarTrace32.dll", "VirtualCarTraceAttribution-x86.exe", "VirtualCarTraceSummary-x86.exe", "VirtualCarIgnition-x86.exe"}
	paths := make([]string, len(names))
	for i, name := range names {
		contents, e := embeddedBytes(name)
		if e != nil {
			return "", "", "", "", e
		}
		p := filepath.Join(dir, "bin", name)
		if e := installByteFile(p, contents); e != nil {
			return "", "", "", "", e
		}
		if !equalFileAndBytes(p, contents) {
			return "", "", "", "", errors.New("отказ проверки SHA-256 встроенного компонента")
		}
		paths[i] = p
	}
	return paths[0], paths[1], paths[2], paths[3], nil
}
func getRegistryProvider() (string, bool, error) {
	var key syscall.Handle
	err := syscall.RegOpenKeyEx(syscall.HKEY_LOCAL_MACHINE, w(providerKey), 0, syscall.KEY_READ|keyWow6432, &key)
	if errors.Is(err, syscall.ERROR_FILE_NOT_FOUND) {
		return "", false, nil
	}
	if err != nil {
		return "", false, err
	}
	defer syscall.RegCloseKey(key)
	var size uint32
	var kind uint32
	if e := syscall.RegQueryValueEx(key, w("FunctionLibrary"), nil, &kind, nil, &size); e != nil {
		return "", true, e
	}
	if kind != syscall.REG_SZ || size < 2 || size > 8192 {
		return "", true, errors.New("некорректное значение FunctionLibrary")
	}
	b := make([]byte, size)
	if e := syscall.RegQueryValueEx(key, w("FunctionLibrary"), nil, &kind, &b[0], &size); e != nil {
		return "", true, e
	}
	ws := make([]uint16, size/2)
	for i := range ws {
		ws[i] = uint16(b[i*2]) | uint16(b[i*2+1])<<8
	}
	return syscall.UTF16ToString(ws), true, nil
}
func setRegString(key syscall.Handle, name, value string) error {
	v := syscall.StringToUTF16(value)
	r := call(pRegSetValue, uintptr(key), uintptr(unsafe.Pointer(w(name))), 0, syscall.REG_SZ, uintptr(unsafe.Pointer(&v[0])), uintptr(len(v)*2))
	if r != 0 {
		return syscall.Errno(r)
	}
	return nil
}
func setRegDword(key syscall.Handle, name string, val uint32) error {
	r := call(pRegSetValue, uintptr(key), uintptr(unsafe.Pointer(w(name))), 0, syscall.REG_DWORD, uintptr(unsafe.Pointer(&val)), 4)
	if r != 0 {
		return syscall.Errno(r)
	}
	return nil
}
func registerProvider(proxy string) error {
	if err := validatePE32(proxy, ".dll"); err != nil {
		return err
	}
	contents, e := embeddedBytes("VirtualCarTrace32.dll")
	if e != nil {
		return e
	}
	if !equalFileAndBytes(proxy, contents) {
		return errors.New("тестовая DLL отличается от встроенного компонента")
	}
	if existing, ok, e := getRegistryProvider(); e != nil {
		return e
	} else if ok {
		if equalFileAndBytes(existing, contents) {
			return nil
		}
		return errors.New("регистрация существует и принадлежит другой DLL; ничего не заменено")
	}
	var key syscall.Handle
	var disposition uint32
	r := call(pRegCreate, uintptr(syscall.HKEY_LOCAL_MACHINE), uintptr(unsafe.Pointer(w(providerKey))), 0, 0, 0, syscall.KEY_SET_VALUE|keyWow6432, 0, uintptr(unsafe.Pointer(&key)), uintptr(unsafe.Pointer(&disposition)))
	if r != 0 {
		return syscall.Errno(r)
	}
	defer syscall.RegCloseKey(key)
	if disposition != 1 {
		return errors.New("регистрация появилась параллельно; ничего не перезаписано")
	}
	for _, pair := range [][2]string{{"Vendor", "VirtualCar local test"}, {"Name", providerName}, {"FunctionLibrary", proxy}} {
		if e := setRegString(key, pair[0], pair[1]); e != nil {
			return e
		}
	}
	for _, name := range []string{"CAN", "ISO15765"} {
		if e := setRegDword(key, name, 1); e != nil {
			return e
		}
	}
	return nil
}
func unregisterProvider() error {
	existing, ok, err := getRegistryProvider()
	if err != nil {
		return err
	}
	if !ok {
		return nil
	}
	contents, err := embeddedBytes("VirtualCarTrace32.dll")
	if err != nil {
		return err
	}
	if !equalFileAndBytes(existing, contents) {
		return errors.New("адаптер не совпадает с нашей тестовой DLL; удаление запрещено")
	}
	r := call(pRegDelete, uintptr(syscall.HKEY_LOCAL_MACHINE), uintptr(unsafe.Pointer(w(providerKey))), keyWow6432, 0)
	if r != 0 {
		return syscall.Errno(r)
	}
	return nil
}
func elevate(operation, proxy string) error {
	self, err := os.Executable()
	if err != nil {
		return err
	}
	params := operation
	if proxy != "" {
		params += " " + fmt.Sprintf("%q", proxy)
	}
	sei := shellExecuteInfo{Size: uint32(unsafe.Sizeof(shellExecuteInfo{})), Mask: 0x40, Verb: w("runas"), File: w(self), Params: w(params), Show: 1}
	if call(pShellExecuteEx, uintptr(unsafe.Pointer(&sei))) == 0 {
		return errors.New("UAC отменён или запуск от администратора невозможен")
	}
	if sei.Process == 0 {
		return errors.New("не удалось получить процесс UAC")
	}
	defer call(kernel32.NewProc("CloseHandle"), sei.Process)
	wait := call(kernel32.NewProc("WaitForSingleObject"), sei.Process, 0xFFFFFFFF)
	if wait != 0 {
		return fmt.Errorf("ошибка ожидания администратора: %d", wait)
	}
	var exitCode uint32
	if call(kernel32.NewProc("GetExitCodeProcess"), sei.Process, uintptr(unsafe.Pointer(&exitCode))) == 0 {
		return errors.New("неизвестный код возврата UAC")
	}
	if exitCode != 0 {
		return fmt.Errorf("административная операция завершилась с кодом %d", exitCode)
	}
	return nil
}
func ensureProvider(proxy string) (string, error) {
	contents, err := embeddedBytes("VirtualCarTrace32.dll")
	if err != nil {
		return "", err
	}
	existing, found, err := getRegistryProvider()
	if err != nil {
		return "", err
	}
	if found {
		if !equalFileAndBytes(existing, contents) {
			return "", errors.New("VirtualCar Trace VM dev26 зарегистрирован с другой DLL. Удалите прежнюю регистрацию адаптера dev26 через OneClick dev26, либо укажите корректный путь. Никакие ключи не перезаписаны")
		}
		return existing, nil
	}
	setStatus("Регистрация тестового J2534: разрешите UAC…")
	if err := elevate("--register", proxy); err != nil {
		return "", err
	}
	existing, found, err = getRegistryProvider()
	if err != nil {
		return "", err
	}
	if !found || !equalFileAndBytes(existing, contents) {
		return "", errors.New("после регистрации J2534 DLL не найдена или не совпадает")
	}
	return existing, nil
}
func runWorkflow(sectorv, dll string) {
	var err error
	defer func() {
		updateLock.Lock()
		latestErr = err
		updateLock.Unlock()
		call(pPostMessage, hwnd, wmAppDone, 0, 0)
	}()
	dir, e := localDirectory()
	if e != nil {
		err = e
		return
	}
	setStatus("Извлечение встроенных Windows x86-компонентов…")
	proxy, attribution, summary, ignition, e := extractFiles(dir)
	if e != nil {
		err = e
		return
	}
	if e = safeLaunchPaths(sectorv, dll, proxy); e != nil {
		err = e
		return
	}
	if saved, saveErr := json.MarshalIndent(struct {
		SectorV string `json:"sectorv"`
		DLL     string `json:"dll"`
	}{sectorv, dll}, "", "  "); saveErr == nil {
		_ = os.WriteFile(filepath.Join(dir, "settings.json"), saved, 0600)
	}
	if _, e = ensureProvider(proxy); e != nil {
		err = e
		return
	}
	logs := filepath.Join(dir, "logs")
	if e = os.MkdirAll(logs, 0700); e != nil {
		err = e
		return
	}
	stamp := time.Now().Format("20060102-150405")
	raw := filepath.Join(logs, "j2534-trace-"+stamp+".jsonl")
	home, _ := os.UserHomeDir()
	reports := filepath.Join(home, "Desktop", "VirtualCar-Trace-Results")
	if e = os.MkdirAll(reports, 0700); e != nil {
		reports = filepath.Join(dir, "reports")
		if e = os.MkdirAll(reports, 0700); e != nil {
			err = e
			return
		}
	}
	report := filepath.Join(reports, "j2534-attribution-"+stamp+".json")
	sum := filepath.Join(reports, "j2534-summary-"+stamp+".json")
	setStatus("SectorV запущен. Выберите «VirtualCar Trace VM dev26» и выполните чтение VIN/CEM. Затем закройте SectorV.")
	cmd := exec.Command(sectorv)
	cmd.Dir = filepath.Dir(sectorv)
	// Process-specific settings. No system environment or user credentials are modified.
	cmd.Env = append(os.Environ(), "VCAR_TRACE_REAL_DLL="+dll, "VCAR_TRACE_LOG_PATH="+raw)
	if e = cmd.Start(); e != nil {
		err = fmt.Errorf("не удалось открыть SectorV: %w", e)
		return
	}
	waitErr := cmd.Wait()
	if !fileExists(raw) {
		err = fmt.Errorf("трасса не создана. Выберите именно '%s' в SectorV и повторите запуск (код завершения: %v)", providerName, waitErr)
		return
	}
	setStatus("SectorV закрыт. Анализ J2534-трассы и формирование отчётов…")
	if out, e := exec.Command(attribution, "-in", raw, "-out", report).CombinedOutput(); e != nil {
		err = fmt.Errorf("ошибка атрибуции: %v; %s", e, string(out))
		return
	}
	if out, e := exec.Command(summary, "-in", raw, "-out", sum).CombinedOutput(); e != nil {
		err = fmt.Errorf("ошибка сводного отчёта: %v; %s", e, string(out))
		return
	}
	if !fileExists(report) {
		err = errors.New("анализатор не создал итоговый JSON")
		return
	}
	ignitionReport := filepath.Join(reports, "j2534-ignition-"+stamp+".json")
	if out, e := exec.Command(ignition, "-in", raw, "-out", ignitionReport).CombinedOutput(); e != nil {
		err = fmt.Errorf("ошибка анализа питания/зажигания: %v; %s", e, string(out))
		return
	}
	var a json.RawMessage
	var ig json.RawMessage
	if data, e := os.ReadFile(report); e == nil {
		a = data
	} else {
		err = e
		return
	}
	if data, e := os.ReadFile(ignitionReport); e == nil {
		ig = data
	} else {
		err = e
		return
	}
	assessment, e := buildAssessment(a, ig)
	if e != nil {
		err = e
		return
	}
	rawSanitized, re := os.ReadFile(raw)
	if re != nil {
		err = re
		return
	}
	assessment.CoreBridge, e = readCoreBridgeAssessment(rawSanitized)
	if e != nil {
		err = e
		return
	}
	ab, e := json.Marshal(assessment)
	if e != nil {
		err = e
		return
	}
	combined, e := json.MarshalIndent(map[string]json.RawMessage{"attribution": a, "ignition": ig, "assessment": ab}, "", "  ")
	if e != nil {
		err = e
		return
	}
	latest := filepath.Join(reports, "j2534-diagnostics.json")
	if e = installByteFile(latest, combined); e != nil {
		err = e
		return
	}
	updateLock.Lock()
	lastReport = latest
	updateLock.Unlock()
	setStatus("Готово. Отчёт J2534/питание: " + latest)
	call(pPostMessage, hwnd, wmAppStatus, 0, 0)
	// Update UI on the GUI thread via wmAppDone, not from the worker.
	updateLock.Lock()
	latestAssessment = conciseAssessment(assessment)
	updateLock.Unlock()
}
func main() {
	if len(os.Args) > 1 {
		switch os.Args[1] {
		case "--register":
			if len(os.Args) != 3 {
				os.Exit(2)
			}
			if e := registerProvider(os.Args[2]); e != nil {
				os.Exit(1)
			}
			return
		case "--unregister":
			if e := unregisterProvider(); e != nil {
				os.Exit(1)
			}
			return
		}
	}
	guiMain()
}
