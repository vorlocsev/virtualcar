#!/usr/bin/env python3
"""Classify private local VirtualCar D2 request metadata, never raw vehicle data.

A group is one textual native logger process prefix; PID reuse means groups
are NOT authenticated sessions. No raw line or PID is exported.
"""
from collections import Counter
from pathlib import Path
import argparse
import json
import re

SCHEMA = "virtualcar-b3a318-p2-ecu-requests-v1"
MAX_ROWS = 150000  # cap on relevant D2 events, not unrelated native log rows
MAX_LINE = 512
MAX_SOURCE_BYTES = 256 * 1024 * 1024  # 256 MiB; bounded full-source scan
MAX_SOURCE_ROWS = 6000000
PREFIX = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([A-Za-z0-9_.-]{1,48})\] ")
HEX_BYTE = re.compile(r"^[0-9A-Fa-f]{2}$")
REQUEST = "P2 D2 request target/opcode/baud/flags (BE) "
NO_ECU_FIXTURE = re.compile(
    r"^P2 D2 command: no recorded ECU fixture for target CB ([0-9A-Fa-f]{2}) B9 (F0|FB)$")
NO_VALIDATED_FIXTURE = re.compile(
    r"^P2 D2 read command: no validated response fixture CB ([0-9A-Fa-f]{2}) B9 (F0|FB)$")
A3_NO_REPLY = "P2 D2 CEM A3/A6: no verified response implementation"
STAGED_B9FB = "P2 D2 read-only recorded frames staged CB 50 B9 FB"


def _metadata(event):
    if not event.startswith(REQUEST):
        return None
    fields = event[len(REQUEST):].strip().split()
    if len(fields) != 16 or any(HEX_BYTE.fullmatch(p) is None for p in fields):
        return None
    buf = bytes.fromhex("".join(fields))
    target, opcode, baud, flags = (
        int.from_bytes(buf[i:i+4], "big") for i in (0, 4, 8, 12)
    )
    # Valid byte target, source-defined D2 read opcodes only.
    if target > 255 or opcode not in (0xF0, 0xFB):
        return None
    if not 0 < baud <= 1000000:
        return None
    return target, opcode, baud, flags


def analyze(lines):
    groups = {}
    oversized = 0
    malformed = 0
    count = 0
    for line in lines:
        if count >= MAX_ROWS:
            raise ValueError("bounded_native_rows_exceeded")
        count += 1
        if len(line) > MAX_LINE:
            oversized += 1
            continue
        m = PREFIX.match(line.lstrip("\ufeff"))
        if not m:
            continue
        # PID/name never included in output. A PID may be reused; group is
        # merely a segment in this supplied bounded file, not a real session.
        group_key = m.group(1) + "\0" + m.group(2)
        event = line.lstrip("\ufeff")[m.end():].strip()
        if not (event.startswith(REQUEST) or event.startswith("P2 D2 ")):
            continue
        g = groups.setdefault(group_key, {
            "requests": Counter(), "no_recorded": Counter(),
            "no_validated": Counter(), "a3_no_reply": 0,
            "staged_b9fb_50": 0,
        })
        if event.startswith(REQUEST):
            data = _metadata(event)
            if data is None:
                malformed += 1
            else:
                target, opcode, baud, _flags = data
                g["requests"][(target, opcode, baud)] += 1
            continue
        if event == A3_NO_REPLY:
            g["a3_no_reply"] += 1
            continue
        if event == STAGED_B9FB:
            g["staged_b9fb_50"] += 1
            continue
        for regex, key in ((NO_ECU_FIXTURE, "no_recorded"),
                           (NO_VALIDATED_FIXTURE, "no_validated")):
            v = regex.fullmatch(event)
            if v:
                g[key][(int(v.group(1), 16), int(v.group(2), 16))] += 1
                break
    reported = []
    for index, g in enumerate(groups.values(), 1):
        requests = g["requests"]
        f0 = Counter()
        fb = 0
        route_baud = Counter()
        for (target, op, baud), n in requests.items():
            if op == 0xF0:
                f0[target] += n
                route_baud[(target, baud)] += n
            if op == 0xFB:
                fb += n
        reported.append({
            "local_group": index,
            "group_is_verified_session": False,
            "b9f0_request_count": sum(f0.values()),
            "b9f0_target_count": len(f0),
            "b9f0_targets": [{"node": f"0x{t:02X}", "count": f0[t]}
                             for t in sorted(f0)],
            "b9f0_target_baud": [{"node": f"0x{t:02X}", "baud_bps": b,
                                  "count": n}
                                 for (t, b), n in sorted(route_baud.items())],
            "b9f0_no_recorded_fixture_count": sum(
                n for (target, op), n in g["no_recorded"].items() if op == 0xF0),
            "b9f0_no_validated_fixture_count": sum(
                n for (target, op), n in g["no_validated"].items() if op == 0xF0),
            "b9fb_request_count": fb,
            "b9fb_50_staged_count": g["staged_b9fb_50"],
            "a3_a6_no_verified_response_count": g["a3_no_reply"],
            "b9f0_response_delivered_verified": False,
            "ecu_identity_accepted_verified": False,
        })
    return {
        "schema_version": SCHEMA,
        "scope": "bounded_native_logger_groups_only",
        "group_count": len(reported),
        "groups": reported,
        "malformed_request_metadata": malformed,
        "oversized_rows_ignored": oversized,
        "cross_process_correlation_verified": False,
        "sectorv_ecu_identification_accepted": False,
        "oem_cem_response_provenance_verified": False,
        "limitations": [
            "Source PID/process groups are not authenticated client sessions and may be recycled.",
            "B9F0 request or missing fixture is not proof of a delivered or decoded ECU response.",
            "B9FB staged does not prove a VIN accepted by original SectorV or VIDA.",
            "No raw VIN, CAN payload, source PID/process name, flags, key or local path exported.",
        ],
    }


def _relevant_rows(source, scan):
    """Stream the ENTIRE bounded native log, keeping only D2 events.

    Do not truncate the source, print its contents, or copy event payloads.
    Discard unrelated logging before the 150k event cap. Preserve the
    oversized D2 event counter without keeping oversized source lines.
    """
    for line in source:
        scan["source_rows_scanned"] += 1
        if scan["source_rows_scanned"] > MAX_SOURCE_ROWS:
            raise ValueError("bounded_source_rows_exceeded")
        prefix = line[:MAX_LINE].lstrip("\ufeff")
        m = PREFIX.match(prefix)
        if m is None or not prefix[m.end():].startswith("P2 D2 "):
            continue
        scan["relevant_d2_rows_seen"] += 1
        if len(line) > MAX_LINE:
            # Counts as ignored by analyze(); emit no actual source bytes.
            yield "X" * (MAX_LINE + 1)
        else:
            yield line


def main(argv=None):
    p = argparse.ArgumentParser(description="Privacy-safe local D2 ECU request evidence")
    p.add_argument("--native", required=True, help="Read-only bounded native logger text")
    args = p.parse_args(argv)
    path = Path(args.native)
    try:
        if not path.is_file() or path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("invalid_or_excessive_input")
        scan = {"source_rows_scanned": 0, "relevant_d2_rows_seen": 0}
        with path.open("r", encoding="utf-8-sig", errors="replace") as stream:
            report = analyze(_relevant_rows(stream, scan))
        report["complete_source_scan"] = True
        report["source_scan_counts"] = scan
    except (OSError, ValueError):
        p.exit(2, "ERROR: invalid_or_unreadable_bounded_input\n")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
