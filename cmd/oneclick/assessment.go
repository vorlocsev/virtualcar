package main

import (
	"encoding/json"
	"fmt"
	"strings"
)

// Assessment is limited to observed J2534 metadata. It never asserts a key position
// or validates a CEM reply and it never includes CAN payloads or credentials.
type Assessment struct {
	CoreBridge CoreBridgeAssessment `json:"j2534_vehicle_core"`
	Version    string               `json:"version"`
	VBatt      struct {
		Attempts   int     `json:"attempts"`
		Successful int     `json:"successful"`
		LastMV     *uint32 `json:"last_mv,omitempty"`
		State      string  `json:"state"`
	} `json:"vbatt"`
	PinSelection struct {
		CANPSAttempts      int    `json:"can_ps_attempts"`
		CANPSAccepted      int    `json:"can_ps_accepted"`
		ISO15765PSAttempts int    `json:"iso15765_ps_attempts"`
		ISO15765PSAccepted int    `json:"iso15765_ps_accepted"`
		State              string `json:"state"`
	} `json:"pin_selection"`
	CEM struct {
		A3Writes              int    `json:"a3_writes"`
		A3IntervalsWithData   int    `json:"a3_intervals_with_data"`
		B9F0Writes            int    `json:"b9f0_writes"`
		B9F0IntervalsWithData int    `json:"b9f0_intervals_with_data"`
		B9FBWrites            int    `json:"b9fb_writes"`
		B9FBIntervalsWithData int    `json:"b9fb_intervals_with_data"`
		Note                  string `json:"note"`
	} `json:"cem"`
	A3Shape struct {
		KnownShapeTX        int    `json:"known_shape_tx"`
		TXIntervalsWithData int    `json:"tx_intervals_with_data"`
		E302CandidateRX     int    `json:"e3_02_candidate_rx"`
		OtherA3TX           int    `json:"other_a3_tx"`
		Status              string `json:"status"`
		Note                string `json:"note"`
	} `json:"a3_shape"`
	PowerReference struct {
		Requests          int    `json:"requests"`
		IntervalsWithData int    `json:"intervals_with_data"`
		CandidateHeaders  int    `json:"candidate_headers"`
		Status            string `json:"status"`
		Note              string `json:"note"`
	} `json:"d2_ignition_reference_6660"`
	D2Unclassified struct {
		UnresolvedTotal       int            `json:"unresolved_total"`
		PossibleA6            int            `json:"possible_a6"`
		PossibleReference6660 int            `json:"possible_reference_6660"`
		ByBaud                map[string]int `json:"by_baud"`
		Note                  string         `json:"note"`
	} `json:"d2_unclassified"`
	IgnitionPosition string   `json:"ignition_position"`
	Limitations      []string `json:"limitations"`
}

type ignitionMeta struct {
	Connects []struct {
		ProtocolID uint32 `json:"protocol_id"`
		Status     uint32 `json:"status"`
		Count      int    `json:"count"`
	} `json:"connects"`
	VBattReadAttempts       int      `json:"vbatt_read_attempts"`
	VBattSuccessfulValuesMV []uint32 `json:"vbatt_successful_values_mv"`
}
type attributionMeta struct {
	Sessions []struct {
		Baud      uint32 `json:"baud"`
		Intervals []struct {
			TX            string         `json:"tx"`
			RXMessages    int            `json:"rx_messages_until_next_write"`
			RXClassCounts map[string]int `json:"rx_class_counts"`
		} `json:"intervals"`
	} `json:"sessions"`
}

func buildAssessment(attributionJSON, ignitionJSON []byte) (Assessment, error) {
	var a Assessment
	a.Version = "0.3.6.7-dev26"
	a.IgnitionPosition = "unknown"
	a.A3Shape.Status = "not_observed"
	a.A3Shape.Note = "A3 02 03 A5 A5 00 occurs in both the hardware-identification and normal-mode code paths. The TX bytes do not establish which code path was executed. E3 02 is a candidate header only; neither RX nor byte matching proves CEM confirmation. Legacy logs cannot distinguish A3 shapes."
	a.PowerReference.Status = "not_observed"
	a.PowerReference.Note = "D2 request A6 1A 04 01 (ref 6660); received data or E6 header is not proof of ignition position."
	a.D2Unclassified.ByBaud = map[string]int{}
	a.D2Unclassified.Note = "Opaque D2 TX classification: does not reveal any CAN payload; A6 outside known framing is a candidate only."
	a.CEM.Note = "RX following a write is a temporal association, not a validated ECU response."
	a.Limitations = []string{
		"READ_VBATT is adapter voltage, not ignition/key state.",
		"CAN_PS and ISO15765_PS errors do not prove an ignition problem.",
		"TX/RX classification does not verify CEM reply content or authorization.",
	}
	var i ignitionMeta
	if err := json.Unmarshal(ignitionJSON, &i); err != nil {
		return a, fmt.Errorf("ignition JSON: %w", err)
	}
	var t attributionMeta
	if err := json.Unmarshal(attributionJSON, &t); err != nil {
		return a, fmt.Errorf("attribution JSON: %w", err)
	}
	a.VBatt.Attempts = i.VBattReadAttempts
	a.VBatt.Successful = len(i.VBattSuccessfulValuesMV)
	a.VBatt.State = "not_observed"
	if a.VBatt.Attempts > 0 {
		a.VBatt.State = "failed_or_partial"
		if a.VBatt.Successful == a.VBatt.Attempts {
			a.VBatt.State = "all_reads_ok"
		}
	}
	if a.VBatt.Successful > 0 {
		mv := i.VBattSuccessfulValuesMV[len(i.VBattSuccessfulValuesMV)-1]
		a.VBatt.LastMV = &mv
	}
	for _, c := range i.Connects {
		if c.ProtocolID == 0x8004 {
			a.PinSelection.CANPSAttempts += c.Count
			if c.Status == 0 {
				a.PinSelection.CANPSAccepted += c.Count
			}
		}
		if c.ProtocolID == 0x8005 {
			a.PinSelection.ISO15765PSAttempts += c.Count
			if c.Status == 0 {
				a.PinSelection.ISO15765PSAccepted += c.Count
			}
		}
	}
	a.PinSelection.State = "not_observed"
	total := a.PinSelection.CANPSAttempts + a.PinSelection.ISO15765PSAttempts
	if total > 0 {
		a.PinSelection.State = "partial_or_supported"
		if a.PinSelection.CANPSAccepted+a.PinSelection.ISO15765PSAccepted == 0 {
			a.PinSelection.State = "all_observed_connections_failed"
		}
	}
	for _, s := range t.Sessions {
		for _, v := range s.Intervals {
			switch v.TX {
			case "d2_unresolved_tx":
				a.D2Unclassified.UnresolvedTotal++
				a.D2Unclassified.ByBaud[fmt.Sprintf("%d", s.Baud)]++
			case "d2_a6_marker_tx":
				a.D2Unclassified.PossibleA6++
			case "d2_power_ref_6660_possible_tx":
				a.D2Unclassified.PossibleReference6660++
			}
			if v.TX == "d2_power_ref_6660_tx" {
				a.PowerReference.Requests++
				if v.RXMessages > 0 {
					a.PowerReference.IntervalsWithData++
				}
				a.PowerReference.CandidateHeaders += v.RXClassCounts["d2_power_6660_candidate"]
			}
			switch v.TX {
			case "a3_0203_shape_tx":
				a.CEM.A3Writes++
				a.A3Shape.KnownShapeTX++
				if v.RXMessages > 0 {
					a.A3Shape.TXIntervalsWithData++
				}
				a.A3Shape.E302CandidateRX += v.RXClassCounts["e3_02_candidate"]
				if v.RXMessages > 0 {
					a.CEM.A3IntervalsWithData++
				}
			case "a3_tx":
				a.A3Shape.OtherA3TX++
				a.CEM.A3Writes++
				if v.RXMessages > 0 {
					a.CEM.A3IntervalsWithData++
				}
			case "b9f0_tx":
				a.CEM.B9F0Writes++
				if v.RXMessages > 0 {
					a.CEM.B9F0IntervalsWithData++
				}
			case "b9fb_tx":
				a.CEM.B9FBWrites++
				if v.RXMessages > 0 {
					a.CEM.B9FBIntervalsWithData++
				}
			}
		}
	}
	if a.A3Shape.KnownShapeTX > 0 {
		a.A3Shape.Status = "request_seen_response_unverified"
		if a.A3Shape.TXIntervalsWithData == 0 {
			a.A3Shape.Status = "request_seen_no_rx"
		}
	}
	if a.PowerReference.Requests > 0 {
		a.PowerReference.Status = "requests_observed"
	}
	return a, nil
}

func conciseAssessment(a Assessment) string {
	v := "Питание: нет успешного измерения"
	if a.VBatt.LastMV != nil {
		v = fmt.Sprintf("Питание: %.2f В (%d/%d успешных чтений)", float64(*a.VBatt.LastMV)/1000, a.VBatt.Successful, a.VBatt.Attempts)
	}
	ps := "J2534-2 PS: запросов не обнаружено"
	if a.PinSelection.CANPSAttempts+a.PinSelection.ISO15765PSAttempts > 0 {
		ps = fmt.Sprintf("CAN_PS: %d/%d; ISO15765_PS: %d/%d подключений", a.PinSelection.CANPSAccepted, a.PinSelection.CANPSAttempts, a.PinSelection.ISO15765PSAccepted, a.PinSelection.ISO15765PSAttempts)
	}
	cem := fmt.Sprintf("CEM RX: A3 %d/%d; B9F0 %d/%d; B9FB %d/%d интервалов", a.CEM.A3IntervalsWithData, a.CEM.A3Writes, a.CEM.B9F0IntervalsWithData, a.CEM.B9F0Writes, a.CEM.B9FBIntervalsWithData, a.CEM.B9FBWrites)
	power := "D2 Ref 6660: в отчёте не обнаружен (старые трассы не распознают)"
	if a.PowerReference.Requests > 0 {
		power = fmt.Sprintf("D2 Ref 6660 (зажигание): TX %d; интервалы с RX %d (не подтверждено)", a.PowerReference.Requests, a.PowerReference.IntervalsWithData)
	}
	normal := fmt.Sprintf("A3-шаблон 02 03: TX %d; RX-интервалы %d; E3 02 кандидатов %d (сценарий неизвестен)", a.A3Shape.KnownShapeTX, a.A3Shape.TXIntervalsWithData, a.A3Shape.E302CandidateRX)
	unknown := fmt.Sprintf("Неразобранные D2 TX: %d; кандидаты A6: %d; Ref6660?: %d", a.D2Unclassified.UnresolvedTotal, a.D2Unclassified.PossibleA6, a.D2Unclassified.PossibleReference6660)
	core := "Vehicle Core: данных dev26 нет"
	if a.CoreBridge.Enabled {
		core = fmt.Sprintf("Vehicle Core: D2 TX %d; A3 без эталона %d; B9F0 без эталона %d; B9FB штатный %d; пометки маршрута %d",
			a.CoreBridge.InspectedD2TX, a.CoreBridge.A3NeedsEvidence, a.CoreBridge.B9F0NeedsEvidence,
			a.CoreBridge.B9FBDelegated, a.CoreBridge.RouteMismatchAnnotations)
	}
	return strings.Join([]string{v, ps, power, normal, unknown, core, "Зажигание: НЕ ОПРЕДЕЛЕНО (не означает OFF)", cem}, "\r\n")
}

// readAssessmentFile supports both dev18 reports (without assessment) and dev19.
// It reads only the sanitized result JSON; never touches the authorization store.
func readAssessmentFile(source []byte) (Assessment, error) {
	var report struct {
		Attribution json.RawMessage `json:"attribution"`
		Ignition    json.RawMessage `json:"ignition"`
		Assessment  json.RawMessage `json:"assessment"`
	}
	if err := json.Unmarshal(source, &report); err != nil {
		return Assessment{}, err
	}
	if len(report.Assessment) > 0 {
		var a Assessment
		if err := json.Unmarshal(report.Assessment, &a); err != nil {
			return a, err
		}
		if a.Version == "" {
			return a, fmt.Errorf("invalid assessment version")
		}
		return a, nil
	}
	if len(report.Attribution) == 0 || len(report.Ignition) == 0 {
		return Assessment{}, fmt.Errorf("missing attribution or ignition")
	}
	return buildAssessment(report.Attribution, report.Ignition)
}
