#!/usr/bin/env python3
"""B3A70: read-only, privacy-safe native J2534 filter-channel lifetime check.

Only an isolated B3A69 x86 CEM40 B9FB smoke log is supported. This does
NOT inspect or attest an original VIDA session, installed J2534 provider, VIN,
physical adapter, OEM response or T111/T122. No log payload is exported.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

SCHEMA = "virtualcar-b3a70-isolated-cem40-filter-channel-v1"
PREFIX = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([A-Za-z0-9_.-]{1,48})\] ")
HEX = re.compile(r"^[0-9A-Fa-f]{2}$")
MAX_BYTES = 8 * 1024 * 1024
MAX_LINE = 512

LABELS = {
    "strict_policy": ("J2534 native strict RX filter policy (BE)", 4),
    "accepted": ("J2534 filter accepted channel/type/id/protocol/baud (BE)", 20),
    "stopped": ("J2534 filter stopped channel/id (BE)", 8),
    "tx": ("TX context channel/protocol/flags/baud/time-us (BE)", 20),
    "rx": ("RX context channel/protocol/status/baud/time-us (BE)", 20),
    "d2": ("P2 D2 request target/opcode/baud/flags (BE)", 16),
}


def _blank():
    return {
        "schema_version": SCHEMA,
        "status": "NOT_VERIFIED",
        "source_scope": "isolated_owner_native_smoke_log_only",
        "native_logger_groups": 0,
        "marker_counts": {key: 0 for key in LABELS},
        "malformed_native_markers": 0,
        "same_channel_for_accepted_filters_and_tx_rx": False,
        "protocol_mode": "not_verified",
        "baud_bps": "not_verified",
        "filter_lifetime_balanced": False,
        "first_filter_tx_count": 0,
        "first_filter_rx_count": 0,
        "second_filter_tx_count": 0,
        "second_filter_rx_count": 0,
        "d2_40_b9fb_request_markers": 0,
        "strict_policy_loaded": False,
        "failures": [],
        "original_vida_dll_loaded_verified": False,
        "original_vida_filter_channel_verified": False,
        "original_vida_readvin_verified": False,
        "vehicle_identity_verified": False,
        "physical_j2534_verified": False,
        "raw_pid_filter_id_vin_mask_frame_path_exported": False,
    }


def _extract(line):
    if not isinstance(line, str) or len(line) > MAX_LINE:
        return None
    m = PREFIX.match(line)
    if not m:
        return None
    event = line[m.end():]
    for key, (label, width) in LABELS.items():
        if not event.startswith(label):
            continue
        rest = event[len(label):]
        if not rest.startswith(" "):
            return ("malformed", (m.group(1), m.group(2)), ())
        parts = rest.strip().split()
        if len(parts) != width or any(HEX.fullmatch(b) is None for b in parts):
            return ("malformed", (m.group(1), m.group(2)), ())
        raw = bytes(int(b, 16) for b in parts)
        data = tuple(int.from_bytes(raw[i:i + 4], "big")
                     for i in range(0, len(raw), 4))
        return (key, (m.group(1), m.group(2).lower()), data)
    return None


def analyze(lines):
    """Pure categorical analysis; neither raw logs nor private values returned."""
    report = _blank()
    parsed = []
    groups = set()
    for line in lines:
        event = _extract(line.rstrip("\r\n"))
        if event is None:
            continue
        kind, group, values = event
        if kind == "malformed":
            report["malformed_native_markers"] += 1
            continue
        groups.add(group)
        parsed.append((kind, values))
        report["marker_counts"][kind] += 1
    report["native_logger_groups"] = len(groups)
    problems = []
    if len(groups) != 1:
        problems.append("expected_single_native_logger_group")
    if report["malformed_native_markers"]:
        problems.append("malformed_native_marker")
    counts = report["marker_counts"]
    if [counts[k] for k in ("strict_policy", "accepted", "stopped",
                           "tx", "rx", "d2")] != [1, 2, 2, 2, 13, 2]:
        problems.append("unexpected_isolated_smoke_marker_counts")

    active = {}
    filters = []
    policy_values = []
    d2_valid = 0
    all_channels = set()
    for kind, data in parsed:
        if kind == "strict_policy":
            policy_values.append(data[0])
        elif kind == "accepted":
            channel, typ, fid, protocol, baud = data
            all_channels.add(channel)
            if typ != 1 or protocol != 0x8004 or baud != 125000:
                problems.append("unexpected_filter_type_protocol_or_baud")
            key = (channel, fid)
            if active or key in active or any(x["key"] == key for x in filters):
                problems.append("overlapping_or_duplicate_filter_lifetime")
            item = {"key": key, "tx": 0, "rx": 0, "d2": 0, "stopped": False}
            active[key] = item
            filters.append(item)
        elif kind == "stopped":
            channel, fid = data
            all_channels.add(channel)
            item = active.pop((channel, fid), None)
            if item is None:
                problems.append("stop_without_active_matching_filter")
            else:
                item["stopped"] = True
        elif kind in ("tx", "rx"):
            channel, protocol, flags_or_status, baud, _ = data
            all_channels.add(channel)
            if protocol != 5 or baud != 125000:
                problems.append("unexpected_internal_can_protocol_or_baud")
            if kind == "rx" and not (flags_or_status & 0x100):
                problems.append("rx_missing_can_29bit_id")
            if len(active) != 1:
                problems.append("tx_rx_without_single_active_pass_filter")
            else:
                item = next(iter(active.values()))
                if item["key"][0] != channel:
                    problems.append("tx_rx_channel_differs_from_active_filter")
                item[kind] += 1
        elif kind == "d2":
            target, op, baud, _ = data
            if target != 0x40 or op != 0xFB or baud != 125000:
                problems.append("different_d2_target_opcode_or_baud")
            else:
                d2_valid += 1
            if len(active) != 1:
                problems.append("d2_request_outside_single_filter_lifetime")
            else:
                next(iter(active.values()))["d2"] += 1

    report["strict_policy_loaded"] = len(policy_values) == 1 and policy_values[0] == 1
    if not report["strict_policy_loaded"]:
        problems.append("strict_policy_not_attested_on_isolated_loader")
    report["d2_40_b9fb_request_markers"] = d2_valid
    report["filter_lifetime_balanced"] = (
        len(filters) == 2 and all(x["stopped"] for x in filters)
        and not active)
    if not report["filter_lifetime_balanced"]:
        problems.append("filter_lifetime_not_balanced")
    report["same_channel_for_accepted_filters_and_tx_rx"] = (
        len(all_channels) == 1 and len(filters) == 2)
    if not report["same_channel_for_accepted_filters_and_tx_rx"]:
        problems.append("filter_and_transport_channels_not_identical")
    if len(filters) >= 1:
        report["first_filter_tx_count"] = filters[0]["tx"]
        report["first_filter_rx_count"] = filters[0]["rx"]
    if len(filters) >= 2:
        report["second_filter_tx_count"] = filters[1]["tx"]
        report["second_filter_rx_count"] = filters[1]["rx"]
    if len(filters) == 2:
        if [(x["tx"], x["rx"], x["d2"]) for x in filters] != [
                (1, 0, 1), (1, 13, 1)]:
            problems.append("negative_positive_lifetime_tx_rx_d2_mismatch")
    if not problems:
        report["status"] = "B3A70_ISOLATED_FILTER_CHANNEL_PASS"
        report["protocol_mode"] = "CAN_PS_via_internal_CAN"
        report["baud_bps"] = "125000"
    report["failures"] = sorted(set(problems))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-log", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        source = args.native_log
        if source.is_symlink() or not source.is_file():
            raise ValueError("missing log")
        size = source.stat().st_size
        if size < 1 or size > MAX_BYTES:
            raise ValueError("unsafe log size")
        with source.open("r", encoding="utf-8", errors="replace") as stream:
            result = analyze(stream)
    except (OSError, ValueError, UnicodeError):
        print("B3A70: SOURCE_UNAVAILABLE_OR_INVALID", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    print("Original VIDA filter/channel/ReadVin: NOT_VERIFIED")
    return 0 if result["status"] == "B3A70_ISOLATED_FILTER_CHANNEL_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
