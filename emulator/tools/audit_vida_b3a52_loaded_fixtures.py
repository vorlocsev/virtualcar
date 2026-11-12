#!/usr/bin/env python3
"""Read-only B3A52 historic native loaded D2 fixture classification.

Input rows MUST be from a separate, integrity-verified frozen native log
prefix and its saved B3A47 append window. This helper neither opens private
files nor prints paths, PID, VIN, CAN bytes, or source hashes.
"""
from collections import Counter
import re

SCHEMA = "virtualcar-b3a52-native-loaded-d2-fixtures-v1"
MAX_LINE = 512
MAX_FIXTURES = 14
PREFIX = re.compile(r"^\[PID=[0-9a-fA-F]{8} [A-Za-z0-9_.-]{1,48}\] ")
ACTIVE = "Active INI: "
FIXTURE = "P2 fixture target/opcode/response-id/frame-count (BE) "
D2_REQUEST = "P2 D2 request target/opcode/baud/flags (BE) "
HEX_BYTE = re.compile(r"^[0-9A-Fa-f]{2}$")
INI_NAME = re.compile(r"(?:^|[/\\])virtualcar\.ini\Z", re.I)
BASE_ORDER = [(0x40, 0xFB), (0x40, 0xF0), (0x50, 0xFB),
              (0x50, 0xF0), (0x40, 0xFC), (0x50, 0xFC)]


def _metadata(event, label):
    if not event.startswith(label):
        return None
    parts = event[len(label):].strip().split()
    if len(parts) != 16 or any(HEX_BYTE.fullmatch(part) is None for part in parts):
        return None
    return bytes(int(part, 16) for part in parts)


def classify_initialization(historical_lines, frozen_window_lines):
    """Compare an exact native text PID only in memory, never export it.

    A matching PID may be recycled, and the log is not independent
    attestation of original VIDA DLL loading.
    """
    clients = Counter()
    for row in frozen_window_lines:
        if len(row) > MAX_LINE:
            continue
        match = PREFIX.match(row)
        if match is None:
            continue
        meta = _metadata(row[match.end():], D2_REQUEST)
        if meta is None:
            continue
        target, opcode = (int.from_bytes(meta[i:i+4], "big") for i in (0, 4))
        if target in (0x40, 0x50) and opcode == 0xFB:
            clients[row[:match.end()]] += 1
    report = {
        "schema_version": SCHEMA,
        "observed_d2_b9fb_requests": sum(clients.values()),
        "native_logger_pid_groups": len(clients),
        "init_record": "not_found_in_bounded_prebaseline_tail",
        "loaded_d2_b9fb": {"CEM_40": "not_observed", "CEM_50": "not_observed"},
        "init_fixture_metadata": "not_observed",
        "historical_config_source_path_exported": False,
        "original_vida_process_attested": False,
        "oem_reply_authenticated": False,
        "vin_accepted": False,
    }
    if len(clients) != 1:
        report["init_record"] = ("no_d2_request_pid" if not clients
                                 else "ambiguous_multiple_native_logger_pids")
        return report
    prefix = next(iter(clients))
    starts = [i for i, row in enumerate(historical_lines)
              if len(row) <= MAX_LINE and row.startswith(prefix + ACTIVE)]
    if not starts:
        return report
    start = starts[-1]
    path = historical_lines[start][len(prefix + ACTIVE):].strip()
    if INI_NAME.search(path) is None:
        report["init_record"] = "native_marker_with_unexpected_ini_filename"
        return report
    report["init_record"] = "native_active_ini_marker_same_pid_before_baseline"
    records = []
    malformed = 0
    for row in historical_lines[start + 1:start + 49]:
        if not row.startswith(prefix):
            continue
        event = row[len(prefix):]
        if event.startswith(ACTIVE):
            break
        if not event.startswith(FIXTURE):
            continue
        meta = _metadata(event, FIXTURE)
        if meta is None:
            malformed += 1
            continue
        words = tuple(int.from_bytes(meta[i:i+4], "big") for i in (0, 4, 8, 12))
        records.append(words)
        if len(records) > MAX_FIXTURES:
            break
    if malformed or len(records) != MAX_FIXTURES:
        report["init_fixture_metadata"] = "incomplete_or_malformed"
        return report
    if [(t, cmd) for t, cmd, _rid, _n in records[:6]] != BASE_ORDER:
        report["init_fixture_metadata"] = "unexpected_base_fixture_order"
        return report
    if any(count > 64 for _, _, _, count in records):
        report["init_fixture_metadata"] = "invalid_declared_frame_count"
        return report
    report["init_fixture_metadata"] = "14_native_fixture_records_classified"
    report["loaded_d2_b9fb"] = {
        "CEM_40": ("zero_frames_loaded" if records[0][3] == 0 else "frames_loaded_unverified"),
        "CEM_50": ("zero_frames_loaded" if records[2][3] == 0 else "frames_loaded_unverified"),
    }
    return report
