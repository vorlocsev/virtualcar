package main

import (
	"encoding/json"
	"strings"
	"testing"
)

func TestD2IgnitionRefTXSeparateFromVIN(t *testing.T) {
	attr := []byte(`{"sessions":[{"intervals":[{"tx":"a3_tx","rx_messages_until_next_write":0},{"tx":"d2_power_ref_6660_tx","rx_messages_until_next_write":0},{"tx":"b9fb_tx","rx_messages_until_next_write":13}]}]}`)
	a, e := buildAssessment(attr, []byte(`{}`))
	if e != nil {
		t.Fatal(e)
	}
	if a.PowerReference.Requests != 1 || a.PowerReference.IntervalsWithData != 0 || a.CEM.B9FBIntervalsWithData != 1 || a.IgnitionPosition != "unknown" {
		t.Fatalf("%+v", a)
	}
}
func TestD2IgnitionCandidateDoesNotChangeKeyState(t *testing.T) {
	attr := []byte(`{"sessions":[{"intervals":[{"tx":"d2_power_ref_6660_tx","rx_messages_until_next_write":1,"rx_class_counts":{"d2_power_6660_candidate":1}}]}]}`)
	a, e := buildAssessment(attr, []byte(`{}`))
	if e != nil {
		t.Fatal(e)
	}
	if a.PowerReference.Requests != 1 || a.PowerReference.CandidateHeaders != 1 || a.IgnitionPosition != "unknown" {
		t.Fatalf("%+v", a)
	}
}
func TestD2ReferenceAbsentStillUnknown(t *testing.T) {
	a, e := buildAssessment([]byte(`{"sessions":[]}`), []byte(`{}`))
	if e != nil {
		t.Fatal(e)
	}
	if a.PowerReference.Status != "not_observed" || !strings.Contains(conciseAssessment(a), "в отчёте не обнаружен") {
		t.Fatal(a)
	}
}
func TestD2NoPayloadOrSecretWritten(t *testing.T) {
	a, e := buildAssessment([]byte(`{"token":"PRIVATE", "sessions":[]}`), []byte(`{"VIN":"SECRET"}`))
	if e != nil {
		t.Fatal(e)
	}
	b, _ := json.Marshal(a)
	if strings.Contains(string(b), "PRIVATE") || strings.Contains(string(b), "SECRET") {
		t.Fatal(string(b))
	}
}
