package main

import "testing"

func TestLegacyNoProtocolNotAssumed(t *testing.T) {
	r, e := Analyze([]byte(`{"event":"connect","status":3,"value":500000}` + "\n"))
	if e != nil || r.ConnectProtocolMissing != 1 || len(r.Connects) != 0 || r.IgnitionPosition != "unknown" {
		t.Fatalf("%+v %v", r, e)
	}
}
func TestJ1850PWMError(t *testing.T) {
	r, _ := Analyze([]byte(`{"event":"connect","protocol_id":2,"status":3,"value":41600}` + "\n"))
	if len(r.Connects) != 1 || r.Connects[0].Protocol != "J1850PWM" || r.Connects[0].Status != 3 {
		t.Fatal(r)
	}
}
func TestCANErrorDistinct(t *testing.T) {
	r, _ := Analyze([]byte(`{"event":"connect","protocol_id":5,"status":3,"value":500000}` + "\n"))
	if r.Connects[0].Protocol != "CAN" {
		t.Fatal(r)
	}
}
func TestReadVBatt(t *testing.T) {
	r, _ := Analyze([]byte(`{"event":"ioctl","ioctl_id":3,"status":0,"vbatt_mv":12450}` + "\n"))
	if r.VBattReadAttempts != 1 || r.VBattSuccessfulValuesMV[0] != 12450 || r.IgnitionPosition != "unknown" {
		t.Fatal(r)
	}
}
func TestFailedVBattDoesNotReadVoltage(t *testing.T) {
	r, _ := Analyze([]byte(`{"event":"ioctl","ioctl_id":3,"status":3}` + "\n"))
	if r.VBattReadAttempts != 1 || len(r.VBattSuccessfulValuesMV) != 0 {
		t.Fatal(r)
	}
}
func TestNoSecretOutput(t *testing.T) {
	r, _ := Analyze([]byte(`{"event":"connect","protocol_id":2,"status":3,"value":41600,"vin":"SENSITIVEVIN","token":"SECRET"}` + "\n"))
	if r.Lines != 1 || r.IgnitionPosition != "unknown" {
		t.Fatal(r)
	}
}
func TestIgnoreBadLine(t *testing.T) {
	r, _ := Analyze([]byte("not_json\n"))
	if r.Ignored != 1 {
		t.Fatal(r)
	}
}
func TestMultipleGroups(t *testing.T) {
	r, _ := Analyze([]byte(`{"event":"connect","protocol_id":5,"status":0,"value":500000}` + "\n" + `{"event":"connect","protocol_id":2,"status":3,"value":500000}` + "\n"))
	if len(r.Connects) != 2 || r.Connects[0].ProtocolID != 2 {
		t.Fatal(r)
	}
}
