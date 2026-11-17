#!/usr/bin/env python3
"""B3A298: read-only, owner-controlled VIDA GUI action vs J2534 log window.

1. Start this tool with original VIDA open and virtual J2534 logging enabled.
2. When CAPTURE_READY appears, perform ONE GUI action (Read Vehicle or
   CEM ECU Identification) in original VIDA.
3. Return to the console and press Enter. The tool reads only the bytes
   appended to the log AFTER the first file-size snapshot.
4. Capture the corresponding VIDA GUI screenshot separately.

The tool never prints VIN, chassis, complete lines, frame bytes, source paths
or private data; it does not operate VIDA, launch any jobs, touch SQL or ECU,
modify any file/INI/driver/registry, or assert GUI acceptance from traffic.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys

HOST_LINE = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([^\]]+)\] (.*)$")
HEX_BYTES = re.compile(r"^(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*$")
DIDS = ("F110", "F114", "F106", "A45F", "DD02")
D2_NAMES = (
    (0x40, 0xB9, 0xF0, "CEM40_B9F0"),
    (0x40, 0xB9, 0xFB, "CEM40_B9FB"),
    (0x40, 0xAE, 0x1B, "CEM40_AE1B"),
    (0x50, 0xB9, 0xF0, "CEM50_B9F0"),
    (0x50, 0xB9, 0xFB, "CEM50_B9FB"),
)
D2_KEYS = {(target, service, opcode): name
           for target, service, opcode, name in D2_NAMES}

OUTCOMES = {
    "P2 D2 read-only recorded frames staged": "STAGED",
    "P2 D2 read command: no validated response fixture": "NO_FIXTURE",
    "P2 D2 strict route rejected (no fixture emitted)": "ROUTE_REJECTED",
    "P2 D2 command: no recorded ECU fixture for target": "NO_ECU_FIXTURE",
}


def hex_suffix(message: str, prefix: str) -> bytes | None:
    if not message.startswith(prefix + " "):
        return None
    value = message[len(prefix) + 1:].strip()
    if not HEX_BYTES.fullmatch(value):
        return None
    return bytes.fromhex(value)


def analyze(text: str, pid: str, gate: str) -> list[str]:
    counts = Counter()
    for line in text.splitlines():
        match = HOST_LINE.match(line)
        if not match or match.group(1).upper() != pid or match.group(2).upper() != "IEXPLORE.EXE":
            continue
        counts["PID_LINES"] += 1
        message = match.group(3)

        tx = hex_suffix(message, "TX (app request)")
        if tx is not None and len(tx) >= 7:
            arbitration = int.from_bytes(tx[:4], "big")
            if arbitration == 0x18DA50F1 and tx[4] == 0x22:
                did = tx[5:7].hex().upper()
                if did in DIDS:
                    counts[f"UDS_{did}_TX"] += 1
            if (arbitration == 0x000FFFFE and len(tx) >= 8
                    and tx[4] == 0xCB):
                name = D2_KEYS.get((tx[5], tx[6], tx[7]), "OTHER")
                counts[f"D2_{name}_TX"] += 1

        rx = hex_suffix(message, "PassThruReadMsgs -> delivered")
        if rx is not None and len(rx) >= 7:
            arbitration = int.from_bytes(rx[:4], "big")
            if arbitration == 0x18DAF150:
                payload = rx[4:]
                if payload[0] == 0x62 and len(payload) >= 3:
                    did = payload[1:3].hex().upper()
                    if did in DIDS:
                        counts[f"UDS_{did}_POSITIVE_DELIVERED"] += 1
                elif payload[:2] == bytes.fromhex("7F22"):
                    counts[f"UDS_22_NRC_{payload[2]:02X}_DELIVERED"] += 1

        if message.startswith("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE) "):
            counts["D2_DELIVERED_FRAME_META"] += 1

        for prefix, category in OUTCOMES.items():
            raw = hex_suffix(message, prefix)
            if raw is None or len(raw) != 4:
                continue
            name = D2_KEYS.get((raw[1], raw[2], raw[3]), "OTHER")
            counts[f"D2_{name}_{category}"] += 1
            break

    output = [
        f"B3A298_GATE={gate.upper().replace('-', '_')}",
        f"B3A298_EXACT_PID={pid}",
        f"B3A298_PID_LINES_IN_WINDOW={counts['PID_LINES']}",
        "B3A298_SCOPE=APPENDED_BYTES_OF_SINGLE_GUI_ACTION",
        "B3A298_NRC_ATTRIBUTION=SERVICE_ONLY_NOT_TO_INDIVIDUAL_DID",
    ]
    for did in DIDS:
        output.append(f"B3A298_UDS_{did}_TX={counts[f'UDS_{did}_TX']}")
        output.append(f"B3A298_UDS_{did}_POSITIVE_DELIVERED={counts[f'UDS_{did}_POSITIVE_DELIVERED']}")
    for code in ("31", "11", "33", "78"):
        output.append(f"B3A298_UDS_22_NRC_{code}_DELIVERED={counts[f'UDS_22_NRC_{code}_DELIVERED']}")
    for name in tuple(name for *_, name in D2_NAMES) + ("OTHER",):
        for suffix in ("TX", "STAGED", "NO_FIXTURE", "ROUTE_REJECTED", "NO_ECU_FIXTURE"):
            if (name != "OTHER" or counts[f"D2_OTHER_{suffix}"]):
                output.append(f"B3A298_D2_{name}_{suffix}={counts[f'D2_{name}_{suffix}']}")
    output.extend((
        f"B3A298_D2_DELIVERED_FRAME_META={counts['D2_DELIVERED_FRAME_META']}",
        "B3A298_GUI_ACCEPTANCE=NEEDS_SEPARATE_SCREENSHOT",
        "B3A298_RESULT=READ_ONLY_COMPLETE",
    ))
    return output


def main() -> int:
    p = argparse.ArgumentParser(description="B3A298: isolate one original VIDA GUI action in J2534 log")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--pid", default="00001828")
    p.add_argument("--gate", choices=("readvin", "cem-ident"), required=True)
    p.add_argument("--max-bytes", type=int, default=32 * 1024 * 1024)
    args = p.parse_args()
    pid = args.pid.upper()
    if re.fullmatch(r"[0-9A-F]{8}", pid) is None or not 1 <= args.max_bytes <= 128 * 1024 * 1024:
        print("B3A298_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    try:
        before = args.log.stat()
        if not args.log.is_file():
            raise OSError("not file")
    except OSError:
        print("B3A298_RESULT=ERROR_LOG_UNAVAILABLE")
        return 1

    print("B3A298_CAPTURE_READY=TRUE")
    print("B3A298_INSTRUCTION=PERFORM_ONE_VIDA_GUI_ACTION_THEN_PRESS_ENTER")
    try:
        input()
    except (EOFError, KeyboardInterrupt):
        print("B3A298_RESULT=ERROR_CAPTURE_CANCELLED")
        return 1

    try:
        after = args.log.stat()
        if after.st_size < before.st_size or (before.st_ino and after.st_ino
                                            and before.st_ino != after.st_ino):
            print("B3A298_RESULT=ERROR_LOG_REPLACED_OR_TRUNCATED")
            return 1
        changed = after.st_size - before.st_size
        if changed > args.max_bytes:
            print("B3A298_RESULT=ERROR_WINDOW_TOO_LARGE")
            return 1
        with args.log.open("rb") as stream:
            stream.seek(before.st_size)
            new_data = stream.read(changed)
    except OSError:
        print("B3A298_RESULT=ERROR_LOG_READ")
        return 1
    print(f"B3A298_LOG_DELTA_BYTES={len(new_data)}")
    for item in analyze(new_data.decode("latin-1"), pid, args.gate):
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
