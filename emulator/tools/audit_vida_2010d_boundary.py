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

# Legacy VIDA2010D logs include API preparation in plain-text form. The
# arguments to Connect are an API log claim, not a recorded success status.
_NUMBER = r"(?:0[xX][0-9A-Fa-f]{1,8}|[0-9]{1,10})"
CONNECT_CALL = re.compile(
    r"^PassThruConnect\(\s*([0-9]{1,10})\s*,\s*(" + _NUMBER
    + r")\s*,\s*(" + _NUMBER + r")\s*,\s*([0-9]{1,10})"
    + r"\s*,\s*([0-9]{1,10})\s*\)\s*$", re.I)
CONFIG_RATE = re.compile(
    r"^PassThruIoctl SET_CONFIG DATA_(?:RATA|RATE)=([0-9]{1,10}),"
    r"\s*LOOPBACK=([0-9]{1,10})\s+BIT_SAMPLE_POINT=([0-9]{1,10})\s*$", re.I)
CONFIG_STMIN = re.compile(
    r"^PassThruIoctl SET_CONFIG CAN_XON_XOFF_STMIN=([0-9]{1,10})\s*$", re.I)
FILTER_START = re.compile(
    r"^Start J2534 message filter ID [0-9]{1,10} on channel ([0-9]{1,10})\s*$", re.I)
PERIODIC_START = re.compile(
    r"^Start J2534 periodic message channelId:\s*([0-9]{1,10})\s+pMsgId:\s*[0-9]{1,10}\s*$", re.I)
STAGE_ORDER = ("connect_call", "set_config_rate", "set_config_stmin",
               "start_filter", "start_periodic", "write_call")


def _uint32(text):
    number = int(text, 16 if text.lower().startswith("0x") else 10)
    return number if number <= 0xFFFFFFFF else None


def _preflight():
    return {
        "connect_call_observed": False,
        "connect_protocol_matches_published_sample": False,
        "connect_flags_match_published_sample": False,
        "connect_declared_baud_bps": None,
        "set_config_rate_observed": False,
        "set_config_rate_matches_connect": None,
        "set_config_loopback_disabled": False,
        "set_config_sample_point_68": False,
        "set_config_stmin_40": False,
        "filter_start_observed": False,
        "filter_channel_matches_connect": None,
        "periodic_start_observed": False,
        "periodic_channel_matches_connect": None,
        "write_channel_matches_connect": None,
        "observed_stage_order": [],
        "matches_published_sample_call_order": False,
        "connect_success_verified": False,
        "filter_effect_verified": False,
        "periodic_effect_verified": False,
    }


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
                "preflight": _preflight(),
                "_connect_channel": None,
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
        pre = active["preflight"]
        candidate = CONNECT_CALL.fullmatch(message)
        if candidate:
            _, proto, flags, baud, channel = candidate.groups()
            decoded = [_uint32(x) for x in (proto, flags, baud, channel)]
            if None in decoded:
                errors["invalid_preflight_connect_metadata"] += 1
            else:
                protocol_id, flag_word, bitrate, connected_channel = decoded
                active["_connect_channel"] = connected_channel
                pre["connect_call_observed"] = True
                pre["connect_protocol_matches_published_sample"] = (
                    protocol_id == 0x10000001)
                pre["connect_flags_match_published_sample"] = (
                    flag_word == 0x20000100)
                pre["connect_declared_baud_bps"] = (
                    bitrate if bitrate in (125000, 500000) else None)
                pre["observed_stage_order"].append("connect_call")
            continue
        cfg = CONFIG_RATE.fullmatch(message)
        if cfg:
            bitrate, loopback, sample_point = (_uint32(x) for x in cfg.groups())
            if None in (bitrate, loopback, sample_point):
                errors["invalid_preflight_config_metadata"] += 1
            else:
                pre["set_config_rate_observed"] = True
                pre["set_config_rate_matches_connect"] = (
                    bitrate == pre["connect_declared_baud_bps"]
                    if pre["connect_declared_baud_bps"] is not None else None)
                pre["set_config_loopback_disabled"] = loopback == 0
                pre["set_config_sample_point_68"] = sample_point == 68
                pre["observed_stage_order"].append("set_config_rate")
            continue
        stmin = CONFIG_STMIN.fullmatch(message)
        if stmin:
            value = _uint32(stmin.group(1))
            if value is None:
                errors["invalid_preflight_config_metadata"] += 1
            else:
                pre["set_config_stmin_40"] = value == 40
                pre["observed_stage_order"].append("set_config_stmin")
            continue
        filt = FILTER_START.fullmatch(message)
        if filt:
            channel = _uint32(filt.group(1))
            if channel is None:
                errors["invalid_preflight_filter_metadata"] += 1
            else:
                pre["filter_start_observed"] = True
                pre["filter_channel_matches_connect"] = (
                    channel == active["_connect_channel"]
                    if active["_connect_channel"] is not None else None)
                pre["observed_stage_order"].append("start_filter")
            continue
        periodic = PERIODIC_START.fullmatch(message)
        if periodic:
            channel = _uint32(periodic.group(1))
            if channel is None:
                errors["invalid_preflight_periodic_metadata"] += 1
            else:
                pre["periodic_start_observed"] = True
                pre["periodic_channel_matches_connect"] = (
                    channel == active["_connect_channel"]
                    if active["_connect_channel"] is not None else None)
                pre["observed_stage_order"].append("start_periodic")
            continue
        write = WRITE.match(message)
        if write:
            channel = _uint32(write.group(1))
            if channel is None:
                errors["invalid_preflight_write_metadata"] += 1
                continue
            active["write_call_observed"] = True
            pre["write_channel_matches_connect"] = (
                channel == active["_connect_channel"]
                if active["_connect_channel"] is not None else None)
            pre["observed_stage_order"].append("write_call")
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
        pre = item["preflight"]
        pre["matches_published_sample_call_order"] = (
            tuple(pre["observed_stage_order"]) == STAGE_ORDER
            and pre["connect_protocol_matches_published_sample"]
            and pre["connect_flags_match_published_sample"]
            and pre["set_config_rate_matches_connect"] is True
            and pre["set_config_loopback_disabled"]
            and pre["set_config_sample_point_68"]
            and pre["set_config_stmin_40"]
            and pre["filter_channel_matches_connect"] is True
            and pre["periodic_channel_matches_connect"] is True
            and pre["write_channel_matches_connect"] is True)
        item.pop("_connect_channel", None)
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
            "Connect, filter and periodic entries show logged API attempts, not successful return codes.",
            "Published call order is one historical DiCE sample and NOT a requirement for Virtual Car clients.",
            "DATA_RATA is treated as the historical log label, not evidence of a different J2534 parameter.",
            "A channel match associates explicit IDs inside a threadless excerpt but does not prove synchronous execution.",
            "Unobserved preparation calls may reflect a truncated log rather than a missing adapter capability.",
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
