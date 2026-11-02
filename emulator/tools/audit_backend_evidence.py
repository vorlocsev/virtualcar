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
    "tx_received", "periodic_fired", "probe_classified", "route_selected", "response_generated", "filter_pass",
    "filter_drop", "rx_queued", "rx_dequeued", "rx_dropped",
    "response_aborted", "tracking_overflow", "request_completed",
))
ROUTES = frozenset(("UNKNOWN", "CEM", "ECM", "ECU_OTHER", "UNHANDLED"))
OUTCOMES = frozenset(("unknown", "responded", "no_response", "aborted",
                      "dropped", "unverified"))
REASONS = frozenset((
    "none", "unsupported_bus", "missing_profile", "no_response",
    "unhandled_request", "unimplemented_probe", "filter_reject", "queue_full", "other",
    "tracking_limit", "flow_overflow", "superseded", "clear_rx_buffer",
    "channel_disconnect", "device_close", "d2_superseded", "read_timeout",
))
SESSION = re.compile(r"[0-9a-fA-F]{16}\Z")
# Only compile-time identifiers from the DLL are accepted. They reveal request
# shape, not VIN, payload content or the presence of a physical ECU.
PROBES = {
    "FUNC29_TP_SUPPRESSED": {
        "service": "3E80", "can_id": "0x18DB33F1",
        "id_format": "29bit", "target": None,
    },
}
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


# Published community Arduino/MCP2515 TX shapes, not OEM module responses.
# Exact source: drpioneer/Volvo-P2-informer main@9cd3a6f603915e074ac28c73eccec6b7473e8297.
# Labels are source-bound observations only; 2.5T observations cannot be
# promoted into XC90 V8 MY2009 identity/response evidence.
for _probe, _service in (
    ("P2INF_LS_VIN_F190", "22F190"),
    ("P2INF_LS_REM_A6", "A6"),
    ("P2INF_LS_CCM_A6", "A6"),
    ("P2INF_HS_ECM_A6", "A6"),
    ("P2INF_HS_TCM_A5", "A5"),
    ("P2INF_HS_DEM_A6", "A6"),
):
    PROBES[_probe] = {
        "service": _service, "can_id": "0x000FFFFE",
        "id_format": "29bit", "target": None,
    }



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
        if e["probe"] == "FUNC29_TP_SUPPRESSED":
            # Only the metadata shapes emitted by the 500-kbit/s CAN/
            # ISO15765 classifier are compatible with this known probe.
            if e["baud"] != 500000 or e["protocol"] not in (5, 6):
                return None
        if e["probe"].startswith("P2INF_"):
            # Refuse wrong-protocol / wrong-bus provenance even if a
            # locally supplied JSONL line spoofs an allowlisted token.
            required_baud = 125000 if "_LS_" in e["probe"] else 500000
            if e["protocol"] != 5 or e["baud"] != required_baud:
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
        "context_conflict": False, "context_fields": set(), "terminal": None,
        "duplicate_terminal": False, "late_events": False,
        "saw_tx": False, "origin": "unknown", "probes": set(),
        "last_tick": None, "sequence_conflict": False,
        "dequeue_without_queue": False, "queued_open": 0,
    }


def _update(r, e):
    kind = e["kind"]
    # A record with a missing TX, repeated TX, out-of-order monotonic ticks,
    # or a dequeue without a previously queued frame is incomplete evidence.
    # rx_dropped does NOT consume queued_open: enqueue failures also emit it.
    if r["last_tick"] is not None and e["tick"] < r["last_tick"]:
        r["clock_conflict"] = True
    r["last_tick"] = e["tick"]
    if kind in ("tx_received", "periodic_fired"):
        if r["saw_tx"] or r["counts"]:
            r["sequence_conflict"] = True
    elif not r["saw_tx"]:
        r["sequence_conflict"] = True
    if kind == "probe_classified" and (
            r["counts"]["rx_queued"] or r["counts"]["rx_dequeued"]
            or r["terminal"] is not None):
        r["sequence_conflict"] = True
    if kind == "rx_queued":
        r["queued_open"] += 1
    if kind == "rx_dequeued":
        if r["queued_open"] <= 0:
            r["dequeue_without_queue"] = True
        else:
            r["queued_open"] -= 1
    r["counts"][kind] += 1
    if kind == "probe_classified":
        r["probes"].add(e["probe"])
    for field in ("channel", "protocol", "baud"):
        if r[field] != e[field]:
            r["context_conflict"] = True
            r["context_fields"].add(field)
    if e["freq"] != r["freq"]:
        r["clock_conflict"] = True
    if kind in ("tx_received", "periodic_fired"):
        r["saw_tx"] = True
        r["origin"] = "periodic" if kind == "periodic_fired" else "app_write"
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
    if r["duplicate_terminal"] or r["late_events"] or r["sequence_conflict"]:
        return "unverified", "inconsistent_event_lifecycle"
    if r["clock_conflict"]:
        return "unverified", "inconsistent_clock"
    if r["dequeue_without_queue"]:
        return "unverified", "dequeue_without_queue"
    if not r["saw_tx"]:
        return "unverified", "missing_tx_evidence"
    if terminal is None:
        if delivered:
            return "unverified", "rx_seen_without_terminal"
        if queued:
            return "unverified", "queued_not_delivered"
        return "unverified", "no_terminal_evidence"
    outcome, reason = terminal
    if outcome == "no_response" and (queued or delivered):
        return "unverified", "rx_evidence_with_no_response"
    # A confirmed suppress-positive-response keepalive is not a failed ECU
    # discovery attempt. Require the exact probe, correct functional route,
    # an explicit silent terminal and *no* contradictory RX/response events.
    if (r["probes"] == {"FUNC29_TP_SUPPRESSED"}
            and r["routes"] == {"ECU_OTHER"}
            and r["baud"] == 500000 and r["protocol"] in (5, 6)
            and outcome == "no_response" and reason == "no_response"
            and not queued and not delivered and not lost
            and not r["counts"]["response_generated"]
            and not r["counts"]["filter_pass"]
            and not r["counts"]["response_aborted"]):
        return "suppressed", "functional_tester_present_no_rx_expected"
    if reason == "missing_profile" and outcome == "no_response":
        return "no_fixture", "explicit_missing_profile"
    if reason in ("unsupported_bus", "unhandled_request", "unimplemented_probe") and outcome == "no_response":
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
        if delivered > 0 and not lost and r["queued_open"] == 0:
            return "delivered", "j2534_rx_only"
        return "unverified", "terminal_without_clean_rx"
    if delivered:
        return "partial_rx", "rx_without_confirmed_terminal"
    if outcome == "no_response":
        return "unverified", "explicit_no_response"
    return "unverified", "unconfirmed_transport"


def _trusted_probe(r):
    """Only a uniquely classified, well-ordered request can enter coverage."""
    if len(r["probes"]) != 1 or not r["saw_tx"] or r["sequence_conflict"]:
        return None
    return next(iter(r["probes"]))


def _result(r):
    status, reason = _classify(r)
    c = r["counts"]
    probe = _trusted_probe(r)
    details = PROBES[probe] if probe else None
    duration = None
    if (not r["clock_conflict"] and r["start_tick"] is not None
            and r["end_tick"] is not None and r["end_tick"] >= r["start_tick"]):
        duration = round((r["end_tick"] - r["start_tick"]) * 1000 / r["freq"], 3)
    return {
        "session": r["session"], "request": r["ordinal"],
        "request_origin": r["origin"] if not r["sequence_conflict"] else "unknown",
        "route": r["route"] if len(r["routes"]) == 1 else "UNKNOWN",
        # Allowlisted metadata only; never repair conflicting legacy evidence.
        "observed_routes": sorted(r["routes"]),
        "evidence_conflicts": sorted(r["context_fields"] | (
            {"route"} if len(r["routes"]) > 1 else set())),
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
    records = list(transactions.values())
    results = [_result(r) for r in records]
    # Coverage is only about observed J2534 writes and fired periodic requests.
    # No probe is not a failure, no fixture, an ECU response, or a timeout.
    coverage_counts = {probe: Counter() for probe in PROBES}
    coverage_origins = {
        probe: {"app_write": Counter(), "periodic": Counter(), "unknown": Counter()}
        for probe in PROBES
    }
    unattributed = 0
    for record, result in zip(records, results):
        probe = _trusted_probe(record)
        if probe is None:
            unattributed += 1
        else:
            coverage_counts[probe][result["status"]] += 1
            coverage_origins[probe][result["request_origin"]][result["status"]] += 1
    observed = {
        probe: counts for probe, counts in coverage_counts.items() if counts
    }
    coverage = {
        "scope": "allowlisted_request_shapes_only",
        "not_observed_is_not_unsupported": True,
        "attributed_requests": len(results) - unattributed,
        "unattributed_requests": unattributed,
        "probes": [
            {
                "probe": probe,
                "observed_requests": sum(counts.values()),
                "status_counts": dict(sorted(counts.items())),
                "by_origin": {
                    origin: dict(sorted(by_status.items()))
                    for origin, by_status in sorted(coverage_origins[probe].items())
                    if by_status
                },
            }
            for probe, counts in sorted(coverage_counts.items())
        ],
    }
    return {
        "format": OUTPUT_FORMAT, "contains_payload_data": False,
        "client_acceptance_verified": False,
        "identity_verified": False,
        "probe_detail_available": bool(observed),
        "coverage": coverage,
        "limitations": [
            "Missing, reordered or incomplete queue/terminal events downgrade delivery to unverified",
            "Only exact allowlisted probe_classified shapes identify a request; legacy logs remain unknown",
            "Coverage describes observed app writes and J2534 periodic firings only; never infer an ECU reply from an unobserved probe",
            "delivered means J2534 RX dequeue, not complete D2/ISO-TP or client acceptance",
            "A missing terminal event does not prove a client timeout",
            "Origin breakdown counts observed J2534 events, not VDASH internal decisions or ECU presence",
            "suppressed means exact silent 3E80 functional request, never ECU discovery or client acceptance",
        ],
        "summary": {
            "requests": len(results), "sessions": len(sessions),
            "invalid_lines": errors["invalid_lines"],
            "statuses": dict(sorted(Counter(r["status"] for r in results).items())),
            "request_origins": dict(sorted(
                Counter(r["request_origin"] for r in results).items())),
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

