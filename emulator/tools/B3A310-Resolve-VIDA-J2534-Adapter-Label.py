#!/usr/bin/env python3
"""B3A310 - resolve the exact current J2534 provider LABEL for original VIDA epoch 3.

Read-only: recover original logged epoch3 Active INI using B3A306's fixed log
window, match its DLL parent directory against the CURRENT 32-bit J2534
FunctionLibrary registry. Print ONLY the matching provider label (registry
subkey name), status/counts, and CURRENT GGD readiness. Never output paths,
VIN, raw log lines, ECU bytes, hashes, INI contents or full registry values.
No writes/driver loads/VIDA actions. A directory match is not proof which
provider was selected historically. Label may be renamed since capture.
"""
from __future__ import annotations
import argparse
import ntpath
import os
from pathlib import Path
import re
import runpy
import sys

PID_RE = re.compile(r"[0-9A-Fa-f]{8}\Z")
LABEL_RE = re.compile(r"[A-Za-z0-9 _().-]{1,120}\Z")


def peer(filename: str):
    return runpy.run_path(
        str(Path(__file__).resolve().with_name(filename)),
        run_name="b3a310_peer_import",
    )


def registry_labels_32():
    if os.name != "nt":
        return "UNSUPPORTED_PLATFORM", []
    import winreg
    entries = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\PassThruSupport.04.04", 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as root:
            index = 0
            while True:
                try:
                    label = winreg.EnumKey(root, index)
                except OSError as error:
                    if getattr(error, "winerror", None) == 259:
                        break
                    return "ENUMERATION_ERROR", []
                index += 1
                try:
                    with winreg.OpenKey(root, label, 0, winreg.KEY_READ) as entry:
                        raw, typ = winreg.QueryValueEx(entry, "FunctionLibrary")
                        if typ in (winreg.REG_SZ, winreg.REG_EXPAND_SZ) and isinstance(raw, str):
                            entries.append((label, os.path.expandvars(raw)))
                except OSError:
                    continue
    except FileNotFoundError:
        return "NOT_PRESENT", []
    except PermissionError:
        return "ACCESS_DENIED", []
    except OSError:
        return "READ_ERROR", []
    return "READ_OK", entries


def resolve(paths: dict[int, bytes | None], registered: list[tuple[str, str]],
            readiness=None) -> list[str]:
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    current_ini = b306["decode_log_path"](paths.get(3))
    dirname = b307["canonical_dir_from_ini"](current_ini)
    matches = [(label, dll) for label, dll in registered
               if dirname and b307["canonical_dir_from_dll"](dll) == dirname]
    output = [
        "B3A310_SOURCE=HISTORICAL_EPOCH3_ACTIVE_INI_PLUS_CURRENT_REG32",
        f"B3A310_EPOCH3_PROVIDER_MATCH_COUNT={len(matches)}",
        "B3A310_MATCH_LEVEL=REGISTERED_DLL_DIRECTORY",
        "B3A310_HISTORICAL_PROVIDER_SELECTION=NOT_PROVEN",
    ]
    if len(matches) != 1:
        output.append("B3A310_ADAPTER_LABEL=UNRESOLVED")
        output.append("B3A310_RESULT=AMBIGUOUS_OR_NO_MATCH")
        return output
    label, _ = matches[0]
    # Registry labels are already visible in the user's list, but avoid
    # leaking unusual paths/identifiers embedded in arbitrary key names.
    safe_label = label if LABEL_RE.fullmatch(label) else "UNSAFE_LABEL_REDACTED"
    output.append("B3A310_ADAPTER_LABEL=" + safe_label)
    if readiness is not None:
        try:
            ready = readiness(current_ini)
            output.append("B3A310_EPOCH3_CURRENT_GGD_READY=" +
                          ("TRUE" if ready else "FALSE"))
        except (OSError, ValueError):
            output.append("B3A310_EPOCH3_CURRENT_GGD_READY=READ_ERROR")
    else:
        output.append("B3A310_EPOCH3_CURRENT_GGD_READY=NOT_ASSESSED")
    output.extend((
        "B3A310_HISTORICAL_BINARY_IDENTITY=NOT_PROVEN",
        "B3A310_NO_REGISTRY_INI_DLL_WRITES=TRUE",
        "B3A310_RESULT=READ_ONLY_COMPLETE",
    ))
    return output


def main() -> int:
    p = argparse.ArgumentParser(description="Resolve unique epoch3 J2534 adapter label")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--window-start", required=True, type=int)
    p.add_argument("--window-end", required=True, type=int)
    p.add_argument("--lookback-bytes", type=int, default=4194304)
    p.add_argument("--expected-action-lines", type=int, required=True)
    p.add_argument("--pid", default="00002710")
    args = p.parse_args()
    pid = args.pid.upper()
    if (not PID_RE.fullmatch(pid) or args.window_start <= 0
            or args.window_end <= args.window_start
            or not 1 <= args.lookback_bytes <= 32*1024*1024
            or not 1 <= args.expected_action_lines <= 500000):
        print("B3A310_RESULT=ERROR_ARGUMENTS")
        return 2
    b300 = peer("B3A300-Recover-VIDA-Gate-Window.py")
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    try:
        with args.log.open("rb") as stream:
            sample, _, trim, start = b300["capture_historic"](
                stream, end_offset=args.window_end,
                window_bytes=args.window_end - args.window_start +
                min(args.lookback_bytes, args.window_start))
    except (ValueError, OSError):
        print("B3A310_RESULT=ERROR_ORIGINAL_LOG")
        return 1
    paths, audit = b306["scan"](
        sample, begin=start + trim,
        action_start=args.window_start, action_end=args.window_end,
        pid=pid, expected_action_lines=args.expected_action_lines)
    if "B3A306_ACTION_CENSUS_MATCH=TRUE" not in audit or not paths.get(3):
        print("B3A310_RESULT=ERROR_CENSUS_OR_EPOCH3_PATH")
        return 1
    state, provider_list = registry_labels_32()
    print("B3A310_HISTORICAL_CENSUS_MATCH=TRUE")
    print("B3A310_REG32_STATUS=" + state)
    if state != "READ_OK":
        print("B3A310_RESULT=ERROR_REG32_UNAVAILABLE")
        return 1

    def current_ready(path):
        if (path is None or not ntpath.isabs(path)
                or ntpath.basename(path).casefold() != "virtualcar.ini"
                or not os.path.isfile(path)):
            raise OSError("INI missing")
        getter = b306["win_ini_getter"](path)
        values = b306["evaluate_current"](getter)
        return values["lab_and_route_ready"] == "TRUE"

    for result in resolve(paths, provider_list, readiness=current_ready):
        print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
