package main

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

func TestFromDev18ActualReport(t *testing.T) {
	raw, err := os.ReadFile("../../../j2534-diagnostics.json")
	if err != nil {
		t.Skip("test only when sample report is provided")
	}
	var report struct {
		Attribution json.RawMessage `json:"attribution"`
		Ignition    json.RawMessage `json:"ignition"`
	}
	if e := json.Unmarshal(raw, &report); e != nil {
		t.Fatal(e)
	}
	a, e := buildAssessment(report.Attribution, report.Ignition)
	if e != nil {
		t.Fatal(e)
	}
	if a.VBatt.Attempts != 13 || a.VBatt.Successful != 13 || a.VBatt.LastMV == nil || *a.VBatt.LastMV != 12500 {
		t.Fatalf("vbatt: %+v", a.VBatt)
	}
	if a.PinSelection.CANPSAttempts != 18 || a.PinSelection.CANPSAccepted != 0 || a.PinSelection.ISO15765PSAttempts != 2 || a.PinSelection.ISO15765PSAccepted != 0 {
		t.Fatalf("pin: %+v", a.PinSelection)
	}
	if a.CEM.A3Writes != 3 || a.CEM.A3IntervalsWithData != 0 || a.CEM.B9F0Writes != 3 || a.CEM.B9F0IntervalsWithData != 0 || a.CEM.B9FBWrites != 8 || a.CEM.B9FBIntervalsWithData < 1 {
		t.Fatalf("cem: %+v", a.CEM)
	}
	if a.IgnitionPosition != "unknown" {
		t.Fatal(a.IgnitionPosition)
	}
}
func TestEmptyReportNotSuccess(t *testing.T) {
	a, e := buildAssessment([]byte(`{}`), []byte(`{}`))
	if e != nil {
		t.Fatal(e)
	}
	if a.VBatt.State != "not_observed" || a.PinSelection.State != "not_observed" || a.IgnitionPosition != "unknown" || a.CEM.A3Writes != 0 {
		t.Fatal(a)
	}
}
func TestAllVBattGood(t *testing.T) {
	a, e := buildAssessment([]byte(`{}`), []byte(`{"vbatt_read_attempts":2,"vbatt_successful_values_mv":[12000,12500]}`))
	if e != nil {
		t.Fatal(e)
	}
	if a.VBatt.State != "all_reads_ok" || *a.VBatt.LastMV != 12500 {
		t.Fatal(a)
	}
}
func TestPartialVBattNotMisclassified(t *testing.T) {
	a, _ := buildAssessment([]byte(`{}`), []byte(`{"vbatt_read_attempts":2,"vbatt_successful_values_mv":[12500]}`))
	if a.VBatt.State != "failed_or_partial" {
		t.Fatal(a)
	}
}
func TestPSCountsKnownAndNotSilentlyMapped(t *testing.T) {
	a, _ := buildAssessment([]byte(`{}`), []byte(`{"connects":[{"protocol_id":5,"status":0,"count":10},{"protocol_id":32772,"status":3,"count":3},{"protocol_id":32773,"status":0,"count":2}]}`))
	if a.PinSelection.CANPSAttempts != 3 || a.PinSelection.ISO15765PSAttempts != 2 || a.PinSelection.ISO15765PSAccepted != 2 || a.PinSelection.State != "partial_or_supported" {
		t.Fatal(a.PinSelection)
	}
}
func TestAllPSRejected(t *testing.T) {
	a, _ := buildAssessment([]byte(`{}`), []byte(`{"connects":[{"protocol_id":32772,"status":3,"count":1}]}`))
	if a.PinSelection.State != "all_observed_connections_failed" {
		t.Fatal(a.PinSelection)
	}
}
func TestA3NotConfusedWithB9FB(t *testing.T) {
	a, _ := buildAssessment([]byte(`{"sessions":[{"intervals":[{"tx":"a3_tx","rx_messages_until_next_write":0},{"tx":"b9fb_tx","rx_messages_until_next_write":13}]}]}`), []byte(`{}`))
	if a.CEM.A3IntervalsWithData != 0 || a.CEM.B9FBIntervalsWithData != 1 {
		t.Fatal(a.CEM)
	}
}
func TestRXAfterA3NotAuthenticated(t *testing.T) {
	a, _ := buildAssessment([]byte(`{"sessions":[{"intervals":[{"tx":"a3_tx","rx_messages_until_next_write":1}]}]}`), []byte(`{}`))
	if a.CEM.A3IntervalsWithData != 1 || !strings.Contains(a.CEM.Note, "not a validated") {
		t.Fatal(a.CEM)
	}
}
func TestNoSecretsInAssessment(t *testing.T) {
	a, _ := buildAssessment([]byte(`{"token":"DONT_COPY","sessions":[{"intervals":[]}]}`), []byte(`{"vin":"SENSITIVE","vbatt_read_attempts":1}`))
	b, _ := json.Marshal(a)
	if strings.Contains(string(b), "DONT_COPY") || strings.Contains(string(b), "SENSITIVE") {
		t.Fatal(string(b))
	}
}
func TestBadJSONRejected(t *testing.T) {
	if _, e := buildAssessment([]byte(`not_json`), []byte(`{}`)); e == nil {
		t.Fatal("accepted")
	}
	if _, e := buildAssessment([]byte(`{}`), []byte(`not_json`)); e == nil {
		t.Fatal("accepted")
	}
}
func TestGuiLabelsExplicitlyUnknown(t *testing.T) {
	a, _ := buildAssessment([]byte(`{}`), []byte(`{}`))
	s := conciseAssessment(a)
	if !strings.Contains(s, "НЕ ОПРЕДЕЛЕНО") || !strings.Contains(s, "не означает OFF") {
		t.Fatal(s)
	}
}
func TestReadOldCombinedWithoutAssessment(t *testing.T) {
	a, e := readAssessmentFile([]byte(`{"attribution":{"sessions":[]},"ignition":{"vbatt_read_attempts":1,"vbatt_successful_values_mv":[12500]}}`))
	if e != nil || a.VBatt.LastMV == nil || *a.VBatt.LastMV != 12500 {
		t.Fatal(a, e)
	}
}
func TestReadNewCombined(t *testing.T) {
	a, e := readAssessmentFile([]byte(`{"assessment":{"version":"vX","ignition_position":"unknown"}}`))
	if e != nil || a.Version != "vX" {
		t.Fatal(a, e)
	}
}
func TestReadCombinedMalformed(t *testing.T) {
	if _, e := readAssessmentFile([]byte(`{"assessment":{"ignition_position":"unknown"}}`)); e == nil {
		t.Fatal("missing version accepted")
	}
}

func TestDev21UnknownD2SeparateFromVIN(t *testing.T) {
	attr := []byte(`{"sessions":[{"baud":125000,"intervals":[{"tx":"d2_unresolved_tx","rx_messages_until_next_write":0},{"tx":"d2_a6_marker_tx","rx_messages_until_next_write":0},{"tx":"d2_power_ref_6660_possible_tx","rx_messages_until_next_write":0}]},{"baud":500000,"intervals":[{"tx":"a3_tx","rx_messages_until_next_write":0},{"tx":"b9fb_tx","rx_messages_until_next_write":13}]}]}`)
	a, e := buildAssessment(attr, []byte(`{}`))
	if e != nil {
		t.Fatal(e)
	}
	if a.D2Unclassified.UnresolvedTotal != 1 || a.D2Unclassified.PossibleA6 != 1 || a.D2Unclassified.PossibleReference6660 != 1 || a.D2Unclassified.ByBaud["125000"] != 1 {
		t.Fatalf("%+v", a.D2Unclassified)
	}
	if a.PowerReference.Requests != 0 || a.IgnitionPosition != "unknown" || a.CEM.B9FBIntervalsWithData != 1 {
		t.Fatal(a)
	}
}
func TestDev21CandidateCannotBeTreatedAsIgnition(t *testing.T) {
	a, e := buildAssessment([]byte(`{"sessions":[{"intervals":[{"tx":"d2_power_ref_6660_possible_tx","rx_messages_until_next_write":1}]}]}`), []byte(`{}`))
	if e != nil {
		t.Fatal(e)
	}
	if a.PowerReference.Requests != 0 || a.IgnitionPosition != "unknown" {
		t.Fatal(a)
	}
}

func TestDev22NormalModeHasItsOwnStatus(t *testing.T) {
	attr := []byte(`{"sessions":[{"baud":500000,"intervals":[{"tx":"a3_tx","rx_messages_until_next_write":0},{"tx":"a3_0203_shape_tx","rx_messages_until_next_write":0},{"tx":"b9fb_tx","rx_messages_until_next_write":13}]}]}`)
	a, err := buildAssessment(attr, []byte(`{}`))
	if err != nil {
		t.Fatal(err)
	}
	if a.A3Shape.KnownShapeTX != 1 || a.A3Shape.OtherA3TX != 1 || a.A3Shape.E302CandidateRX != 0 || a.A3Shape.Status != "request_seen_no_rx" {
		t.Fatalf("shape: %+v", a.A3Shape)
	}
	if a.CEM.A3Writes != 2 || a.CEM.A3IntervalsWithData != 0 || a.CEM.B9FBIntervalsWithData != 1 {
		t.Fatal(a.CEM)
	}
	if a.IgnitionPosition != "unknown" {
		t.Fatal(a.IgnitionPosition)
	}
}
func TestDev22E302CandidateIsNotAuthentication(t *testing.T) {
	attr := []byte(`{"sessions":[{"intervals":[{"tx":"a3_0203_shape_tx","rx_messages_until_next_write":1,"rx_class_counts":{"e3_02_candidate":1}}]}]}`)
	a, err := buildAssessment(attr, []byte(`{}`))
	if err != nil {
		t.Fatal(err)
	}
	if a.A3Shape.E302CandidateRX != 1 || a.A3Shape.Status != "request_seen_response_unverified" || a.IgnitionPosition != "unknown" {
		t.Fatal(a)
	}
	if !strings.Contains(a.A3Shape.Note, "do not establish") {
		t.Fatal(a.A3Shape.Note)
	}
}
func TestDev22LegacyA3NotClaimedNormal(t *testing.T) {
	a, err := buildAssessment([]byte(`{"sessions":[{"intervals":[{"tx":"a3_tx","rx_messages_until_next_write":0}]}]}`), []byte(`{}`))
	if err != nil {
		t.Fatal(err)
	}
	if a.A3Shape.KnownShapeTX != 0 || a.A3Shape.Status != "not_observed" || a.A3Shape.OtherA3TX != 1 {
		t.Fatal(a)
	}
}
