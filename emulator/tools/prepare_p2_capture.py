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

MAX_INPUT_BYTES = 4 * 1024 * 1024
OUTPUT_FILES = ("channel-chronology.json", "b9fb-followup.json",
                "capture-summary.json")


def prepare(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_INPUT_BYTES:
        raise ValueError("source_size_exceeded")
    chronology = audit_chronology(source)
    followup = audit_followup(source)
    epochs = chronology["epochs"]
    if not epochs or not any(e["events"] for e in epochs):
        raise ValueError("no_native_p2_events")
    # A truncated log is still diagnostic evidence, just not evidence
    # of a completed capture. Do NOT silently upgrade EOF to PassThruClose.
    all_closed = all(e["boundary"] == "passthru_close" for e in epochs)
    native_context_complete = all(e["channel_metadata_complete"]
                                  for e in epochs)
    known_process = any(e["observed_process_label"]
                        == "sectorv_exe_in_native_log" for e in epochs)
    a3_count = sum(e["a3_requested"] for e in epochs)
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
        "b9fb_requests_observed": b9fb_count,
        "b9fb_transport_completions_observed": completed,
        "chronology_outcomes": dict(chronology["outcome_counts"]),
        "native_chronology_parse_errors": dict(chronology["parse_events"]),
        "native_followup_parse_errors": dict(followup["parse_errors"]),
        "last_b9fb_to_first_a3_client_acceptance_verified": False,
        "same_run_with_sectorv_client_verified": False,
        "xc90_v8_my2009_verified": False,
        "a3_security_access_verified": False,
        "safe_to_infer_complete_client_session": False,
        "limitations": [
            "A log ending at EOF without PassThruClose is an incomplete capture.",
            "Same-channel TX/RX events do not establish B9FB semantic acceptance.",
            "A source process label is untrusted and is not executable attestation.",
            "Historical PR30/run188 reports cannot be merged with this log.",
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
