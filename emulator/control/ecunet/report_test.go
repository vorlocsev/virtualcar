package ecunet

import (
	"strings"
	"testing"
)

func TestAnalyzeLatestSession(t *testing.T) {
	log := `[PID=0 vdash_u.exe] TX (app request) 00 00 07 DF 09 02
=== SECTORV VIRTUALCAR SESSION 20261030-120000 ===
[PID=1 vdash_u.exe] TX (app request) 00 00 07 DF 09 02
[PID=1 vdash_u.exe] RX START_OF_MESSAGE (ISO15765)
[PID=1 vdash_u.exe] PassThruReadMsgs -> delivered 00 00 07 E8 49 02 01 59
[PID=1 vdash_u.exe] TX (app request) 18 DB 33 F1 3E 80
[PID=2 SectorV.exe] TX (app request) 00 0F FF FE CB 50 B9 FB 00 00
[PID=2 SectorV.exe] TX (app request) 00 0F FF FE CB 50 B9 F0 00 00
[PID=2 SectorV.exe] TX (app request) 00 0F FF FE CB 50 B9 FC 00 00
[PID=2 vdash_u.exe] Passive CAN recorded fixture replay (not OEM-authenticated)
`
	s := Analyze(log)
	if s.VDASHVinRequests != 1 || s.VDASHVinDelivered != 1 || s.VDASHRxStart != 1 || s.VDASH29BitTesterPresent != 1 || s.RecordedPassiveRX != 1 {
		t.Fatalf("vdash: %+v", s)
	}
	if s.SectorB9FB != 1 || s.SectorB9F0 != 1 || s.SectorB9FC != 1 {
		t.Fatalf("sector: %+v", s)
	}
	if !strings.Contains(s.Report(), "не список обнаруженных") {
		t.Fatal("missing interpretation warning")
	}
}
func TestNoVehicleClaimFromProbe(t *testing.T) {
	s := Analyze(`[PID=1 vdash_u.exe] TX (app request) 18 DB 33 F1 3E 80`)
	if s.VDASHVinDelivered != 0 || s.SectorB9F0 != 0 {
		t.Fatal(s)
	}
}

func TestLastVDASHConnectionNotECUCount(t *testing.T) {
	log := `=== SECTORV VIRTUALCAR SESSION 20261030-140000 ===
[PID=1 vdash_u.exe] VirtualCar DLL initialized
[PID=1 vdash_u.exe] TX (app request) 00 00 07 DF 09 02
[PID=1 vdash_u.exe] PassThruReadMsgs -> delivered 00 00 07 E8 49 02 01 59
[PID=1 vdash_u.exe] VirtualCar DLL initialized
[PID=1 vdash_u.exe] TX (app request) 00 00 07 DF 09 02
[PID=1 vdash_u.exe] RX START_OF_MESSAGE (ISO15765)
[PID=1 vdash_u.exe] PassThruReadMsgs -> delivered 00 00 07 E8 49 02 01 59
[PID=1 vdash_u.exe] TX (app request) 18 DB 33 F1 3E 80`
	s := Analyze(log)
	if s.VDASHSessions != 2 || s.VDASHVinDelivered != 2 || s.LastVDASHVinDelivered != 1 || s.LastVDASHIdentityQueries != 0 {
		t.Fatalf("incorrect total or last session: %+v", s)
	}
	if !strings.Contains(s.Report(), "НЕ число ECU") {
		t.Fatalf("bad interpretation: %s", s.Report())
	}
}

func TestSectorReadIDRequests(t *testing.T) {
	log := `=== SECTORV VIRTUALCAR SESSION 20261030-140000 ===
[PID=1 SectorV.exe] TX (app request) 00 00 07 26 03 22 F1 14 00 00
[PID=1 SectorV.exe] TX (app request) 00 00 07 26 03 22 F1 B0 00 00
[PID=1 SectorV.exe] TX (app request) 00 00 07 26 03 22 F1 A3 00 00
[PID=1 SectorV.exe] TX (app request) 00 00 07 26 03 22 F1 06 00 00`
	s := Analyze(log)
	if s.SectorF114 != 1 || s.SectorF1B0 != 1 || s.SectorF1A3 != 1 || s.SectorF106 != 1 {
		t.Fatal(s)
	}
}
