#!/usr/bin/env python3
"""B3A292: read-only VIDA D2 route outcome attribution, exact IEXPLORE PID.

The VirtualCar DLL writes the four-byte CB target B9 opcode on the same
"staged", "no validated fixture", and "strict route rejected" log lines.
This tool counts those observed outcomes by target/opcode and recorded baud,
without inferring them from unrelated TX counts. No VIN or CAN frame payload
is printed. No files, registry, original VIDA or ECU are modified.
"""
from __future__ import annotations

import argparse
from collections import Counter, deque
from pathlib import Path
import re
import sys

PID_LINE = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([^\]]+)\] (.*)$")
HEX = re.compile(r"^(?:[0-9a-fA-F]{2})(?: [0-9a-fA-F]{2})*$")
CONTEXT = "P2 D2 service context channel/target/service/opcode/baud (BE) "
OUTCOMES = {
    "P2 D2 read-only recorded frames staged ": "STAGED",
    "P2 D2 read command: no validated response fixture ": "NO_FIXTURE",
    "P2 D2 strict route rejected (no fixture emitted) ": "ROUTE_REJECTED",
    "P2 D2 command: no recorded ECU fixture for target ": "NO_ECU_FIXTURE",
}


def bytes_if_hex(s: str, n: int) -> bytes | None:
    if not HEX.fullmatch(s):
        return None
    b = bytes.fromhex(s)
    return b if len(b) == n else None


def u32(b: bytes, offset: int) -> int:
    return int.from_bytes(b[offset:offset + 4], "big")


def audit(lines: list[str], pid: str) -> list[str]:
    counts = Counter()
    channel_serial: dict[int, int] = {}
    # Context is logged immediately in process_d2 under PassThruWriteMsgs'
    # serialized route handling; fail closed when an event does not match it.
    context: tuple[int, int, int, int, int, int] | None = None
    for line in lines:
        m = PID_LINE.match(line.rstrip("\r\n"))
        if m is None or m.group(1).upper() != pid or m.group(2).upper() != "IEXPLORE.EXE":
            continue
        counts["PID_LINES"] += 1
        body = m.group(3)
        if body.startswith("J2534 scope channel_connect (BE) "):
            v = bytes_if_hex(body.partition("(BE) ")[2], 32)
            if v is not None:
                channel_serial[u32(v, 0)] = u32(v, 8)
            context = None
            continue
        if body.startswith("J2534 scope channel_disconnect (BE) "):
            v = bytes_if_hex(body.partition("(BE) ")[2], 32)
            if v is not None and channel_serial.get(u32(v, 0)) == u32(v, 8):
                channel_serial.pop(u32(v, 0), None)
            context = None
            continue
        if body.startswith(CONTEXT):
            v = bytes_if_hex(body[len(CONTEXT):], 20)
            if v is None:
                context = None
                counts["INVALID_CONTEXT"] += 1
            else:
                ch, target, service, opcode, baud = (u32(v, i) for i in (0, 4, 8, 12, 16))
                context = (ch, channel_serial.get(ch, -1), target, service, opcode, baud)
            continue

        for prefix, outcome in OUTCOMES.items():
            if not body.startswith(prefix):
                continue
            data = bytes_if_hex(body[len(prefix):], 4)
            if data is None:
                counts["MALFORMED_OUTCOME"] += 1
                break
            # Only emit target/subcommand, never the literal CAN frame.
            target, service, opcode = data[1], data[2], data[3]
            if data[0] not in (0xCB, 0xCF, 0xCA):
                counts["UNEXPECTED_PREFIX"] += 1
                break
            if (
                context is None
                or context[2] != target
                or context[3] != service
                or context[4] != opcode
            ):
                counts["OUTCOME_WITHOUT_MATCHING_CONTEXT"] += 1
                # We can still independently attribute observed target/service
                # and opcode from the outcome bytes, not channel or baud.
                label = f"target:{target:02X},service:{service:02X},opcode:{opcode:02X},baud:UNKNOWN,serial:UNKNOWN"
            else:
                _, serial, _, _, _, baud = context
                label = f"target:{target:02X},service:{service:02X},opcode:{opcode:02X},baud:{baud},serial:{serial}"
            counts[(outcome, label)] += 1
            context = None
            break

    out = [
        f"B3A292_EXACT_PID={pid}",
        f'B3A292_PID_LINES={counts["PID_LINES"]}',
        "B3A292_SCOPE=RECORDED_D2_OUTCOMES_NOT_GUI_ACCEPTANCE",
    ]
    for outcome in ("STAGED", "NO_FIXTURE", "ROUTE_REJECTED", "NO_ECU_FIXTURE"):
        rows = [
            (key[1], n) for key, n in counts.items()
            if isinstance(key, tuple) and key[0] == outcome
        ]
        out.append(f"B3A292_{outcome}_TOTAL={sum(n for _, n in rows)}")
        for label, n in sorted(rows):
            out.append(f"B3A292_{outcome}={label},count:{n}")
    for err in ("INVALID_CONTEXT", "MALFORMED_OUTCOME", "UNEXPECTED_PREFIX",
                "OUTCOME_WITHOUT_MATCHING_CONTEXT"):
        out.append(f"B3A292_{err}={counts[err]}")
    out.append("B3A292_RESULT=READ_ONLY_COMPLETE")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="B3A292 D2 route outcome audit (read-only)")
    ap.add_argument("--log", required=True, type=Path)
    ap.add_argument("--pid", default="00001828")
    ap.add_argument("--tail-lines", type=int, default=100000)
    args = ap.parse_args()
    pid = args.pid.upper()
    if re.fullmatch(r"[0-9A-F]{8}", pid) is None or not 1 <= args.tail_lines <= 500000:
        print("B3A292_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    try:
        with args.log.open("r", encoding="latin-1", errors="replace") as handle:
            lines = list(deque(handle, maxlen=args.tail_lines))
    except OSError:
        print("B3A292_RESULT=ERROR_LOG_UNAVAILABLE")
        return 1
    for line in audit(lines, pid):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
