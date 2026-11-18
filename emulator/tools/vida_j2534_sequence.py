#!/usr/bin/env python3
"""Read-only, session-scoped VIDA request-sequence inference from backend audit v1.

Shows only observed request order. Does not inspect original VIDA/SQL or claim
that VIDA accepted the VIN, that an ECU exists, or that any DID was supported.
No raw log fields, VINs or private paths are written into the output.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys

INPUT_FORMAT = "virtualcar-backend-audit-v1"
OUTPUT_FORMAT = "virtualcar-vida-j2534-sequence-v1"
MAX_BYTES = 8 * 1024 * 1024
MAX_TRANSACTIONS = 20000
TARGETS = {
    "0x18DA10F1": "ECM", "0x18DA18F1": "TCM",
    "0x18DA1AF1": "DEM", "0x18DA01F1": "BCM",
    "0x18DA32F1": "SAS", "0x18DA76F1": "HCM",
}
STATUSES = frozenset(("unverified", "delivered", "partial_rx", "timeout",
                      "no_fixture", "unsupported"))


class SequenceError(ValueError):
    """Errors intentionally omit source data and filenames."""


def _unique_object(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise SequenceError("duplicate key")
        result[k] = v
    return result


def _nonfinite(_):
    raise SequenceError("nonfinite number")


def _positive_int(v, maximum=MAX_TRANSACTIONS):
    return type(v) is int and 0 < v <= maximum


def _is_anchor(row):
    """Recognized *request shape*, NOT a read or accepted VIN."""
    if row["service"] == "B9FB":
        return (row["protocol"] == "CAN" and row["baud_bps"] == 125000
                and row["can_id"] == "0x000FFFFE" and row["id_format"] == "29bit"
                and row["target"] in ("0x40", "0x50"))
    if row["service"] == "22F114":
        return (row["protocol"] == "ISO15765" and row["baud_bps"] == 500000
                and ((row["can_id"], row["id_format"])
                     in (("0x726", "11bit"), ("0x18DA50F1", "29bit"))))
    return False


def _target(row):
    module = TARGETS.get(row["can_id"])
    if (module is not None and row["protocol"] == "ISO15765"
            and row["baud_bps"] == 500000 and row["id_format"] == "29bit"
            and row["service"] is None
            and row["target"] == f"{module}_REQUEST_ONLY"):
        return module
    return None


def analyze(report):
    if (type(report) is not dict or report.get("format") != INPUT_FORMAT
            or report.get("contains_payload_data") is not False
            or report.get("client_acceptance_verified") is not False
            or report.get("identity_verified") is not False):
        raise SequenceError("unsupported or overclaimed audit")
    rows = report.get("transactions")
    if type(rows) is not list or len(rows) > MAX_TRANSACTIONS:
        raise SequenceError("invalid transactions")
    by_session = defaultdict(list)
    ordinals = set()
    for row in rows:
        if type(row) is not dict or not _positive_int(row.get("session")) or not _positive_int(row.get("request")):
            raise SequenceError("invalid transaction key")
        if row["request"] in ordinals:
            raise SequenceError("duplicate request ordinal")
        ordinals.add(row["request"])
        if (type(row.get("protocol")) is not str or row["protocol"] not in ("CAN", "ISO15765", "other")
                or type(row.get("baud_bps")) is not int or not 1 <= row["baud_bps"] <= 10000000
                or type(row.get("status")) is not str or row["status"] not in STATUSES
                or type(row.get("rx_dequeued")) is not int or not 0 <= row["rx_dequeued"] <= 20000
                or type(row.get("service")) not in (str, type(None))
                or type(row.get("can_id")) not in (str, type(None))
                or type(row.get("target")) not in (str, type(None))
                or type(row.get("id_format")) is not str):
            raise SequenceError("invalid transaction evidence")
        by_session[row["session"]].append(row)
    sessions = []
    global_anchors = global_post_targets = 0
    for sid, items in sorted(by_session.items()):
        items.sort(key=lambda r: r["request"])
        anchor_ordinals = [r["request"] for r in items if _is_anchor(r)]
        earliest_anchor = min(anchor_ordinals) if anchor_ordinals else None
        observed = defaultdict(lambda: {"requests": 0, "rx_dequeued_frames": 0,
                                        "statuses": set(), "first_request": None})
        pre_anchor = 0
        for r in items:
            target = _target(r)
            if target is None:
                continue
            if earliest_anchor is None or r["request"] <= earliest_anchor:
                pre_anchor += 1
                continue
            entry = observed[target]
            entry["requests"] += 1
            entry["rx_dequeued_frames"] += r["rx_dequeued"]
            entry["statuses"].add(r["status"])
            if entry["first_request"] is None:
                entry["first_request"] = r["request"]
        details = [{"target_request_label": key, "observed_requests": value["requests"],
                    "first_request_ordinal": value["first_request"],
                    "backend_statuses": sorted(value["statuses"]),
                    "j2534_rx_dequeued_frames": value["rx_dequeued_frames"]}
                   for key, value in sorted(observed.items())]
        global_anchors += len(anchor_ordinals)
        global_post_targets += sum(v["requests"] for v in observed.values())
        sessions.append({
            "session_ordinal": sid,
            "vin_shaped_tx_requests": len(anchor_ordinals),
            "first_vin_request_ordinal": earliest_anchor,
            "pre_anchor_or_unanchored_ecu_target_requests": pre_anchor,
            "post_anchor_ecu_target_requests": sum(v["requests"] for v in observed.values()),
            "targets_after_vin_shaped_tx": details,
            "vida_gui_vin_acceptance": "not_tested",
            "ecu_identification": "not_tested",
            "t111": "not_tested", "t122": "not_tested",
        })
    return {
        "format": OUTPUT_FORMAT, "scope": "backend_session_order_only",
        "vin_shaped_tx_total": global_anchors,
        "ecu_target_tx_after_vin_shaped_tx_total": global_post_targets,
        "sessions": sessions,
        "same_gui_workflow_verified": False, "client_vin_accepted": False,
        "ecu_identity_verified": False, "physical_j2534_verified": False,
        "limitations": [
            "A request after a VIN-shaped request in one backend session does not prove VIDA GUI state progression",
            "RX dequeue is J2534 delivery, not a parsed application response or VIN acceptance",
            "Target labels describe outgoing requests only; ECU presence and response capabilities are unverified",
            "Session ordinals are local to one audit input; no cross-file clock correlation is asserted",
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--audit-report", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        if (args.audit_report.is_symlink() or not args.audit_report.is_file()
                or args.audit_report.stat().st_size > MAX_BYTES
                or args.audit_report.resolve() == args.output.resolve()
                or args.output.is_symlink()):
            raise SequenceError("unsafe file")
        data = args.audit_report.read_bytes()
        if len(data) > MAX_BYTES:
            raise SequenceError("oversized source")
        report = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object,
                            parse_constant=_nonfinite)
        output = analyze(report)
        with args.output.open("x", encoding="utf-8") as fp:
            json.dump(output, fp, indent=2, ensure_ascii=False)
            fp.write("\n")
    except (OSError, ValueError, UnicodeError, RecursionError):
        print("VIDA request sequence audit failed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
