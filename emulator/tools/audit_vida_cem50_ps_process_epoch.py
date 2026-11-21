#!/usr/bin/env python3
"""B3A72: read-only process-epoch-correlated PS DLL / native Active INI evidence.

Requires the exact B3A45 local baseline and source log. Does not start VIDA,
load J2534, change registry/INI, or export PID, VIN, paths or raw frames.
The same text PID is not proof of the same process creation epoch.
"""
import argparse
import json
import ntpath
from pathlib import Path
import re
import sys

import audit_vida_j2534_session_window as window
import audit_vida_cem50_loaded_module as live
import audit_vida_b3a52_loaded_fixtures as old

SCHEMA = "virtualcar-b3a72-ps-process-epoch-v1"
PREFIX = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([a-zA-Z0-9_.-]{1,48})\] ")
MAX_TAIL = 32 * 1024 * 1024


def _ini_for(dll):
    return ntpath.join(ntpath.dirname(dll), "virtualcar.ini")


EPOCH_LABEL = "Process creation FILETIME (BE) "


def _epoch_marker(row, pid, host):
    """Parse an epoch marker in memory; never return the FILETIME in a report."""
    if not isinstance(row, str) or len(row) > 512:
        return False, None
    match = PREFIX.match(row)
    if (match is None or int(match.group(1), 16) != pid
            or match.group(2).casefold() != host.casefold()):
        return False, None
    event = row[match.end():]
    if not event.startswith(EPOCH_LABEL):
        return False, None
    parts = event[len(EPOCH_LABEL):].strip().split()
    if len(parts) != 8 or any(re.fullmatch(r"[0-9A-Fa-f]{2}", x) is None for x in parts):
        return True, None
    return True, int.from_bytes(bytes(int(x, 16) for x in parts), "big")


def analyze(history, appended, processes, *, host="iexplore.exe",
            expected_dll=live.DEFAULT_DLL, disk_sha=None,
            expected_sha=live.PINNED_SHA256):
    """Pure categorical evaluation; PID, FILETIME, paths and payload stay private."""
    if host not in live.ALLOWED_HOSTS or not ntpath.isabs(expected_dll):
        raise ValueError("unexpected host or DLL")
    result = {
        "schema_version": SCHEMA,
        "status": "NOT_ASSESSED",
        "host_category": host,
        "native_b9fb_pid_groups": 0,
        "native_b9fb_requests": 0,
        "same_text_pid_live_exact_dll": False,
        "same_text_pid_native_active_ini": False,
        "logged_ini_path_matches_dll_directory": False,
        "native_loaded_b9fb_cem40": "not_observed",
        "native_loaded_b9fb_cem50": "not_observed",
        "native_loaded_fixture_metadata": "not_observed",
        "disk_sha_matches_pinned": (None if disk_sha is None else
                                    disk_sha.casefold() == expected_sha.casefold()),
        "process_creation_epoch_marker_present": False,
        "process_creation_epoch_live_value_available": False,
        "process_creation_epoch_verified": False,
        "ini_bytes_loaded_verified": False,
        "original_vida_readvin_verified": False,
        "ecu_rx_delivered_verified": False,
        "source_contains_private_pid_path_or_payload": False,
    }
    timeline = list(history) + list(appended)
    # The B3A52 classifier sees initialization records both before and after
    # the frozen baseline, while counting requests only in the appended window.
    native = old.classify_initialization([], appended)
    result["native_b9fb_requests"] = native["observed_d2_b9fb_requests"]
    result["native_b9fb_pid_groups"] = native["native_logger_pid_groups"]
    if native["native_logger_pid_groups"] != 1:
        result["status"] = ("NO_D2_B9FB_REQUEST_PID" if not native["native_logger_pid_groups"]
                            else "AMBIGUOUS_D2_B9FB_PIDS")
        return result

    eligible = set()
    request_positions = []
    for index, row in enumerate(appended):
        match = PREFIX.match(row) if len(row) <= 512 else None
        if match is None or match.group(2).casefold() != host:
            continue
        rest = row[match.end():]
        meta = old._metadata(rest, old.D2_REQUEST)
        if meta is None:
            continue
        target = int.from_bytes(meta[:4], "big")
        opcode = int.from_bytes(meta[4:8], "big")
        if target in (0x40, 0x50) and opcode == 0xFB:
            pid_value = int(match.group(1), 16)
            eligible.add(pid_value)
            request_positions.append((index, pid_value))
    if len(eligible) != 1:
        result["status"] = "NO_UNAMBIGUOUS_REQUEST_PID_IN_CHOSEN_HOST"
        return result
    pid = next(iter(eligible))
    request_index = max(index for index, candidate in request_positions
                        if candidate == pid) + len(history)
    # Reclassify initialization only up to the request; later PID reuse or
    # another DLL initialization must not overwrite the request's evidence.
    native = old.classify_initialization(timeline[:request_index], appended)

    matching = [p for p in processes if p.get("exe", "").casefold() == host
                and p.get("pid") == pid]
    if not matching:
        result["status"] = "NO_LIVE_MATCHING_PROCESS_PID"
        return result
    paths = matching[0].get("modules")
    if paths is None:
        result["status"] = "MODULE_ENUMERATION_BLOCKED"
        return result
    if not any(live._same_path(path, expected_dll) for path in paths):
        result["status"] = "NO_EXACT_PS_DLL_FOR_REQUEST_PID"
        return result
    result["same_text_pid_live_exact_dll"] = True

    # Select the latest creation marker before this request. If Windows reused
    # a PID, the current process must match this exact FILETIME, not the PID text.
    epoch_markers = []
    for index, row in enumerate(timeline[:request_index + 1]):
        present, value = _epoch_marker(row, pid, host)
        if present:
            epoch_markers.append((index, value))
    epoch_index = epoch_markers[-1][0] if epoch_markers else -1
    epoch_value = epoch_markers[-1][1] if epoch_markers else None
    result["process_creation_epoch_marker_present"] = bool(epoch_markers)
    live_epoch = matching[0].get("creation_filetime")
    result["process_creation_epoch_live_value_available"] = type(live_epoch) is int
    if epoch_markers and epoch_value is not None and type(live_epoch) is int:
        result["process_creation_epoch_verified"] = epoch_value == live_epoch
    if epoch_markers and epoch_value is None:
        epoch_state = "PROCESS_CREATION_EPOCH_MARKER_MALFORMED"
    elif not epoch_markers:
        epoch_state = "CORRELATED_SAME_TEXT_PID_EPOCH_NOT_ATTESTED"
    elif type(live_epoch) is not int:
        epoch_state = "PROCESS_CREATION_EPOCH_LIVE_TIME_UNAVAILABLE"
    elif epoch_value != live_epoch:
        epoch_state = "PROCESS_CREATION_EPOCH_MISMATCH"
    else:
        epoch_state = "PROCESS_CREATION_EPOCH_MATCH"

    # The INI marker must belong to the same latest DLL initialization epoch
    # and precede the request. Old PID-reuse initialization is not accepted.
    active = []
    for index, row in enumerate(timeline[:request_index]):
        if index <= epoch_index or len(row) > 512:
            continue
        match = PREFIX.match(row)
        if (match is not None and int(match.group(1), 16) == pid
                and match.group(2).casefold() == host
                and row[match.end():].startswith(old.ACTIVE)):
            active.append((index, row[match.end():].strip()))
    if not active:
        result["status"] = "NO_ACTIVE_INI_AFTER_PROCESS_EPOCH"
        return result
    result["same_text_pid_native_active_ini"] = True
    if not live._same_path(active[-1][1], _ini_for(expected_dll)):
        result["status"] = "ACTIVE_INI_MARKER_POINTS_ELSEWHERE"
        return result
    result["logged_ini_path_matches_dll_directory"] = True
    result["native_loaded_b9fb_cem40"] = native["loaded_d2_b9fb"]["CEM_40"]
    result["native_loaded_b9fb_cem50"] = native["loaded_d2_b9fb"]["CEM_50"]
    result["native_loaded_fixture_metadata"] = native["init_fixture_metadata"]
    if native["init_fixture_metadata"] != "14_native_fixture_records_classified":
        result["status"] = "MATCHED_PATH_WITH_INCOMPLETE_INIT_METADATA"
    elif epoch_state != "PROCESS_CREATION_EPOCH_MATCH":
        result["status"] = epoch_state
    elif result["disk_sha_matches_pinned"] is True:
        result["status"] = "CORRELATED_SAME_PROCESS_EPOCH_EXACT_DLL_ACTIVE_INI"
    else:
        result["status"] = "SAME_PROCESS_EPOCH_BUT_DISK_SHA_UNVERIFIED"
    return result

def _owner_lines(log, private_baseline):
    """B3A45 verifies complete prefix SHA and extracts only the appended window."""
    if log.is_symlink() or not log.is_file() or not private_baseline.is_file():
        raise ValueError("source unavailable")
    if private_baseline.stat().st_size > 131072:
        raise ValueError("oversized baseline")
    base = json.loads(private_baseline.read_text(encoding="utf-8"))
    if (type(base) is not dict or set(base) !=
            {"schema_version", "private_do_not_publish", "original_vida", "virtual_j2534"}
            or base["schema_version"] != window.SCHEMA
            or base["private_do_not_publish"] is not True):
        raise ValueError("baseline schema mismatch")
    state = base["virtual_j2534"]
    if not state.get("present"):
        raise ValueError("historical log was absent at baseline")
    appended, _, _ = window._append(log, state)
    stop = state["bytes"]
    if type(stop) is not int or not 0 <= stop <= window.MAX_SOURCE:
        raise ValueError("invalid baseline offset")
    start = max(0, stop - MAX_TAIL)
    before = log.stat()
    with log.open("rb") as stream:
        stream.seek(start)
        raw = stream.read(stop - start)
    after = log.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("source changed during historical read")
    if start:
        raw = raw[raw.find(b"\n") + 1:] if b"\n" in raw else b""
    return [s for s in raw.decode("utf-8", "replace").splitlines()
            if len(s) <= 512], appended


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--virtual-log", required=True, type=Path)
    parser.add_argument("--private-baseline", required=True, type=Path)
    parser.add_argument("--host-exe", choices=live.ALLOWED_HOSTS, default="iexplore.exe")
    parser.add_argument("--expected-dll", default=live.DEFAULT_DLL)
    parser.add_argument("--expected-sha256", default=live.PINNED_SHA256)
    parser.add_argument("--private-output", type=Path)
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("live snapshot requires Windows")
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", args.expected_sha256):
        parser.error("invalid expected SHA256")
    if ntpath.basename(args.expected_dll).casefold() != "j2534cem50ps.dll":
        parser.error("unexpected PS DLL name")
    if args.private_output is not None:
        window._external(args.private_output, (args.virtual_log, args.private_baseline))
    history, appended = _owner_lines(args.virtual_log, args.private_baseline)
    records = live._windows_records(args.host_exe)
    report = analyze(history, appended, records, host=args.host_exe,
                     expected_dll=args.expected_dll,
                     expected_sha=args.expected_sha256,
                     disk_sha=live._sha256(args.expected_dll))
    if args.private_output is not None:
        args.private_output.parent.mkdir(parents=True, exist_ok=True)
        with args.private_output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    print("B3A72 Process-epoch PS INI:", report["status"])
    for key in ("native_b9fb_requests", "native_b9fb_pid_groups",
                "same_text_pid_live_exact_dll", "same_text_pid_native_active_ini",
                "logged_ini_path_matches_dll_directory",
                "native_loaded_fixture_metadata", "native_loaded_b9fb_cem40",
                "native_loaded_b9fb_cem50", "disk_sha_matches_pinned"):
        print(key + ":", report[key])
    print("Process creation epoch verified:", report["process_creation_epoch_verified"])
    print("Loaded INI bytes / ECU RX / VIDA ReadVin: NOT_VERIFIED")
    print("No PID, path, FILETIME, VIN or raw frames exported; no state changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
