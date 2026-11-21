#!/usr/bin/env python3
"""B3A56: read-only, privacy-safe snapshot of the PS DLL in a live VIDA host.

Uses Windows Toolhelp PROCESS/MODULE snapshots. Never launches VIDA, reads a VIN,
opens J2534, modifies registry/files or claims a historic load from a snapshot.
Only aggregate booleans/counts are emitted; no PID, path or source module list.
"""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
import ntpath
from pathlib import Path
import re
import sys

SCHEMA = "virtualcar-b3a56-live-module-snapshot-v1"
ALLOWED_HOSTS = ("iexplore.exe", "java.exe", "vidamonitor.exe")
DEFAULT_DLL = r"C:\ProgramData\J2534-CEM50-PS\J2534CEM50PS.dll"
PINNED_SHA256 = "7F21E2606C6E7981ECDEDFE6769F180981C6DDFFFFBCC5C35CD4A6E983C98C3E"


def _same_path(a, b):
    """Strict textual Windows path comparison: aliases are NOT treated as proof."""
    if not isinstance(a, str) or not isinstance(b, str):
        return False
    return ntpath.normcase(ntpath.normpath(a.replace("/", "\\"))) == ntpath.normcase(
        ntpath.normpath(b.replace("/", "\\")))


def _sha256(path):
    try:
        h = hashlib.sha256()
        with open(path, "rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest().upper()
    except OSError:
        return None


def analyze(records, *, expected_dll=DEFAULT_DLL, expected_sha256=PINNED_SHA256,
            host_exe="iexplore.exe", disk_digest=None, ini_present=False):
    """Summarize synthetic or live Toolhelp records without echoing identities."""
    if host_exe not in ALLOWED_HOSTS or not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("invalid host or SHA256")
    if not ntpath.isabs(expected_dll) or ntpath.basename(expected_dll).lower() != "j2534cem50ps.dll":
        raise ValueError("unexpected DLL target")
    host_count = inspected = blocked = exact = same_name_other = 0
    for item in records:
        if not isinstance(item, dict) or str(item.get("exe", "")).casefold() != host_exe.casefold():
            continue
        host_count += 1
        if item.get("modules") is None:
            blocked += 1
            continue
        inspected += 1
        modules = item["modules"]
        for path in modules:
            if not isinstance(path, str):
                continue
            if _same_path(path, expected_dll):
                exact += 1
            elif ntpath.basename(path).casefold() == "j2534cem50ps.dll":
                same_name_other += 1
    sha_match = None if disk_digest is None else disk_digest.upper() == expected_sha256.upper()
    if exact:
        status = ("EXACT_DLL_IN_HOST_SHA_MATCH" if sha_match is True else
                  "EXACT_DLL_IN_HOST_DISK_SHA_MISMATCH" if sha_match is False else
                  "EXACT_DLL_IN_HOST_DISK_UNREADABLE")
    elif not host_count:
        status = "NO_HOST_PROCESS_IN_SNAPSHOT"
    elif blocked:
        status = "INCONCLUSIVE_MODULE_ACCESS"
    elif same_name_other:
        status = "ONLY_SAME_NAME_OTHER_PATH"
    else:
        status = "EXPECTED_DLL_NOT_SEEN_AT_SNAPSHOT"
    return {
        "schema_version": SCHEMA, "evidence_class": "OWNER_LOCAL_LIVE_MODULE_SNAPSHOT",
        "status": status, "selected_host_exe_category": host_exe,
        "host_processes_present": host_count,
        "host_processes_modules_inspected": inspected,
        "host_processes_module_inspection_blocked": blocked,
        "exact_module_path_instances": exact,
        "same_basename_other_path_instances": same_name_other,
        "installed_disk_sha256_matches_pinned": sha_match,
        "expected_ini_present_at_module_directory": bool(ini_present),
        "loaded_ini_contents_verified": False,
        "original_vida_readvin_pass_verified": False,
        "ecu_identification_verified": False,
        "raw_paths_pids_modules_or_vin_exported": False,
        "limitations": [
            "Only a point-in-time live process module snapshot; not historical DLL load.",
            "Disk SHA256 validates current file bytes, not in-memory module contents.",
            "Module presence does not prove which J2534 entry point VIDA called.",
            "The source derives virtualcar.ini beside the loaded DLL; disk presence does not prove its content was read.",
            "A missing module can reflect process exit, a different process, or insufficient access.",
            "No link to the original VIDA GUI action/ReadVin or to received ECU data is established.",
        ],
    }


def _windows_records(host_exe):
    """Enumerate process/module paths with Toolhelp; never export PIDs or paths."""
    if sys.platform != "win32":
        raise RuntimeError("B3A56 live enumeration requires Windows")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    DWORD = wintypes.DWORD
    PTR = ctypes.c_void_p

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", DWORD), ("cntUsage", DWORD), ("th32ProcessID", DWORD),
            ("th32DefaultHeapID", ctypes.c_size_t), ("th32ModuleID", DWORD),
            ("cntThreads", DWORD), ("th32ParentProcessID", DWORD),
            ("pcPriClassBase", wintypes.LONG), ("dwFlags", DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    class MODULEENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", DWORD), ("th32ModuleID", DWORD), ("th32ProcessID", DWORD),
            ("GlblcntUsage", DWORD), ("ProccntUsage", DWORD),
            ("modBaseAddr", PTR), ("modBaseSize", DWORD), ("hModule", PTR),
            ("szModule", wintypes.WCHAR * 256),
            ("szExePath", wintypes.WCHAR * 260),
        ]

    kernel.CreateToolhelp32Snapshot.argtypes = [DWORD, DWORD]
    kernel.CreateToolhelp32Snapshot.restype = PTR
    kernel.Process32FirstW.argtypes = [PTR, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Process32NextW.argtypes = [PTR, ctypes.POINTER(PROCESSENTRY32W)]
    kernel.Module32FirstW.argtypes = [PTR, ctypes.POINTER(MODULEENTRY32W)]
    kernel.Module32NextW.argtypes = [PTR, ctypes.POINTER(MODULEENTRY32W)]
    kernel.CloseHandle.argtypes = [PTR]
    invalid = PTR(-1).value

    def snapshot(flags, pid):
        handle = kernel.CreateToolhelp32Snapshot(flags, pid)
        return None if handle in (None, invalid) else handle

    processes = snapshot(0x00000002, 0)  # TH32CS_SNAPPROCESS
    if processes is None:
        raise RuntimeError("cannot enumerate process snapshot")
    result = []
    try:
        proc = PROCESSENTRY32W()
        proc.dwSize = ctypes.sizeof(proc)
        ok = kernel.Process32FirstW(processes, ctypes.byref(proc))
        while ok:
            if str(proc.szExeFile).casefold() == host_exe.casefold():
                mods = snapshot(0x00000008 | 0x00000010, proc.th32ProcessID)
                paths = None
                if mods is not None:
                    paths = []
                    try:
                        mod = MODULEENTRY32W()
                        mod.dwSize = ctypes.sizeof(mod)
                        mok = kernel.Module32FirstW(mods, ctypes.byref(mod))
                        if not mok:
                            paths = None  # Failed enumeration is INCONCLUSIVE, not an empty module list.
                        while mok:
                            paths.append(str(mod.szExePath))
                            mok = kernel.Module32NextW(mods, ctypes.byref(mod))
                    finally:
                        kernel.CloseHandle(mods)
                # PID remains in-memory only; analyze() and stdout never export it.
                result.append({"exe": host_exe, "modules": paths, "pid": int(proc.th32ProcessID)})
            ok = kernel.Process32NextW(processes, ctypes.byref(proc))
    finally:
        kernel.CloseHandle(processes)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-exe", choices=ALLOWED_HOSTS, default="iexplore.exe")
    parser.add_argument("--expected-dll", default=DEFAULT_DLL)
    parser.add_argument("--expected-sha256", default=PINNED_SHA256)
    parser.add_argument("--private-output", type=Path)
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        parser.error("this live snapshot runs only on Windows")
    if not ntpath.isabs(args.expected_dll):
        parser.error("--expected-dll must be absolute")
    records = _windows_records(args.host_exe)
    expected_ini = ntpath.join(ntpath.dirname(args.expected_dll), "virtualcar.ini")
    report = analyze(records, expected_dll=args.expected_dll,
                     expected_sha256=args.expected_sha256,
                     host_exe=args.host_exe, disk_digest=_sha256(args.expected_dll),
                     ini_present=Path(expected_ini).is_file())
    if args.private_output is not None:
        output = args.private_output.resolve()
        repo_root = Path(__file__).resolve().parents[2]
        if output.is_relative_to(repo_root):
            parser.error("private output must be outside the repository")
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=False, sort_keys=True)
            stream.write("\n")
    print("B3A56 Live PS module:", report["status"])
    for name in ("host_processes_present", "host_processes_modules_inspected",
                 "host_processes_module_inspection_blocked",
                 "exact_module_path_instances", "same_basename_other_path_instances",
                 "installed_disk_sha256_matches_pinned",
                 "expected_ini_present_at_module_directory"):
        print(name + ":", report[name])
    print("Actual active INI / VIDA ReadVin / ECU identification: NOT_VERIFIED")
    print("No PID/path/VIN exposed; no registry, VIDA, J2534 or DLL modifications")


if __name__ == "__main__":
    main()
