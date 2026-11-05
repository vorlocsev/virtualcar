#!/usr/bin/env python3
"""Source-local J2534 device Open/Close lifecycle check, no ECU payload output.

A process label, PID, and a syntactically complete transport reply do not
establish one open J2534 device. A client may reconnect in the same process.
This audit is conservative: it does not execute PassThru or a client.
"""
from collections import Counter
import re

FORMAT = "virtualcar-native-j2534-device-lifecycle-v1"
MAX_LINES = 50000
MAX_BYTES = 4 * 1024 * 1024
PREFIX = re.compile(r"^\[PID=([0-9a-fA-F]{8}) ([^\]\r\n]{1,80})\] (.*)$")
OPEN = "PassThruOpen -> device 1"
CLOSE = "PassThruClose"
# These messages should occur only after a successful J2534 Open. A
# failed PassThruConnect can still be logged inside an open device.
TRAFFIC = (
    "J2534 Connect result protocol/flags/baud/status (BE)",
    "TX context channel/protocol/flags/baud/time-us (BE)",
    "RX context channel/protocol/status/baud/time-us (BE)",
    "TX (app request)",
    "PassThruReadMsgs -> delivered",
    "PassThruReadMsgs timeout:",
    "PassThruDisconnect channel (BE)",
    "PassThruDisconnect",
)


def audit(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid_native_lifecycle_source")
    lines = source.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("too_many_native_lifecycle_lines")
    state = {}
    host_labels = {}
    errors = Counter()
    open_total = close_total = 0
    scoped_lines = 0
    for line in lines:
        match = PREFIX.fullmatch(line)
        if match is None:
            if line.startswith("=== SECTORV VIRTUALCAR SESSION "):
                errors["explicit_session_separator"] += 1
            continue
        pid, host, text = match.groups()
        scoped_lines += 1
        if pid not in state:
            state[pid] = False
            host_labels[pid] = host
        elif host_labels[pid] != host:
            errors["pid_process_label_changed"] += 1
        if text == OPEN:
            open_total += 1
            if state[pid]:
                errors["nested_open"] += 1
            state[pid] = True
        elif text == CLOSE:
            close_total += 1
            if not state[pid]:
                errors["close_without_open"] += 1
            state[pid] = False
        elif text.startswith(TRAFFIC) and not state[pid]:
            errors["traffic_outside_open"] += 1
    if any(state.values()):
        errors["open_not_closed"] += sum(state.values())
    if not scoped_lines:
        status = "no_native_process_markers"
    elif len(state) != 1:
        status = "multiple_native_process_scopes"
    elif open_total == 0 and close_total == 0:
        status = "no_explicit_device_lifecycle"
    elif open_total > 1 and not errors:
        status = "multiple_closed_device_cycles"
    elif errors:
        status = "invalid_or_incomplete_device_lifecycle"
    elif open_total == 1 and close_total == 1:
        status = "single_closed_device_cycle"
    else:
        status = "invalid_or_incomplete_device_lifecycle"
    return {
        "format": FORMAT,
        "source_scope": "one_untrusted_native_text_source",
        "read_only": True,
        "contains_payload_data": False,
        "process_scope_count": len(state),
        "device_open_count": open_total,
        "device_close_count": close_total,
        "status": status,
        "single_closed_device_cycle_verified": (
            status == "single_closed_device_cycle"),
        "error_counts": dict(sorted(errors.items())),
        "client_process_identity_verified": False,
        "client_acceptance_verified": False,
        "ecu_enumeration_verified": False,
        "limitations": [
            "A native PID/hostname is untrusted source text, not executable attestation.",
            "A closed J2534 device cycle does not prove that the client accepted VIN or any ECU.",
            "Multiple Open/Close cycles in one PID are not one uninterrupted diagnostic device session.",
            "Only allowlisted lifecycle counts are exported; no raw source or identifiers.",
        ],
    }
