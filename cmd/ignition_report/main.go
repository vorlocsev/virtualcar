package main

import (
	"bufio"
	"bytes"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"sort"
)

type Event struct {
	Schema     int     `json:"schema"`
	Event      string  `json:"event"`
	Status     uint32  `json:"status"`
	Channel    uint32  `json:"channel"`
	Value      uint32  `json:"value"`
	ProtocolID *uint32 `json:"protocol_id,omitempty"`
	IoctlID    *uint32 `json:"ioctl_id,omitempty"`
	VbattMV    *uint32 `json:"vbatt_mv,omitempty"`
}
type ConnectStats struct {
	ProtocolID uint32 `json:"protocol_id"`
	Protocol   string `json:"protocol"`
	Baud       uint32 `json:"baud"`
	Status     uint32 `json:"status"`
	Count      int    `json:"count"`
}
type IoctlStats struct {
	ID     uint32 `json:"id"`
	Name   string `json:"name"`
	Status uint32 `json:"status"`
	Count  int    `json:"count"`
}
type Report struct {
	Version                 string         `json:"version"`
	Scope                   string         `json:"scope"`
	Lines                   int            `json:"lines"`
	Ignored                 int            `json:"ignored"`
	ConnectProtocolKnown    int            `json:"connect_protocol_known"`
	ConnectProtocolMissing  int            `json:"connect_protocol_missing"`
	Connects                []ConnectStats `json:"connects"`
	Ioctls                  []IoctlStats   `json:"ioctls"`
	VBattReadAttempts       int            `json:"vbatt_read_attempts"`
	VBattSuccessfulValuesMV []uint32       `json:"vbatt_successful_values_mv"`
	IgnitionPosition        string         `json:"ignition_position"`
	InterpretationLimit     string         `json:"interpretation_limit"`
}

func protocolName(id uint32) string {
	switch id {
	case 1:
		return "J1850VPW"
	case 2:
		return "J1850PWM"
	case 3:
		return "ISO9141"
	case 4:
		return "ISO14230"
	case 5:
		return "CAN"
	case 6:
		return "ISO15765"
	case 0x8004:
		return "CAN_PS"
	case 0x8005:
		return "ISO15765_PS"
	default:
		return "unknown_or_extended"
	}
}
func ioctlName(id uint32) string {
	switch id {
	case 1:
		return "GET_CONFIG"
	case 2:
		return "SET_CONFIG"
	case 3:
		return "READ_VBATT"
	case 4:
		return "FIVE_BAUD_INIT"
	case 5:
		return "FAST_INIT"
	case 7:
		return "CLEAR_TX_BUFFER"
	case 8:
		return "CLEAR_RX_BUFFER"
	case 9:
		return "CLEAR_PERIODIC_MSGS"
	case 10:
		return "CLEAR_MSG_FILTERS"
	case 14:
		return "READ_PROG_VOLTAGE"
	default:
		return "other"
	}
}
func Analyze(src []byte) (Report, error) {
	r := Report{Version: "0.3.6.7-dev19", Scope: "J2534 call metadata only", IgnitionPosition: "unknown", InterpretationLimit: "READ_VBATT measures supply voltage, not ignition/key position. Ignition state is not available in this trace. A J1850PWM connect failure does not prove ignition is off. Actual ECU responses are not validated."}
	connects := map[[3]uint32]int{}
	ioctls := map[[2]uint32]int{}
	r.Connects = []ConnectStats{}
	r.Ioctls = []IoctlStats{}
	r.VBattSuccessfulValuesMV = []uint32{}
	s := bufio.NewScanner(bytes.NewReader(src))
	s.Buffer(make([]byte, 64*1024), 1024*1024)
	for s.Scan() {
		r.Lines++
		var e Event
		if err := json.Unmarshal(s.Bytes(), &e); err != nil {
			r.Ignored++
			continue
		}
		switch e.Event {
		case "connect":
			if e.ProtocolID == nil {
				r.ConnectProtocolMissing++
				continue
			}
			r.ConnectProtocolKnown++
			connects[[3]uint32{*e.ProtocolID, e.Value, e.Status}]++
		case "ioctl":
			if e.IoctlID == nil {
				continue
			}
			ioctls[[2]uint32{*e.IoctlID, e.Status}]++
			if *e.IoctlID == 3 {
				r.VBattReadAttempts++
				if e.Status == 0 && e.VbattMV != nil {
					r.VBattSuccessfulValuesMV = append(r.VBattSuccessfulValuesMV, *e.VbattMV)
				}
			}
		}
	}
	if err := s.Err(); err != nil {
		return r, err
	}
	for k, n := range connects {
		r.Connects = append(r.Connects, ConnectStats{k[0], protocolName(k[0]), k[1], k[2], n})
	}
	for k, n := range ioctls {
		r.Ioctls = append(r.Ioctls, IoctlStats{k[0], ioctlName(k[0]), k[1], n})
	}
	sort.Slice(r.Connects, func(i, j int) bool {
		a, b := r.Connects[i], r.Connects[j]
		if a.ProtocolID != b.ProtocolID {
			return a.ProtocolID < b.ProtocolID
		}
		if a.Baud != b.Baud {
			return a.Baud < b.Baud
		}
		return a.Status < b.Status
	})
	sort.Slice(r.Ioctls, func(i, j int) bool {
		a, b := r.Ioctls[i], r.Ioctls[j]
		if a.ID != b.ID {
			return a.ID < b.ID
		}
		return a.Status < b.Status
	})
	return r, nil
}
func main() {
	in := flag.String("in", "", "JSONL path")
	out := flag.String("out", "", "output JSON path")
	flag.Parse()
	if *in == "" || *out == "" {
		fmt.Fprintln(os.Stderr, "-in and -out required")
		os.Exit(2)
	}
	src, e := os.ReadFile(*in)
	if e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
	r, e := Analyze(src)
	if e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
	b, e := json.MarshalIndent(r, "", "  ")
	if e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
	if e = os.WriteFile(*out, append(b, '\n'), 0600); e != nil {
		fmt.Fprintln(os.Stderr, e)
		os.Exit(1)
	}
}
