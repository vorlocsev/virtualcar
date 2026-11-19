#!/usr/bin/env python3
"""Read-only, privacy-preserving audit of bounded native + SectorV Hardware logs.

No raw line, timestamp, vehicle ID, PID, path, CAN data or key is ever exported.
Native and client streams are NOT correlated into a verified same-session pair.
"""
from collections import Counter
from pathlib import Path
import argparse
import json
import re

SCHEMA = "b3a314-sectorv-hardware-observation-v1"
MAX_ROWS = 100000
MAX_LINE = 2048
NATIVE_PREFIX = re.compile(r"^\[PID=[0-9A-Fa-f]{8} [A-Za-z0-9_.-]{1,48}\] ")
CLIENT_PREFIX = re.compile(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3} [+-]\d\d:\d\d \[client\] ")
NATIVE_HARDWARE_MARKERS = {
    "A3_TX_OBSERVED": "P2_HW_TX_A3_OBSERVED",
    "E0_TX_AFTER_A3_UNVERIFIED": "P2_HW_TX_E0_AFTER_A3_UNVERIFIED",
    "F0_TX_AFTER_E0_UNVERIFIED": "P2_HW_TX_F0_AFTER_E0_UNVERIFIED",
    "INVALID_SHAPE": "P2_HW_TX_INVALID_SHAPE",
    "WRONG_BUS": "P2_HW_TX_WRONG_BUS",
    "OUT_OF_ORDER": "P2_HW_TX_OUT_OF_ORDER",
}
NATIVE_UNIMPLEMENTED = "P2 D2 CEM A3/A6: no verified response implementation"
NATIVE_BUS_MISMATCH = "P2 D2 CEM A3/A6 strict bus mismatch: no response"
NATIVE_B9FB = "P2 D2 read-only recorded frames staged CB 50 B9 FB"
CLIENT_VIN = re.compile(
    r"^P2 VIN RX v3 comm=0x(40|50): result=(received|no-reply|partial), "
    r"observed=(\d+), ignored=(\d+), matched=(\d+), elapsedMs=(\d+)\.$")
CLIENT_HW = re.compile(
    r"^P2 hardware-session RX v3 comm=0x(40|50): result=(received|no-reply|partial), "
    r"observed=(\d+), ignored=(\d+), matched=(\d+), elapsedMs=(\d+)\.$")
HW_FAILED = "P2 automatic identification failed at Hardware:"


def _guarded_lines(lines):
    for index, line in enumerate(lines):
        if index >= MAX_ROWS:
            raise ValueError("maximum_log_rows_exceeded")
        if len(line) > MAX_LINE:
            # Never parse oversized evidence or echo its contents.
            yield None
        else:
            yield line.strip()


def _client_event(text, pattern):
    m = pattern.fullmatch(text)
    if not m:
        return None
    route, result, observed, ignored, matched, elapsed = m.groups()
    values = tuple(map(int, (observed, ignored, matched, elapsed)))
    if any(v > 1000000 for v in values):
        return None
    return route, result, values


def analyze(native_lines, client_lines):
    """Only classification counts. Never verifies an ECU reply or VIN identity."""
    native = Counter()
    malformed_native = 0
    for line in _guarded_lines(native_lines):
        if line is None:
            malformed_native += 1
            continue
        m = NATIVE_PREFIX.match(line)
        if m is None:
            # Native records without a verified logger prefix cannot be ascribed.
            continue
        event = line[m.end():]
        for kind, marker in NATIVE_HARDWARE_MARKERS.items():
            if event == marker:
                native[kind] += 1
                break
        else:
            if event == NATIVE_UNIMPLEMENTED:
                native["A3_A6_UNIMPLEMENTED"] += 1
            elif event == NATIVE_BUS_MISMATCH:
                native["A3_A6_BUS_MISMATCH"] += 1
            elif event == NATIVE_B9FB:
                native["B9FB_50_STAGED"] += 1
            elif event.startswith("P2_HW_TX_"):
                malformed_native += 1
    client = Counter()
    malformed_client = 0
    state = "initial"
    ordered_vin_hw_failure = 0
    for line in _guarded_lines(client_lines):
        if line is None:
            malformed_client += 1
            continue
        m = CLIENT_PREFIX.match(line)
        if m is None:
            continue
        event = line[m.end():]
        vin = _client_event(event, CLIENT_VIN)
        if vin is not None:
            route, result, (observed, _ignored, matched, _elapsed) = vin
            client[f"VIN_{route}_{result.replace('-', '_')}"] += 1
            if route == "50" and result == "received" and matched > 0 and matched <= observed:
                state = "vin50_rx_unverified"
            continue
        hw = _client_event(event, CLIENT_HW)
        if hw is not None:
            route, result, (observed, _ignored, matched, elapsed) = hw
            client[f"HW_{route}_{result.replace('-', '_')}"] += 1
            if result == "no-reply" and observed == 0 and matched == 0 and elapsed > 0:
                client[f"HW_{route}_timeout_observed"] += 1
            if route == "50" and result == "no-reply" and state == "vin50_rx_unverified":
                state = "vin50_then_hw50_no_reply"
            continue
        if event.startswith(HW_FAILED):
            client["HW_CLIENT_FAILURE"] += 1
            if state == "vin50_then_hw50_no_reply":
                ordered_vin_hw_failure += 1
            state = "initial"
    return {
        "schema_version": SCHEMA,
        "scope": "provided_bounded_text_windows_only",
        "native_event_counts": {k: native[k] for k in (
            *NATIVE_HARDWARE_MARKERS.keys(), "A3_A6_UNIMPLEMENTED",
            "A3_A6_BUS_MISMATCH", "B9FB_50_STAGED")},
        "client_event_counts": {k: client[k] for k in (
            "VIN_40_received", "VIN_40_no_reply", "VIN_50_received",
            "VIN_50_no_reply", "HW_40_received", "HW_40_partial",
            "HW_40_no_reply", "HW_50_received", "HW_50_partial",
            "HW_50_no_reply", "HW_40_timeout_observed",
            "HW_50_timeout_observed", "HW_CLIENT_FAILURE")},
        "client_ordered_vin50_rx_then_hw50_no_reply_then_hardware_failure": ordered_vin_hw_failure,
        "malformed_or_unknown_native_hardware_markers": malformed_native,
        "oversized_client_rows_ignored": malformed_client,
        "positive_hardware_session_verified": False,
        "vehicle_identity_verified": False,
        "native_and_client_same_session_attested": False,
        "notes": [
            "A staged B9FB or matching VIN RX is a transport observation, not decoded VIN acceptance.",
            "A Hardware TX marker is not an ECU response or accepted session.",
            "Hardware no-reply records are client observations; no authentic CEM data is inferred.",
            "No PID, VIN, paths, full timestamps, ECU key or CAN payload is exported.",
            "Input log windows may contain different attempts; cross-log pairing is NOT asserted.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Private read-only SectorV Hardware log classifier")
    p.add_argument("--native", required=True, help="Bounded native log; path never exported")
    p.add_argument("--client", required=True, help="Bounded SectorV log; path never exported")
    args = p.parse_args(argv)
    try:
        # Read only, refuse files larger than the maximum possible meaningful text.
        files = (Path(args.native), Path(args.client))
        if any(not q.is_file() or q.stat().st_size > MAX_ROWS * MAX_LINE for q in files):
            raise ValueError("invalid_or_excessive_input")
        with files[0].open("r", encoding="utf-8-sig", errors="replace") as nf:
            with files[1].open("r", encoding="utf-8-sig", errors="replace") as cf:
                result = analyze(nf, cf)
    except (OSError, ValueError):
        p.exit(2, "ERROR: invalid_or_unreadable_bounded_input\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
