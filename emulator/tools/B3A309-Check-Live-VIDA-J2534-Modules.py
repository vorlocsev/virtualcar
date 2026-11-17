#!/usr/bin/env python3
"""B3A309: inspect LOADED current VIDA IEXPLORE modules read-only.

Recover original epoch2/epoch3 Active INI origins from the fixed historical
log (source: GetModuleFileNameA(g_module) + virtualcar.ini). Find exactly one
registered 32-bit J2534 FunctionLibrary DLL in each matching directory,
then query the currently running *explicit* IEXPLORE.EXE PID module list
using Toolhelp32 (TH32CS_SNAPMODULE|TH32CS_SNAPMODULE32).

No registry edits, DLL LoadLibrary, file writes, VEHICLE/VIDA actions, VIN,
private filenames, module names, paths, raw ECU frames or hashes are output.
A loaded matching DLL is evidence it is present in the process now, NOT
proof it handled a particular historic PassThruOpen or current request.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import ntpath
from pathlib import Path
import re
import runpy
import sys

VALID_PID = re.compile(r"[0-9A-Fa-f]{8}\Z")

TH32CS_SNAPMODULE = 0x00000008
TH32CS_SNAPMODULE32 = 0x00000010
MAX_PATH = 260


class MODULEENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("th32ModuleID", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("GlblcntUsage", wintypes.DWORD),
        ("ProccntUsage", wintypes.DWORD),
        ("modBaseAddr", ctypes.c_void_p),
        ("modBaseSize", wintypes.DWORD),
        ("hModule", ctypes.c_void_p),
        ("szModule", wintypes.WCHAR * 256),
        ("szExePath", wintypes.WCHAR * MAX_PATH),
    ]


def peer(filename: str):
    return runpy.run_path(
        str(Path(__file__).resolve().with_name(filename)),
        run_name="b3a309_import_only",
    )


def canonical_file(path: str | None) -> str | None:
    if not path or not ntpath.isabs(path):
        return None
    return ntpath.normcase(ntpath.normpath(path))


def candidates(paths: dict[int, bytes | None], reg32: dict) -> dict[int, str | None]:
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    decode = b306["decode_log_path"]
    ini_dir = b307["canonical_dir_from_ini"]
    dll_dir = b307["canonical_dir_from_dll"]
    matches = {}
    for ep in (2, 3):
        active_dir = ini_dir(decode(paths.get(ep)))
        found = [
            canonical_file(p) for p in reg32.get("paths", [])
            if active_dir and dll_dir(p) == active_dir
        ]
        matches[ep] = found[0] if len(found) == 1 else None
    return matches


def read_process_modules(pid: int) -> tuple[str, set[str]]:
    if sys.platform != "win32":
        return "UNSUPPORTED_PLATFORM", set()
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    # Check the executable image name before treating an arbitrary PID as VIDA.
    open_proc = k32.OpenProcess
    open_proc.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    open_proc.restype = ctypes.c_void_p
    get_image = k32.QueryFullProcessImageNameW
    get_image.argtypes = (ctypes.c_void_p, wintypes.DWORD,
                          wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD))
    get_image.restype = wintypes.BOOL
    close_proc = k32.CloseHandle
    close_proc.argtypes = (ctypes.c_void_p,)
    close_proc.restype = wintypes.BOOL
    # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000 (no debug privileges).
    proc = open_proc(0x1000, False, pid)
    if not proc:
        return "PROCESS_NOT_FOUND_OR_ACCESS_DENIED", set()
    try:
        name = ctypes.create_unicode_buffer(32768)
        length = wintypes.DWORD(len(name))
        if not get_image(proc, 0, name, ctypes.byref(length)):
            return "PROCESS_IMAGE_QUERY_ERROR", set()
        if ntpath.basename(name.value).casefold() != "iexplore.exe":
            return "PID_NOT_IEXPLORE", set()
    finally:
        close_proc(proc)

    snapshot = k32.CreateToolhelp32Snapshot
    snapshot.argtypes = (wintypes.DWORD, wintypes.DWORD)
    snapshot.restype = ctypes.c_void_p
    first = k32.Module32FirstW
    first.argtypes = (ctypes.c_void_p, ctypes.POINTER(MODULEENTRY32W))
    first.restype = wintypes.BOOL
    nxt = k32.Module32NextW
    nxt.argtypes = (ctypes.c_void_p, ctypes.POINTER(MODULEENTRY32W))
    nxt.restype = wintypes.BOOL
    close = k32.CloseHandle
    close.argtypes = (ctypes.c_void_p,)
    close.restype = wintypes.BOOL

    handle = snapshot(TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32, pid)
    if handle == ctypes.c_void_p(-1).value or handle is None:
        error = ctypes.get_last_error()
        return ("PROCESS_NOT_FOUND_OR_CLOSED" if error == 87 else
                "MODULE_ENUM_ACCESS_OR_BITNESS_ERROR" if error in (5, 299)
                else "MODULE_ENUM_ERROR"), set()
    try:
        entry = MODULEENTRY32W()
        entry.dwSize = ctypes.sizeof(entry)
        if not first(handle, ctypes.byref(entry)):
            error = ctypes.get_last_error()
            return ("PROCESS_NOT_FOUND_OR_CLOSED" if error in (87, 1168)
                    else "MODULE_ENUM_ACCESS_OR_BITNESS_ERROR"
                    if error in (5, 299) else "MODULE_ENUM_ERROR"), set()
        loaded = set()
        while True:
            name = canonical_file(entry.szExePath)
            if name:
                loaded.add(name)
            entry.dwSize = ctypes.sizeof(entry)
            if not nxt(handle, ctypes.byref(entry)):
                break
        return "READ_OK", loaded
    finally:
        close(handle)


def report(paths: dict[int, bytes | None], registry: dict,
           process_status: str, modules: set[str]) -> list[str]:
    reg32 = registry.get("32", {"state": "UNAVAILABLE", "paths": []})
    resolved = candidates(paths, reg32)
    lines = [
        "B3A309_PROCESS_SCOPE=CURRENT_PID_NOT_HISTORICAL_SNAPSHOT",
        "B3A309_LOADED_MODULE_ENUM_STATUS=" + process_status,
        "B3A309_REG32_STATUS=" + reg32.get("state", "UNAVAILABLE"),
        "B3A309_REG32_ENTRIES=" + str(len(reg32.get("paths", []))),
        "B3A309_LOADED_MODULE_COUNT=" + (str(len(modules)) if process_status == "READ_OK" else "UNKNOWN"),
    ]
    for ep in (2, 3):
        candidate = resolved.get(ep)
        lines.append(f"B3A309_EPOCH{ep}_UNIQUE_REG32_DLL_ORIGIN=" +
                     ("TRUE" if candidate else "FALSE"))
        if not candidate or process_status != "READ_OK":
            status = "NOT_ASSESSED"
        else:
            status = "TRUE" if candidate in modules else "FALSE"
        lines.append(f"B3A309_EPOCH{ep}_REGISTERED_DLL_LOADED_NOW={status}")
    lines.extend((
        "B3A309_REGISTERED_DLL_PRESENT_NOT_PROOF_OF_PROVIDER_SELECTED",
        "B3A309_HISTORICAL_DLL_LOADED_IN_THIS_PID=NOT_ASSESSED",
        "B3A309_NO_MODULE_OR_REGISTRY_WRITES=TRUE",
        "B3A309_GUI_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A309_RESULT=READ_ONLY_COMPLETE",
    ))
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="B3A309 inspect live IEXPLORE J2534 loaded modules")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--window-start", type=int, required=True)
    parser.add_argument("--window-end", type=int, required=True)
    parser.add_argument("--lookback-bytes", type=int, default=4194304)
    parser.add_argument("--expected-action-lines", type=int, required=True)
    parser.add_argument("--historical-pid", default="00002710")
    parser.add_argument("--live-pid-decimal", required=True, type=int)
    args = parser.parse_args()
    hpid = args.historical_pid.upper()
    if (not VALID_PID.fullmatch(hpid) or args.live_pid_decimal <= 0
            or args.live_pid_decimal > 0xFFFFFFFF
            or args.window_start <= 0 or args.window_end <= args.window_start
            or not 1 <= args.lookback_bytes <= 32*1024*1024
            or not 1 <= args.expected_action_lines <= 500000):
        print("B3A309_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    recover = peer("B3A300-Recover-VIDA-Gate-Window.py")["capture_historic"]
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    try:
        with args.log.open("rb") as f:
            data, _, discard, start = recover(
                f, end_offset=args.window_end,
                window_bytes=args.window_end-args.window_start +
                min(args.lookback_bytes, args.window_start))
    except (OSError, ValueError):
        print("B3A309_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    paths, details = b306["scan"](
        data, begin=start+discard, action_start=args.window_start,
        action_end=args.window_end, pid=hpid,
        expected_action_lines=args.expected_action_lines)
    if "B3A306_ACTION_CENSUS_MATCH=TRUE" not in details or not paths:
        print("B3A309_RESULT=ERROR_HISTORY_CENSUS_OR_PATHS")
        return 1
    current_status, modules = read_process_modules(args.live_pid_decimal)
    print("B3A309_HISTORICAL_CENSUS_MATCH=TRUE")
    for item in report(paths, b307["registry_sources"](), current_status, modules):
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
