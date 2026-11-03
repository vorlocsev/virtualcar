#!/usr/bin/env python3
"""Conservative chronology audit of prior sanitized SectorV report JSON.

Accepts legacy d2-sectorv-report.json or d2-sectorv-latest*.json
summaries. A report without original per-event time or TX channel ID is
never treated as proof of a linked B9FB-to-A3 ECU transaction.
No source fields are echoed, only allowlisted aggregate metadata.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

FORMAT = "virtualcar-sectorv-report-chronology-v1"
MAX_BYTES = 256 * 1024
MAX_RUNS = 256
MAX_EVENTS = 4096
EVENTS = frozenset({
    "run_start", "can_connect_500k", "can_connect_125k", "a3_request",
    "a3_unmatched", "b9fb_request", "b9fb_ordered_complete",
    "disconnect", "close",
})
SESSIONS = frozenset({"ordered_frames_complete", "incomplete_disconnect"})
BARRIER = frozenset({"can_connect_500k", "can_connect_125k", "disconnect", "close"})


def _nonnegative(value, limit=100000):
    return type(value) is int and 0 <= value <= limit


def _summarize_timeline(run):
    timeline = run.get("timeline")
    if timeline is None:
        return "timeline_unavailable"
    if not isinstance(timeline, list) or len(timeline) > MAX_EVENTS:
        raise ValueError("invalid_timeline")
    events = []
    last_order = 0
    for row in timeline:
        if not isinstance(row, dict):
            raise ValueError("invalid_timeline_event")
        order, event, window = (row.get("order"), row.get("event"),
                                row.get("connection_window"))
        if (not _nonnegative(order, MAX_EVENTS) or order <= last_order
                or type(event) is not str or event not in EVENTS
                or not _nonnegative(window, MAX_EVENTS)):
            raise ValueError("invalid_timeline_order_or_event")
        last_order = order
        events.append((order, event, window))
    event_count = Counter(kind for _, kind, _ in events)
    for source_key, name in (
        ("a3_requests", "a3_request"),
        ("a3_requests_unmatched", "a3_unmatched"),
        ("b9fb_requests", "b9fb_request"),
    ):
        if source_key in run and run[source_key] != event_count[name]:
            raise ValueError("timeline_and_summary_disagree")
    sessions = run.get("sessions", [])
    if not isinstance(sessions, list) or len(sessions) > MAX_EVENTS:
        raise ValueError("invalid_sessions")
    completed_sessions = sum(1 for session in sessions
                             if isinstance(session, dict)
                             and session.get("status") == "ordered_frames_complete")
    if event_count["b9fb_ordered_complete"] != completed_sessions:
        raise ValueError("timeline_and_completed_sessions_disagree")
    a3 = [row for row in events if row[1] == "a3_request"]
    complete = [row for row in events if row[1] == "b9fb_ordered_complete"]
    if not a3:
        outcome = "no_a3_request_observed"
    elif not complete:
        outcome = "no_completed_b9fb_observed"
    elif len(a3) != 1 or len(complete) != 1:
        outcome = "multiple_events_no_unique_pairing"
    elif a3[0][0] < complete[0][0]:
        outcome = "a3_before_completed_b9fb"
    elif a3[0][2] != complete[0][2]:
        outcome = "a3_after_b9fb_in_different_connection_window"
    elif any(x[1] in BARRIER
             for x in events if complete[0][0] < x[0] < a3[0][0]):
        outcome = "a3_after_b9fb_with_intervening_connection_barrier"
    else:
        outcome = "a3_after_b9fb_order_in_same_connection_window"
    after_run = run.get("a3_after_b9fb_same_process_run")
    if after_run is not None and not _nonnegative(after_run, MAX_EVENTS):
        raise ValueError("invalid_reported_after_count")
    if (after_run == 0
            and outcome == "a3_after_b9fb_order_in_same_connection_window"):
        raise ValueError("contradictory_reported_after_count")
    return outcome


def audit(document):
    if not isinstance(document, dict):
        raise ValueError("invalid_source")
    version = document.get("analyzer_version")
    if (type(version) is not str or not version.startswith("0.3.6.7-dev")
            or len(version) > 80 or document.get("process_filter") != "SectorV.exe"
            or document.get("route") != "0x50"
            or document.get("expected_frames") != 13):
        raise ValueError("not_a_recognized_sectorv_report")
    if document.get("client_vin_accepted") not in (None, "unknown"):
        raise ValueError("unsupported_client_claim")
    if document.get("ecu_identified") not in (None, "unknown"):
        raise ValueError("unsupported_identity_claim")
    runs = document.get("runs")
    if runs is None:
        if "sessions" not in document:
            raise ValueError("missing_legacy_sessions")
        runs = [document]
    if not isinstance(runs, list) or len(runs) > MAX_RUNS or not runs:
        raise ValueError("invalid_runs")
    observations = []
    complete_total = 0
    incomplete_total = 0
    for run in runs:
        if not isinstance(run, dict):
            raise ValueError("invalid_run")
        sessions = run.get("sessions")
        if not isinstance(sessions, list) or len(sessions) > MAX_EVENTS:
            raise ValueError("invalid_session_list")
        complete = 0
        incomplete = 0
        for entry in sessions:
            if (not isinstance(entry, dict)
                    or entry.get("status") not in SESSIONS
                    or entry.get("expected_frames") != 13
                    or not _nonnegative(entry.get("frames_delivered"), 13)):
                raise ValueError("invalid_session_status")
            if entry["status"] == "ordered_frames_complete":
                if entry["frames_delivered"] != 13:
                    raise ValueError("incomplete_reported_as_complete")
                complete += 1
            elif entry["frames_delivered"] != 0:
                raise ValueError("inconsistent_disconnect_count")
            if entry["status"] == "incomplete_disconnect":
                incomplete += 1
        for key in ("a3_requests", "a3_requests_unmatched", "b9fb_requests"):
            if key in run and not _nonnegative(run[key], MAX_EVENTS):
                raise ValueError("invalid_report_count")
        if ("a3_requests" in run and "a3_requests_unmatched" in run
                and run["a3_requests_unmatched"] > run["a3_requests"]):
            raise ValueError("unmatched_exceeds_requests")
        chronology = _summarize_timeline(run)
        complete_total += complete
        incomplete_total += incomplete
        observations.append({
            "chronology": chronology,
            "b9fb_complete_sessions": complete,
            "b9fb_incomplete_disconnect_sessions": incomplete,
            "a3_requests_reported": run.get("a3_requests"),
            "a3_unmatched_reported": run.get("a3_requests_unmatched"),
            "a3_after_completed_b9fb_same_channel_verified": False,
            "client_acceptance_verified": False,
        })
    counts = Counter(record["chronology"] for record in observations)
    return {
        "format": FORMAT,
        "evidence_scope": "historical_sanitized_report_only",
        "read_only": True,
        "contains_payload_data": False,
        "source_version_family": "sectorv_d2_0.3.6.7",
        "runs_in_report": len(observations),
        "b9fb_complete_sessions": complete_total,
        "b9fb_incomplete_disconnect_sessions": incomplete_total,
        "chronology_counts": dict(sorted(counts.items())),
        "observations": observations,
        "tx_channel_binding_verified": False,
        "native_clock_join_verified": False,
        "b9fb_semantic_acceptance_verified": False,
        "a3_positive_reply_verified": False,
        "ecu_identity_verified": False,
        "limitations": [
            "Input is a derived historical SectorV summary, not original J2534 TX/RX bytes.",
            "Even an A3 after B9FB in one connection window does not establish the same J2534 TX channel.",
            "Different connection windows do not prove physically different ECU routes without channel IDs.",
            "Timeline order is not a measured source-local time interval.",
            "Delivered B9FB is not proof SectorV accepted the VIN or identified an ECU.",
            "No original VIN, CAN payload, process PID, private timestamp, path or report metadata is copied.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise ValueError("same_file")
        if args.source.stat().st_size > MAX_BYTES:
            raise ValueError("too_large")
        report = audit(json.loads(args.source.read_text(
            encoding="utf-8-sig", errors="replace")))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, UnicodeError, ValueError, TypeError):
        print("Historical SectorV chronology audit refused source/output",
              file=sys.stderr)
        return 2
    print("PASS: historical SectorV summary chronology checked; channel/acceptance unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
