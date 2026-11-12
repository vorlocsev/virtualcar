#!/usr/bin/env python3
"""Classify owner-local D2 request/result metadata without exporting vehicle data.

Input is native VirtualCar text already bounded to one independently validated
append interval (e.g. B3A47). This module does not attest to original VIDA or
read an ECU. It never prints raw lines, CAN bytes, VIN, paths, PIDs or hosts.
"""
from collections import Counter
import re

SCHEMA = "virtualcar-b3a50-d2-route-matrix-v1"
REQUEST = "P2 D2 request target/opcode/baud/flags (BE)"
RESULTS = {
    "strict_bus_rejected": "P2 D2 strict route rejected (no fixture emitted)",
    "no_validated_fixture": "P2 D2 read command: no validated response fixture",
    "no_target_fixture": "P2 D2 command: no recorded ECU fixture for target",
    "recorded_frames_staged": "P2 D2 read-only recorded frames staged",
}
PREFIX = re.compile(r"^\[PID=[0-9A-Fa-f]{8} [A-Za-z0-9_.-]{1,48}\] ")
HEX_BYTE = re.compile(r"^[0-9A-Fa-f]{2}$")
TARGET = {0x40: "CEM_40", 0x50: "CEM_50"}
COMMAND = {0xFB: "B9FB", 0xF0: "B9F0", 0xFC: "B9FC"}
BAUD = {10400: "10400", 125000: "125000", 250000: "250000", 500000: "500000"}
MAX_LINE = 512
MAX_GAP = 24
MAX_ROWS = 250000


def _bytes(event, label, n):
    if not event.startswith(label + " "):
        return None
    words = event[len(label) + 1:].strip().split()
    if len(words) != n or any(not HEX_BYTE.fullmatch(w) for w in words):
        return None
    return bytes(int(w, 16) for w in words)


def _request(event):
    data = _bytes(event, REQUEST, 16)
    if data is None:
        return None
    target, cmd, baud, _flags = (int.from_bytes(data[i:i+4], "big")
                                 for i in (0, 4, 8, 12))
    return (target, cmd, baud) if target in TARGET and cmd in COMMAND else None


def _outcome(event, label):
    data = _bytes(event, label, 4)
    if (data is None or data[0] != 0xCB or data[2] != 0xB9 or
            data[1] not in TARGET or data[3] not in COMMAND):
        return None
    return data[1], data[3]


def analyze(lines):
    requests, results, paired = Counter(), Counter(), Counter()
    pending = {}  # exact host+PID string for local pairing only; never exported
    invalid_request = invalid_result = unpaired = ambiguous = 0
    for pos, line in enumerate(lines):
        if pos >= MAX_ROWS:
            raise ValueError("bounded_native_lines_exceeded")
        if len(line) > MAX_LINE:
            continue
        match = PREFIX.match(line)
        if not match:
            continue
        local_key = line[:match.end()]
        event = line[match.end():]
        if event.startswith(REQUEST):
            record = _request(event)
            if record is None:
                invalid_request += 1
            else:
                requests[record] += 1
                pending.setdefault(local_key, []).append((pos, record))
            continue
        outcome = next((kind for kind, marker in RESULTS.items()
                        if event.startswith(marker)), None)
        if outcome is None:
            continue
        results[outcome] += 1
        address = _outcome(event, RESULTS[outcome])
        if address is None:
            invalid_result += 1
            unpaired += 1
            continue
        choices = [x for x in pending.get(local_key, ())
                   if 0 < pos - x[0] <= MAX_GAP and x[1][:2] == address]
        if len(choices) != 1:
            unpaired += 1
            ambiguous += len(choices) > 1
            continue
        selected = choices[0]
        pending[local_key].remove(selected)
        target, cmd, baud = selected[1]
        paired[(target, cmd, baud, outcome)] += 1

    modes = [{"target": TARGET[t], "command": COMMAND[c],
              "baud_bps": BAUD.get(b, "other"), "count": n}
             for (t, c, b), n in sorted(requests.items())]
    paired_modes = []
    for (t, c, b, kind), n in sorted(paired.items()):
        expected = 125000 if t == 0x40 else 500000
        paired_modes.append({
            "target": TARGET[t], "command": COMMAND[c],
            "baud_bps": BAUD.get(b, "other"), "outcome": kind,
            "count": n, "differs_from_base_fixture_baud": b != expected,
        })
    total = sum(requests.values())
    matched = sum(paired.values())
    return {
        "schema_version": SCHEMA,
        "scope": "bounded_native_logger_lines_not_client_attestation",
        "observed_d2_request_count": total,
        "per_request_modes": modes,
        "outcome_marker_counts": {name: results[name] for name in RESULTS},
        "same_logger_prefix_paired_outcomes": matched,
        "unpaired_requests": total - matched,
        "unpaired_outcomes": unpaired,
        "ambiguous_pairings": ambiguous,
        "malformed_request_metadata": invalid_request,
        "malformed_outcome_metadata": invalid_result,
        "paired_route_outcomes": paired_modes,
        "original_vida_client_verified": False,
        "genuine_ecu_rx_verified": False,
        "vin_accepted_verified": False,
        "limitations": [
            "Pairing is bounded to 24 native logger lines sharing a textual PID+host prefix.",
            "Same logger prefix is not proof of loaded original VIDA DLL or OEM RX.",
            "Base fixture 0x40=125k, 0x50=500k is an emulator assumption, not MY2009 OEM routing.",
            "No raw vehicle identifier, CAN payload, PID, hostname, local path or unknown flag is exported.",
        ],
    }
