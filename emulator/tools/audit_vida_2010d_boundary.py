#!/usr/bin/env python3
"""Conservative offline audit of the older two-bracket VIDA 2010D text log.

Example input header: [J2534ChannelMana][VehCom] PassThruWriteMsgs...
This variant has no visible thread identifier, so cross-line channel/command
attribution is only chronological and must NOT imply successful CAN delivery.
All output fields are fixed or allowlisted; no original payload is exported.
"""
import argparse
from collections import Counter
import html
import json
from pathlib import Path
import re
import sys

FORMAT = "virtualcar-vida-2010d-d2-boundary-v1"
MAX_BYTES = 2 * 1024 * 1024
MAX_LINES = 15000
TIME = re.compile(r"^(\d{2}):(\d{2}):(\d{2}),(\d{3})\s+")
HEADER = re.compile(
    r"^(?:\d{2}:\d{2}:\d{2},\d{3}\s+)?\[([^\]\r\n]{1,48})\]"
    r"\[([^\]\r\n]{1,48})\]\s+(.+)$")
REQUEST = re.compile(
    r"^VehComm request:\s*Ecu\s+'(40|50)',\s*Message\s+'(B9FB|B9F0|B9FC|A3)'",
    re.IGNORECASE)
WRITE = re.compile(r"^PassThruWriteMsgs\((\d+),\s*PASSTHRU_MSG,\s*(\d+),\s*(\d+)\)", re.I)
WRITE_ERROR = re.compile(
    r"^J2534 function:\s*passThruWriteMsgs failed with return value:(ERR_[A-Z_]+)\b", re.I)
ANY_ERROR = re.compile(
    r"^J2534 function:\s*passThru(?:Open|Close|Disconnect|Ioctl(?:_[A-Za-z]+)?)"
    r" failed with return value:(ERR_[A-Z_]+)\b", re.I)
PACKET = re.compile(r"^--->\s*\(0\)\s*(.*)$")
RX_PACKET = re.compile(r"^<---\s*\(\d+\)\s*(.*)$")
HEX = re.compile(r"^[0-9A-Fa-f]{2}$")
ALLOWED_ERRORS = frozenset({
    "ERR_DEVICE_NOT_CONNECTED", "ERR_DEVICE_IN_USE", "ERR_FAILED",
    "ERR_INVALID_DEVICE_ID", "ERR_TIMEOUT", "ERR_BUFFER_EMPTY",
})


def _time(line):
    m = TIME.match(line)
    if m is None:
        return None
    h, minute, second, millis = map(int, m.groups())
    if h > 23 or minute > 59 or second > 59:
        return None
    return ((h * 60 + minute) * 60 + second) * 1000 + millis


def _delta(after, before):
    if after is None or before is None:
        return None
    value = (after - before) % 86400000
    return value if value <= 60000 else None


def _safe_error(code):
    upper = code.upper()
    return upper if upper in ALLOWED_ERRORS else "other_error"


def _dump_matches(data, target, service):
    tokens = [x.strip() for x in data.rstrip(",").split(",")]
    if len(tokens) != 12 or not all(HEX.fullmatch(x) for x in tokens):
        return False
    values = bytes(int(x, 16) for x in tokens)
    expected = bytes.fromhex("00 0F FF FE CB") + bytes((int(target, 16),))
    return (service.startswith("B9") and values[:7] == expected + b"\xB9"
            and values[7] == int(service[2:], 16))


def audit(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("source_size")
    lines = source.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("too_many_lines")
    results = []
    active = None
    errors = Counter()
    ignore = 0
    for number, raw in enumerate(lines, 1):
        line = html.unescape(raw)
        m = HEADER.match(line)
        if m is None:
            ignore += 1
            continue
        category, second, message = m.groups()
        # The extended three-bracket VIDA format is already audited by
        # audit_j2534_discovery.py. Do not guess which thread is the owner.
        if category.strip() not in ("J2534ChannelMana", "DiagConnection"):
            ignore += 1
            continue
        if second.strip() != "VehCom":
            ignore += 1
            continue
        now = _time(line)
        request = REQUEST.match(message)
        if category.strip() == "DiagConnection" and request:
            if active is not None:
                active["next_request_delta_ms"] = _delta(now, active.pop("_clock"))
                results.append(active)
            target, service = request.groups()
            active = {
                "target": "0x" + target.upper(),
                "service": service.upper(),
                "source_line": number,
                "write_call_observed": False,
                "write_failure_code": None,
                "request_dump_matches": False,
                "rx_dump_lines_unverified": 0,
                "next_request_delta_ms": None,
                "_clock": now,
            }
            continue
        if category.strip() != "J2534ChannelMana":
            continue
        fault = ANY_ERROR.match(message)
        if fault:
            errors[_safe_error(fault.group(1))] += 1
        if active is None:
            continue
        if WRITE.match(message):
            active["write_call_observed"] = True
            continue
        fault = WRITE_ERROR.match(message)
        if fault:
            if active["write_call_observed"]:
                active["write_failure_code"] = _safe_error(fault.group(1))
                active["write_failure_offset_ms"] = _delta(now, active["_clock"])
            else:
                errors["unbound_write_failure"] += 1
            continue
        dumped = PACKET.match(message)
        if dumped:
            active["request_dump_matches"] |= _dump_matches(
                dumped.group(1), active["target"][2:], active["service"])
            continue
        if RX_PACKET.match(message):
            active["rx_dump_lines_unverified"] += 1
    if active is not None:
        active.pop("_clock")
        results.append(active)
    for item in results:
        item["outcome"] = ("write_failed" if item["write_failure_code"] else
                           "write_attempt_result_unknown" if item["write_call_observed"] else
                           "request_only")
        item["j2534_write_success_verified"] = False
        item["ecu_response_verified"] = False
        item["client_acceptance_verified"] = False
    return {
        "format": FORMAT,
        "read_only": True,
        "contains_payload_data": False,
        "attempts": results,
        "counts": dict(sorted(Counter(a["outcome"] for a in results).items())),
        "adapter_error_counts": dict(sorted(errors.items())),
        "ignored_no_matching_vida_header": ignore,
        "thread_binding_verified": False,
        "limitations": [
            "The two-bracket VIDA 2010D format lacks a thread ID; all cross-line associations are chronological.",
            "An arrow dump after a failed write is not evidence of transmitted CAN data.",
            "A received-dump line without matched channel/timing is not a validated ECU response.",
            "No B9FB field parser, identity, checksum, or ECU acceptance is inferred.",
            "next_request_delta_ms is measured between request log lines, not after the last RX frame.",
            "Other client and hardware runs cannot be joined to this log by wall clock alone.",
            "No original lines, device serials, VIN, payload, host path or request operands are exported.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("log", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.log.resolve() == args.output.resolve():
            raise ValueError("same_path")
        if args.log.stat().st_size > MAX_BYTES:
            raise ValueError("too_large")
        report = audit(args.log.read_text(encoding="utf-8-sig", errors="replace"))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
    except (OSError, UnicodeError, ValueError):
        print("Legacy VIDA audit refused input or output (details withheld)",
              file=sys.stderr)
        return 2
    print("PASS: legacy VIDA write boundary audited; ECU response unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
