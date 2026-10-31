package simple

import (
	"fmt"
	"strings"
	"testing"
)

func fixture(year int, count int) []byte {
	codes := "123456789ABCDEFGHJKLMNPRSTVWXY"
	vin := []byte("YV1CR8556A1511566")
	vin[9] = codes[year-2001]
	// Replicate the historically observed 13-frame D2 fixture.
	frames := []string{
		"8F 50 F9 FB 57 00 30 66", "09 70 28 30 30 35 0D 0A",
		"0A 59 56 31 43 52 38 35", "0B 35 35 36 39 31 35 31",
		"0C 31 35 36 36 0D 0A 32 35", "0D 31 35 36 38 39 35 32",
		"0E 0D 0A 32 39 35 0D 0A", "0F 31 39 38 36 32 35 0D",
		"08 0A 32 31 0D 0A 32 30", "09 30 35 31 32 0D 0A 30",
		"0A 30 30 30 34 33 33 38", "0B 36 30 34 30 38 32 32",
		"4F 30 36 39 33 31 0D 0A",
	}
	// Alter VIN bytes at the relevant 3 frames to match the generated year.
	idx := 9 // model year position in VIN
	_ = idx
	frames[3] = fmt.Sprintf("0B %02X %02X %02X %02X %02X %02X %02X", vin[7], vin[8], vin[9], vin[10], vin[11], vin[12], vin[13])
	frames[4] = fmt.Sprintf("0C %02X %02X %02X 0D 0A 32 35", vin[14], vin[15], vin[16])
	// Frame 2 is 7 VIN bytes, frame 3 7, frame 4 3.
	frames[2] = fmt.Sprintf("0A %02X %02X %02X %02X %02X %02X %02X", vin[0], vin[1], vin[2], vin[3], vin[4], vin[5], vin[6])
	var b strings.Builder
	fmt.Fprintf(&b, "[Vehicle]\nVIN=%s\nModelYear=%d\n[P2]\nStrictRouting=1\n[D2_50]\nResponseId=01200003\nB9FBFrameCount=%d\n", vin, year, count)
	for i := 0; i < 13; i++ {
		fmt.Fprintf(&b, "B9FBFrame%X=%s\n", i, frames[i])
	}
	return []byte(b.String())
}

func TestProfileReady(t *testing.T) {
	if err := ProfileReady(fixture(2009, 13), 2009); err != nil {
		t.Fatal(err)
	}
	if err := ProfileReady(fixture(2005, 13), 2005); err != nil {
		t.Fatal(err)
	}
	if err := ProfileReady(fixture(2005, 13), 2009); err == nil {
		t.Fatal("must reject donor as 2009")
	}
	if err := ProfileReady(fixture(2009, 0), 2009); err == nil {
		t.Fatal("must reject empty B9FB")
	}
	if err := ProfileReady([]byte("[Vehicle]\nVIN=INVALID\n"), 2009); err == nil {
		t.Fatal("must reject missing VIN")
	}
}
func TestProfileLabel(t *testing.T) {
	if got := ProfileLabel(fixture(2009, 13)); !strings.Contains(got, "2009") {
		t.Fatal(got)
	}
	if got := ProfileLabel([]byte("[Vehicle]\nVIN=INVALID")); !strings.Contains(got, "Подготовить") {
		t.Fatal(got)
	}
}
func TestResult(t *testing.T) {
	if got := Result(nil); !strings.Contains(got, "пока не запрашивал") {
		t.Fatal(got)
	}
	log := "[PID=00000001 SectorV.exe] TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n" +
		"[PID=00000001 SectorV.exe] P2 D2 read command: no validated response fixture CB 50 B9 FB\n"
	if got := Result([]byte(log)); !strings.Contains(got, "Ответ не настроен") {
		t.Fatal(got)
	}
}
