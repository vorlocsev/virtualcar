package main

import (
	"strings"
	"testing"
)

func TestRealChannelSequence(t *testing.T) {
	text := `{"schema":15,"event":"connect","channel":11,"status":0,"value":500000}
{"schema":15,"event":"write","channel":11,"status":0,"count":1,"class":"a3_tx"}
{"schema":15,"event":"read","channel":11,"status":16,"count":0,"class":"other"}
{"schema":15,"event":"connect","channel":12,"status":0,"value":125000}
{"schema":15,"event":"write","channel":12,"status":0,"count":1,"class":"b9fb_tx"}
{"schema":15,"event":"read","channel":12,"status":0,"count":13,"class":"d2_rx_fragment"}
{"schema":15,"event":"disconnect","channel":11,"status":0}
{"schema":15,"event":"disconnect","channel":12,"status":0}
`
	r, e := summarize(strings.NewReader(text))
	if e != nil {
		t.Fatal(e)
	}
	if len(r.Sessions) != 2 || r.A3Writes != 1 || r.B9FBWrites != 1 || r.B9E0Writes != 0 || r.B9F0Writes != 0 {
		t.Fatalf("wrong counters: %+v", r)
	}
	if r.Sessions[0].Baud != 500000 || r.Sessions[1].Baud != 125000 || r.Sessions[0].ReadCallsAfterA3WithData != 0 {
		t.Fatalf("wrong channel attribution: %+v", r.Sessions)
	}
}
func TestReuseChannelIDCreatesNewGeneration(t *testing.T) {
	text := `{"schema":15,"event":"connect","channel":7,"status":0,"value":500000}
{"schema":15,"event":"disconnect","channel":7,"status":0}
{"schema":15,"event":"connect","channel":7,"status":0,"value":125000}
{"schema":15,"event":"write","channel":7,"status":0,"count":1,"class":"b9f0_tx"}
`
	r, e := summarize(strings.NewReader(text))
	if e != nil {
		t.Fatal(e)
	}
	if len(r.Sessions) != 2 || r.Sessions[0].Generation != 1 || r.Sessions[1].Generation != 2 || r.Sessions[0].B9F0Writes != 0 || r.Sessions[1].B9F0Writes != 1 {
		t.Fatalf("reuse attribution: %+v", r.Sessions)
	}
}
func TestTxErrorsNotSuccess(t *testing.T) {
	text := `{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}
{"schema":15,"event":"write","channel":1,"status":7,"count":0,"class":"a3_tx"}
{"schema":15,"event":"read","channel":1,"status":0,"count":1,"class":"e3_candidate"}
`
	r, e := summarize(strings.NewReader(text))
	if e != nil {
		t.Fatal(e)
	}
	if r.A3Writes != 0 || r.Sessions[0].TxErrors != 1 || r.Sessions[0].ReadCallsAfterA3WithData != 0 {
		t.Fatal(r)
	}
	if !r.UnknownRealCEMReply {
		t.Fatal("must never claim known reply")
	}
}
func TestDisconnectedWriteUnattributed(t *testing.T) {
	text := `{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}
{"schema":15,"event":"disconnect","channel":1,"status":0}
{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}
`
	r, e := summarize(strings.NewReader(text))
	if e != nil {
		t.Fatal(e)
	}
	if r.A3Writes != 0 || r.EventsWithoutLiveChannel != 1 {
		t.Fatal(r)
	}
}
func TestIgnoredAndTooManyFields(t *testing.T) {
	text := "not JSON\n" + `{"schema":15,"event":"connect","channel":1,"status":0,"value":500000,"secret":"DO_NOT_ECHO"}` + "\n"
	r, e := summarize(strings.NewReader(text))
	if e != nil {
		t.Fatal(e)
	}
	if r.Ignored != 1 || len(r.Sessions) != 1 {
		t.Fatal(r)
	}
	if strings.Contains(r.InterpretationLimit, "DO_NOT_ECHO") {
		t.Fatal("secret echoed")
	}
}
func TestConnectFailure(t *testing.T) {
	r, e := summarize(strings.NewReader(`{"schema":15,"event":"connect","channel":2,"status":7,"value":500000}`))
	if e != nil {
		t.Fatal(e)
	}
	if len(r.Sessions) != 0 {
		t.Fatal(r)
	}
}
func TestReadAfterA3OnlySameChannel(t *testing.T) {
	text := `{"schema":15,"event":"connect","channel":1,"status":0,"value":500000}
{"schema":15,"event":"connect","channel":2,"status":0,"value":125000}
{"schema":15,"event":"write","channel":1,"status":0,"count":1,"class":"a3_tx"}
{"schema":15,"event":"read","channel":2,"status":0,"count":1,"class":"e3_candidate"}
`
	r, e := summarize(strings.NewReader(text))
	if e != nil {
		t.Fatal(e)
	}
	if r.Sessions[0].ReadCallsAfterA3WithData != 0 || r.Sessions[1].ReadCallsWithData != 1 {
		t.Fatal(r.Sessions)
	}
}
func TestEmptyLog(t *testing.T) {
	r, e := summarize(strings.NewReader(""))
	if e != nil {
		t.Fatal(e)
	}
	if len(r.Sessions) != 0 {
		t.Fatal(r)
	}
}
