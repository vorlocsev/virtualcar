#!/usr/bin/env python3
"""B3A308: read-only current J2534 DLL binary identity vs original VIDA epochs.

Given the exact original VIDA log anchored window (action 1830 lines),
recover Active INI origins for Open epochs 2 and 3 using B3A306. For
each origin, find registered FunctionLibrary DLLs in 32-bit J2534 registry
view, matching only the DIRECTORY of that origin. If and only if exactly
one DLL is registered in an epoch directory, read its current binary bytes
without loading/executing it, check PE CPU architecture and two SOURCE-
backed GGD lab string markers, and compare both binary SHA256 values in
memory, outputting ONLY equality (not hash or binary bytes).

Caveats: same-directory matching is NOT historical loader attribution.
PE machine, presence/absence of source strings, and current file hashes
are NOT proof of registration selected by original VIDA nor of historical
GGD lab enable/config values. Does not read original VIDA SQL or raw ECU
payloads, print file/INI/registry paths, write files, change registration,
modify vehicle or emulator, run CI jobs, or launch any application.
"""
from __future__ import annotations

import argparse
import hashlib
import ntpath
from pathlib import Path
import re
import runpy
import sys

MAX_BINARY_BYTES = 64 * 1024 * 1024
PID_RE = re.compile(r"[0-9A-Fa-f]{8}\Z")
GGD_MARKERS = {
    "A45F": b"B3A274 LAB CEM50 GGD A45F synthetic positive",
    "DD02": b"B3A274 LAB CEM50 GGD DD02 synthetic positive",
}


def peer(name: str):
    return runpy.run_path(
        str(Path(__file__).resolve().with_name(name)),
        run_name="b3a308_import_peer",
    )


def read_binary(path: str) -> bytes:
    """Bounded current file read; does not load the DLL into any process."""
    file = Path(path)
    size = file.stat().st_size
    if size <= 0 or size > MAX_BINARY_BYTES:
        raise ValueError("size outside bounded audit")
    with file.open("rb") as stream:
        result = stream.read(MAX_BINARY_BYTES + 1)
    if len(result) != size:
        raise ValueError("size changed while reading")
    return result


def classify_bytes(data: bytes) -> dict[str, str]:
    """Do not emit bytes or SHA256, only synthesized metadata and digest internally."""
    if len(data) < 0x40 or data[:2] != b"MZ":
        machine = "NOT_PE"
    else:
        pe_off = int.from_bytes(data[0x3C:0x40], "little")
        if pe_off > len(data) - 6 or data[pe_off:pe_off+4] != b"PE\x00\x00":
            machine = "NOT_PE"
        else:
            number = int.from_bytes(data[pe_off+4:pe_off+6], "little")
            machine = {0x014C: "X86", 0x8664: "X64", 0xAA64: "ARM64"}.get(
                number, "OTHER")
    return {
        "machine": machine,
        "marker_a45f": "TRUE" if GGD_MARKERS["A45F"] in data else "FALSE",
        "marker_dd02": "TRUE" if GGD_MARKERS["DD02"] in data else "FALSE",
        "sha256_internal": hashlib.sha256(data).hexdigest(),
        "length": str(len(data)),
    }


def compare_current(paths, registry, read=read_binary):
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    decode = b306["decode_log_path"]
    ini_dir = b307["canonical_dir_from_ini"]
    dll_dir = b307["canonical_dir_from_dll"]

    view = registry.get("32", {"state": "UNAVAILABLE", "paths": []})
    registry_dlls = list(view.get("paths", []))
    output = [
        "B3A308_REGISTRY_VIEW=HKLM_J2534_32BIT",
        f"B3A308_REG32_STATUS={view.get('state', 'UNAVAILABLE')}",
        f"B3A308_REG32_ENTRY_COUNT={len(registry_dlls)}",
        "B3A308_COMPARISON=CURRENT_BINARY_NOT_HISTORICAL_DLL",
        "B3A308_DLL_TO_INI_MATCH=DIRECTORY_ONLY",
        "B3A308_PE_GGD_STRING_MARKERS_NOT_PROOF_OF_ACTIVE_LAB",
    ]
    inspected = {}
    for epoch in (2, 3):
        raw = decode(paths.get(epoch))
        directory = ini_dir(raw)
        matches = (
            [path for path in registry_dlls if dll_dir(path) == directory]
            if directory else []
        )
        output.append(f"B3A308_EPOCH{epoch}_DIRECTORY_MATCH_COUNT={len(matches)}")
        if view.get("state") != "READ_OK":
            output.append(f"B3A308_EPOCH{epoch}_BINARY_STATUS=REGISTRY_UNAVAILABLE")
            continue
        if directory is None:
            output.append(f"B3A308_EPOCH{epoch}_BINARY_STATUS=INI_PATH_UNAVAILABLE")
            continue
        if len(matches) != 1:
            output.append(f"B3A308_EPOCH{epoch}_BINARY_STATUS=AMBIGUOUS_OR_NO_MATCH")
            continue
        try:
            binary = read(matches[0])
            if not (0 < len(binary) <= MAX_BINARY_BYTES):
                raise ValueError("binary size")
            result = classify_bytes(binary)
        except (OSError, ValueError):
            output.append(f"B3A308_EPOCH{epoch}_BINARY_STATUS=UNREADABLE")
            continue
        inspected[epoch] = result
        output.extend((
            f"B3A308_EPOCH{epoch}_BINARY_STATUS=READ_ONLY_INSPECTED",
            f"B3A308_EPOCH{epoch}_PE_MACHINE={result['machine']}",
            f"B3A308_EPOCH{epoch}_BINARY_SIZE_BYTES={result['length']}",
            f"B3A308_EPOCH{epoch}_GGD_A45F_MARKER={result['marker_a45f']}",
            f"B3A308_EPOCH{epoch}_GGD_DD02_MARKER={result['marker_dd02']}",
        ))
    if 2 in inspected and 3 in inspected:
        equal = inspected[2]["sha256_internal"] == inspected[3]["sha256_internal"]
        output.append(f"B3A308_EPOCH2_VS_3_CURRENT_DLL_BYTES_EQUAL={'TRUE' if equal else 'FALSE'}")
    else:
        output.append("B3A308_EPOCH2_VS_3_CURRENT_DLL_BYTES_EQUAL=UNKNOWN")
    output.extend((
        "B3A308_SAME_HASH_DOES_NOT_MEAN_SAME_HISTORIC_MODULE",
        "B3A308_STRING_MARKER_ABSENCE_NOT_PROOF_OF_NO_CODE",
        "B3A308_SOURCE_ENABLED_STATE=NOT_AVAILABLE_PER_HISTORIC_OPEN",
        "B3A308_ORIGINAL_VIDA_PROVIDER_SELECTED=NOT_PROVEN",
        "B3A308_GUI_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A308_RESULT=READ_ONLY_COMPLETE",
    ))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="B3A308 read-only J2534 registered DLL PE identity")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--window-start", type=int, required=True)
    parser.add_argument("--window-end", type=int, required=True)
    parser.add_argument("--lookback-bytes", type=int, default=4194304)
    parser.add_argument("--expected-action-lines", type=int, required=True)
    parser.add_argument("--pid", default="00002710")
    args = parser.parse_args()
    pid = args.pid.upper()
    if (PID_RE.fullmatch(pid) is None or args.window_start <= 0
            or args.window_end <= args.window_start
            or not 1 <= args.lookback_bytes <= 32 * 1024 * 1024
            or not 1 <= args.expected_action_lines <= 500000):
        print("B3A308_RESULT=ERROR_INVALID_ARGUMENT")
        return 2

    peers = peer("B3A300-Recover-VIDA-Gate-Window.py")
    origins = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    registry_tool = peer("B3A307-Audit-J2534-Registry-Origins.py")
    lookback = min(args.window_start, args.lookback_bytes)
    try:
        with args.log.open("rb") as stream:
            data, _, trimmed, begin = peers["capture_historic"](
                stream, end_offset=args.window_end,
                window_bytes=args.window_end - args.window_start + lookback)
    except (OSError, ValueError):
        print("B3A308_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1

    paths, report = origins["scan"](
        data, begin=begin + trimmed,
        action_start=args.window_start,
        action_end=args.window_end,
        pid=pid,
        expected_action_lines=args.expected_action_lines,
    )
    if ("B3A306_ACTION_CENSUS_MATCH=TRUE" not in report
            or not paths or not paths.get(2) or not paths.get(3)):
        print("B3A308_RESULT=ERROR_ACTION_CENSUS_OR_PROFILE_PATH")
        return 1
    print(f"B3A308_CAPTURE_START={args.window_start}")
    print(f"B3A308_CAPTURE_END={args.window_end}")
    print(f"B3A308_ACTION_CENSUS_MATCH=TRUE")
    for row in compare_current(paths, registry_tool["registry_sources"]()):
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
