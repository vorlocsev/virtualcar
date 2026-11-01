#!/usr/bin/env python3
"""Summarize privacy-safe Virtual Car backend JSONL without inferring ECU identity.

Input is the optional virtualcar-backend-v1 event stream, NOT the raw J2534
text log. No payload/VIN, PID, source path, original request ID or session ID
is ever copied to output. RX dequeued means J2534 delivery, not client acceptance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

FORMAT = "virtualcar-backend-v1"
OUTPUT_FORMAT = "virtualcar-backend-audit-v1"
MAX_LINE = 4096
MAX_EVENTS = 200000
MAX_REQUESTS = 20000
KINDS = frozenset((
    "tx_received", "probe_classified", "route_selected", "response_generated", "filter_pass",
    "filter_drop", "rx_queued", "rx_dequeued", "rx_dropped",
    "response_aborted", "tracking_overflow", "request_completed",
))
ROUTES = frozenset(("UNKNOWN", "CEM", "ECM", "ECU_OTHER", "UNHANDLED"))
OUTCOMES = frozenset(("unknown", "responded", "no_response", "aborted",
                      "dropped", "unverified"))
REASONS = frozenset((
    "none", "unsupported_bus", "missing_profile", "no_response",
    "unhandled_request", "filter_reject", "queue_full", "other",
    "tracking_limit", "flow_overflow", "superseded", "clear_rx_buffer",
    "channel_disconnect", "device_close", "d2_superseded", "read_timeout",
))
SESSION = re.compile(r"[0-9a-fA-F]{16}\Z")
# Only compile-time identifiers from the DLL are accepted. They reveal request
# shape, not VIN, payload content or the presence of a physical ECU.
PROBES = {}
for _target in ("40", "50"):
    for _op in ("A3", "A6", "B9F0", "B9FB", "B9FC"):
        PROBES[f"D2_{_target}_{_op}"] = {
            "service": _op, "can_id": "0x000FFFFE",
            "id_format": "29bit", "target": f"0x{_target}"}
for _kind, _id, _bits in (("726", "0x726", "11bit"),
                         ("29", "0x18DA50F1", "29bit")):
    for _did in ("F114", "F1B0", "F1A3", "F106", "F190"):
        PROBES[f"P3_{_kind}_{_did}"] = {
            "service": f"22{_did}", "can_id": _id,
            "id_format": _bits, "target": None}



def _uint(value, maximum):
    return type(value) is int and 0 < value <= maximum


def _decode(line):
    """Reject untrusted events without reflecting their contents to the report."""
    if len(line) > MAX_LINE:
        return None
    try:
        e = json.loads(line)
    except (ValueError, TypeError):
        return None
    if not isinstance(e, dict) or e.get("format") != FORMAT:
        return None
    # Malformed nested values must not raise TypeError during set membership.
    if any(type(e.get(k)) is not str for k in ("kind", "route", "reason", "outcome")):
        return None
    if e["kind"] not in KINDS or e["route"] not in ROUTES:
        return None
    if e["reason"] not in REASONS or e["outcome"] not in OUTCOMES:
        return None
    if not isinstance(e.get("session_id"), str) or not SESSION.fullmatch(e["session_id"]):
        return None
    if not _uint(e.get("request_id"), (1 << 64) - 1):
        return None
    if not _uint(e.get("channel"), (1 << 32) - 1):
        return None
    if not _uint(e.get("protocol"), (1 << 32) - 1):
        return None
    if not _uint(e.get("baud"), 10000000):
        return None
    if not _uint(e.get("tick"), (1 << 63) - 1):
        return None
    if not _uint(e.get("freq"), 1000000000000):
        return None
    if e["kind"] == "probe_classified":
        if type(e.get("probe")) is not str or e["probe"] not in PROBES:
            return None
    # Explicit allowlist. Unknown keys, including raw CAN or VIN, are discarded.
    out = {k: e[k] for k in ("session_id", "request_id", "kind", "route",
                              "reason", "outcome", "channel", "protocol",
                              "baud", "tick", "freq")}
    if e["kind"] == "probe_classified":
        out["probe"] = e["probe"]
    return out


def _new_event(e, session_number, ordinal):
    return {
        "session": session_number, "ordinal": ordinal,
        "channel": e["channel"], "protocol": e["protocol"],
        "baud": e["baud"], "route": "UNKNOWN", "routes": set(),
        "counts": Counter(), "start_tick": None, "end_tick": None,
        "freq": e["freq"], "clock_conflict": False,
        "context_conflict": False, "terminal": None,
        "duplicate_terminal": False, "late_events": False,
        "saw_tx": False, "probes": set(),
    }


def _update(r, e):
    kind = e["kind"]
    r["counts"][kind] += 1
    if kind == "probe_classified":
        r["probes"].add(e["probe"])
    if (r["channel"], r["protocol"], r["baud"]) != (
            e["channel"], e["protocol"], e["baud"]):
        r["context_conflict"] = True
    if e["freq"] != r["freq"]:
        r["clock_conflict"] = True
    if kind == "tx_received":
        r["saw_tx"] = True
        if r["start_tick"] is None:
            r["start_tick"] = e["tick"]
    if r["terminal"] is not None and kind != "request_completed":
        r["late_events"] = True
    if e["route"] != "UNKNOWN":
        r["routes"].add(e["route"])
        r["route"] = e["route"]
    if kind == "request_completed":
        if r["terminal"] is not None:
            r["duplicate_terminal"] = True
        else:
            r["terminal"] = (e["outcome"], e["reason"])
            r["end_tick"] = e["tick"]


def _classify(r):
    c = r["counts"]
    delivered = c["rx_dequeued"]
    queued = c["rx_queued"]
    lost = c["rx_dropped"] + c["filter_drop"]
    terminal = r["terminal"]
    if len(r["probes"]) > 1:
        return "unverified", "conflicting_probe_evidence"
    if r["context_conflict"] or len(r["routes"]) > 1:
        return "unverified", "inconsistent_route_or_channel"
    if r["duplicate_terminal"] or r["late_events"]:
        return "unverified", "inconsistent_event_lifecycle"
    if not r["saw_tx"]:
        return "unverified", "missing_tx_evidence"
    if terminal is None:
        if delivered:
            return "unverified", "rx_seen_without_terminal"
        if queued:
            return "unverified", "queued_not_delivered"
        return "unverified", "no_terminal_evidence"
    outcome, reason = terminal
    if reason == "missing_profile" and outcome == "no_response":
        return "no_fixture", "explicit_missing_profile"
    if reason in ("unsupported_bus", "unhandled_request") and outcome == "no_response":
        return "unsupported", reason
    # Current DLL does not produce a terminal timeout. Never infer timeout
    # from missing events or from an unexplained PassThruClose.
    if reason == "read_timeout":
        return "timeout", "explicit_timeout"
    if outcome in ("aborted", "dropped"):
        if delivered:
            return "partial_rx", "rx_delivery_interrupted"
        return "unverified", "aborted_or_dropped_before_rx"
    if outcome == "responded":
        if delivered > 0 and not lost:
            return "delivered", "j2534_rx_only"
        return "unverified", "terminal_without_clean_rx"
    if delivered:
        return "partial_rx", "rx_without_confirmed_terminal"
    if outcome == "no_response":
        return "unverified", "explicit_no_response"
    return "unverified", "unconfirmed_transport"


def _result(r):
    status, reason = _classify(r)
    c = r["counts"]
    details = PROBES[next(iter(r["probes"]))] if len(r["probes"]) == 1 else None
    duration = None
    if (not r["clock_conflict"] and r["start_tick"] is not None
            and r["end_tick"] is not None and r["end_tick"] >= r["start_tick"]):
        duration = round((r["end_tick"] - r["start_tick"]) * 1000 / r["freq"], 3)
    return {
        "session": r["session"], "request": r["ordinal"],
        "route": r["route"] if len(r["routes"]) == 1 else "UNKNOWN",
        "channel": r["channel"],
        "protocol": {5: "CAN", 6: "ISO15765"}.get(r["protocol"], "other"),
        "baud_bps": r["baud"],
        "can_id": details["can_id"] if details else None,
        "service": details["service"] if details else None,
        "target": details["target"] if details else None,
        "id_format": details["id_format"] if details else "unknown",
        "elapsed_ms": duration,
        "rx_queued": c["rx_queued"], "rx_dequeued": c["rx_dequeued"],
        "rx_dropped": c["rx_dropped"], "filter_dropped": c["filter_drop"],
        "terminal_seen": r["terminal"] is not None,
        "status": status, "reason": reason,
    }


def audit(lines):
    sessions = {}
    transactions = {}
    errors = Counter()
    for index, line in enumerate(lines, 1):
        if index > MAX_EVENTS:
            raise ValueError("event_limit")
        e = _decode(line)
        if e is None:
            errors["invalid_lines"] += 1
            continue
        session = e["session_id"].lower()
        if session not in sessions:
            sessions[session] = len(sessions) + 1
        key = (session, e["request_id"])
        if key not in transactions:
            if len(transactions) >= MAX_REQUESTS:
                raise ValueError("request_limit")
            transactions[key] = _new_event(e, sessions[session], len(transactions) + 1)
        _update(transactions[key], e)
    results = [_result(r) for r in transactions.values()]
    return {
        "format": OUTPUT_FORMAT, "contains_payload_data": False,
        "client_acceptance_verified": False,
        "identity_verified": False,
        "probe_detail_available": any(bool(r["probes"]) for r in transactions.values()),
        "limitations": [
            "Only exact allowlisted probe_classified shapes identify a request; legacy logs remain unknown",
            "delivered means J2534 RX dequeue, not complete D2/ISO-TP or client acceptance",
            "A missing terminal event does not prove a client timeout",
        ],
        "summary": {
            "requests": len(results), "sessions": len(sessions),
            "invalid_lines": errors["invalid_lines"],
            "statuses": dict(sorted(Counter(r["status"] for r in results).items())),
        },
        "transactions": results,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Private local backend JSONL")
    parser.add_argument("--output", type=Path, required=True,
                        help="New JSON report path; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise ValueError("same_file")
        with args.source.open("r", encoding="utf-8", errors="replace") as fh:
            report = audit(fh)
        with args.output.open("x", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    except (OSError, ValueError):
        # Never echo a user-provided path or raw log content in an error.
        print("Unable to complete read-only backend audit", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
