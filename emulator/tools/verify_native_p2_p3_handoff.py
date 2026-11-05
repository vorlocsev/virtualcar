#!/usr/bin/env python3
"""Fail-closed gate for ONE native x86 J2534 synthetic B9FB/B9F0/P3 run.

This program reads a private native log locally, but writes only an
allowlisted pass/fail manifest. Never export the raw log or vehicle strings.
"""
import argparse
import json
from pathlib import Path
import sys

from prepare_p2_capture import prepare

MAX_BYTES = 4 * 1024 * 1024
FORMAT = "virtualcar-native-p2-p3-single-process-handoff-v1"


def verify(source):
    reports = prepare(source)
    summary = reports["capture-summary.json"]
    cross = summary["cross_audit_consistency"]
    f0 = summary["b9f0_native_transport_audit"]
    if (summary["native_epochs"] != 1
            or summary["all_native_epochs_closed"] is not True
            or summary["native_tx_rx_context_complete"] is not True):
        raise ValueError("native_process_epoch_incomplete")
    if (summary["b9fb_requests_observed"] != 1
            or summary["b9fb_transport_completions_observed"] != 1
            or summary["b9f0_requests_observed"] != 1
            or summary["a3_requests_observed"] != 0):
        raise ValueError("unexpected_b9fb_b9f0_request_sequence")
    if (cross["transport_completion_count_agrees"] is not True
            or cross["first_b9f0_cross_audit_status"]
            != "first_b9f0_same_channel_target_clock_agrees"
            or type(cross["first_b9f0_gap_ms_when_cross_verified"])
            not in (int, float)):
        raise ValueError("independent_b9fb_to_b9f0_gap_not_verified")
    if (f0["request_count"] != 1
            or f0["status_counts"] != {"positive_transport_complete": 1}
            or f0["post_positive_first_next_tx_service_counts"]
            != {"p3_read_data_by_identifier": 1}
            or f0["post_positive_first_next_tx_observed_count"] != 1
            or f0["post_positive_first_p3_response_status_counts"]
            != {"positive_transport_complete": 1}
            or f0["post_positive_first_p3_positive_transport_count"] != 1):
        raise ValueError("native_b9f0_p3_transport_chain_incomplete")
    if (f0["parser_error_counts"] or summary["native_followup_parse_errors"]
            or summary["native_chronology_parse_errors"]):
        raise ValueError("native_source_context_ambiguous")
    if (summary["xc90_v8_my2009_verified"]
            or summary["same_run_with_sectorv_client_verified"]
            or summary["safe_to_infer_complete_client_session"]
            or summary["b9f0_response_verified"]
            or f0["client_acceptance_verified"]
            or f0["ecu_enumeration_verified"]
            or f0["part_number_decoded"]):
        raise ValueError("fabricated_client_or_identity_verdict")
    # The derived public gate is intentionally much smaller than the three
    # sanitizer reports. No timing, VIN, DID, PID, host, CAN bytes or path.
    return {
        "format": FORMAT,
        "read_only": True,
        "evidence_scope": "one_synthetic_native_x86_dll_process",
        "single_closed_native_epoch_verified": True,
        "b9fb_positive_transport_verified": True,
        "direct_b9fb_to_b9f0_request_verified": True,
        "b9f0_positive_transport_verified": True,
        "first_p3_did_positive_transport_verified": True,
        "client_acceptance_verified": False,
        "ecu_inventory_verified": False,
        "real_xc90_v8_my2009_verified": False,
        "physical_j2534_verified": False,
        "contains_payload_data": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log", type=Path, help="Private one-run native J2534 log")
    parser.add_argument("--output", type=Path, required=True,
                        help="New, never-overwritten sanitized result JSON")
    args = parser.parse_args(argv)
    try:
        if args.log.resolve() == args.output.resolve():
            raise ValueError("source_output_overlap")
        if args.log.stat().st_size > MAX_BYTES:
            raise ValueError("source_too_large")
        report = verify(args.log.read_text(encoding="utf-8-sig", errors="replace"))
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, sort_keys=True, indent=2)
            handle.write("\n")
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        print("Native P2/P3 gate failed; private source withheld", file=sys.stderr)
        return 2
    print("PASS: synthetic x86 P2/P3 J2534 chain; client acceptance NOT tested")
    return 0


if __name__ == "__main__":
    sys.exit(main())
