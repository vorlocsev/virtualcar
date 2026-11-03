#!/usr/bin/env python3
"""Gate one synthetic native x86 B9FB -> A3 TX clock in the same PID/epoch.

The source must be a native Virtual Car J2534 text log captured by
verify_native_b9fb_a3.ps1. The result is an allowlisted aggregate, never
a reproduction of raw RX/TX bytes, VIN, PID, host or path.

Success proves the native DLL's *synthetic* followup timing is measurable.
It does not prove SectorV Hardware acceptance or a real A3/E3 exchange.
"""
import argparse
import json
from pathlib import Path
import sys

from audit_d2_followup_window import audit, MAX_BYTES

FORMAT = "virtualcar-native-d2-followup-gate-v1"


def verify(source):
    result = audit(source)
    if (result["completed_b9fb_count"] != 1
            or result["incomplete_b9fb_count"] != 0
            or len(result["observations"]) != 1
            or result["parse_errors"]):
        raise ValueError("incomplete_or_conflicted_native_d2")
    record = result["observations"][0]
    if (record["b9fb_target"] != "0x50"
            or record["b9fb_rx_frames"] != 13
            or record["b9fb_transport_complete"] is not True
            or record["followup_observation"] != "first_next_tx_observed"
            or record["first_next_tx_service"] != "d2_a3_target_known"
            or record["first_next_tx_target"] != "0x50"
            or record["first_next_tx_same_target"] is not True
            or record["first_next_tx_same_channel"] is not True
            or record["first_next_tx_same_baud"] is not True):
        raise ValueError("native_b9fb_to_a3_route_or_order_invalid")
    delta = record["last_rx_to_first_next_tx_ms"]
    duration = record["b9fb_tx_to_last_rx_ms"]
    if (type(delta) not in (int, float) or not 0 <= delta <= 60000
            or type(duration) not in (int, float) or not 0 <= duration <= 60000):
        raise ValueError("native_time_us_not_comparable")
    expected_500 = "first_tx_within_window" if delta <= 500 else "first_tx_later_than_window"
    expected_1000 = "first_tx_within_window" if delta <= 1000 else "first_tx_later_than_window"
    if record["within_500_ms"] != expected_500 or record["within_1000_ms"] != expected_1000:
        raise ValueError("inconsistent_native_time_window")
    if (record["client_accepted_b9fb"] is not False
            or record["ecu_identity_verified"] is not False
            or result["client_acceptance_verified"] is not False
            or result["same_run_with_sectorv_client_verified"] is not False
            or result["xc90_v8_my2009_verified"] is not False):
        raise ValueError("unsupported_vehicle_or_client_claim")

    # Do not create a single-run cross-log join: these are the native
    # DLL's own source-local event timestamps only.
    return {
        "format": FORMAT,
        "evidence_scope": "synthetic_native_x86_dll_only",
        "native_d2_followup_verified": True,
        "source_clock": result["source_clock"],
        "completed_b9fb_count": 1,
        "b9fb_rx_frames": 13,
        "b9fb_target": "0x50",
        "first_next_tx_service": record["first_next_tx_service"],
        "first_next_tx_target": record["first_next_tx_target"],
        "first_next_tx_same_channel": True,
        "first_next_tx_same_target": True,
        "b9fb_tx_to_last_rx_ms": duration,
        "last_rx_to_first_next_tx_ms": delta,
        "within_500_ms": expected_500,
        "within_1000_ms": expected_1000,
        "client_acceptance_verified": False,
        "a3_positive_reply_verified": False,
        "ecu_identity_verified": False,
        "same_run_with_sectorv_client_verified": False,
        "xc90_v8_my2009_verified": False,
        "limitations": [
            "Native source-local time-us only; not a PR30/SectorV client clock join.",
            "Finite timing is not proof of B9FB semantic acceptance or real E3.",
            "Only allowlisted CEM target and timing summary; no VIN, CAN, PID, host, or original paths.",
            "No timing threshold is asserted for real SectorV; synthetic CI scheduling can vary.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.log.resolve() == args.output.resolve():
            raise ValueError("same_source_and_output")
        if args.log.stat().st_size > MAX_BYTES:
            raise ValueError("source_size_exceeded")
        report = verify(args.log.read_text(encoding="utf-8-sig", errors="replace"))
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, sort_keys=True, indent=2)
            output.write("\n")
    except (OSError, ValueError, UnicodeError):
        print("Native followup evidence gate refused input or output",
              file=sys.stderr)
        return 2
    print("PASS: native synthetic 13-frame B9FB to A3 time-us verified; SectorV unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
