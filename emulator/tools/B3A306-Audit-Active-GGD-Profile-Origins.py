#!/usr/bin/env python3
"""B3A306: original VIDA J2534 Active INI origins and CURRENT read-only guard state.

The native VirtualCar DLL derives g_profile_path from GetModuleFileNameA(g_module)
and appends virtualcar.ini; it logs "Active INI: " while load_config() runs
BEFORE "PassThruOpen -> device 1". Different canonical paths therefore
indicate different DLL module directories (or equivalent path aliasing) at
their respective Opens, not merely changed bytes in a single INI.

No paths, VIN, ECU payloads, raw frames, full log lines, or INI values are
printed; only non-identifying booleans/counts are reported. The optional
--inspect-current-files flag reads ONLY selected INI keys (no write), using
Windows GetPrivateProfileStringW. CURRENT files may differ from the
HISTORICAL content loaded during the captured original VIDA session.
"""
from __future__ import annotations

import argparse
from collections import Counter
import ctypes
from ctypes import wintypes
import ntpath
import os
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(rb"^\[PID=([0-9a-fA-F]{8}) ([^\]\r\n]{1,120})\] (.*)$")
PID = re.compile(r"[0-9a-fA-F]{8}\Z")
INI = b"Active INI: "
INIT = b"VirtualCar DLL initialized"
OPEN = b"PassThruOpen -> device 1"


def scan(data: bytes, *, begin: int, action_start: int, action_end: int,
         pid: str, expected_action_lines: int) -> tuple[dict[int, bytes | None], list[str]]:
    epoch = 0
    paths: dict[int, bytes | None] = {}
    stats = Counter()
    pending_path: bytes | None = None
    pending_init = False
    offset = begin

    for raw in data.splitlines(keepends=True):
        row_start, row_end = offset, offset + len(raw)
        offset = row_end
        if not raw.endswith(b"\n"):
            stats["PARTIAL"] += 1
            continue
        if row_start < action_start < row_end:
            stats["ACTION_CROSSING"] += 1
            continue
        match = TAG.match(raw.rstrip(b"\r\n"))
        if not match or match.group(1).decode("ascii").upper() != pid or match.group(2).upper() != b"IEXPLORE.EXE":
            continue
        in_action = action_start <= row_start < action_end
        if in_action:
            stats["ACTION_LINES"] += 1
        msg = match.group(3)
        if msg.startswith(INI):
            pending_path = msg[len(INI):]
            stats["PATH_LOGS"] += 1
            continue
        if msg.startswith(INIT):
            pending_init = True
            stats["INIT_LOGS"] += 1
            continue
        if msg.startswith(OPEN):
            epoch += 1
            paths[epoch] = pending_path
            stats["OPENS"] += 1
            if pending_init:
                stats["INIT_TO_OPEN"] += 1
            if in_action:
                stats["ACTION_OPENS"] += 1
            pending_path = None
            pending_init = False
            continue

    output = [
        f"B3A306_EXACT_PID={pid}",
        f"B3A306_ACTION_LINES={stats['ACTION_LINES']}",
        f"B3A306_EXPECTED_ACTION_LINES={expected_action_lines}",
        f"B3A306_ACTION_CENSUS_MATCH={'TRUE' if stats['ACTION_LINES']==expected_action_lines else 'FALSE'}",
        f"B3A306_PREWINDOW_OPENS={stats['OPENS']-stats['ACTION_OPENS']}",
        f"B3A306_ACTION_OPENS={stats['ACTION_OPENS']}",
        f"B3A306_PATH_LOGS={stats['PATH_LOGS']}",
        f"B3A306_INIT_LOGS={stats['INIT_LOGS']}",
        f"B3A306_INIT_LINKED_TO_OPEN={stats['INIT_TO_OPEN']}",
        f"B3A306_ACTION_BOUNDARY_CROSSING_LINES={stats['ACTION_CROSSING']}",
    ]
    if stats["ACTION_LINES"] != expected_action_lines:
        output.append("B3A306_RESULT=ERROR_ACTION_CENSUS_MISMATCH")
        return {}, output
    for ep in sorted(paths):
        output.append(
            f"B3A306_EPOCH={ep},path_logged:{'TRUE' if paths[ep] else 'FALSE'}"
        )
    return paths, output


def decode_log_path(raw: bytes | None) -> str | None:
    if not raw:
        return None
    # The native DLL uses GetModuleFileNameA, hence the Windows ANSI codepage.
    try:
        result = raw.decode("mbcs" if os.name == "nt" else "latin-1", "strict")
    except UnicodeError:
        return None
    if any(ord(ch) < 0x20 for ch in result) or not result:
        return None
    return result


def canonical(raw: bytes | None) -> str | None:
    s = decode_log_path(raw)
    if s is None:
        return None
    return ntpath.normcase(ntpath.normpath(s))


def path_comparison(paths: dict[int, bytes | None]) -> str:
    p2, p3 = canonical(paths.get(2)), canonical(paths.get(3))
    if not p2 or not p3:
        return "UNKNOWN"
    return "SAME" if p2 == p3 else "DIFFERENT"


def source_num(value: str, fallback: int) -> int:
    if not value:
        return fallback
    base = 16 if value.startswith(("0x", "0X")) else 10
    number = value[2:] if base == 16 else value
    if not number or not re.fullmatch(
        r"[0-9A-Fa-f]+" if base == 16 else r"[0-9]+", number
    ):
        return fallback
    # Source uses U32 arithmetic.
    result = int(number, base) & 0xFFFFFFFF
    return result


def source_hex(value: str, fallback: int) -> int:
    if value.startswith(("0x", "0X")):
        value = value[2:]
    if not value or not re.fullmatch(r"[0-9a-fA-F]+", value):
        return fallback
    return int(value, 16) & 0xFFFFFFFF


def evaluate_current(get) -> dict[str, str]:
    # Exactly the C read keys and defaults, no private value output.
    enabled = source_num(get("Diagnostics", "EnableGGDCemLab", "0"), 0) == 1
    count = source_num(get("Vehicle", "ECUCount", "2"), 2)
    if not 1 <= count <= 8:  # MAX_ECUS = 8
        count = 1
    matching = 0
    for i in range(count):
        sec = f"ECU{i}"
        req = source_hex(get(sec, "RequestId", "726" if i == 1 else "7E0"),
                         0x726 if i == 1 else 0x7E0)
        rsp = source_hex(get(sec, "ResponseId", "72E" if i == 1 else "7E8"),
                         0x72E if i == 1 else 0x7E8)
        if req == 0x18DA50F1 and rsp == 0x18DAF150:
            matching += 1
    return {
        "lab_enabled": "TRUE" if enabled else "FALSE",
        "cem29_route_present": "TRUE" if matching else "FALSE",
        "matching_route_count": str(matching),
        "lab_and_route_ready": "TRUE" if enabled and matching else "FALSE",
    }


def win_ini_getter(path: str):
    func = ctypes.WinDLL("kernel32", use_last_error=True).GetPrivateProfileStringW
    func.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                     wintypes.LPCWSTR, wintypes.LPWSTR,
                     wintypes.DWORD, wintypes.LPCWSTR]
    func.restype = wintypes.DWORD

    def get(section: str, key: str, default: str) -> str:
        out = ctypes.create_unicode_buffer(512)
        func(section, key, default, out, len(out), path)
        return out.value

    return get


def inspect_current(paths: dict[int, bytes | None]) -> list[str]:
    out = ["B3A306_CURRENT_FILE_INSPECTION=READ_ONLY"]
    if os.name != "nt":
        return out + ["B3A306_CURRENT_FILE_INSPECTION_STATUS=UNSUPPORTED_PLATFORM"]
    for epoch in (2, 3):
        original = decode_log_path(paths.get(epoch))
        # Never accept an arbitrary path or a non-INI target from a log.
        allowed = (original is not None and ntpath.isabs(original)
                   and ntpath.basename(original).casefold() == "virtualcar.ini")
        present = allowed and os.path.isfile(original)
        out.append(
            f"B3A306_EPOCH{epoch}_CURRENT_INI_PRESENT={'TRUE' if present else 'FALSE'}"
        )
        if not present:
            out.append(f"B3A306_EPOCH{epoch}_CURRENT_STATE=NOT_ASSESSED")
            continue
        try:
            values = evaluate_current(win_ini_getter(original))
        except (OSError, ValueError):
            out.append(f"B3A306_EPOCH{epoch}_CURRENT_STATE=READ_ERROR")
            continue
        out.append(f"B3A306_EPOCH{epoch}_CURRENT_STATE=READ_ONLY_EVALUATED")
        for k, v in values.items():
            out.append(f"B3A306_EPOCH{epoch}_CURRENT_{k.upper()}={v}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="B3A306 safe J2534 epoch source/current profile audit")
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--window-start", type=int, required=True)
    p.add_argument("--window-end", type=int, required=True)
    p.add_argument("--lookback-bytes", type=int, default=4*1024*1024)
    p.add_argument("--expected-action-lines", type=int, required=True)
    p.add_argument("--pid", default="00002710")
    p.add_argument("--inspect-current-files", action="store_true")
    args = p.parse_args()
    pid = args.pid.upper()
    if (not PID.fullmatch(pid) or args.window_start <= 0
            or args.window_end <= args.window_start
            or not 1 <= args.lookback_bytes <= 32*1024*1024
            or not 1 <= args.expected_action_lines <= 500000):
        print("B3A306_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    capture = runpy.run_path(
        str(Path(__file__).resolve().with_name("B3A300-Recover-VIDA-Gate-Window.py")),
        run_name="b3a306_import_capture"
    )["capture_historic"]
    lookback = min(args.lookback_bytes, args.window_start)
    try:
        with args.log.open("rb") as stream:
            chunk, _, discarded, start = capture(
                stream, end_offset=args.window_end,
                window_bytes=args.window_end-args.window_start+lookback)
    except (ValueError, OSError):
        print("B3A306_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    print(f"B3A306_COMBINED_START={start}")
    print(f"B3A306_COMBINED_END={args.window_end}")
    print(f"B3A306_PARTIAL_LEADING_BYTES={discarded}")
    paths, report = scan(chunk, begin=start+discarded,
                         action_start=args.window_start,
                         action_end=args.window_end,
                         pid=pid,
                         expected_action_lines=args.expected_action_lines)
    for row in report:
        print(row)
    if not paths:
        return 1
    print(f"B3A306_EPOCH2_VS_3_NORMALIZED_PATH={path_comparison(paths)}")
    print("B3A306_PATH_SOURCE=GETMODULEFILENAMEA_DLL_DIRECTORY_PLUS_VIRTUALCAR_INI")
    print("B3A306_DIFFERENT_PATHS=DIFFERENT_MODULE_DIRECTORIES_OR_PATH_ALIASING")
    if args.inspect_current_files:
        for row in inspect_current(paths):
            print(row)
    else:
        print("B3A306_CURRENT_FILE_INSPECTION=NOT_REQUESTED")
    print("B3A306_HISTORICAL_ENABLE_FLAG=NOT_LOGGED")
    print("B3A306_CURRENT_INI_VALUES_ARE_NOT_HISTORICAL_PROOF")
    print("B3A306_ORIGINAL_VIDA_GUI_IDENT_ACCEPTANCE=NOT_ASSESSED")
    print("B3A306_RESULT=READ_ONLY_COMPLETE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
