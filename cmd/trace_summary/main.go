package main

import (
	"bufio"
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
)

type Event struct {
	Schema    int    `json:"schema"`
	Ms        uint32 `json:"ms"`
	Event     string `json:"event"`
	Channel   uint32 `json:"channel"`
	Status    uint32 `json:"status"`
	Requested uint32 `json:"requested"`
	Count     uint32 `json:"count"`
	Class     string `json:"class"`
	CanID     string `json:"can_id"`
	Size      uint32 `json:"size"`
	Value     uint32 `json:"value"`
}
type Session struct {
	Channel                  uint32   `json:"channel"`
	Generation               int      `json:"generation"`
	Baud                     uint32   `json:"baud"`
	ConnectStatus            uint32   `json:"connect_status"`
	A3Writes                 int      `json:"a3_writes"`
	B9E0Writes               int      `json:"b9e0_writes"`
	B9F0Writes               int      `json:"b9f0_writes"`
	B9FBWrites               int      `json:"b9fb_writes"`
	ReadCalls                int      `json:"read_calls"`
	ReadCallsWithData        int      `json:"read_calls_with_data"`
	ReadCallsAfterA3WithData int      `json:"reads_after_a3_with_data"`
	ReadStatus16             int      `json:"reads_status_16_buffer_empty"`
	TxErrors                 int      `json:"tx_errors"`
	DisconnectSeen           bool     `json:"disconnect_seen"`
	Events                   []string `json:"ordered_events"`
}
type Report struct {
	Version                  string    `json:"version"`
	InterpretationLimit      string    `json:"interpretation_limit"`
	Lines                    int       `json:"lines"`
	Ignored                  int       `json:"ignored"`
	Sessions                 []Session `json:"sessions"`
	EventsWithoutLiveChannel int       `json:"events_without_live_channel"`
	LastWriteClass           string    `json:"last_write_class"`
	A3Writes                 int       `json:"a3_writes"`
	B9E0Writes               int       `json:"b9e0_writes"`
	B9F0Writes               int       `json:"b9f0_writes"`
	B9FBWrites               int       `json:"b9fb_writes"`
	UnknownRealCEMReply      bool      `json:"unknown_real_cem_reply"`
}

func summarize(r io.Reader) (Report, error) {
	out := Report{Version: "0.3.6.7-dev15", InterpretationLimit: "ChannelID is real J2534 call parameter; read_with_data is not ECU response validation; candidate echo does not prove authentication; events captured only if traced adapter was selected.", UnknownRealCEMReply: true, Sessions: []Session{}}
	gen := make(map[uint32]int)
	active := make(map[uint32]int)
	scanner := bufio.NewScanner(r)
	scanner.Buffer(make([]byte, 4096), 1024*1024)
	for scanner.Scan() {
		out.Lines++
		var e Event
		if err := json.Unmarshal(scanner.Bytes(), &e); err != nil || e.Schema != 15 || e.Event == "" {
			out.Ignored++
			continue
		}
		if e.Event == "connect" {
			if e.Status != 0 {
				continue
			}
			gen[e.Channel]++
			s := Session{Channel: e.Channel, Generation: gen[e.Channel], Baud: e.Value, Events: []string{"connect"}}
			out.Sessions = append(out.Sessions, s)
			active[e.Channel] = len(out.Sessions) - 1
			continue
		}
		if e.Event != "write" && e.Event != "read" && e.Event != "disconnect" {
			continue
		}
		idx, exists := active[e.Channel]
		if !exists {
			out.EventsWithoutLiveChannel++
			continue
		}
		s := &out.Sessions[idx]
		switch e.Event {
		case "write":
			if len(s.Events) < 200 {
				s.Events = append(s.Events, e.Class)
			}
			if e.Status != 0 {
				s.TxErrors++
			}
			if e.Status != 0 || e.Count == 0 {
				continue
			}
			out.LastWriteClass = e.Class
			switch e.Class {
			case "a3_tx":
				s.A3Writes++
				out.A3Writes++
			case "b9e0_tx":
				s.B9E0Writes++
				out.B9E0Writes++
			case "b9f0_tx":
				s.B9F0Writes++
				out.B9F0Writes++
			case "b9fb_tx":
				s.B9FBWrites++
				out.B9FBWrites++
			}
		case "read":
			s.ReadCalls++
			if e.Status == 16 {
				s.ReadStatus16++
			}
			if e.Count > 0 && e.Status == 0 {
				s.ReadCallsWithData++
				if s.A3Writes > 0 {
					s.ReadCallsAfterA3WithData++
				}
			}
			if len(s.Events) < 200 && (e.Count > 0 || (e.Status != 0 && e.Status != 16)) {
				s.Events = append(s.Events, "read:"+e.Class)
			}
		case "disconnect":
			s.DisconnectSeen = true
			if len(s.Events) < 200 {
				s.Events = append(s.Events, "disconnect")
			}
			delete(active, e.Channel)
		}
	}
	if err := scanner.Err(); err != nil {
		return out, err
	}
	// One-line summary sorts sessions by time of first connect, preserved in slice.
	return out, nil
}
func main() {
	in := flag.String("in", "", "Input VirtualCarTrace32 JSONL")
	out := flag.String("out", "j2534-summary.json", "Output sanitized summary")
	flag.Parse()
	if *in == "" {
		fmt.Fprintln(os.Stderr, "provide -in path")
		os.Exit(2)
	}
	f, err := os.Open(*in)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	defer f.Close()
	report, err := summarize(f)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	data = append(data, '\n')
	if err = os.WriteFile(*out, data, 0600); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Printf("Analysis complete: %d J2534 session(s). Share only the generated j2534-summary.json.\n", len(report.Sessions))
}
