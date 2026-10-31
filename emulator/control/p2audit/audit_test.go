package p2audit

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func fixture(t *testing.T, name string) string {
	t.Helper()
	bytes, err := os.ReadFile(filepath.Join("..", "..", name))
	if err != nil {
		t.Fatal(err)
	}
	return string(bytes)
}
func getFixture(p Profile, name string) Fixture {
	for _, f := range p.Fixtures {
		if f.Name == name {
			return f
		}
	}
	panic("not found: " + name)
}
func TestLabVINFixture(t *testing.T) {
	p := ReadProfile(fixture(t, "virtualcar-p2-b9fb-lab-vin.ini"))
	f := getFixture(p, "D2_50")
	if !f.Valid || f.Count != 13 || f.ResponseID != 0x01200003 || len(f.VINs) != 1 || f.VINs[0] != p.VIN {
		t.Fatalf("wrong profile: %+v / %+v", p, f)
	}
	if getFixture(p, "D2_40").Count != 0 {
		t.Fatal("unexpected CEM 0x40 response")
	}
	if strings.Contains(p.Report(), p.VIN) {
		t.Fatal("report reveals VIN")
	}
}
func TestMaskedVINFixture(t *testing.T) {
	p := ReadProfile(fixture(t, "virtualcar-p2-b9fb-demo.ini"))
	f := getFixture(p, "D2_50")
	if f.Valid {
		t.Fatal("masked VIN must be flagged as incoherent")
	}
	if !strings.Contains(strings.Join(f.Issues, " "), "не совпадает") {
		t.Fatalf("missing mismatch: %+v", f.Issues)
	}
}
func TestMissingFixture(t *testing.T) {
	p := ReadProfile(fixture(t, "virtualcar-p2.ini"))
	if getFixture(p, "D2_50").Count != 0 || getFixture(p, "D2_40").Count != 0 {
		t.Fatal("base P2 contains unexpected data")
	}
}
func TestBrokenHeader(t *testing.T) {
	text := strings.Replace(fixture(t, "virtualcar-p2-b9fb-lab-vin.ini"), "8F 50 F9 FB", "8F 40 F9 FB", 1)
	f := getFixture(ReadProfile(text), "D2_50")
	if f.Valid {
		t.Fatal("wrong target accepted")
	}
}
func TestMissingFrame(t *testing.T) {
	text := strings.Replace(fixture(t, "virtualcar-p2-b9fb-lab-vin.ini"), "B9FBFrameC = 4F 30 36 39 33 31 0D 0A", "", 1)
	f := getFixture(ReadProfile(text), "D2_50")
	if f.Valid {
		t.Fatal("missing last frame accepted")
	}
}
func TestVINMismatch(t *testing.T) {
	text := strings.Replace(fixture(t, "virtualcar-p2-b9fb-lab-vin.ini"), "VIN = YV1CZ0002A0000001", "VIN = YV1CZ0002A0000002", 1)
	f := getFixture(ReadProfile(text), "D2_50")
	if f.Valid || !strings.Contains(strings.Join(f.Issues, " "), "не совпадает") {
		t.Fatal("VIN conflict not reported")
	}
}
func TestLogAfterSessionMarker(t *testing.T) {
	old := "[PID=00000001 SectorV.exe] TX (app request) 00 0F FF FE CB 40 B9 FB 00\n"
	now := "=== SECTORV VIRTUALCAR SESSION 20261030-090000 ===\n" +
		"[PID=00000002 SectorV.exe] TX (app request) 00 0F FF FE CB 50 B9 FB 00\n" +
		"[PID=00000002 SectorV.exe] P2 D2 read-only recorded frames staged CB 50 B9 FB\n" +
		recordedRX(t, "[PID=00000002 SectorV.exe] ") +
		"[PID=00000002 SectorV.exe] PassThruClose\n"
	s := SummarizeLog(old + now)
	if s.Requests40 != 0 || s.Requests50 != 1 || s.Delivered50 != 13 || !s.Complete50 || !s.ClosedAfter50 {
		t.Fatalf("wrong log summary: %+v", s)
	}
}
func TestLogLatestPIDFallback(t *testing.T) {
	s := SummarizeLog("[PID=00000001 SectorV.exe] TX (app request) 00 0F FF FE CB 40 B9 FB\n" +
		"[PID=00000002 SectorV.exe] TX (app request) 00 0F FF FE CB 50 B9 FB\n")
	if s.Requests40 != 0 || s.Requests50 != 1 || s.LastProcess != "00000002" {
		t.Fatalf("mixed process log: %+v", s)
	}
}

func TestP2BusPhaseAndResetCurrentLog(t *testing.T) {
	pre := "[PID=00000002 SectorV.exe] "
	lines := pre + "PassThruConnect protocol / flags / baud (BE) 00 00 00 05 00 00 01 00 00 01 E8 48\n" +
		pre + "TX (app request) 00 0F FF FE CB 40 B9 FB 00 00 00 00\n" +
		pre + "P2 D2 request target/opcode/baud/flags (BE) 00 00 00 40 00 00 00 FB 00 01 E8 48 00 00 01 00\n" +
		pre + "PassThruConnect protocol / flags / baud (BE) 00 00 00 05 00 00 01 00 00 07 A1 20\n" +
		pre + "TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n" +
		pre + "P2 D2 request target/opcode/baud/flags (BE) 00 00 00 50 00 00 00 FB 00 07 A1 20 00 00 01 00\n" +
		pre + "TX (app request) 00 0F FF FE FF C8 00 00 00 00 00 00\n" +
		pre + "P2 FF C8 broadcast reset: no physical ECU; intentionally silent\n"
	summary := SummarizeLog(lines)
	if summary.Requests40LS != 1 || summary.Requests50HS != 1 || summary.ResetBroadcasts != 1 || summary.MetadataEvents != 2 {
		t.Fatalf("bad bus-phase summary: %+v", summary)
	}
	if strings.Contains(summary.Report(), "discovery probe") || !strings.Contains(summary.Report(), "сброса ECU") {
		t.Fatal("incorrect FF C8 interpretation")
	}
}
func TestOldLogsInferBusSpeed(t *testing.T) {
	pre := "[PID=00000002 SectorV.exe] "
	lines := pre + "PassThruConnect protocol / flags / baud (BE) 00 00 00 05 00 00 01 00 00 01 E8 48\n" +
		pre + "TX (app request) 00 0F FF FE CB 40 B9 FB 00 00 00 00\n" +
		pre + "PassThruConnect protocol / flags / baud (BE) 00 00 00 05 00 00 01 00 00 07 A1 20\n" +
		pre + "TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n"
	summary := SummarizeLog(lines)
	if summary.Requests40LS != 1 || summary.Requests50HS != 1 || summary.MetadataEvents != 0 {
		t.Fatalf("legacy bus parsing broken: %+v", summary)
	}
}
func TestFFResetNotCountedTwice(t *testing.T) {
	pre := "[PID=00000002 SectorV.exe] "
	summary := SummarizeLog(pre + "TX (app request) 00 0F FF FE FF C8 00 00 00 00 00 00\n" +
		pre + "D2 FF C8 discovery probe: no verified response fixture 00 0F FF FE FF C8 00 00 00 00 00 00\n")
	if summary.ResetBroadcasts != 1 {
		t.Fatalf("counted commentary as command: %+v", summary)
	}
}

// recordedRX constructs a full 13-frame test log from a synthetic public
// fixture, instead of accepting 13 arbitrary messages as a correct replay.
func recordedRX(t *testing.T, prefix string) string {
	t.Helper()
	ini := parseINI(fixture(t, "virtualcar-p2-b9fb-lab-vin.ini"))
	sec := ini["D2_50"]
	var b strings.Builder
	for i := 0; i < 13; i++ {
		frame, err := decode8(sec[frameKey(0xFB, i)])
		if err != nil {
			t.Fatal(err)
		}
		fmt.Fprintf(&b, "%sPassThruReadMsgs -> delivered 01 20 00 03", prefix)
		for _, v := range frame {
			fmt.Fprintf(&b, " %02X", v)
		}
		b.WriteString("\n")
	}
	return b.String()
}
func TestYearAndHistoricalFieldsAdvisory(t *testing.T) {
	ini := fixture(t, "virtualcar-p2-b9fb-lab-vin.ini")
	p := ReadProfile(ini)
	if p.ModelYear != 2010 || len(p.Issues) != 0 {
		t.Fatalf("model year mismatch: %+v", p)
	}
	f := getFixture(p, "D2_50")
	if !f.Valid || !strings.Contains(strings.Join(f.Advisories, " "), "200512") {
		t.Fatalf("historical provenance warning missing: %+v", f)
	}
	modified := strings.Replace(ini, "ModelYear = 2010", "ModelYear = 2009", 1)
	p = ReadProfile(modified)
	if len(p.Issues) == 0 || !strings.Contains(strings.Join(p.Issues, " "), "ModelYear") {
		t.Fatal("year mismatch accepted")
	}
	if strings.Contains(p.Report(), p.VIN) {
		t.Fatal("audit leaked VIN")
	}
}
func TestReplayFrameOrderAndTruncation(t *testing.T) {
	prefix := "[PID=00000002 SectorV.exe] "
	start := prefix + "TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n"
	good := recordedRX(t, prefix)
	s := SummarizeLog(start + good + prefix + "PassThruClose\n")
	if !s.Complete50 || len(s.Replays50) != 1 || s.Replays50[0].Frames != 13 {
		t.Fatalf("no complete reply: %+v", s)
	}
	lines := strings.Split(strings.TrimSuffix(good, "\n"), "\n")
	lines[4], lines[5] = lines[5], lines[4]
	invalid := SummarizeLog(start + strings.Join(lines, "\n") + "\n")
	if invalid.Complete50 || invalid.Replays50[0].Fault == "" {
		t.Fatalf("wrong order accepted: %+v", invalid)
	}
	incomplete := SummarizeLog(start + strings.Join(lines[:12], "\n") + "\n")
	if incomplete.Complete50 {
		t.Fatal("12/13 frames accepted")
	}
	duplicate := SummarizeLog(start + good + lines[12] + "\n")
	if duplicate.Complete50 {
		t.Fatal("extra frame accepted")
	}
	// An early terminal followed by the rest must never be counted as complete.
	earlyEnd := strings.Split(strings.TrimSuffix(good, "\n"), "\n")
	earlyEnd[5] = earlyEnd[12]
	badEnd := SummarizeLog(start + strings.Join(earlyEnd, "\n") + "\n")
	if badEnd.Complete50 {
		t.Fatal("early terminal accepted")
	}
}

func TestD2AlternateSeriesAndSubblock(t *testing.T) {
	frames := [][]byte{
		{0x97, 0x50, 0xF9, 0xFB, 0x57, 0, 0x31, 0x82},
		{0x11, 0x17, 0x96, '0', '0', '2', 0x0D, 0x0A},
		{0x55, 0xFF, 0xFF, 0xFF, 0xFF, 0, 0, 0},
		{0x8F, 0x50, 0xF9, 0xFB, 0xFF, 0xFF, 0xFF, 0xFF},
		{0x4C, 0xFF, 0xFF, 0xFF, 0xFF, 0, 0, 0},
	}
	if reason := checkFrameSequence(frames, 0x50, 0xFB); reason != "" {
		t.Fatalf("VIDA-style 0x10 series rejected: %s", reason)
	}
	var log strings.Builder
	prefix := "[PID=00000022 SectorV.exe] "
	log.WriteString(prefix + "TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n")
	for _, frame := range frames {
		log.WriteString(prefix + "PassThruReadMsgs -> delivered 01 20 00 03")
		for _, v := range frame {
			fmt.Fprintf(&log, " %02X", v)
		}
		log.WriteByte('\n')
	}
	sum := SummarizeLog(log.String())
	if !sum.Complete50 || len(sum.Replays50) != 1 || !sum.Replays50[0].SequenceOK {
		t.Fatalf("D2 base-0x10 replay rejected: %+v", sum)
	}
	frames[1][0] = 0x12
	if checkFrameSequence(frames, 0x50, 0xFB) == "" {
		t.Fatal("invalid series order accepted")
	}
}

func TestStrictP2ProfileAndFrameCapacity(t *testing.T) {
	p := ReadProfile(fixture(t, "virtualcar-p2-b9fb-lab-vin.ini"))
	if !p.StrictRouting || !strings.Contains(p.Report(), "строгая") {
		t.Fatal("strict routing setting is not reported")
	}
	s := strings.Replace(fixture(t, "virtualcar-p2-b9fb-lab-vin.ini"), "B9FBFrameCount = 13", "B9FBFrameCount = 65", 1)
	f := getFixture(ReadProfile(s), "D2_50")
	if f.Valid || !strings.Contains(strings.Join(f.Issues, " "), "64") {
		t.Fatalf("over-capacity D2 fixture not flagged: %+v", f)
	}
}

func TestFC140FramingAndChecksum(t *testing.T) {
	stream := []byte{0x50, 0xF9, 0xFC, 0x8C, 0}
	for i := 0; i < 140; i++ {
		stream = append(stream, byte(i%5))
	}
	for _, v := range stream[5:] {
		stream[4] += v
	}
	frames := make([][]byte, 0, 21)
	for i := 0; i < 21; i++ {
		chunk := 7
		if i == 20 {
			chunk = 5
		}
		header := byte(0x08 | (i & 7))
		if i == 0 {
			header = 0x8F
		}
		if i == 20 {
			header = 0x4D
		}
		frame := make([]byte, 8)
		frame[0] = header
		copy(frame[1:], stream[i*7:i*7+chunk])
		frames = append(frames, frame)
	}
	if err := checkFrameSequence(frames, 0x50, 0xFC); err != "" {
		t.Fatal(err)
	}
	payload, err := decodeFC140Frames(frames, 0x50)
	if err != nil || len(payload) != 142 {
		t.Fatalf("FC140 rejected: %v", err)
	}
	frames[3][5] ^= 1
	if _, err := decodeFC140Frames(frames, 0x50); err == nil {
		t.Fatal("invalid FC140 checksum accepted")
	}
	frames[3][5] ^= 1
	frames[20][0] = 0x4F
	if _, err := decodeFC140Frames(frames, 0x50); err == nil {
		t.Fatal("wrong final length accepted")
	}
}

func TestMissingResponseIsNotIncompleteD2(t *testing.T) {
	lines := "[PID=00000003 SectorV.exe] PassThruConnect protocol / flags / baud (BE) 00 00 00 05 00 00 01 00 00 07 A1 20\n" +
		"[PID=00000003 SectorV.exe] TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n" +
		"[PID=00000003 SectorV.exe] P2 D2 read command: no validated response fixture CB 50 B9 FB\n" +
		"[PID=00000003 SectorV.exe] PassThruClose\n"
	s := SummarizeLog(lines)
	if s.Requests50 != 1 || s.Missing50 != 1 || len(s.Replays50) != 1 || s.Replays50[0].Frames != 0 {
		t.Fatalf("unexpected summary: %+v", s)
	}
	report := s.Report()
	if !strings.Contains(report, "0 доставленных кадров") || strings.Contains(report, "Нет подтверждённого завершающего кадра D2") {
		t.Fatalf("misleading zero-frame audit: %s", report)
	}
}


func TestDonorStyleP2ProfileWarnsAboutMissingCEMRoutes(t *testing.T) {
	profile := "[Vehicle]\nVIN=YV1CZ0002A0000001\nModelYear=2010\nECUCount=1\n" +
		"[ECU0]\nRequestId=7E0\nResponseId=7E8\n" +
		"[D2_50]\nResponseId=01200003\nFrameCount=0\n"
	p := ReadProfile(profile)
	if p.ECUCount != 1 || p.HasCEM726 || p.HasCEM29 {
		t.Fatalf("wrong route capabilities: %+v", p)
	}
	report := p.Report()
	for _, s := range []string{"0x726: не настроен", "0x18DA50F1: не настроен", "D2 A3/A6"} {
		if !strings.Contains(report, s) { t.Fatalf("missing %s: %s", s, report) }
	}
	if strings.Contains(report, p.VIN) { t.Fatal("full VIN leaked") }
}

func TestConfiguredElevenAndTwentyNineBitRoutes(t *testing.T) {
	profile := "[Vehicle]\nVIN=YV1CZ0002A0000001\nECUCount=3\n" +
		"[ECU0]\nRequestId=7E0\n" +
		"[ECU1]\nRequestId=726\n" +
		"[ECU2]\nRequestId=18DA50F1\n"
	p := ReadProfile(profile)
	if p.ECUCount != 3 || !p.HasCEM726 || !p.HasCEM29 { t.Fatalf("missing routes: %+v", p) }
	if strings.Contains(p.Report(), "0x726: не настроен") || strings.Contains(p.Report(), "0x18DA50F1: не настроен") {
		t.Fatal("configured routes reported missing")
	}
}
