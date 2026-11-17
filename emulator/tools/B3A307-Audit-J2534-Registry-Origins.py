#!/usr/bin/env python3
"""B3A307: read-only J2534 v04.04 registry to original VIDA DLL-origin audit.

Original VirtualCar creates virtualcar.ini beside the LOADED J2534 DLL:
GetModuleFileNameA(g_module) -> parent directory -> virtualcar.ini.
The same native IEXPLORE.EXE PID loaded different Active INI paths in
PassThruOpen epochs 2 and 3. This tool checks whether those historical
DIRECTORIES correspond to any current J2534 v04.04 FunctionLibrary entry
in the 32- and 64-bit HKLM registry views.

CAVEATS:
- A same-directory match does NOT prove which exact DLL or version VIDA
  loaded: there may be multiple DLLs in that directory, a loader shim,
  an unregistered direct load, or an alias/junction.
- Registry entries and INI content are CURRENT, not a past snapshot.
- A registered provider does NOT establish active use in original VIDA.
- No registry writes, DLL loads, VIDA/ECU actions, file changes, raw VIN,
  original log payloads, provider names or path strings are emitted.
"""
from __future__ import annotations

import argparse
import ntpath
import os
from pathlib import Path
import re
import runpy
import sys

MAX_WINDOW = 32 * 1024 * 1024
PID = re.compile(r"[0-9A-Fa-f]{8}\Z")
ROOT = r"SOFTWARE\PassThruSupport.04.04"


def peer(filename: str):
    return runpy.run_path(
        str(Path(__file__).resolve().with_name(filename)),
        run_name="b3a307_peer_import",
    )


def canonical_dir_from_ini(path: str | None) -> str | None:
    if not path or not ntpath.isabs(path):
        return None
    if ntpath.basename(path).casefold() != "virtualcar.ini":
        return None
    return ntpath.normcase(ntpath.normpath(ntpath.dirname(path)))


def canonical_dir_from_dll(path: str | None) -> str | None:
    if not isinstance(path, str) or not ntpath.isabs(path):
        return None
    if ntpath.splitext(path)[1].casefold() != ".dll":
        return None
    return ntpath.normcase(ntpath.normpath(ntpath.dirname(path)))


def registry_sources() -> dict[str, dict]:
    """Only read HKLM\SOFTWARE\PassThruSupport.04.04 using explicit WOW64 views."""
    output = {}
    if os.name != "nt":
        return {
            "32": {"state": "UNSUPPORTED_PLATFORM", "paths": []},
            "64": {"state": "UNSUPPORTED_PLATFORM", "paths": []},
        }
    try:
        import winreg
    except ImportError:
        return {
            "32": {"state": "UNSUPPORTED_PLATFORM", "paths": []},
            "64": {"state": "UNSUPPORTED_PLATFORM", "paths": []},
        }

    views = {
        "32": winreg.KEY_WOW64_32KEY,
        "64": winreg.KEY_WOW64_64KEY,
    }
    for view, flag in views.items():
        paths = []
        state = "READ_OK"
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, ROOT, 0,
                                winreg.KEY_READ | flag) as root:
                idx = 0
                while True:
                    try:
                        child = winreg.EnumKey(root, idx)
                    except OSError as e:
                        if getattr(e, "winerror", None) in (259,):
                            break  # ERROR_NO_MORE_ITEMS
                        # Python winreg EnumKey may use OSError without winerror.
                        if getattr(e, "errno", None) == 22:
                            break
                        # A normal exhausted iterator also raises OSError:
                        # WinError 259 is supported on Windows.
                        state = "ENUMERATION_ERROR"
                        break
                    idx += 1
                    try:
                        with winreg.OpenKey(root, child, 0, winreg.KEY_READ) as key:
                            value, value_type = winreg.QueryValueEx(key, "FunctionLibrary")
                            if value_type in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(value, str):
                                paths.append(os.path.expandvars(value))
                    except (OSError, ValueError):
                        continue
        except FileNotFoundError:
            state = "NOT_PRESENT"
        except PermissionError:
            state = "ACCESS_DENIED"
        except OSError:
            state = "READ_ERROR"
        output[view] = {"state": state, "paths": paths}
    return output


def snapshot_report(paths: dict[int, bytes | None], registry: dict[str, dict],
                    get_current=None) -> list[str]:
    from_b3a306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    decode = from_b3a306["decode_log_path"]
    canonical = from_b3a306["canonical"]
    evaluate = from_b3a306["evaluate_current"]
    original = {ep: decode(paths.get(ep)) for ep in (2, 3)}
    directories = {ep: canonical_dir_from_ini(original[ep]) for ep in (2, 3)}
    p2, p3 = canonical(paths.get(2)), canonical(paths.get(3))
    out = [
        "B3A307_SOURCE=ORIGINAL_VIDA_LOG_PLUS_CURRENT_WINDOWS_REGISTRY",
        "B3A307_REGISTRY_VERSION=PASSTHRUSUPPORT_04_04",
        "B3A307_COMPARE_LEVEL=DLL_PARENT_DIRECTORY_ONLY",
        "B3A307_EXACT_DLL_IDENTITY=NOT_PROVEN",
        "B3A307_HISTORICAL_REGISTRY_STATE=NOT_SAVED",
        "B3A307_ORIGINAL_VIDA_PROVIDER_SELECTION=NOT_PROVEN",
        "B3A307_EPOCH2_INI_LOGGED=" + ("TRUE" if original[2] else "FALSE"),
        "B3A307_EPOCH3_INI_LOGGED=" + ("TRUE" if original[3] else "FALSE"),
        "B3A307_NORMALIZED_INI_PATHS_DIFFER=" +
        ("UNKNOWN" if p2 is None or p3 is None else "TRUE" if p2 != p3 else "FALSE"),
    ]
    for view in ("32", "64"):
        result = registry.get(view, {"state": "UNAVAILABLE", "paths": []})
        registry_paths = [
            canonical_dir_from_dll(path)
            for path in result.get("paths", ())
        ]
        out.append(f"B3A307_REG{view}_STATUS={result['state']}")
        out.append(f"B3A307_REG{view}_FUNCTIONLIBRARY_ENTRIES={len(registry_paths)}")
        out.append(f"B3A307_REG{view}_VALID_ABSOLUTE_DLL_PATH_ENTRIES="
                   f"{sum(item is not None for item in registry_paths)}")
        for ep in (2, 3):
            base = directories[ep]
            count = sum(p == base for p in registry_paths) if base else 0
            out.append(
                f"B3A307_REG{view}_EPOCH{ep}_SAME_DIRECTORY_ENTRIES={count}"
            )
            if base is None:
                verdict = "UNKNOWN"
            elif result["state"] != "READ_OK":
                verdict = "NOT_ASSESSED"
            else:
                verdict = "TRUE" if count else "FALSE"
            out.append(f"B3A307_REG{view}_EPOCH{ep}_DIR_MATCH={verdict}")

    if get_current is None:
        out.append("B3A307_CURRENT_INI_INSPECTION=NOT_REQUESTED")
    else:
        out.append("B3A307_CURRENT_INI_INSPECTION=READ_ONLY")
        for ep in (2, 3):
            if not original[ep]:
                out.append(f"B3A307_EPOCH{ep}_CURRENT_READY=NOT_ASSESSED")
                continue
            try:
                values = evaluate(get_current(original[ep]))
                out.append(f"B3A307_EPOCH{ep}_CURRENT_READY="
                           f"{values['lab_and_route_ready']}")
            except (OSError, ValueError):
                out.append(f"B3A307_EPOCH{ep}_CURRENT_READY=READ_ERROR")
    out.extend((
        "B3A307_CURRENT_READY_IS_NOT_HISTORICAL_GGD_STATE",
        "B3A307_NO_REGISTRY_OR_INI_MUTATIONS=TRUE",
        "B3A307_VIDA_GUI_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A307_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="B3A307 read-only current J2534 provider origin audit")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--window-start", required=True, type=int)
    p.add_argument("--window-end", required=True, type=int)
    p.add_argument("--lookback-bytes", type=int, default=4 * 1024 * 1024)
    p.add_argument("--expected-action-lines", type=int, required=True)
    p.add_argument("--pid", default="00002710")
    p.add_argument("--inspect-current-files", action="store_true")
    args = p.parse_args()

    pid = args.pid.upper()
    if (not PID.fullmatch(pid) or args.window_start <= 0
            or args.window_end <= args.window_start
            or not 1 <= args.lookback_bytes <= MAX_WINDOW
            or not 1 <= args.expected_action_lines <= 500000):
        print("B3A307_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    recovery = peer("B3A300-Recover-VIDA-Gate-Window.py")["capture_historic"]
    old = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    lookback = min(args.lookback_bytes, args.window_start)
    try:
        with args.log.open("rb") as stream:
            sample, _, trim, begin = recovery(
                stream,
                end_offset=args.window_end,
                window_bytes=args.window_end - args.window_start + lookback,
            )
    except (OSError, ValueError):
        print("B3A307_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    paths, audit = old["scan"](
        sample, begin=begin + trim, action_start=args.window_start,
        action_end=args.window_end, pid=pid,
        expected_action_lines=args.expected_action_lines,
    )
    match = next((line for line in audit if
                  line.startswith("B3A306_ACTION_CENSUS_MATCH=")), "")
    if not paths or match != "B3A306_ACTION_CENSUS_MATCH=TRUE":
        print("B3A307_RESULT=ERROR_CENSUS_OR_PATH_RECOVERY")
        return 1

    print(f"B3A307_COMBINED_START={begin}")
    print(f"B3A307_COMBINED_END={args.window_end}")
    print(f"B3A307_ACTION_LINE_COUNT={args.expected_action_lines}")
    print("B3A307_ACTION_CENSUS_MATCH=TRUE")
    getter = None
    if args.inspect_current_files and os.name == "nt":
        # Reuse exact source-backed Win32 read-only INI parsing.
        native = old["win_ini_getter"]
        def getter(path):
            if (not ntpath.isabs(path)
                    or ntpath.basename(path).casefold() != "virtualcar.ini"
                    or not os.path.isfile(path)):
                raise OSError("No safe current INI file")
            return native(path)
    for line in snapshot_report(paths, registry_sources(), get_current=getter):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
