package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func fakePE(machine, magic uint16) []byte {
	b := make([]byte, 256)
	b[0] = 'M'
	b[1] = 'Z'
	b[0x3c] = 0x80
	copy(b[128:], []byte("PE\x00\x00"))
	b[132] = byte(machine)
	b[133] = byte(machine >> 8)
	b[152] = byte(magic)
	b[153] = byte(magic >> 8)
	return b
}
func TestValidPE32(t *testing.T) {
	d := t.TempDir()
	f := filepath.Join(d, "test.exe")
	os.WriteFile(f, fakePE(0x14c, 0x10b), 0600)
	if e := validatePE32(f, ".exe"); e != nil {
		t.Fatal(e)
	}
}
func TestRejectPE64(t *testing.T) {
	d := t.TempDir()
	f := filepath.Join(d, "test.exe")
	os.WriteFile(f, fakePE(0x8664, 0x20b), 0600)
	if e := validatePE32(f, ".exe"); e == nil {
		t.Fatal("accepted x64")
	}
}
func TestRejectNonPE(t *testing.T) {
	d := t.TempDir()
	f := filepath.Join(d, "test.exe")
	os.WriteFile(f, []byte("NO"), 0600)
	if e := validatePE32(f, ".exe"); e == nil {
		t.Fatal("accepted")
	}
}
func TestRejectExtension(t *testing.T) {
	d := t.TempDir()
	f := filepath.Join(d, "test.dll")
	os.WriteFile(f, fakePE(0x14c, 0x10b), 0600)
	if e := validatePE32(f, ".exe"); e == nil {
		t.Fatal("accepted")
	}
}
func TestAutoPaths(t *testing.T) {
	d := t.TempDir()
	a := filepath.Join(d, "Desktop", "SectorV")
	b := filepath.Join(d, "Desktop", "SectorV-VirtualCar-v0.3.6.6")
	os.MkdirAll(a, 0700)
	os.MkdirAll(b, 0700)
	os.WriteFile(filepath.Join(a, "SectorV.exe"), []byte("EXE"), 0600)
	os.WriteFile(filepath.Join(b, "VirtualCarJ2534.dll"), []byte("DLL"), 0600)
	exe, dll := autoPaths(d)
	if !strings.HasSuffix(exe, "SectorV.exe") || !strings.HasSuffix(dll, "VirtualCarJ2534.dll") {
		t.Fatalf("%q %q", exe, dll)
	}
}
func TestEqualFile(t *testing.T) {
	d := t.TempDir()
	f := filepath.Join(d, "x")
	os.WriteFile(f, []byte("hello"), 0600)
	if !equalFileAndBytes(f, []byte("hello")) || equalFileAndBytes(f, []byte("HELLO")) {
		t.Fatal("hash")
	}
}
func TestInstallFile(t *testing.T) {
	d := t.TempDir()
	f := filepath.Join(d, "sub", "x")
	for _, value := range []string{"a", "a", "b"} {
		if e := installByteFile(f, []byte(value)); e != nil {
			t.Fatal(e)
		}
	}
	v, _ := os.ReadFile(f)
	if string(v) != "b" {
		t.Fatal(string(v))
	}
}
func TestRejectSameProxy(t *testing.T) {
	d := t.TempDir()
	exe := filepath.Join(d, "sectorv.exe")
	dll := filepath.Join(d, "real.dll")
	proxy := filepath.Join(d, "proxy.dll")
	for _, p := range []string{exe, dll, proxy} {
		os.WriteFile(p, fakePE(0x14c, 0x10b), 0600)
	}
	if e := safeLaunchPaths(exe, dll, proxy); e == nil {
		t.Fatal("accepted recursive DLL")
	}
}
func TestRejectBadRealDll(t *testing.T) {
	d := t.TempDir()
	exe := filepath.Join(d, "sectorv.exe")
	dll := filepath.Join(d, "real.dll")
	proxy := filepath.Join(d, "proxy.dll")
	os.WriteFile(exe, fakePE(0x14c, 0x10b), 0600)
	os.WriteFile(dll, fakePE(0x8664, 0x20b), 0600)
	os.WriteFile(proxy, fakePE(0x14c, 0x10b), 0600)
	if e := safeLaunchPaths(exe, dll, proxy); e == nil {
		t.Fatal("accepted x64 DLL")
	}
}
