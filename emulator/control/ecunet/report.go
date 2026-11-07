// Package ecunet audits observed J2534 discovery without equating a VIN response
// with an ECU inventory, or guessing identities from generic TesterPresent.
package ecunet

import (
	"fmt"
	"strings"
)

type Summary struct {
	SectorB9FB, SectorB9F0, SectorB9FC                                              int
	SectorF114, SectorF1B0, SectorF1A3, SectorF106                                  int
	VDASHVinRequests, VDASHVinDelivered, VDASHRxStart                               int
	VDASH29BitTesterPresent, VDASHReadIdentifier, RecordedPassiveRX, ExtraD2Replays int
	VDASHSessions, SectorSessions                                                   int
	LastVDASHVinRequested, LastVDASHVinDelivered, LastVDASHRxStart                  int
	LastVDASHIdentityQueries                                                        int
}

func Analyze(log string) Summary {
	if i := strings.LastIndex(log, "=== SECTORV VIRTUALCAR SESSION "); i >= 0 {
		log = log[i:]
	}
	var out Summary
	// Each DLL initialization is a fresh PassThru client instance. This is
	// preferable to confusing 20 reconnects with 20 distinct ECU identities.
	for _, line := range strings.Split(log, "\n") {
		line = strings.TrimSpace(line)
		isSector := strings.Contains(line, " SectorV.exe]")
		isVDASH := strings.Contains(line, " vdash_u.exe]")
		if isVDASH && strings.Contains(line, "VirtualCar DLL initialized") {
			out.VDASHSessions++
			out.LastVDASHVinRequested = 0
			out.LastVDASHVinDelivered = 0
			out.LastVDASHRxStart = 0
			out.LastVDASHIdentityQueries = 0
		}
		if isSector && strings.Contains(line, "VirtualCar DLL initialized") {
			out.SectorSessions++
		}
		if isSector && strings.Contains(line, "TX (app request)") {
			switch {
			case strings.Contains(line, "00 0F FF FE CB"):
				if strings.Contains(line, "B9 FB") {
					out.SectorB9FB++
				}
				if strings.Contains(line, "B9 F0") {
					out.SectorB9F0++
				}
				if strings.Contains(line, "B9 FC") {
					out.SectorB9FC++
				}
			case strings.Contains(line, "00 00 07 26 03 22 F1 14"):
				out.SectorF114++
			case strings.Contains(line, "00 00 07 26 03 22 F1 B0"):
				out.SectorF1B0++
			case strings.Contains(line, "00 00 07 26 03 22 F1 A3"):
				out.SectorF1A3++
			case strings.Contains(line, "00 00 07 26 03 22 F1 06"):
				out.SectorF106++
			}
		}
		if isVDASH {
			if strings.Contains(line, "TX (app request) 00 00 07 DF 09 02") {
				out.VDASHVinRequests++
				out.LastVDASHVinRequested++
			}
			if strings.Contains(line, "PassThruReadMsgs -> delivered 00 00 07 E8 49 02 01") {
				out.VDASHVinDelivered++
				out.LastVDASHVinDelivered++
			}
			if strings.Contains(line, "RX START_OF_MESSAGE (ISO15765)") {
				out.VDASHRxStart++
				out.LastVDASHRxStart++
			}
			if strings.Contains(line, "TX (app request) 18 DB 33 F1 3E 80") {
				out.VDASH29BitTesterPresent++
			}
			if strings.Contains(line, "TX (app request)") && strings.Contains(line, " 22 F1 ") {
				out.VDASHReadIdentifier++
				out.LastVDASHIdentityQueries++
			}
		}
		if strings.Contains(line, "Passive CAN recorded fixture replay") {
			out.RecordedPassiveRX++
		}
		if strings.Contains(line, "P2 D2 read-only recorded frames staged") &&
			!strings.Contains(line, "B9 FB") && !strings.Contains(line, "B9 F0") && !strings.Contains(line, "B9 FC") {
			out.ExtraD2Replays++
		}
	}
	return out
}

func (s Summary) Report() string {
	verdict := "В последнем сеансе VDASH не обнаружены запросы 22 F1xx для идентификации ECU."
	if s.LastVDASHIdentityQueries > 0 {
		verdict = "В последнем сеансе VDASH были запросы 22 F1xx: проверяйте их адреса и ответные данные."
	}
	return fmt.Sprintf("СЕТЬ ECU (наблюдаемый транспорт, не список обнаруженных блоков)\n"+
		"Подключений VDASH: %d; SectorV: %d. Это число сеансов, НЕ число ECU.\n"+
		"VDASH всего: запросов VIN 09 02: %d; VIN-ответов доставлено: %d; RxStart: %d\n"+
		"VDASH последняя попытка: VIN %d/%d, RxStart %d, идентификационных запросов 22 F1xx: %d\n"+
		"SectorV: P2 B9FB=%d, B9F0=%d, B9FC=%d; P3 F114=%d, F1B0=%d, F1A3=%d, F106=%d\n"+
		"VDASH 29-битный TesterPresent 3E80 (положительный ответ подавлен): %d\n"+
		"Воспроизведено пассивных записанных CAN кадров: %d; дополнительных D2 ответов: %d\n"+
		"%s\n"+
		"Одна доставка VIN доказывает транспортный обмен, но не идентификацию CEM/ECM.\n",
		s.VDASHSessions, s.SectorSessions,
		s.VDASHVinRequests, s.VDASHVinDelivered, s.VDASHRxStart,
		s.LastVDASHVinDelivered, s.LastVDASHVinRequested, s.LastVDASHRxStart, s.LastVDASHIdentityQueries,
		s.SectorB9FB, s.SectorB9F0, s.SectorB9FC, s.SectorF114, s.SectorF1B0, s.SectorF1A3, s.SectorF106,
		s.VDASH29BitTesterPresent, s.RecordedPassiveRX, s.ExtraD2Replays, verdict)
}
