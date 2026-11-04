#!/usr/bin/env python3
"""Cross-check two allowlisted summaries of one synthetic native x86 run.

No raw CAN, PID, VIN, adapter secret, hardware auth, or client parser data.
One input describes the entire session; the other the first post-B9FB TX.
This cannot prove a genuine SectorV or XC90 CEM transaction.
"""
import argparse
import json
from pathlib import Path
import sys

MAX_BYTES = 256 * 1024
EXPECTED_SEQUENCE = (
    ("b9fb_tx", "0x50", "ch1"),
    ("b9fb_rx_complete", "0x50", "ch1"),
    ("a3_tx", "0x50", "ch1"),
    ("a3_tx", "0x40", "ch2"),
    ("a3_tx", "0x40", "ch1"),
    ("b9fb_tx", "0x40", "ch2"),
)


def verify(chronology, timing):
    if (not isinstance(chronology, dict) or not isinstance(timing, dict)
            or chronology.get("format") != "virtualcar-native-p2-channel-chronology-v3"
            or timing.get("format") != "virtualcar-native-d2-followup-gate-v1"
            or chronology.get("epochs_with_events") != 1
            or len(chronology.get("epochs", [])) != 1
            or chronology.get("parse_events")
            or timing.get("native_d2_followup_verified") is not True):
        raise ValueError("unexpected_native_evidence_scope")
    epoch = chronology["epochs"][0]
    item = epoch.get("first_completed_b9fb_to_later_a3")
    if (not isinstance(item, dict)
            or epoch.get("boundary") != "passthru_close"
            or epoch.get("outcome") != "multiple_candidates_no_unique_pairing"
            or epoch.get("b9fb_completed") != 1
            or epoch.get("b9fb_requested") != 2
            or epoch.get("a3_requested") != 3
            or epoch.get("b9fb_incomplete") != 1
            or epoch.get("channel_metadata_complete") is not True
            or item.get("status") != "same_channel_target_timed"
            or item.get("b9fb_completion_order") != 2
            or item.get("first_later_a3_order") != 3
            or item.get("same_channel_target_generation_verified") is not True):
        raise ValueError("inconsistent_first_later_a3_correlation")
    events = epoch.get("events", [])
    if (len(events) != len(EXPECTED_SEQUENCE)
            or tuple((e.get("kind"), e.get("target"), e.get("channel"))
                     for e in events) != EXPECTED_SEQUENCE
            or any(e.get("order") != i for i, e in enumerate(events, 1))
            or [e.get("baud_bps") for e in events]
               != [500000, 500000, 500000, 125000, 500000, 125000]):
        raise ValueError("unexpected_synthetic_native_event_order")
    if (timing.get("first_next_tx_service") != "d2_a3_target_known"
            or timing.get("first_next_tx_target") != "0x50"
            or timing.get("first_next_tx_same_target") is not True
            or timing.get("first_next_tx_same_channel") is not True
            or timing.get("b9fb_rx_frames") != 13
            or timing.get("other_unanswered_b9fb_attempts") != 1
            or timing.get("client_acceptance_verified") is not False
            or chronology.get("client_b9fb_acceptance_verified") is not False
            or chronology.get("a3_security_access_verified") is not False):
        raise ValueError("unexpected_first_native_tx_or_client_claim")
    measured = item.get("last_b9fb_rx_to_first_later_a3_ms")
    first = timing.get("last_rx_to_first_next_tx_ms")
    if (type(measured) not in (int, float)
            or type(first) not in (int, float)
            or measured < 0 or first < 0
            or abs(measured - first) > 0.001):
        raise ValueError("native_source_clock_disagreement")
    # Return a minimal fixed-only result. Actual timestamps live in the
    # two separate sanitized reports and must never be copied from raw logs.
    return {
        "format": "virtualcar-native-channel-correlation-gate-v1",
        "synthetic_native_same_channel_first_a3_verified": True,
        "native_first_a3_gap_ms": measured,
        "b9fb_rx_frames": 13,
        "channel_alias": "ch1",
        "a3_target": "0x50",
        "session_summary_still_ambiguous": True,
        "sectorv_client_acceptance_verified": False,
        "a3_security_access_verified": False,
        "xc90_v8_my2009_verified": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("chronology", type=Path)
    p.add_argument("timing", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        paths = [x.resolve() for x in (args.chronology, args.timing, args.output)]
        if len(set(paths)) != 3:
            raise ValueError("colliding_paths")
        for item in (args.chronology, args.timing):
            if item.stat().st_size > MAX_BYTES:
                raise ValueError("large_input")
        result = verify(
            json.loads(args.chronology.read_text(encoding="utf-8-sig")),
            json.loads(args.timing.read_text(encoding="utf-8-sig")))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, UnicodeError, ValueError, TypeError):
        print("Synthetic native channel correlation audit refused input/output",
              file=sys.stderr)
        return 2
    print("PASS: first native A3 channel/timing correlated; SectorV still unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
