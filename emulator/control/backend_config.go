package main

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"crypto/rand"
)

// dev49: read-only ECU telemetry is opt-in. This editor preserves unrelated
// INI values, including private vehicle data, and keeps a local backup.
func backendTelemetrySetting(data []byte) (bool, error) {
	_, _, _, value, err := locateBackendSetting(data)
	return value == "1", err
}

func locateBackendSetting(data []byte) ([]string, int, int, string, error) {
	// A UTF-8 BOM belongs to the file prefix, not to every INI line.
	text := strings.TrimPrefix(string(data), "\ufeff")
	lines := strings.Split(strings.ReplaceAll(text, "\r\n", "\n"), "\n")
	section := ""
	header := -1
	keyline := -1
	value := ""
	for i, raw := range lines {
		line := strings.TrimSpace(raw)
		if strings.HasPrefix(line, "[") && strings.HasSuffix(line, "]") {
			section = strings.TrimSpace(line[1 : len(line)-1])
			if strings.EqualFold(section, "Diagnostics") {
				if header >= 0 {
					return nil, -1, -1, "", errors.New("несколько секций [Diagnostics]; настройки не изменены")
				}
				header = i
			}
			continue
		}
		if !strings.EqualFold(section, "Diagnostics") || strings.HasPrefix(line, ";") || strings.HasPrefix(line, "#") {
			continue
		}
		k, v, ok := strings.Cut(line, "=")
		if !ok || !strings.EqualFold(strings.TrimSpace(k), "BackendTelemetryEnabled") {
			continue
		}
		if keyline >= 0 {
			return nil, -1, -1, "", errors.New("дублируется BackendTelemetryEnabled; настройки не изменены")
		}
		keyline = i
		value = strings.TrimSpace(strings.SplitN(v, ";", 2)[0])
	}
	return lines, header, keyline, value, nil
}

func rewriteBackendTelemetry(data []byte, enabled bool) ([]byte, error) {
	lines, header, keyline, _, err := locateBackendSetting(data)
	if err != nil {
		return nil, err
	}
	value := "0"
	if enabled {
		value = "1"
	}
	if keyline >= 0 {
		lines[keyline] = "BackendTelemetryEnabled=" + value
	} else {
		// Use the validated header from the reader, including case/space rules.
		if header >= 0 {
			lines = append(lines[:header+1], append([]string{"BackendTelemetryEnabled=" + value}, lines[header+1:]...)...)
		} else {
			if len(lines) > 0 && lines[len(lines)-1] != "" {
				lines = append(lines, "")
			}
			lines = append(lines, "[Diagnostics]", "BackendTelemetryEnabled="+value)
		}
	}
	separator := "\n"
	if strings.Contains(string(data), "\r\n") {
		separator = "\r\n"
	}
	result := strings.Join(lines, separator)
	if !strings.HasSuffix(result, separator) {
		result += separator
	}
	if strings.HasPrefix(string(data), "\ufeff") {
		result = "\ufeff" + result
	}
	return []byte(result), nil
}

// Return the new setting. No registry writes, J2534 calls or ECU messages.
func toggleBackendTelemetry(path string) (bool, error) {
	original, err := os.ReadFile(path)
	if err != nil {
		return false, err
	}
	old, err := backendTelemetrySetting(original)
	if err != nil {
		return false, err
	}
	next := !old
	updated, err := rewriteBackendTelemetry(original, next)
	if err != nil {
		return false, err
	}
	mode := os.FileMode(0600)
	if st, e := os.Stat(path); e == nil {
		mode = st.Mode().Perm()
	}
	tmp, err := os.CreateTemp(filepath.Dir(path), ".virtualcar-dev49-*.new")
	if err != nil {
		return false, err
	}
	tmpPath := tmp.Name()
	defer os.Remove(tmpPath)
	if err = tmp.Chmod(mode); err == nil {
		_, err = tmp.Write(updated)
	}
	if closeErr := tmp.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return false, err
	}
	// Windows can report the same UnixNano value for rapid consecutive
	// toggles. A timestamp-only backup name can overwrite the first backup.
	// Use an unpredictable, independent suffix and refuse any collision.
	var nonce [16]byte
	if _, err = rand.Read(nonce[:]); err != nil {
		return false, err
	}
	backup := fmt.Sprintf("%s.dev49-%x.bak", path, nonce)
	if _, statErr := os.Lstat(backup); statErr == nil {
		return false, fmt.Errorf("backup name collision")
	} else if !os.IsNotExist(statErr) {
		return false, statErr
	}
	if err = os.Rename(path, backup); err != nil {
		return false, err
	}
	if err = os.Rename(tmpPath, path); err != nil {
		if restoreErr := os.Rename(backup, path); restoreErr != nil {
			return false, fmt.Errorf("%w; восстановите резервную копию %s: %v", err, backup, restoreErr)
		}
		return false, err
	}
	return next, nil
}
