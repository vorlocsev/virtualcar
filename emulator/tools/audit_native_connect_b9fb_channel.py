#!/usr/bin/env python3
"""Correlate B9FB TX with a PRIOR successful J2534 Connect on its channel.

The DLL's aggregate Connect result alone omits channel ID. A newly
emitted metadata marker supplies channel/protocol/flags/baud and must
be followed by a matching successful result before a later B9FB app TX.
This is local text-log transport provenance only, not authenticated
client execution, a real ECU, or verified vehicle identity.
"""
from collections import Counter
import re

FORMAT = "virtualcar-native-b9fb-connect-channel-binding-v1"
MAX_BYTES = 4 * 1024 * 1024
MAX_LINES = 50000
PREFIX = re.compile(r"^\[PID=([0-9a-fA-F]{8}) ([^\]\r\n]{1,80})\] (.*)$")
HEX = re.compile(r"[0-9a-fA-F]{2}\Z")
BIND = "J2534 Connect bound channel/protocol/flags/baud (BE)"
RESULT = "J2534 Connect result protocol/flags/baud/status (BE)"
TX_CONTEXT = "TX context channel/protocol/flags/baud/time-us (BE)"
TX_APP = "TX (app request)"
DISCONNECT = "PassThruDisconnect channel (BE)"


def _words(text, size):
    parts = text.strip().split(" ")
    if len(parts) != size or any(HEX.fullmatch(x) is None for x in parts):
        return None
    raw = bytes(int(part, 16) for part in parts)
    return tuple(int.from_bytes(raw[i:i + 4], "big")
                 for i in range(0, len(raw), 4))


def _bytes(text):
    parts = text.strip().split(" ")
    if not parts or any(HEX.fullmatch(x) is None for x in parts):
        return None
    return bytes(int(part, 16) for part in parts)


def audit(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid_connect_binding_source")
    lines = source.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("connect_binding_line_limit")
    state = {}
    labels = {}
    error_counts = Counter()
    result_counts = Counter()
    b9fb_checks = []
    bind_events = 0
    for line in lines:
        matched = PREFIX.fullmatch(line)
        if matched is None:
            continue
        pid, label, body = matched.groups()
        if pid not in state:
            state[pid] = {"pending": None, "connected": {}, "tx": None}
            labels[pid] = label
        elif labels[pid] != label:
            error_counts["process_label_changed"] += 1
        current = state[pid]
        if body == "PassThruOpen -> device 1":
            current["pending"] = None
            current["connected"].clear()
            current["tx"] = None
        elif body == "PassThruClose":
            if current["pending"] is not None:
                error_counts["incomplete_connect_result"] += 1
            current["pending"] = None
            current["connected"].clear()
            current["tx"] = None
        elif body.startswith(BIND):
            bind_events += 1
            values = _words(body[len(BIND):], 16)
            if values is None or values[0] == 0:
                error_counts["malformed_connect_channel_marker"] += 1
                current["pending"] = None
            else:
                if current["pending"] is not None:
                    error_counts["unpaired_connect_channel_marker"] += 1
                current["pending"] = values
        elif body.startswith(RESULT):
            words = _words(body[len(RESULT):], 16)
            if words is None:
                error_counts["malformed_connect_result"] += 1
                current["pending"] = None
                continue
            protocol, flags, baud, status = words
            if status == 0:
                result_counts["success"] += 1
                if current["pending"] is None:
                    result_counts["success_without_channel_marker"] += 1
                else:
                    channel, bp, bf, bb = current["pending"]
                    if (bp, bf, bb) != (protocol, flags, baud):
                        error_counts["bound_result_mode_mismatch"] += 1
                    elif channel in current["connected"]:
                        error_counts["reused_live_channel"] += 1
                    else:
                        current["connected"][channel] = (protocol, baud)
                        result_counts["successful_channel_bindings"] += 1
            elif current["pending"] is not None:
                error_counts["bound_marker_with_failed_connect"] += 1
            current["pending"] = None
        elif body.startswith(DISCONNECT):
            words = _words(body[len(DISCONNECT):], 4)
            if words is None:
                error_counts["malformed_disconnect_channel"] += 1
            else:
                current["connected"].pop(words[0], None)
                current["tx"] = None
        elif body.startswith(TX_CONTEXT):
            words = _words(body[len(TX_CONTEXT):], 20)
            if words is None:
                error_counts["malformed_tx_channel_context"] += 1
                current["tx"] = None
            else:
                current["tx"] = words
        elif body.startswith(TX_APP):
            payload = _bytes(body[len(TX_APP):])
            context = current["tx"]
            current["tx"] = None
            if (payload is None or len(payload) < 8
                    or int.from_bytes(payload[:4], "big") != 0x000FFFFE
                    or payload[4] != 0xCB or payload[6:8] != b"\xB9\xFB"
                    or payload[5] not in (0x40, 0x50)):
                continue
            if context is None:
                b9fb_checks.append(False)
                continue
            channel, protocol, _flags, baud, _clock = context
            expected_baud = 125000 if payload[5] == 0x40 else 500000
            b9fb_checks.append(
                protocol == 5 and baud == expected_baud
                and current["connected"].get(channel) == (protocol, baud))
    if any(x["pending"] is not None for x in state.values()):
        error_counts["incomplete_connect_result"] += sum(
            x["pending"] is not None for x in state.values())
    if error_counts:
        status = "invalid_connect_channel_evidence"
    elif len(state) > 1:
        status = "multiple_native_process_scopes"
    elif not b9fb_checks:
        status = "no_b9fb_app_request"
    elif len(b9fb_checks) != 1:
        status = "multiple_b9fb_requests_not_one_handoff"
    elif b9fb_checks[0]:
        status = "one_b9fb_bound_to_prior_successful_channel_connect"
    elif not bind_events:
        status = "legacy_no_channel_connect_binding_metadata"
    else:
        status = "b9fb_not_bound_to_prior_successful_channel_connect"
    return {
        "format": FORMAT,
        "read_only": True,
        "contains_payload_data": False,
        "source_scope": "untrusted_native_text_log",
        "native_process_scope_count": len(state),
        "connect_channel_marker_count": bind_events,
        "connect_success_count": result_counts["success"],
        "connect_success_without_channel_marker_count":
            result_counts["success_without_channel_marker"],
        "successful_channel_bindings_count":
            result_counts["successful_channel_bindings"],
        "b9fb_request_count": len(b9fb_checks),
        "status": status,
        "one_b9fb_bound_to_prior_successful_channel_connect": (
            status == "one_b9fb_bound_to_prior_successful_channel_connect"),
        "error_counts": dict(sorted(error_counts.items())),
        "client_executable_identity_verified": False,
        "client_accepted_b9fb_verified": False,
        "vehicle_identity_verified": False,
        "limitations": [
            "J2534 channel IDs and event order are derived from untrusted local text, not client process authentication.",
            "A successful native Connect on the matching channel does not prove a client displayed the vehicle.",
            "Older native logs without explicit channel binding cannot independently attribute aggregate Connect OK.",
            "No source PID, executable name, VIN, CAN message, DID, ECU part number or private timestamp is exported.",
        ],
    }
