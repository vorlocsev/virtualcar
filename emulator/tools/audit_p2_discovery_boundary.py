#!/usr/bin/env python3
"""Evidence boundary between redacted J2534 delivery and curated SectorV UI.

Does not correlate transactions across processes, parse identity bytes, infer
client acceptance, authorize A3, or create any replay material.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

SCHEMA = "virtualcar-p2-discovery-boundaries-v1"
STATUS = {"delivered", "partial_rx", "no_fixture", "unsupported", "timeout",
          "unverified", "negative_response"}
TFIELDS = {"format", "read_only", "contains_payload_data", "replay_approved",
           "notes", "transactions", "counts", "parse_errors",
           "obd_observation", "observed_event_markers"}
GFIELDS = {"schema_version", "client", "client_version", "scenario",
           "same_client_run", "observation_order", "b9fb_client_matcher",
           "hardware_a3", "normal_mode_warning_observed", "ecu_reachable_observed",
           "normal_mode_predicate", "expected_e3_response_bytes",
           "a3_security_access_authorized", "b9fb_vehicle_identity_accepted",
           "client_ecu_identification_accepted", "replay_approved", "findings"}

def integer(value, maximum=1_000_000):
    return type(value) is int and 0 <= value <= maximum

def validate_transport(source):
    if type(source) is not dict or not {
            "format", "read_only", "contains_payload_data", "replay_approved",
            "transactions", "counts"} <= set(source) or set(source) - TFIELDS:
        raise ValueError("not an allowlisted J2534 audit")
    if (source["format"] != "virtualcar-j2534-evidence-v1"
            or source["read_only"] is not True
            or source["contains_payload_data"] is not False
            or source["replay_approved"] is not False):
        raise ValueError("J2534 input must be a privacy-safe read-only audit")
    items = source["transactions"]
    if type(items) is not list or len(items) > 20000 or type(source["counts"]) is not dict:
        raise ValueError("bad J2534 transaction list")
    statuses = Counter()
    for item in items:
        if type(item) is not dict or not {
                "route", "service", "status", "target", "channel", "id_format",
                "protocol", "baud_bps", "rx_frames"} <= set(item):
            raise ValueError("incomplete J2534 transaction")
        route, service, state = item["route"], item["service"], item["status"]
        if route not in ("D2", "P3", "OBD") or state not in STATUS:
            raise ValueError("unknown route or status")
        if type(service) is not str or not re.fullmatch(r"[0-9A-F]{2,6}|other", service):
            raise ValueError("unsupported service")
        if item["target"] not in (None, "0x40", "0x50") and route == "D2":
            raise ValueError("unknown D2 target")
        if item["channel"] is not None and not integer(item["channel"], 0xFFFFFFFF):
            raise ValueError("invalid channel")
        if item["id_format"] not in ("11bit", "29bit", "unknown"):
            raise ValueError("invalid ID format")
        if item["protocol"] not in ("CAN", "ISO15765", "other", "unknown"):
            raise ValueError("invalid protocol")
        if item["baud_bps"] is not None and not integer(item["baud_bps"], 2_000_000):
            raise ValueError("invalid baud")
        if not integer(item["rx_frames"], 100000):
            raise ValueError("invalid RX count")
        statuses[state] += 1
    if any(s not in STATUS or not integer(v, 20000) for s, v in source["counts"].items()):
        raise ValueError("invalid status counters")
    if statuses != source["counts"]:
        raise ValueError("J2534 audit counters disagree")
    return items

def validate_gate(gate):
    if type(gate) is not dict or set(gate) != GFIELDS:
        raise ValueError("not an allowlisted SectorV gate report")
    if (gate["schema_version"] != "virtualcar-sectorv-gate-report-v1"
            or gate["client"] != "SectorV" or gate["same_client_run"] is not True
            or gate["replay_approved"] is not False
            or gate["scenario"] not in ("P2_MY2005_lab", "P2_MY2009_lab", "unknown_lab")
            or type(gate["client_version"]) is not str
            or not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", gate["client_version"])):
        raise ValueError("invalid client report")
    for key in ("normal_mode_predicate", "expected_e3_response_bytes",
                "a3_security_access_authorized", "b9fb_vehicle_identity_accepted",
                "client_ecu_identification_accepted"):
        if gate[key] != "unknown":
            raise ValueError("unverified client acceptance")
    if type(gate["normal_mode_warning_observed"]) is not bool:
        raise ValueError("invalid warning")
    count = gate["ecu_reachable_observed"]
    if count is not None and not integer(count, 100):
        raise ValueError("invalid ECU count")
    matcher = gate["b9fb_client_matcher"]
    if matcher != "not_observed":
        if type(matcher) is not dict or set(matcher) != {
                "observed", "matched", "ignored", "frame_matcher_complete"}:
            raise ValueError("invalid matcher")
        if not all(integer(matcher[k], 64) for k in ("observed", "matched", "ignored")):
            raise ValueError("invalid matcher counts")
        if (matcher["matched"] + matcher["ignored"] > matcher["observed"]
                or type(matcher["frame_matcher_complete"]) is not bool
                or matcher["frame_matcher_complete"] !=
                (matcher["observed"] > 0 and matcher["observed"] == matcher["matched"]
                 and matcher["ignored"] == 0)):
            raise ValueError("contradictory matcher")
    hardware = gate["hardware_a3"]
    if type(hardware) is not dict or set(hardware) - {"40", "50"}:
        raise ValueError("invalid A3 targets")
    for target, ev in hardware.items():
        if (type(ev) is not dict or set(ev) != {"outcome", "elapsed_ms"}
                or ev["outcome"] not in ("timeout", "rx_seen", "unknown")
                or not integer(ev["elapsed_ms"], 60000)):
            raise ValueError("invalid A3 result")
    return matcher, hardware

def summarize(items, stage, target=None):
    selected = [item for item in items if (
        item["route"] == "P3" if stage == "P3" else
        item["route"] == "D2" and item["service"] == stage and
        (target is None or (item["target"] is None if target == "unknown"
                            else item["target"] == "0x" + target)))]
    baud = lambda n: {500000: "500k", 125000: "125k"}.get(
        n, "unknown" if n is None else "other")
    return {"requests": len(selected),
            "statuses": dict(sorted(Counter(x["status"] for x in selected).items())),
            "protocol_categories": dict(sorted(Counter(x["protocol"] for x in selected).items())),
            "baud_categories": dict(sorted(Counter(baud(x["baud_bps"]) for x in selected).items())),
            "id_formats": dict(sorted(Counter(x["id_format"] for x in selected).items())),
            "missing_channel_metadata": sum(x["channel"] is None for x in selected),
            "interpretation": "j2534_transport_only"}

def audit(transport, gate, *, same_run_reviewed=False):
    if type(same_run_reviewed) is not bool:
        raise ValueError("review flag must be a boolean")
    items = validate_transport(transport)
    matcher, hardware = validate_gate(gate)
    stages = {name: summarize(items, name) for name in ("B9FB", "A6", "B9F0", "P3")}
    # A 2002-era target 40 capture cannot stand in for target 50 on late P2.
    # This is a J2534 grouping only, not a cross-process SectorV match.
    stages["B9FB_40"] = summarize(items, "B9FB", "40")
    stages["B9FB_50"] = summarize(items, "B9FB", "50")
    stages["B9FB_unknown_target"] = summarize(items, "B9FB", "unknown")
    stages["A3_40"] = summarize(items, "A3", "40")
    stages["A3_50"] = summarize(items, "A3", "50")
    stages["A3_unknown_target"] = {
        "requests": sum(x["route"] == "D2" and x["service"] == "A3"
                        and x["target"] is None for x in items),
        "interpretation": "unattributable_target"}
    client_match = ("not_observed" if matcher == "not_observed" else
                    "complete_frame_matcher_only" if matcher["frame_matcher_complete"] else
                    "incomplete_frame_matcher")
    if not same_run_reviewed:
        priority = "review_same_run_provenance_first"
    elif not stages["B9FB"]["requests"]:
        priority = "obtain_same_run_j2534_b9fb_tx"
    elif not stages["B9FB"]["statuses"].get("delivered"):
        priority = "investigate_b9fb_transport"
    elif gate["scenario"] in ("P2_MY2005_lab", "P2_MY2009_lab") and \
            not stages["B9FB_50"]["requests"]:
        priority = "verify_b9fb_target_50_transport"
    elif gate["scenario"] in ("P2_MY2005_lab", "P2_MY2009_lab") and \
            not stages["B9FB_50"]["statuses"].get("delivered"):
        priority = "investigate_b9fb_target_50_transport"
    elif gate["scenario"] in ("P2_MY2005_lab", "P2_MY2009_lab") and not any(
            item["route"] == "D2" and item["service"] == "B9FB" and
            item["target"] == "0x50" and item["status"] == "delivered" and
            item["protocol"] == "CAN" for item in items):
        # Delivered frames without a known CAN protocol may be a mislabelled
        # channel or an old text trace with missing connect metadata.
        # Require evidence review; do not claim that SectorV rejected a frame.
        priority = "verify_b9fb_target_50_can_protocol_metadata"
    elif client_match != "complete_frame_matcher_only":
        priority = "obtain_complete_client_b9fb_matcher_evidence"
    elif any(v["outcome"] == "timeout" for v in hardware.values()):
        priority = "investigate_hardware_a3_no_reply_without_emulating_security"
    elif gate["normal_mode_warning_observed"]:
        priority = "identify_client_normal_mode_predicate"
    else:
        priority = "obtain_verified_vehicle_and_ecu_acceptance"
    count = gate["ecu_reachable_observed"]
    return {
        "schema_version": SCHEMA,
        "read_only": True, "contains_payload_data": False, "replay_approved": False,
        "provenance": ("human_reviewed_same_acquisition_not_transaction_linked"
                       if same_run_reviewed else "independent_reports_no_same_run_claim"),
        "cross_source_transaction_attribution": "not_established",
        "client_version": gate["client_version"],
        "scenario": gate["scenario"],
        "stage_evidence": stages,
        "b9fb_target_evidence_boundary": {
            "client_matcher_target": "not_reported_by_gate_schema",
            "j2534_target_50_delivered": bool(stages["B9FB_50"]["statuses"].get("delivered")),
            "j2534_target_40_delivered": bool(stages["B9FB_40"]["statuses"].get("delivered")),
            "j2534_target_50_delivered_known_can": any(
                item["route"] == "D2" and item["service"] == "B9FB" and
                item["target"] == "0x50" and item["status"] == "delivered" and
                item["protocol"] == "CAN" for item in items),
            "j2534_target_50_delivered_unverified_protocol": sum(
                item["route"] == "D2" and item["service"] == "B9FB" and
                item["target"] == "0x50" and item["status"] == "delivered" and
                item["protocol"] != "CAN" for item in items),
            "target_cross_source_match": "not_established",
            "target_50_model_context": (
                "p2_my2005plus_service_node_hypothesis_not_wire_identity"
                if gate["scenario"] in ("P2_MY2005_lab", "P2_MY2009_lab")
                else "unknown_lab_no_target_assumption"),
        },
        "client_observations": {
            "b9fb_frame_matcher": client_match,
            "hardware_a3": {k: hardware[k]["outcome"] for k in sorted(hardware)},
            "normal_mode_warning": gate["normal_mode_warning_observed"],
            "reachable_ecu_count": count if count is not None else "not_observed"},
        "first_investigation_priority": priority,
        "vin_accepted_by_client": "unknown",
        "ecu_identification_accepted": "unknown",
        "normal_mode_predicate": "unknown",
        "a3_security_access_authorized": "unknown",
        "notes": [
            "Independent reports lack shared transaction identifiers or synchronized clocks.",
            "Same-run provenance never establishes per-transaction attribution.",
            "J2534 delivery and B9FB frame matching do not prove accepted VIN.",
            "B9FB target 40/50/unknown are reported separately; a target 40 positive never substitutes for target 50 in the late-P2 laboratory priority.",
            "The SectorV gate schema has no B9FB matcher target field; no cross-source target correspondence is claimed.",
            "CAN versus ISO15765 versus unknown report fields are source channel metadata, not proven ECU hardware compatibility.",
            "B9FB target 50 with no known-CAN delivered transaction triggers protocol metadata review, not any invented client rejection.",
            "A3/E3 observations do not establish SecurityAccess or normal-mode acceptance.",
            "A6/B9F0/P3 delivery cannot establish XC90 MY2009 ECU identity."]}

def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only privacy-safe P2 discovery boundary audit")
    p.add_argument("j2534", type=Path, help="Redacted J2534 report, not a raw log")
    p.add_argument("sectorv", type=Path, help="Curated SectorV gate report")
    p.add_argument("--same-run-reviewed", action="store_true",
                   help="Human-confirmed same run, NOT transaction matching")
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    paths = [x.resolve() for x in (a.j2534, a.sectorv, a.output)]
    if len(set(paths)) != 3:
        p.error("two distinct input files and a separate output required")
    try:
        if a.j2534.stat().st_size > 32 * 1024 * 1024 or a.sectorv.stat().st_size > 256 * 1024:
            raise ValueError("input report too large")
        left = json.loads(a.j2534.read_text(encoding="utf-8"))
        right = json.loads(a.sectorv.read_text(encoding="utf-8"))
        result = audit(left, right, same_run_reviewed=a.same_run_reviewed)
    except (OSError, ValueError, TypeError) as exc:
        p.error("invalid evidence: " + type(exc).__name__)
    try:
        with a.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except OSError as exc:
        p.error("cannot create exclusive output: " + type(exc).__name__)
    print("P2 boundary audit complete; client acceptance UNKNOWN; replay NO")

if __name__ == "__main__":
    main()
