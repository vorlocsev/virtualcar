package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// All profiles in this file are synthetic; no real vehicle data is used.
func assertF10Rewrite(t *testing.T, input, want string, enabled bool) {
	t.Helper()
	data := []byte(input)
	got, err := rewriteBackendTelemetry(data, enabled)
	if err != nil {
		t.Fatal(err)
	}
	if string(got) != want {
		t.Fatalf("rewrite:\n got %q\nwant %q", got, want)
	}
	if string(data) != input {
		t.Fatal("rewrite mutated its input")
	}
	if on, err := backendTelemetrySetting(got); err != nil || on != enabled {
		t.Fatalf("reader rejected rewrite: enabled=%v err=%v", on, err)
	}
	again, err := rewriteBackendTelemetry(got, enabled)
	if err != nil || !bytes.Equal(again, got) {
		t.Fatalf("rewrite is not idempotent: %q err=%v", again, err)
	}
}

func TestBackendTelemetryF10BOMDiagnosticsInsertion(t *testing.T) {
	for _, nl := range []string{"\n", "\r\n"} {
		t.Run(nl, func(t *testing.T) {
			input := "\ufeff[Diagnostics]" + nl + "; synthetic comment" + nl + "[Vehicle]" + nl + "Label=synthetic" + nl
			want := "\ufeff[Diagnostics]" + nl + "BackendTelemetryEnabled=1" + nl + "; synthetic comment" + nl + "[Vehicle]" + nl + "Label=synthetic" + nl
			assertF10Rewrite(t, input, want, true)
		})
	}
}

func TestBackendTelemetryF10FilePrefix(t *testing.T) {
	for _, tt := range []struct{ name, input, want string }{
		{"other first section", "\ufeff[Vehicle]\nLabel=synthetic\n[Diagnostics]\nOther=2\n",
			"\ufeff[Vehicle]\nLabel=synthetic\n[Diagnostics]\nBackendTelemetryEnabled=1\nOther=2\n"},
		{"missing section", "\ufeff[Vehicle]\r\nLabel=synthetic\r\n",
			"\ufeff[Vehicle]\r\nLabel=synthetic\r\n\r\n[Diagnostics]\r\nBackendTelemetryEnabled=1\r\n"},
		{"BOM only", "\ufeff", "\ufeff\n[Diagnostics]\nBackendTelemetryEnabled=1\n"},
		{"empty without BOM", "", "\n[Diagnostics]\nBackendTelemetryEnabled=1\n"},
	} {
		t.Run(tt.name, func(t *testing.T) { assertF10Rewrite(t, tt.input, tt.want, true) })
	}
}

func TestBackendTelemetryF10HeaderParity(t *testing.T) {
	for _, prefix := range []string{"", "\ufeff"} {
		for _, header := range []string{"[ Diagnostics ]", " \t[ dIaGnOsTiCs \t]  ", "[diagnostics]"} {
			t.Run(prefix+header, func(t *testing.T) {
				input := prefix + header + "\n; keep\n[Other]\nBackendTelemetryEnabled=0\n"
				want := prefix + header + "\nBackendTelemetryEnabled=1\n; keep\n[Other]\nBackendTelemetryEnabled=0\n"
				assertF10Rewrite(t, input, want, true)
			})
		}
	}
}

func TestBackendTelemetryF10ExistingKeyAndUnrelatedData(t *testing.T) {
	for _, prefix := range []string{"", "\ufeff"} {
		for _, nl := range []string{"\n", "\r\n"} {
			for _, enabled := range []bool{false, true} {
				value := "0"
				if enabled {
					value = "1"
				}
				input := prefix + "[ Diagnostics ]" + nl + " \tbackendtelemetryenabled = 1 ; old" + nl +
					"; BackendTelemetryEnabled=0" + nl + "# BackendTelemetryEnabled=0" + nl + "Other=синтетика" + nl +
					"[Vehicle]" + nl + "BackendTelemetryEnabled=7" + nl + "Label=synthetic" + nl
				want := strings.Replace(input, " \tbackendtelemetryenabled = 1 ; old", "BackendTelemetryEnabled="+value, 1)
				if on, err := backendTelemetrySetting([]byte(input)); err != nil || !on {
					t.Fatalf("read original: %v %v", on, err)
				}
				assertF10Rewrite(t, input, want, enabled)
			}
		}
	}
}

func assertF10Ambiguous(t *testing.T, input string) {
	t.Helper()
	data := []byte(input)
	if _, err := backendTelemetrySetting(data); err == nil {
		t.Fatal("reader accepted ambiguity")
	}
	for _, enabled := range []bool{false, true} {
		if got, err := rewriteBackendTelemetry(data, enabled); err == nil || got != nil {
			t.Fatalf("writer accepted ambiguity: %q err=%v", got, err)
		}
		if string(data) != input {
			t.Fatal("ambiguous input changed")
		}
	}
}

func TestBackendTelemetryF10DuplicateSections(t *testing.T) {
	for _, prefix := range []string{"", "\ufeff"} {
		for _, middle := range []string{"", "BackendTelemetryEnabled=0\n", "[Other]\nKey=synthetic\n"} {
			for _, last := range []string{"", "BackendTelemetryEnabled=1\n"} {
				input := prefix + "[Diagnostics]\n" + middle + " [ dIaGnOsTiCs ] \n" + last
				t.Run(input, func(t *testing.T) { assertF10Ambiguous(t, input) })
			}
		}
	}
}

func TestBackendTelemetryF10DuplicateKeys(t *testing.T) {
	for _, prefix := range []string{"", "\ufeff"} {
		for _, last := range []string{"BackendTelemetryEnabled=0", " backendtelemetryenabled = 1 ; conflicting"} {
			input := prefix + "[ Diagnostics ]\nBackendTelemetryEnabled=0\n; keep\n" + last + "\n"
			t.Run(input, func(t *testing.T) { assertF10Ambiguous(t, input) })
		}
	}
}

func TestBackendTelemetryF10ToggleBackups(t *testing.T) {
	for _, nl := range []string{"\n", "\r\n"} {
		t.Run(nl, func(t *testing.T) {
			dir := t.TempDir()
			path := filepath.Join(dir, "virtualcar.ini")
			original := "\ufeff[ Diagnostics ]" + nl + "; synthetic" + nl + "[Vehicle]" + nl + "Label=synthetic" + nl
			if err := os.WriteFile(path, []byte(original), 0600); err != nil {
				t.Fatal(err)
			}
			before, err := os.Stat(path)
			if err != nil {
				t.Fatal(err)
			}
			enabled := strings.Replace(original, "; synthetic", "BackendTelemetryEnabled=1"+nl+"; synthetic", 1)
			disabled := strings.Replace(enabled, "BackendTelemetryEnabled=1", "BackendTelemetryEnabled=0", 1)
			for i, want := range []string{enabled, disabled} {
				on, err := toggleBackendTelemetry(path)
				if err != nil || on != (i == 0) {
					t.Fatalf("toggle %d: %v %v", i, on, err)
				}
				got, err := os.ReadFile(path)
				if err != nil || string(got) != want {
					t.Fatalf("profile %d: %q err=%v", i, got, err)
				}
				after, err := os.Stat(path)
				if err != nil || after.Mode().Perm() != before.Mode().Perm() {
					t.Fatalf("file permissions changed: %v", err)
				}
			}
			backups, err := filepath.Glob(path + ".dev49-*.bak")
			if err != nil || len(backups) != 2 {
				t.Fatalf("backups=%v err=%v", backups, err)
			}
			contents := map[string]int{}
			for _, backup := range backups {
				got, err := os.ReadFile(backup)
				if err != nil {
					t.Fatal(err)
				}
				contents[string(got)]++
			}
			if contents[original] != 1 || contents[enabled] != 1 {
				t.Fatalf("backups do not preserve original bytes: %v", contents)
			}
			entries, err := os.ReadDir(dir)
			if err != nil || len(entries) != 3 {
				t.Fatalf("temporary file left behind: %v err=%v", entries, err)
			}
		})
	}
}

func TestBackendTelemetryF10RejectedToggleIsUnchanged(t *testing.T) {
	for _, input := range []string{
		"\ufeff[Diagnostics]\r\nOther=synthetic\r\n[ diagnostics ]\r\n",
		"\ufeff[ Diagnostics ]\nBackendTelemetryEnabled=0\nbackendtelemetryenabled=1\n",
	} {
		t.Run(input, func(t *testing.T) {
			dir := t.TempDir()
			path := filepath.Join(dir, "virtualcar.ini")
			if err := os.WriteFile(path, []byte(input), 0600); err != nil {
				t.Fatal(err)
			}
			before, err := os.Stat(path)
			if err != nil {
				t.Fatal(err)
			}
			if on, err := toggleBackendTelemetry(path); err == nil || on {
				t.Fatalf("ambiguous toggle: %v %v", on, err)
			}
			got, err := os.ReadFile(path)
			if err != nil || string(got) != input {
				t.Fatalf("rejected profile changed: %q err=%v", got, err)
			}
			after, err := os.Stat(path)
			if err != nil || after.Mode().Perm() != before.Mode().Perm() || !after.ModTime().Equal(before.ModTime()) {
				t.Fatalf("rejected profile metadata changed: %v", err)
			}
			entries, err := os.ReadDir(dir)
			if err != nil || len(entries) != 1 {
				t.Fatalf("rejected toggle created files: %v err=%v", entries, err)
			}
		})
	}
}
