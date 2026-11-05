#!/usr/bin/env python3
"""Verify one isolated native x86 synthetic B9FB -> A3 backend lifecycle.

This verifies DLL/J2534 delivery and lack of a fixture for A3. It does NOT
verify any real SectorV/VIDA client, genuine CEM identity or security access.
No raw CAN bytes or identifiers are exported.
"""
import argparse
import json
from pathlib import Path
import sys

from audit_backend_evidence import audit

EXPECTED = (
    # protocol, baud, route, status, reason, service, target, channel, RX
    ("CAN", 500000, "CEM", "delivered", "j2534_rx_only", "B9FB", "0x50", 1, 13),
    ("CAN", 500000, "CEM", "unsupported", "unimplemented_probe", "A3", "0x50", 1, 0),
    ("CAN", 125000, "CEM", "unsupported", "unimplemented_probe", "A3", "0x40", 2, 0),
    ("CAN", 500000, "CEM", "unsupported", "unsupported_bus", "A3", "0x40", 1, 0),
    ("CAN", 125000, "CEM", "no_fixture", "explicit_missing_profile", "B9FB", "0x40", 2, 0),
)
FIELDS = ("protocol", "baud_bps", "route", "status", "reason", "service",
          "target", "channel", "rx_dequeued")


def verify(lines):
    report = audit(lines)
    # One synthetic native session, exactly five request lifecycles.
    if report["summary"] != {
        "requests": 5, "sessions": 1, "invalid_lines": 0,
        "statuses": {"delivered": 1, "no_fixture": 1, "unsupported": 3},
        "request_origins": {"app_write": 5},
    }:
        raise ValueError("unexpected_native_b9fb_a3_summary")
    if len(report["transactions"]) != len(EXPECTED):
        raise ValueError("unexpected_native_transaction_count")
    for index, (record, expected) in enumerate(zip(report["transactions"], EXPECTED)):
        if tuple(record[k] for k in FIELDS) != expected:
            raise ValueError("native_transaction_mismatch")
        if (record["observed_routes"] != ["CEM"]
                or record["evidence_conflicts"]
                or record["protocol"] != "CAN"
                or record["id_format"] != "29bit"
                or record["can_id"] != "0x000FFFFE"
                or not record["terminal_seen"]
                or record["elapsed_ms"] is None
                or record["request_origin"] != "app_write"):
            raise ValueError("incomplete_native_evidence")
        if (record["rx_queued"] != expected[-1]
                or record["rx_dropped"] != 0
                or record["filter_dropped"] != 0):
            raise ValueError("incomplete_native_rx_delivery")
        # Any simulated RX after the confirmed B9FB is a hard failure.
        if index and record["rx_dequeued"]:
            raise ValueError("unverified_positive_a3_or_other_response")
    if report["identity_verified"] or report["client_acceptance_verified"]:
        raise ValueError("client_acceptance_claim_not_allowed")
    report["native_synthetic_b9fb_a3_verified"] = True
    report["evidence_scope"] = "single_native_x86_dll_no_client_no_physical_ecu"
    report["a3_positive_reply_verified"] = False
    report["xc90_v8_my2009_verified"] = False
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Isolated synthetic backend JSONL")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise ValueError("output_equals_source")
        if args.source.stat().st_size > 4 * 1024 * 1024:
            raise ValueError("source_too_large")
        with args.source.open(encoding="utf-8", errors="replace") as source:
            report = verify(source)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, sort_keys=True)
            output.write("\n")
    except (OSError, ValueError):
        print("Synthetic native B9FB-A3 evidence verification failed",
              file=sys.stderr)
        return 2
    print("PASS: native B9FB delivery to J2534; subsequent A3 deliberately unanswered")
    return 0


if __name__ == "__main__":
    sys.exit(main())
