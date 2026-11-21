#!/usr/bin/env python3
"""B3A63: read-only PID-correlated PS DLL / native Active INI evidence.

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

SCHEMA = "virtualcar-b3a63-ps-same-pid-ini-v1"
PREFIX = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([a-zA-Z0-9_.-]{1,48})\] ")
MAX_TAIL = 32 * 1024 * 1024


def _ini_for(dll):
    return ntpath.join(ntpath.dirname(dll), "virtualcar.ini")


def analyze(history, appended, processes, *, host="iexplore.exe",
            expected_dll=live.DEFAULT_DLL, disk_sha=None,
            expected_sha=live.PINNED_SHA256):
    """Pure categorical evaluation; no process identifiers leave the report."""
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
        "process_creation_epoch_verified": False,
        "ini_bytes_loaded_verified": False,
        "original_vida_readvin_verified": False,
        "ecu_rx_delivered_verified": False,
        "source_contains_private_pid_path_or_payload": False,
    }
    # B3A52 recognizes only exact, source-coded P2 D2 B9FB request metadata.
    native = old.classify_initialization(history, appended)
    result["native_b9fb_requests"] = native["observed_d2_b9fb_requests"]
    result["native_b9fb_pid_groups"] = native["native_logger_pid_groups"]
    if native["native_logger_pid_groups"] != 1:
        result["status"] = ("NO_D2_B9FB_REQUEST_PID" if not native["native_logger_pid_groups"]
                            else "AMBIGUOUS_D2_B9FB_PIDS")
        return result
    # B3A52 suppresses PID in its report; recover it only locally and never
    # serialize it. Do not correlate two different IE processes by name alone.
    eligible = set()
    for row in appended:
        m = PREFIX.match(row) if len(row) <= 512 else None
        if m is None or m.group(2).casefold() != host:
            continue
        rest = row[m.end():]
        meta = old._metadata(rest, old.D2_REQUEST)
        if meta is None:
            continue
        target = int.from_bytes(meta[:4], "big")
        opcode = int.from_bytes(meta[4:8], "big")
        if target in (0x40, 0x50) and opcode == 0xFB:
            eligible.add(int(m.group(1), 16))
    if len(eligible) != 1:
        result["status"] = "NO_UNAMBIGUOUS_REQUEST_PID_IN_CHOSEN_HOST"
        return result
    pid = next(iter(eligible))
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
    candidates = []
    for i, row in enumerate(history):
        m = PREFIX.match(row) if len(row) <= 512 else None
        if m is not None and m.group(2).casefold() == host and int(m.group(1), 16) == pid:
            event = row[m.end():]
            if event.startswith(old.ACTIVE):
                candidates.append(event[len(old.ACTIVE):].strip())
    if not candidates:
        result["status"] = "NO_PREBASELINE_ACTIVE_INI_FOR_REQUEST_PID"
        return result
    result["same_text_pid_native_active_ini"] = True
    if not live._same_path(candidates[-1], _ini_for(expected_dll)):
        result["status"] = "ACTIVE_INI_MARKER_POINTS_ELSEWHERE"
        return result
    result["logged_ini_path_matches_dll_directory"] = True
    result["native_loaded_b9fb_cem40"] = native["loaded_d2_b9fb"]["CEM_40"]
    result["native_loaded_b9fb_cem50"] = native["loaded_d2_b9fb"]["CEM_50"]
    result["native_loaded_fixture_metadata"] = native["init_fixture_metadata"]
    result["status"] = ("CORRELATED_SAME_TEXT_PID_EPOCH_NOT_ATTESTED"
                        if native["init_fixture_metadata"] == "14_native_fixture_records_classified"
                        else "MATCHED_PATH_WITH_INCOMPLETE_INIT_METADATA")
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
    print("B3A63 Same-PID PS INI:", report["status"])
    for key in ("native_b9fb_requests", "native_b9fb_pid_groups",
                "same_text_pid_live_exact_dll", "same_text_pid_native_active_ini",
                "logged_ini_path_matches_dll_directory",
                "native_loaded_fixture_metadata", "native_loaded_b9fb_cem40",
                "native_loaded_b9fb_cem50", "disk_sha_matches_pinned"):
        print(key + ":", report[key])
    print("Process epoch / loaded INI bytes / ECU RX / VIDA ReadVin: NOT_VERIFIED")
    print("No PID, path, VIN or raw frames exported; no state changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
