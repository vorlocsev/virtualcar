#!/usr/bin/env python3
"""B3A303: recover J2534 CONNECT flags from before the B3A300 action window.

The recovered CEM_IDENT action begins at exact log byte offset 70691072,
possibly inside a line. This tool reads only older, immutable-position bytes,
drops incomplete boundary lines, and finds the last live connection for a
selected channel and exact original-VIDA PID.

Never prints raw log lines, VIN, frame bytes, source paths, or private values.
No VIDA actions, ECU access, file/INI/SQL writes, DLL/provider/registry edits.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([^\]]+)\] (.*)$")
HEX = re.compile(r"^(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*$")
PID = re.compile(r"[0-9A-Fa-f]{8}\Z")
CONNECT = "J2534 scope channel_connect (BE)"
DISCONNECT = "J2534 scope channel_disconnect (BE)"


def parse_hex(body: str, prefix: str) -> bytes | None:
    if not body.startswith(prefix + " "):
        return None
    tail = body[len(prefix)+1:].strip()
    if HEX.fullmatch(tail) is None:
        return None
    result = bytes.fromhex(tail)
    return result if len(result) == 32 else None


def be32(raw: bytes, off: int) -> int:
    return int.from_bytes(raw[off:off+4], "big")


def scan(text: str, pid: str, channel: int) -> list[str]:
    stats = Counter()
    live: dict[int, tuple[int, int, int, int]] = {}
    last_for_selected = "NOT_SEEN"
    last_serial = None

    for row in text.splitlines():
        m = TAG.match(row)
        if m is None or m.group(1).upper() != pid or m.group(2).upper() != "IEXPLORE.EXE":
            continue
        stats["PID_LINES"] += 1
        body = m.group(3)
        if body.startswith(CONNECT + " "):
            raw = parse_hex(body, CONNECT)
            if raw is None:
                stats["MALFORMED_CONNECT"] += 1
                continue
            ch, hi, lo, proto, baud, flags = (be32(raw, i) for i in (0, 4, 8, 12, 16, 20))
            serial = (hi << 32) | lo
            live[ch] = (serial, proto, baud, flags)
            stats["CONNECT"] += 1
            if ch == channel:
                stats["SELECTED_CONNECT"] += 1
                last_for_selected = "CONNECT"
                last_serial = serial

        if body.startswith(DISCONNECT + " "):
            raw = parse_hex(body, DISCONNECT)
            if raw is None:
                stats["MALFORMED_DISCONNECT"] += 1
                continue
            ch, hi, lo = (be32(raw, i) for i in (0, 4, 8))
            serial = (hi << 32) | lo
            stats["DISCONNECT"] += 1
            if ch in live and live[ch][0] == serial:
                del live[ch]
            if ch == channel:
                stats["SELECTED_DISCONNECT"] += 1
                last_for_selected = "DISCONNECT"
                last_serial = serial

    out = [
        f"B3A303_EXACT_PID={pid}",
        f"B3A303_SELECTED_CHANNEL={channel}",
        f"B3A303_PREWINDOW_PID_LINES={stats['PID_LINES']}",
        f"B3A303_CONNECT_EVENTS={stats['CONNECT']}",
        f"B3A303_DISCONNECT_EVENTS={stats['DISCONNECT']}",
        f"B3A303_SELECTED_CONNECT_EVENTS={stats['SELECTED_CONNECT']}",
        f"B3A303_SELECTED_DISCONNECT_EVENTS={stats['SELECTED_DISCONNECT']}",
        f"B3A303_MALFORMED_CONNECT={stats['MALFORMED_CONNECT']}",
        f"B3A303_MALFORMED_DISCONNECT={stats['MALFORMED_DISCONNECT']}",
        f"B3A303_LAST_SELECTED_EVENT={last_for_selected}",
        f"B3A303_LAST_SELECTED_SERIAL=" +
        (str(last_serial) if last_serial is not None else "UNKNOWN"),
    ]

    current = live.get(channel)
    if current is None:
        out.extend((
            "B3A303_SELECTED_CHANNEL_ACTIVE_AT_WINDOW_START=NOT_PROVEN",
            "B3A303_SELECTED_CONNECT_FLAGS=UNKNOWN",
            "B3A303_CONNECT_ONLY_GGD_GUARD=UNKNOWN",
            "B3A303_OUTCOME=NO_LIVE_CONNECT_IN_SCANNED_PREWINDOW",
        ))
    else:
        serial, proto, baud, flags = current
        guard = proto == 6 and baud == 500000 and flags == 0x100
        out.extend((
            "B3A303_SELECTED_CHANNEL_ACTIVE_AT_WINDOW_START=TRUE",
            f"B3A303_SELECTED_SERIAL={serial}",
            f"B3A303_SELECTED_PROTOCOL={proto}",
            f"B3A303_SELECTED_BAUD={baud}",
            f"B3A303_SELECTED_CONNECT_FLAGS=0x{flags:08X}",
            f"B3A303_CONNECT_ONLY_GGD_GUARD={'TRUE' if guard else 'FALSE'}",
            "B3A303_OUTCOME=LIVE_CONNECT_FOUND",
        ))
    out.extend((
        "B3A303_SCOPE=PREWINDOW_CONNECT_HISTORY_NOT_GUI_ACCEPTANCE",
        "B3A303_NO_INFERRED_RECEIVED_ECU_CONTENT=TRUE",
        "B3A303_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="B3A303 original VIDA prior channel CONNECT flags")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--window-start", required=True, type=int)
    p.add_argument("--lookback-bytes", type=int, default=4 * 1024 * 1024)
    p.add_argument("--pid", default="00002710")
    p.add_argument("--channel", type=int, default=1)
    args = p.parse_args()
    pid = args.pid.upper()
    if (PID.fullmatch(pid) is None or not 1 <= args.channel <= 8
            or args.window_start <= 0
            or not 1 <= args.lookback_bytes <= 32*1024*1024):
        print("B3A303_RESULT=ERROR_INVALID_ARGUMENT")
        return 2

    capture = runpy.run_path(
        str(Path(__file__).resolve().with_name("B3A300-Recover-VIDA-Gate-Window.py")),
        run_name="b3a303_import_capture",
    )["capture_historic"]
    lookback = min(args.lookback_bytes, args.window_start)
    try:
        with args.log.open("rb") as stream:
            data, _, discarded, start = capture(
                stream, end_offset=args.window_start, window_bytes=lookback)
    except (ValueError, OSError):
        print("B3A303_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    print(f"B3A303_PREWINDOW_START={start}")
    print(f"B3A303_PREWINDOW_END={args.window_start}")
    print(f"B3A303_PREWINDOW_REQUESTED_BYTES={lookback}")
    print(f"B3A303_DISCARDED_PARTIAL_LINE_BYTES={discarded}")
    for line in scan(data.decode("latin-1"), pid, args.channel):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
