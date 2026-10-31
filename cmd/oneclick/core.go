package main

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

// PE32 only, to guard against mixing a x64 app with the x86 J2534 proxy.
func validatePE32(path string, extension string) error {
	if !strings.EqualFold(filepath.Ext(path), extension) {
		return fmt.Errorf("нужен файл %s: %s", extension, path)
	}
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	var hdr [4096]byte
	n, err := f.Read(hdr[:])
	if err != nil || n < 128 {
		return errors.New("не удалось прочитать PE-заголовок")
	}
	if hdr[0] != 'M' || hdr[1] != 'Z' {
		return errors.New("нет заголовка MZ")
	}
	off := uint32(hdr[0x3c]) | uint32(hdr[0x3d])<<8 | uint32(hdr[0x3e])<<16 | uint32(hdr[0x3f])<<24
	if off < 64 || off > 4000 || int(off)+26 > n {
		return errors.New("ошибка смещения PE")
	}
	if string(hdr[off:off+4]) != "PE\x00\x00" {
		return errors.New("нет подписи PE")
	}
	machine := uint16(hdr[off+4]) | uint16(hdr[off+5])<<8
	magic := uint16(hdr[off+24]) | uint16(hdr[off+25])<<8
	if machine != 0x014c || magic != 0x010b {
		return fmt.Errorf("ожидается Windows x86 PE32 (machine=%x, magic=%x)", machine, magic)
	}
	return nil
}

func equalFileAndBytes(path string, source []byte) bool {
	data, err := os.ReadFile(path)
	return err == nil && sha256.Sum256(data) == sha256.Sum256(source)
}

func installByteFile(path string, contents []byte) error {
	if equalFileAndBytes(path, contents) {
		return nil
	}
	if err := os.MkdirAll(filepath.Dir(path), 0700); err != nil {
		return err
	}
	tmp := path + ".new"
	if err := os.WriteFile(tmp, contents, 0600); err != nil {
		return err
	}
	if err := os.Rename(tmp, path); err != nil {
		// On Windows Rename doesn't overwrite an existing destination reliably.
		if remErr := os.Remove(path); remErr != nil && !errors.Is(remErr, os.ErrNotExist) {
			_ = os.Remove(tmp)
			return remErr
		}
		if err = os.Rename(tmp, path); err != nil {
			_ = os.Remove(tmp)
			return err
		}
	}
	return nil
}

func autoPaths(home string) (sectorv, dll string) {
	for _, desktop := range []string{filepath.Join(home, "Desktop"), filepath.Join(home, "OneDrive", "Desktop")} {
		exe := filepath.Join(desktop, "SectorV", "SectorV.exe")
		if sectorv == "" && fileExists(exe) {
			sectorv = exe
		}
		cands, _ := filepath.Glob(filepath.Join(desktop, "SectorV-VirtualCar*", "VirtualCarJ2534.dll"))
		for _, c := range cands {
			if dll == "" && fileExists(c) {
				dll = c
			}
		}
		c := filepath.Join(desktop, "VirtualCarJ2534.dll")
		if dll == "" && fileExists(c) {
			dll = c
		}
	}
	return
}

func fileExists(path string) bool {
	stat, err := os.Stat(path)
	return err == nil && stat.Mode().IsRegular()
}

func safeLaunchPaths(sectorv, dll, proxy string) error {
	if err := validatePE32(sectorv, ".exe"); err != nil {
		return fmt.Errorf("SectorV: %w", err)
	}
	if err := validatePE32(dll, ".dll"); err != nil {
		return fmt.Errorf("VirtualCar: %w", err)
	}
	if err := validatePE32(proxy, ".dll"); err != nil {
		return fmt.Errorf("Trace proxy: %w", err)
	}
	b1, err := os.ReadFile(dll)
	if err != nil {
		return err
	}
	b2, err := os.ReadFile(proxy)
	if err != nil {
		return err
	}
	if sha256.Sum256(b1) == sha256.Sum256(b2) {
		return errors.New("путь VirtualCarJ2534.dll указывает на трассирующую прокладку")
	}
	return nil
}
