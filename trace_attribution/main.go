package main

import (
	"bufio"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"
)

const version = "0.3.6.7-dev26"

// The tracer never logs payload bytes. These fields are the only ones read.
type Event struct {
	Schema    int    `json:"schema"`
	Ms        uint32 `json:"ms"`
	Event     string `json:"event"`
	Channel   uint32 `json:"channel"`
	Status    uint32 `json:"status"`
	Requested uint32 `json:"requested"`
	Count     uint32 `json:"count"`
	Class     string `json:"class"`
	Value     uint32 `json:"value"`
}

type Interval struct {
	TX                      string         `json:"tx"`
	TXOk                    bool           `json:"tx_ok"`
	TXCount                 uint32         `json:"tx_count"`
	MultiTXAmbiguous        bool           `json:"multi_tx_ambiguous"`
	RXReadCalls             int            `json:"rx_read_calls_until_next_write"`
	RXCallsWithData         int            `json:"rx_calls_with_data_until_next_write"`
	RXMessageCount          uint64         `json:"rx_messages_until_next_write"`
	RXClassCounts           map[string]int `json:"rx_class_counts,omitempty"`
	RXStatusCounts          map[string]int `json:"rx_status_counts,omitempty"`
	RXMultiMessageAmbiguous bool           `json:"rx_multi_message_ambiguous"`
	TimeToFirstDataMs       *uint32        `json:"ms_to_first_data,omitempty"`
	EndedBy                 string         `json:"ended_by"`
	Interpretation          string         `json:"interpretation"`
	writeMs                 uint32
}

type Session struct {
	Channel             uint32     `json:"channel"`
	Generation          int        `json:"generation"`
	Baud                uint32     `json:"baud"`
	ConnectOK           bool       `json:"connect_ok"`
	DisconnectSeen      bool       `json:"disconnect_seen"`
	SupersededByConnect bool       `json:"superseded_by_connect"`
	ReadsBeforeAnyWrite int        `json:"reads_before_any_write"`
	DataBeforeAnyWrite  int        `json:"data_reads_before_any_write"`
	Intervals           []Interval `json:"intervals"`
}

type RawReport struct {
	Version             string         `json:"version"`
	InputType           string         `json:"input_type"`
	SafetyNote          string         `json:"safety_note"`
	InterpretationLimit string         `json:"interpretation_limit"`
	Lines               int            `json:"lines"`
	Ignored             int            `json:"ignored"`
	UnattributedCalls   int            `json:"unattributed_calls"`
	Sessions            []Session      `json:"sessions"`
	Totals              map[string]int `json:"totals"`
}

func cleanClass(v string) string {
	switch v {
	case "a3_tx", "a3_0203_shape_tx", "e3_02_candidate", "b9e0_tx", "b9f0_tx", "b9fb_tx", "b9fc_tx", "e3_candidate", "f9e0_candidate", "f9f0_candidate", "d2_rx_fragment", "d2_power_ref_6660_tx", "d2_power_6660_candidate", "d2_power_ref_6660_possible_tx", "d2_a6_marker_tx", "d2_unresolved_tx":
		return v
	default:
		return "other"
	}
}
func finish(i *Interval, why string) {
	i.EndedBy = why
	switch {
	case !i.TXOk:
		i.Interpretation = "write_failed_or_count_zero"
	case i.RXCallsWithData == 0:
		i.Interpretation = "no_successful_read_with_data_in_write_interval"
	default:
		i.Interpretation = "rx_data_seen_in_write_interval_not_validated_as_ecu_reply"
	}
}
func rawAnalyze(r io.Reader) (RawReport, error) {
	out := RawReport{Version: version, InputType: "schema15_raw_jsonl", SafetyNote: "Only sanitized numeric statuses and message categories. No CAN payload, VIN, tokens, or paths.", InterpretationLimit: "Each interval starts at one PassThruWriteMsgs completion and ends at next write/disconnect. RX after TX is temporal association, NOT verified response. Proxy records only first recognized class per read batch; multi-message batches ambiguous. Concurrent calls may interleave.", Sessions: []Session{}, Totals: map[string]int{}}
	gen := map[uint32]int{}
	active := map[uint32]int{}
	current := map[uint32]int{}
	sc := bufio.NewScanner(r)
	sc.Buffer(make([]byte, 4096), 1024*1024)
	for sc.Scan() {
		out.Lines++
		var e Event
		if err := json.Unmarshal(sc.Bytes(), &e); err != nil || e.Schema != 15 || e.Event == "" {
			out.Ignored++
			continue
		}
		if e.Event == "connect" {
			if e.Status != 0 {
				out.Totals["connect_failed"]++
				continue
			}
			if old, ok := active[e.Channel]; ok {
				s := &out.Sessions[old]
				s.SupersededByConnect = true
				if k, exists := current[e.Channel]; exists && k >= 0 {
					finish(&s.Intervals[k], "new_connect_same_channel")
				}
			}
			gen[e.Channel]++
			out.Sessions = append(out.Sessions, Session{Channel: e.Channel, Generation: gen[e.Channel], Baud: e.Value, ConnectOK: true, Intervals: []Interval{}})
			active[e.Channel] = len(out.Sessions) - 1
			current[e.Channel] = -1
			out.Totals["connect_ok"]++
			continue
		}
		if e.Event != "read" && e.Event != "write" && e.Event != "disconnect" {
			continue
		}
		j, ok := active[e.Channel]
		if !ok {
			out.UnattributedCalls++
			continue
		}
		s := &out.Sessions[j]
		switch e.Event {
		case "write":
			if k := current[e.Channel]; k >= 0 {
				finish(&s.Intervals[k], "next_write")
			}
			label := cleanClass(e.Class)
			success := e.Status == 0 && e.Count > 0
			s.Intervals = append(s.Intervals, Interval{TX: label, TXOk: success, TXCount: e.Count, MultiTXAmbiguous: e.Count > 1 || e.Requested > 1, RXClassCounts: map[string]int{}, RXStatusCounts: map[string]int{}, writeMs: e.Ms, EndedBy: "open", Interpretation: "incomplete_log"})
			current[e.Channel] = len(s.Intervals) - 1
			out.Totals["tx_"+label]++
			if !success {
				out.Totals["tx_failed_or_empty"]++
			}
		case "read":
			k := current[e.Channel]
			if k < 0 {
				s.ReadsBeforeAnyWrite++
				if e.Status == 0 && e.Count > 0 {
					s.DataBeforeAnyWrite++
				}
				continue
			}
			c := &s.Intervals[k]
			c.RXReadCalls++
			st := fmt.Sprint(e.Status)
			c.RXStatusCounts[st]++
			if e.Status == 0 && e.Count > 0 {
				c.RXCallsWithData++
				c.RXMessageCount += uint64(e.Count)
				if e.Count > 1 {
					c.RXMultiMessageAmbiguous = true
				}
				c.RXClassCounts[cleanClass(e.Class)]++
				if c.TimeToFirstDataMs == nil && c.writeMs != 0 && e.Ms != 0 {
					delta := e.Ms - c.writeMs // uint32 modulo, safe across GetTickCount wrap
					c.TimeToFirstDataMs = &delta
				}
			}
		case "disconnect":
			if e.Status == 0 {
				s.DisconnectSeen = true
				if k := current[e.Channel]; k >= 0 {
					finish(&s.Intervals[k], "disconnect")
				}
				delete(active, e.Channel)
				delete(current, e.Channel)
			} else {
				out.Totals["disconnect_failed"]++
			}
		}
	}
	if err := sc.Err(); err != nil {
		return out, err
	}
	for channel, j := range active {
		k := current[channel]
		if k >= 0 {
			finish(&out.Sessions[j].Intervals[k], "end_of_log")
		}
	}
	return out, nil
}

type LegacySession struct {
	Channel              uint32   `json:"channel"`
	Generation           int      `json:"generation"`
	Baud                 uint32   `json:"baud"`
	ReadCallsWithData    int      `json:"read_calls_with_data"`
	ReadsAfterA3WithData int      `json:"reads_after_a3_with_data"`
	Events               []string `json:"ordered_events"`
}
type LegacyInput struct {
	Version  string          `json:"version"`
	Sessions []LegacySession `json:"sessions"`
}
type LegacyTX struct {
	TX                               string         `json:"tx"`
	CandidateRXEventsBeforeNextWrite map[string]int `json:"candidate_rx_events_before_next_write"`
}
type LegacySessionOutput struct {
	Channel                     uint32     `json:"channel"`
	Generation                  int        `json:"generation"`
	Baud                        uint32     `json:"baud"`
	OldReadsAfterA3WithData     int        `json:"old_reads_after_a3_with_data"`
	WholeSessionDataReads       int        `json:"whole_session_data_reads"`
	OrderedEventsMayBeTruncated bool       `json:"ordered_events_may_be_truncated"`
	TXWindows                   []LegacyTX `json:"tx_windows"`
}
type LegacyReport struct {
	Version             string                `json:"version"`
	InputType           string                `json:"input_type"`
	InterpretationLimit string                `json:"interpretation_limit"`
	Sessions            []LegacySessionOutput `json:"sessions"`
	Warning             string                `json:"warning"`
}

func legacyAnalyze(r io.Reader) (LegacyReport, error) {
	var d LegacyInput
	if err := json.NewDecoder(r).Decode(&d); err != nil {
		return LegacyReport{}, err
	}
	if !strings.HasSuffix(d.Version, "dev15") || d.Sessions == nil {
		return LegacyReport{}, errors.New("expected dev15 j2534-summary.json")
	}
	out := LegacyReport{Version: version, InputType: "reconstructed_from_dev15_summary", InterpretationLimit: "Legacy ordered_events omits ordinary empty reads and limits events to 200. read:other has no recorded status/count. Counts and timing cannot be reconstructed per request from this JSON. Only candidate RX event positions are shown.", Warning: "A3-following data is not A3 response; use raw schema15 trace to assign successful RX calls to write intervals.", Sessions: []LegacySessionOutput{}}
	for _, s := range d.Sessions {
		t := LegacySessionOutput{Channel: s.Channel, Generation: s.Generation, Baud: s.Baud, OldReadsAfterA3WithData: s.ReadsAfterA3WithData, WholeSessionDataReads: s.ReadCallsWithData, OrderedEventsMayBeTruncated: len(s.Events) >= 200, TXWindows: []LegacyTX{}}
		for _, name := range s.Events {
			switch name {
			case "a3_tx", "a3_0203_shape_tx", "e3_02_candidate", "b9e0_tx", "b9f0_tx", "b9fb_tx", "b9fc_tx", "other":
				t.TXWindows = append(t.TXWindows, LegacyTX{TX: name, CandidateRXEventsBeforeNextWrite: map[string]int{}})
			default:
				if strings.HasPrefix(name, "read:") && len(t.TXWindows) > 0 {
					label := strings.TrimPrefix(name, "read:")
					if label != "other" {
						t.TXWindows[len(t.TXWindows)-1].CandidateRXEventsBeforeNextWrite[cleanClass(label)]++
					}
				}
			}
		}
		out.Sessions = append(out.Sessions, t)
	}
	return out, nil
}
func writeJSON(file string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(file, append(b, '\n'), 0600)
}
func main() {
	in := flag.String("in", "", "raw dev15 schema15 JSONL or dev15 j2534-summary.json")
	out := flag.String("out", "j2534-attribution.json", "output filename")
	legacy := flag.Bool("legacy", false, "read existing dev15 summary instead of raw trace")
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
	if *legacy {
		report, e := legacyAnalyze(f)
		if e != nil {
			fmt.Fprintln(os.Stderr, e)
			os.Exit(1)
		}
		err = writeJSON(*out, report)
	} else {
		report, e := rawAnalyze(f)
		if e != nil {
			fmt.Fprintln(os.Stderr, e)
			os.Exit(1)
		}
		err = writeJSON(*out, report)
	}
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fmt.Println("Attribution complete. Share only the generated JSON output, not raw logs or tokens.")
}
