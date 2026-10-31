package main

import (
	"encoding/json"
	"strings"
	"testing"
)

func fixture(lines ...string) string { return strings.Join(lines, "\n") + "\n" }
func TestA3F0FBDoesNotMisattributeVIN(t *testing.T) {
	r, e := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"ms":100,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"ms":110,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}`,
		`{"schema":15,"ms":112,"event":"read","channel":1,"status":16,"count":0,"class":"other"}`,
		`{"schema":15,"ms":200,"event":"write","channel":1,"status":0,"count":1,"class":"b9f0_tx"}`,
		`{"schema":15,"ms":300,"event":"write","channel":1,"status":0,"count":1,"class":"b9fb_tx"}`,
		`{"schema":15,"ms":310,"event":"read","channel":1,"status":0,"count":13,"class":"d2_rx_fragment"}`,
		`{"schema":15,"event":"disconnect","channel":1,"status":0}`)))
	if e != nil {
		t.Fatal(e)
	}
	if len(r.Sessions) != 1 || len(r.Sessions[0].Intervals) != 3 {
		t.Fatal(r)
	}
	a := r.Sessions[0].Intervals
	if a[0].RXCallsWithData != 0 || a[1].RXCallsWithData != 0 || a[2].RXMessageCount != 13 || a[2].RXCallsWithData != 1 {
		t.Fatalf("wrong attribution: %+v", a)
	}
	if !a[2].RXMultiMessageAmbiguous || *a[2].TimeToFirstDataMs != 10 {
		t.Fatalf("missing ambiguity / time: %+v", a[2])
	}
}
func TestChannelGenerationIsolated(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}`,
		`{"schema":15,"event":"disconnect","channel":1,"status":0}`,
		`{"schema":15,"event":"connect","channel":1,"status":0,"value":125000}`,
		`{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"b9fb_tx"}`,
		`{"schema":15,"event":"read","channel":1,"status":0,"count":1,"class":"d2_rx_fragment"}`)))
	if len(r.Sessions) != 2 || r.Sessions[0].Intervals[0].RXCallsWithData != 0 || r.Sessions[1].Intervals[0].RXCallsWithData != 1 || r.Sessions[1].Generation != 2 {
		t.Fatal(r)
	}
}
func TestParallelChannelsNotCrossed(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"event":"connect","channel":3,"status":0,"value":500000}`,
		`{"schema":15,"event":"connect","channel":4,"status":0,"value":125000}`,
		`{"schema":15,"event":"write","channel":3,"status":0,"count":1,"class":"a3_tx"}`,
		`{"schema":15,"event":"write","channel":4,"status":0,"count":1,"class":"b9fb_tx"}`,
		`{"schema":15,"event":"read","channel":4,"status":0,"count":1,"class":"d2_rx_fragment"}`)))
	if r.Sessions[0].Intervals[0].RXCallsWithData != 0 || r.Sessions[1].Intervals[0].RXCallsWithData != 1 {
		t.Fatal(r)
	}
}
func TestOtherWriteEndsPreviousWindow(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}`,
		`{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"other"}`,
		`{"schema":15,"event":"read","channel":1,"status":0,"count":1,"class":"e3_candidate"}`)))
	if r.Sessions[0].Intervals[0].RXCallsWithData != 0 || r.Sessions[0].Intervals[1].RXCallsWithData != 1 {
		t.Fatal(r)
	}
}
func TestReadStatusAndFailedWrite(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"event":"read","channel":1,"status":0,"count":1,"class":"other"}`,
		`{"schema":15,"event":"write","channel":1,"status":7,"count":0,"class":"a3_tx"}`,
		`{"schema":15,"event":"read","channel":1,"status":16,"count":0,"class":"other"}`)))
	s := r.Sessions[0]
	if s.DataBeforeAnyWrite != 1 || s.Intervals[0].TXOk || s.Intervals[0].RXStatusCounts["16"] != 1 || s.Intervals[0].Interpretation != "write_failed_or_count_zero" {
		t.Fatal(r)
	}
}
func TestFailedDisconnectKeepsSession(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"event":"disconnect","channel":1,"status":7}`,
		`{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}`)))
	if r.UnattributedCalls != 0 || r.Totals["disconnect_failed"] != 1 || len(r.Sessions[0].Intervals) != 1 {
		t.Fatal(r)
	}
}
func TestConnectSupersededAndOrphan(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}`,
		`{"schema":15,"event":"connect","channel":1,"status":0,"value":125000}`,
		`{"schema":15,"event":"read","channel":1,"status":0,"count":1,"class":"other"}`,
		`{"schema":15,"event":"write","channel":9,"status":0,"count":1,"class":"b9fb_tx"}`)))
	if !r.Sessions[0].SupersededByConnect || r.Sessions[0].Intervals[0].EndedBy != "new_connect_same_channel" || r.UnattributedCalls != 1 || r.Sessions[1].DataBeforeAnyWrite != 1 {
		t.Fatal(r)
	}
}
func TestIgnoreSecretsAndBadEvents(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture("bad", `{"schema":15,"event":"connect","channel":1,"status":0,"value":500000,"secret":"NEVER_PRINT"}`, `{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"SECRET_TOKEN"}`)))
	b, _ := json.Marshal(r)
	if strings.Contains(string(b), "NEVER_PRINT") || strings.Contains(string(b), "SECRET_TOKEN") || r.Ignored != 1 || r.Sessions[0].Intervals[0].TX != "other" {
		t.Fatal(string(b))
	}
}
func TestLegacyReconstruction(t *testing.T) {
	s := `{"version":"0.3.6.7-dev15","sessions":[{"channel":1,"generation":14,"baud":500000,"read_calls_with_data":13,"reads_after_a3_with_data":13,"ordered_events":["connect","a3_tx","read:other","b9f0_tx","b9fb_tx","read:d2_rx_fragment","read:d2_rx_fragment","disconnect"]}]}`
	r, e := legacyAnalyze(strings.NewReader(s))
	if e != nil {
		t.Fatal(e)
	}
	w := r.Sessions[0].TXWindows
	if len(w) != 3 || len(w[0].CandidateRXEventsBeforeNextWrite) != 0 || len(w[1].CandidateRXEventsBeforeNextWrite) != 0 || w[2].CandidateRXEventsBeforeNextWrite["d2_rx_fragment"] != 2 {
		t.Fatal(r)
	}
}
func TestLegacyMustBeDev15(t *testing.T) {
	if _, e := legacyAnalyze(strings.NewReader(`{"version":"0.3.6.7-dev14","sessions":[]}`)); e == nil {
		t.Fatal("expected error")
	}
}
func TestInvalidInputDoesNotCrash(t *testing.T) {
	_, e := rawAnalyze(strings.NewReader(strings.Repeat("x", 1100000)))
	if e == nil {
		t.Fatal("scanner must reject oversized lines")
	}
}
func TestMsWrap(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"ms":4294967290,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"ms":4294967292,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}`,
		`{"schema":15,"ms":5,"event":"read","channel":1,"status":0,"count":1,"class":"e3_candidate"}`)))
	if *r.Sessions[0].Intervals[0].TimeToFirstDataMs != 9 {
		t.Fatal(r)
	}
}
func TestRXClassIsNotValidation(t *testing.T) {
	r, _ := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}`,
		`{"schema":15,"event":"read","channel":1,"status":0,"count":1,"class":"e3_candidate"}`)))
	if !strings.Contains(r.Sessions[0].Intervals[0].Interpretation, "not_validated") {
		t.Fatal(r)
	}
}

func TestD2PowerReferenceLabelsPreserved(t *testing.T) {
	source := strings.NewReader(`{"schema":15,"ms":1,"event":"connect","channel":1,"status":0,"value":500000}
{"schema":15,"ms":2,"event":"write","channel":1,"status":0,"count":1,"class":"d2_power_ref_6660_tx"}
{"schema":15,"ms":3,"event":"read","channel":1,"status":0,"count":1,"class":"d2_power_6660_candidate"}
{"schema":15,"ms":4,"event":"disconnect","channel":1,"status":0}
`)
	a, e := rawAnalyze(source)
	if e != nil {
		t.Fatal(e)
	}
	if len(a.Sessions) != 1 || len(a.Sessions[0].Intervals) != 1 {
		t.Fatal(a)
	}
	x := a.Sessions[0].Intervals[0]
	if x.TX != "d2_power_ref_6660_tx" || x.RXClassCounts["d2_power_6660_candidate"] != 1 {
		t.Fatalf("%+v", x)
	}
}

func TestDev22NormalModeRXDoesNotBorrowFromB9FB(t *testing.T) {
	r, err := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"ms":100,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"ms":110,"event":"write","channel":1,"status":0,"count":1,"class":"a3_0203_shape_tx"}`,
		`{"schema":15,"ms":120,"event":"read","channel":1,"status":9,"count":0,"class":"other"}`,
		`{"schema":15,"ms":130,"event":"write","channel":1,"status":0,"count":1,"class":"b9fb_tx"}`,
		`{"schema":15,"ms":140,"event":"read","channel":1,"status":0,"count":13,"class":"d2_rx_fragment"}`)))
	if err != nil {
		t.Fatal(err)
	}
	it := r.Sessions[0].Intervals
	if it[0].TX != "a3_0203_shape_tx" || it[0].RXMessageCount != 0 || it[1].RXMessageCount != 13 {
		t.Fatal(it)
	}
}
func TestDev22E302CandidateClassRetained(t *testing.T) {
	r, err := rawAnalyze(strings.NewReader(fixture(
		`{"schema":15,"ms":100,"event":"connect","channel":1,"status":0,"value":500000}`,
		`{"schema":15,"ms":110,"event":"write","channel":1,"status":0,"count":1,"class":"a3_0203_shape_tx"}`,
		`{"schema":15,"ms":130,"event":"read","channel":1,"status":0,"count":1,"class":"e3_02_candidate"}`)))
	if err != nil {
		t.Fatal(err)
	}
	it := r.Sessions[0].Intervals[0]
	if it.RXClassCounts["e3_02_candidate"] != 1 || !strings.Contains(it.Interpretation, "not_validated") {
		t.Fatal(it)
	}
}
