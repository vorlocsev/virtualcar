package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestBackendTelemetryConfig(t *testing.T) {
	tests := []struct {
		name string
		in   string
		on   bool
		want string
	}{
		{"append missing section", "[Vehicle]\nVIN=PRIVATE_VALUE\n", true,
			"[Diagnostics]\nBackendTelemetryEnabled=1"},
		{"disable present setting", "[Diagnostics]\nBackendTelemetryEnabled=1\n", false,
			"BackendTelemetryEnabled=0"},
		{"preserve CRLF", "[Vehicle]\r\nVIN=PRIVATE_VALUE\r\n", true,
			"[Diagnostics]\r\nBackendTelemetryEnabled=1\r\n"},
		{"insert key into existing section", "[Diagnostics]\n; comment\n[Vehicle]\nKey=Value\n", true,
			"[Diagnostics]\nBackendTelemetryEnabled=1\n; comment"},
		{"lowercase section", "[diagnostics]\nbackendtelemetryenabled=0\n", true,
			"BackendTelemetryEnabled=1"},
		{"preserve other settings", "[Vehicle]\nVIN=PRIVATE_VALUE\n[Diagnostics]\nSample=2\n", true,
			"Sample=2"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := rewriteBackendTelemetry([]byte(tt.in), tt.on)
			if err != nil {
				t.Fatal(err)
			}
			if !strings.Contains(string(got), tt.want) {
				t.Fatalf("expected substring %q in %q", tt.want, string(got))
			}
			if strings.Contains(tt.in, "PRIVATE_VALUE") && !strings.Contains(string(got), "PRIVATE_VALUE") {
				t.Fatal("unrelated profile data changed")
			}
			on, err := backendTelemetrySetting(got)
			if err != nil || on != tt.on {
				t.Fatalf("value=%v err=%v", on, err)
			}
		})
	}
}

func TestBackendTelemetryRejectAmbiguity(t *testing.T) {
	for _, input := range []string{
		"[Diagnostics]\nBackendTelemetryEnabled=0\nBackendTelemetryEnabled=1\n",
		"[Diagnostics]\nBackendTelemetryEnabled=0\n[Diagnostics]\nBackendTelemetryEnabled=1\n",
	} {
		if _, err := rewriteBackendTelemetry([]byte(input), true); err == nil {
			t.Fatalf("accepted ambiguous INI: %q", input)
		}
	}
}

func TestBackendTelemetryToggleRoundtripLocalBackup(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "virtualcar.ini")
	profile := "[Vehicle]\r\nVIN=PRIVATE_VALUE\r\n[Diagnostics]\r\nBackendTelemetryEnabled=0\r\n"
	if err := os.WriteFile(path, []byte(profile), 0600); err != nil {
		t.Fatal(err)
	}
	on, err := toggleBackendTelemetry(path)
	if err != nil || !on {
		t.Fatalf("enable: %v %v", on, err)
	}
	data, err := os.ReadFile(path)
	if err != nil || !strings.Contains(string(data), "BackendTelemetryEnabled=1") ||
		!strings.Contains(string(data), "VIN=PRIVATE_VALUE") {
		t.Fatalf("updated profile: %q err=%v", data, err)
	}
	on, err = toggleBackendTelemetry(path)
	if err != nil || on {
		t.Fatalf("disable: %v %v", on, err)
	}
	data, err = os.ReadFile(path)
	if err != nil || !strings.Contains(string(data), "BackendTelemetryEnabled=0") {
		t.Fatalf("disabled profile: %q err=%v", data, err)
	}
	backups, err := filepath.Glob(path + ".dev49-*.bak")
	if err != nil || len(backups) != 2 {
		t.Fatalf("expected two local backups, found %v, err=%v", backups, err)
	}
}

func TestBackendTelemetryMissingProfile(t *testing.T) {
	if _, err := toggleBackendTelemetry(filepath.Join(t.TempDir(), "missing.ini")); err == nil {
		t.Fatal("missing profile was silently created")
	}
}
