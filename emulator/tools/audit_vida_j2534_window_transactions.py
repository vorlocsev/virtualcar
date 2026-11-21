#!/usr/bin/env python3
"""Summarize J2534 transactions in one exact, owner-private append window.

Reuses B3A45's path/prefix/hash-validated append boundary and the existing
privacy-safe J2534 discovery parser. Never emits raw payloads, VIN, PID, paths,
or source lines. This is local evidence analysis, not VIDA/ECU acceptance.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import audit_vida_j2534_session_window as window
import audit_j2534_discovery as discovery

SCHEMA = "virtualcar-vida-j2534-window-transactions-v1"
HOST_CLASSES = ("iexplore", "java", "vidamonitor", "other")
PREFIX = re.compile(r"^\[PID=[0-9a-fA-F]{8} ([A-Za-z0-9_.-]{1,48})\] ")


def _load_baseline(path):
    if not path.is_file() or path.stat().st_size > 128 * 1024:
        raise ValueError("invalid private B3A45 baseline")
    data = json.loads(path.read_text(encoding="utf-8"))
    if (type(data) is not dict or set(data) != {
            "schema_version", "private_do_not_publish",
            "original_vida", "virtual_j2534"}
            or data["schema_version"] != window.SCHEMA
            or data["private_do_not_publish"] is not True):
        raise ValueError("invalid private B3A45 baseline schema")
    return data


def analyze_window(virtual_log, baseline_path, host_class):
    """Return categorical transaction metadata for one appended host class."""
    if host_class not in HOST_CLASSES:
        raise ValueError("unsupported host process category")
    baseline = _load_baseline(baseline_path)
    lines, appended_bytes, dropped = window._append(
        virtual_log, baseline["virtual_j2534"])
    selected = []
    marker_counts = Counter()
    for line in lines:
        match = PREFIX.match(line)
        if match is None:
            continue
        name = match.group(1).lower()
        kind = name[:-4] if name.endswith(".exe") else name
        kind = kind if kind in HOST_CLASSES[:-1] else "other"
        if kind != host_class:
            continue
        selected.append(line)
        event = line[match.end():]
        for key, marker in (
                ("dll_initialized", "VirtualCar DLL initialized"),
                ("open_success", "PassThruOpen -> device 1"),
                ("connect_result", "J2534 Connect result protocol/flags/baud/status (BE)"),
                ("set_config", "J2534 SET_CONFIG channel/parameter/value/applied (BE)"),
                ("app_tx", "TX (app request)"),
                ("rx_delivered", "PassThruReadMsgs -> delivered"),
                ("read_timeout", "PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)"),
                ("close", "PassThruClose"),
                ("disconnect", "PassThruDisconnect"),
        ):
            if event.startswith(marker):
                marker_counts[key] += 1

    audited = discovery.audit(selected, include_obd=True)
    groups = Counter(
        (item["route"], item["service"], item["protocol"],
         item["baud_bps"], item["status"], item["reason"],
         item["request_origin"])
        for item in audited["transactions"]
    )
    transaction_groups = []
    for key, count in sorted(
            groups.items(),
            key=lambda pair: tuple("" if value is None else str(value)
                                   for value in pair[0])):
        route, service, protocol, baud, status, reason, origin = key
        transaction_groups.append({
            "route": route, "service": service, "protocol": protocol,
            "baud_bps": baud, "status": status, "reason": reason,
            "request_origin": origin, "count": count,
        })

    return {
        "schema_version": SCHEMA,
        "source_scope": "owner_local_exact_b3a45_append_window_selected_host_category",
        "host_process_category": host_class,
        "appended_bytes": appended_bytes,
        "complete_lines_in_window": len(lines),
        "selected_host_lines": len(selected),
        "incomplete_edge_fragments_ignored": dropped,
        "native_marker_counts": {key: marker_counts[key] for key in (
            "dll_initialized", "open_success", "connect_result",
            "set_config", "app_tx", "rx_delivered", "read_timeout",
            "close", "disconnect")},
        "recognized_transactions": len(audited["transactions"]),
        "transaction_status_counts": audited["counts"],
        "transaction_groups": transaction_groups,
        "parse_errors": audited["parse_errors"],
        "native_d2_delivery_tags": audited["native_d2_delivery_tags"],
        "client_result": "UNKNOWN",
        "original_vida_vin_accepted_verified": False,
        "ecu_identity_accepted_verified": False,
        "physical_ecu_provenance": "NOT_VERIFIED",
        "raw_payload_vin_pid_path_and_source_lines_exported": False,
        "limitations": [
            "Process name category is not executable or VIDA component authentication.",
            "This host-class filter does not prove the exact DLL path loaded by the process.",
            "A delivered J2534 RX frame is transport evidence, not client VIN or ECU acceptance.",
            "The append window may begin after Open/Connect; absent lifecycle markers do not prove they never occurred.",
            "Unknown request formats remain outside the recognized transaction categories.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--virtual-log", type=Path,
                        help="Exact local SectorVVirtualCar.log used by B3A45")
    source.add_argument("--candidate-manifest", type=Path,
                        help="Private B3A46 manifest used to create the B3A45 baseline")
    parser.add_argument("--candidate-index", type=int,
                        help="Same 1-based candidate index used by B3A45")
    parser.add_argument("--private-baseline", required=True, type=Path,
                        help="B3A45 private baseline JSON, never upload")
    parser.add_argument("--host-class", required=True, choices=HOST_CLASSES)
    parser.add_argument("--output", required=True, type=Path,
                        help="New private categorical JSON, never upload")
    args = parser.parse_args(argv)
    if args.candidate_manifest is not None:
        if args.candidate_index is None:
            parser.error("--candidate-index is required with --candidate-manifest")
        args.virtual_log = window._candidate_log(
            args.candidate_manifest, args.candidate_index)
    elif args.candidate_index is not None:
        parser.error("--candidate-index requires --candidate-manifest")
    sources = (args.virtual_log, args.private_baseline)
    protected = (*sources, args.candidate_manifest) if args.candidate_manifest else sources
    window._external(args.output, protected)
    report = analyze_window(args.virtual_log, args.private_baseline,
                            args.host_class)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    print("B3A55 Transaction window: ANALYZED")
    print("Host process category:", report["host_process_category"])
    print("Native app TX / delivered RX:",
          report["native_marker_counts"]["app_tx"], "/",
          report["native_marker_counts"]["rx_delivered"])
    print("Recognized transactions:", report["recognized_transactions"])
    print("Transaction statuses:", report["transaction_status_counts"])
    for item in report["transaction_groups"]:
        print("Transaction:", item["route"], item["service"], item["protocol"],
              item["baud_bps"], item["status"], item["reason"],
              "count=" + str(item["count"]))
    print("VIDA VIN / ECU acceptance: NOT_VERIFIED")
    print("Private categorical JSON retained locally; do not upload")


if __name__ == "__main__":
    main()
