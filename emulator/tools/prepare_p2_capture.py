#!/usr/bin/env python3
"""Prepare bounded, sanitized P2 evidence from one private native J2534 log.

Only the caller's local raw file is read. Three allowlisted JSON outputs
are written to a NEW directory; no raw log, CAN payload, VIN, PID, host,
device secret or original source path is included.
"""
import argparse
import json
from pathlib import Path
import sys

from audit_d2_followup_window import audit as audit_followup
from audit_native_p2_channel_chronology import audit as audit_chronology
from audit_native_b9f0_response import audit as audit_b9f0

MAX_INPUT_BYTES = 4 * 1024 * 1024
OUTPUT_FILES = ("channel-chronology.json", "b9fb-followup.json",
                "capture-summary.json")


def _cross_audit(chronology, followup):
    """Verify source-local transport counts before exporting related reports.

    A first-A3 correlation is only meaningful for a single native epoch
    with exactly one completed B9FB. Multi-epoch reports stay ambiguous
    even if they happen to have matching aggregate counts.
    """
    chrono_completed = sum(e["b9fb_completed"] for e in chronology["epochs"])
    next_completed = followup["completed_b9fb_count"]
    if (chrono_completed != next_completed
            or next_completed != len(followup["observations"])
            or any(o["b9fb_transport_complete"] is not True
                   for o in followup["observations"])):
        raise ValueError("independent_b9fb_transport_counts_disagree")

    status = "not_comparable"
    gap = None
    b9f0_status = "not_comparable"
    b9f0_gap = None
    if len(chronology["epochs"]) == 1 and chrono_completed == 1:
        epoch = chronology["epochs"][0]
        if not epoch["channel_metadata_complete"] or chronology["parse_events"] or followup["parse_errors"]:
            status = "source_context_incomplete"
            b9f0_status = "source_context_incomplete"
        else:
            candidate = epoch["first_completed_b9fb_to_later_a3"]
            first = followup["observations"][0]
            same_first_a3 = (
                first["followup_observation"] == "first_next_tx_observed"
                and first["first_next_tx_service"] == "d2_a3_target_known"
                and first["first_next_tx_same_channel"] is True
                and first["first_next_tx_same_target"] is True
                and first["first_next_tx_same_baud"] is True)
            timed = (candidate["status"] == "same_channel_target_timed"
                     and candidate["same_channel_target_generation_verified"] is True)
            if timed and not same_first_a3:
                raise ValueError("independent_b9fb_a3_correlation_disagrees")
            if same_first_a3 and not timed:
                # Followup examines only the next app TX, whereas the
                # chronology also checks CLEAR_RX_BUFFER and channel reuse.
                # An intervening native barrier makes this association
                # intentionally uncertain, not a failed/accepted ECU reply.
                if candidate["status"] not in (
                    "intervening_other_app_tx", "clear_rx_between_events",
                    "channel_reused_after_disconnect"):
                    raise ValueError("independent_b9fb_a3_correlation_disagrees")
                status = "native_barrier_blocks_direct_a3_pair"
            if timed:
                a = candidate["last_b9fb_rx_to_first_later_a3_ms"]
                b = first["last_rx_to_first_next_tx_ms"]
                if (type(a) not in (float, int) or type(b) not in (float, int)
                        or a < 0 or b < 0 or abs(a - b) > 0.001):
                    raise ValueError("independent_b9fb_a3_clocks_disagree")
                status = "first_a3_same_channel_target_clock_agrees"
                gap = b
            else:
                status = "no_verified_direct_first_a3_pair"

            # Cross-check the *first* later B9F0 read request independently
            # from A3. It must be the first app TX, not simply a B9F0
            # observed later in a different request window.
            f0 = epoch["first_completed_b9fb_to_later_b9f0"]
            same_first_b9f0 = (
                first["followup_observation"] == "first_next_tx_observed"
                and first["first_next_tx_service"] == "d2_b9f0"
                and first["first_next_tx_same_channel"] is True
                and first["first_next_tx_same_target"] is True
                and first["first_next_tx_same_baud"] is True)
            timed_f0 = (f0["status"] == "same_channel_target_timed"
                        and f0["same_channel_target_generation_verified"] is True)
            if timed_f0 and not same_first_b9f0:
                raise ValueError("independent_b9fb_b9f0_correlation_disagrees")
            if same_first_b9f0 and not timed_f0:
                if f0["status"] not in (
                    "clear_rx_between_events",
                    "channel_reused_after_disconnect",
                    "source_context_incomplete"):
                    raise ValueError("independent_b9fb_b9f0_correlation_disagrees")
                b9f0_status = "native_barrier_blocks_direct_b9f0_pair"
            elif timed_f0:
                a = f0["last_b9fb_rx_to_first_later_b9f0_ms"]
                b = first["last_rx_to_first_next_tx_ms"]
                if (type(a) not in (float, int) or type(b) not in (float, int)
                        or a < 0 or b < 0 or abs(a - b) > 0.001):
                    raise ValueError("independent_b9fb_b9f0_clocks_disagree")
                b9f0_status = "first_b9f0_same_channel_target_clock_agrees"
                b9f0_gap = b
            else:
                b9f0_status = "no_verified_direct_first_b9f0_pair"
    return {
        "transport_completion_count_agrees": True,
        "first_a3_cross_audit_status": status,
        "first_a3_gap_ms_when_cross_verified": gap,
        "first_b9f0_cross_audit_status": b9f0_status,
        "first_b9f0_gap_ms_when_cross_verified": b9f0_gap,
        "b9f0_response_verified": False,
        "client_acceptance_verified": False,
    }


def prepare(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError("source_size_exceeded")
    chronology = audit_chronology(source)
    followup = audit_followup(source)
    b9f0 = audit_b9f0(source)
    epochs = chronology["epochs"]
    if not epochs or not any(e["events"] for e in epochs):
        raise ValueError("no_native_p2_events")
    agreement = _cross_audit(chronology, followup)
    # A truncated log is still diagnostic evidence, just not evidence
    # of a completed capture. Do NOT silently upgrade EOF to PassThruClose.
    all_closed = all(e["boundary"] == "passthru_close" for e in epochs)
    native_context_complete = all(e["channel_metadata_complete"]
                                  for e in epochs)
    known_process = any(e["observed_process_label"]
                        == "sectorv_exe_in_native_log" for e in epochs)
    a3_count = sum(e["a3_requested"] for e in epochs)
    b9f0_count = sum(e["b9f0_requests_observed"] for e in epochs)
    b9fb_count = sum(e["b9fb_requested"] for e in epochs)
    completed = sum(e["b9fb_completed"] for e in epochs)
    summary = {
        "format": "virtualcar-p2-local-capture-summary-v1",
        "read_only": True,
        "evidence_scope": "one_local_native_j2534_text_file",
        "contains_raw_log": False,
        "contains_payload_data": False,
        "raw_source_copied": False,
        "native_epochs": len(epochs),
        "all_native_epochs_closed": all_closed,
        "native_tx_rx_context_complete": native_context_complete,
        "sectorv_process_label_observed_unverified": known_process,
        "a3_requests_observed": a3_count,
        "b9f0_requests_observed": b9f0_count,
        "b9f0_native_transport_audit": {
            "request_count": b9f0["request_count"],
            "status_counts": b9f0["status_counts"],
            "positive_echo_transport_observed": b9f0["any_positive_transport_observed"],
            "parser_error_counts": b9f0["parse_errors"],
            "client_acceptance_verified": False,
            "part_number_decoded": False,
        },
        "b9fb_requests_observed": b9fb_count,
        "b9fb_transport_completions_observed": completed,
        "cross_audit_consistency": agreement,
        "chronology_outcomes": dict(chronology["outcome_counts"]),
        "native_chronology_parse_errors": dict(chronology["parse_events"]),
        "native_followup_parse_errors": dict(followup["parse_errors"]),
        "last_b9fb_to_first_a3_client_acceptance_verified": False,
        "same_run_with_sectorv_client_verified": False,
        "xc90_v8_my2009_verified": False,
        "a3_security_access_verified": False,
        "b9f0_response_verified": False,
        "safe_to_infer_complete_client_session": False,
        "limitations": [
            "A log ending at EOF without PassThruClose is an incomplete capture.",
            "Same-channel TX/RX events do not establish B9FB semantic acceptance.",
            "B9F0 request order is audited separately from any matching B9F0 transport reply.",
            "A positive B9F0 echo and complete D2 framing do not verify part-number semantics, authentic ECU identity or client acceptance.",
            "A source process label is untrusted and is not executable attestation.",
            "Historical PR30/run188 reports cannot be merged with this log.",
            "Independent auditors must agree on positive B9FB completion count; A3 cross-check is restricted to one native epoch.",
            "No raw input, CAN payload, VIN, process ID, host or private path is exported.",
        ],
    }
    return {
        OUTPUT_FILES[0]: chronology,
        OUTPUT_FILES[1]: followup,
        OUTPUT_FILES[2]: summary,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="PRIVATE native SectorVVirtualCar.log")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New local directory for sanitized JSON only")
    args = parser.parse_args(argv)
    created = []
    made_directory = False
    try:
        if args.source.resolve() == args.output_dir.resolve():
            raise ValueError("same_path")
        if args.source.stat().st_size > MAX_INPUT_BYTES:
            raise ValueError("source_too_large")
        data = prepare(args.source.read_text(encoding="utf-8-sig",
                                             errors="replace"))
        # Compute and serialize before creating any output. Fail closed
        # on malformed input or unsupported event records.
        payloads = {
            name: json.dumps(data[name], ensure_ascii=False, sort_keys=True,
                             indent=2) + "\n" for name in OUTPUT_FILES
        }
        args.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
        made_directory = True
        for name in OUTPUT_FILES:
            path = args.output_dir / name
            with path.open("x", encoding="utf-8") as stream:
                created.append(path)
                stream.write(payloads[name])
    except (OSError, UnicodeError, ValueError, TypeError):
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        if made_directory:
            try:
                args.output_dir.rmdir()
            except OSError:
                pass
        print("P2 capture preparation refused input/output; private source withheld",
              file=sys.stderr)
        return 2
    print("PASS: three sanitized P2 evidence summaries prepared locally")
    return 0


if __name__ == "__main__":
    sys.exit(main())
