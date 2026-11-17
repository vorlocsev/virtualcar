#!/usr/bin/env python3
"""B3A305: privacy-safe VIDA GGD epoch RX audit and active-INI path comparison.

Read-only, original VirtualCar J2534 *log* bytes only. The native source
load_config() logs 'Active INI:' and 'VirtualCar DLL initialized' BEFORE it
logs 'PassThruOpen -> device 1'. Bind them to the NEXT device Open epoch.
No INI file is accessed, and its path is NEVER emitted or hashed for output.

Native RX context (channel/protocol/RxStatus/baud/time-us) is logged directly
before PassThruReadMsgs -> delivered. Count 0x18DAF150 service22 positives
and NRC31 by channel and serial/epoch; no per-request NRC attribution is made.

No VIN, OEM payload bytes, arbitrary DID responses, raw log line, timestamps,
paths, personal data, file writes, VIDA operations, ECU or registry activity.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(rb"^\[PID=([0-9A-Fa-f]{8}) ([^\]\r\n]{1,120})\] (.*)$")
HEX = re.compile(rb"^(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*$")
VALID_PID = re.compile(r"[0-9A-Fa-f]{8}\Z")
OPEN = b"PassThruOpen -> device 1"
CLOSE = b"PassThruClose"
INI = b"Active INI: "
INIT = b"VirtualCar DLL initialized"
CONN = b"J2534 scope channel_connect (BE)"
DISC = b"J2534 scope channel_disconnect (BE)"
DEV_CLOSE = b"J2534 scope channel_device_close (BE)"
RXCTX = b"RX context channel/protocol/status/baud/time-us (BE)"
RX = b"PassThruReadMsgs -> delivered"


def hex_bytes(body: bytes, label: bytes, size: int) -> bytes | None:
    if not body.startswith(label + b" "):
        return None
    raw = body[len(label) + 1:].strip()
    if HEX.fullmatch(raw) is None:
        return None
    try:
        value = bytes.fromhex(raw.decode("ascii"))
    except ValueError:
        return None
    return value if len(value) == size else None


def u32(b: bytes, off: int) -> int:
    return int.from_bytes(b[off:off+4], "big")


def classify_rx(payload: bytes) -> str | None:
    if len(payload) < 7 or u32(payload, 0) != 0x18DAF150:
        return None
    data = payload[4:]
    if len(data) >= 3 and data[0] == 0x62:
        did = data[1:3].hex().upper()
        return "POS_" + did if did in ("A45F", "DD02", "F110", "F114", "F106") else "OTHER_POS"
    if data[:2] == b"\x7f\x22" and len(data) >= 3:
        return "NRC31" if data[2] == 0x31 else "OTHER_NRC"
    return None


def audit(data: bytes, *, start_offset: int, action_start: int,
          action_end: int, pid: str, expected_action_lines: int) -> list[str]:
    counts = Counter()
    group = Counter()
    profiles: dict[int, bytes | None] = {}
    epoch_opens = Counter()
    epoch = 0
    pending_path: bytes | None = None
    pending_init = False
    sessions: dict[int, tuple[int, int]] = {}
    rx_context: tuple[int, int, int, int] | None = None
    at = start_offset

    for raw in data.splitlines(keepends=True):
        line_start, line_end = at, at + len(raw)
        at = line_end
        if not raw.endswith(b"\n"):
            counts["PARTIAL_LINE"] += 1
            continue
        if line_start < action_start < line_end:
            counts["ACTION_CROSSING_LINE"] += 1
            continue
        m = TAG.match(raw.rstrip(b"\r\n"))
        if m is None or m.group(1).decode("ascii").upper() != pid or m.group(2).upper() != b"IEXPLORE.EXE":
            continue
        action = action_start <= line_start < action_end
        if action:
            counts["ACTION_LINES"] += 1
        msg = m.group(3)

        if msg.startswith(INI):
            pending_path = msg[len(INI):]
            if action:
                counts["INI_LINES_ACTION"] += 1
            continue
        if msg.startswith(INIT):
            pending_init = True
            if action:
                counts["INITIALIZED_LINES_ACTION"] += 1
            continue

        if msg.startswith(OPEN):
            epoch += 1
            epoch_opens[epoch] = 1 if action else 0
            profiles[epoch] = pending_path
            if pending_init:
                counts["INIT_ATTACHED_TO_OPEN"] += 1
            pending_path = None
            pending_init = False
            sessions.clear()
            rx_context = None
            if action:
                counts["OPEN_ACTION"] += 1
            continue

        if msg == CLOSE:
            sessions.clear()
            rx_context = None
            if action:
                counts["CLOSE_ACTION"] += 1
            continue

        if msg.startswith(CONN + b" "):
            v = hex_bytes(msg, CONN, 32)
            if v is not None:
                ch = u32(v, 0)
                serial = (u32(v, 4) << 32) | u32(v, 8)
                sessions[ch] = (serial, epoch)
            elif action:
                counts["MALFORMED_CONNECT_ACTION"] += 1
            continue

        if msg.startswith(DISC + b" ") or msg.startswith(DEV_CLOSE + b" "):
            typ = DISC if msg.startswith(DISC + b" ") else DEV_CLOSE
            v = hex_bytes(msg, typ, 32)
            if v is not None:
                ch, serial = u32(v, 0), (u32(v, 4) << 32) | u32(v, 8)
                if ch in sessions and sessions[ch][0] == serial:
                    del sessions[ch]
            elif action:
                counts["MALFORMED_DISCONNECT_ACTION"] += 1
            continue

        if msg.startswith(RXCTX + b" "):
            v = hex_bytes(msg, RXCTX, 20)
            if v is None:
                rx_context = None
                if action:
                    counts["MALFORMED_RX_CONTEXT_ACTION"] += 1
            else:
                rx_context = (u32(v, 0), u32(v, 4), u32(v, 8), u32(v, 12))
                if action:
                    counts["RX_CONTEXT_ACTION"] += 1
            continue

        if msg.startswith(RX + b" "):
            context = rx_context
            rx_context = None
            if not action:
                continue
            counts["RX_DELIVERED_LINES_ACTION"] += 1
            # Only classify standard single-payload 7-8 byte responses from
            # target 18DAF150; never print any byte values from the log.
            v = None
            suffix = msg[len(RX) + 1:].strip()
            if HEX.fullmatch(suffix):
                try:
                    v = bytes.fromhex(suffix.decode("ascii"))
                except ValueError:
                    pass
            if v is None:
                counts["RX_PARSE_FAILURE_ACTION"] += 1
                continue
            cls = classify_rx(v)
            if cls is None:
                continue
            counts["CEM22_RX_ACTION"] += 1
            if context is None:
                counts["CEM22_RX_NO_CONTEXT"] += 1
                ch, protocol, status, baud = 0, 0, 0, 0
            else:
                ch, protocol, status, baud = context
            ser, ep = sessions.get(ch, (None, epoch))
            if ser is None:
                counts["CEM22_RX_UNKNOWN_SESSION"] += 1
            group[(ep, ch, "UNKNOWN" if ser is None else str(ser),
                   protocol, baud, cls)] += 1
            counts["CEM22_"+cls] += 1
            continue

        # If anything other than RX occurs immediately after RX context,
        # stop assuming the next line shares that context.
        rx_context = None

    out = [
        f"B3A305_EXACT_PID={pid}",
        f"B3A305_ACTION_START={action_start}",
        f"B3A305_ACTION_END={action_end}",
        f"B3A305_ACTION_LINES={counts['ACTION_LINES']}",
        f"B3A305_EXPECTED_ACTION_LINES={expected_action_lines}",
        f"B3A305_ACTION_CENSUS_MATCH={'TRUE' if counts['ACTION_LINES'] == expected_action_lines else 'FALSE'}",
        f"B3A305_PREWINDOW_OPENS={len(profiles)-sum(epoch_opens.values())}",
        f"B3A305_ACTION_OPENS={counts['OPEN_ACTION']}",
        f"B3A305_ACTION_CLOSES={counts['CLOSE_ACTION']}",
        f"B3A305_INIT_ATTACHED_TO_OPEN={counts['INIT_ATTACHED_TO_OPEN']}",
        f"B3A305_ACTION_INI_LINE_COUNT={counts['INI_LINES_ACTION']}",
        f"B3A305_ACTION_RX_CONTEXT={counts['RX_CONTEXT_ACTION']}",
        f"B3A305_ACTION_RX_DELIVERED_LINES={counts['RX_DELIVERED_LINES_ACTION']}",
        f"B3A305_RX_PARSE_FAILURES={counts['RX_PARSE_FAILURE_ACTION']}",
        f"B3A305_CEM22_RX_MISSING_CONTEXT={counts['CEM22_RX_NO_CONTEXT']}",
        f"B3A305_CEM22_RX_UNKNOWN_SESSION={counts['CEM22_RX_UNKNOWN_SESSION']}",
        f"B3A305_ACTION_CROSSING_LINE_COUNT={counts['ACTION_CROSSING_LINE']}",
    ]
    if counts["ACTION_LINES"] != expected_action_lines:
        out.append("B3A305_RESULT=ERROR_ACTION_CENSUS_MISMATCH")
        return out

    for ep in sorted(profiles):
        path = profiles[ep]
        out.append(f"B3A305_EPOCH={ep},active_ini_path_logged:{'TRUE' if path is not None else 'FALSE'}")
    if 2 in profiles and 3 in profiles and profiles[2] is not None and profiles[3] is not None:
        comparison = "SAME" if profiles[2] == profiles[3] else "DIFFERENT"
    else:
        comparison = "UNKNOWN"
    out.append(f"B3A305_EPOCH2_VS_EPOCH3_ACTIVE_INI_PATH={comparison}")
    for cls in ("NRC31", "OTHER_NRC", "POS_A45F", "POS_DD02", "POS_F110", "POS_F114", "POS_F106", "OTHER_POS"):
        out.append(f"B3A305_CEM22_{cls}_TOTAL={counts['CEM22_'+cls]}")
    for (ep, ch, ser, proto, baud, cls), n in sorted(group.items()):
        out.append(
            f"B3A305_RX=epoch:{ep},channel:{ch},serial:{ser},"
            f"proto:{proto},baud:{baud},type:{cls},count:{n}"
        )
    out.extend((
        "B3A305_ACTIVE_INI_PATH_EQUALITY_DOES_NOT_PROVE_SAME_FILE_CONTENT",
        "B3A305_GGD_ENABLED_AND_ECU_ROUTES_NOT_LOGGED_PER_EPOCH",
        "B3A305_NEGATIVE_RX_HAS_NO_INDIVIDUAL_DID_IDENTIFIER",
        "B3A305_GUI_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A305_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="B3A305 original VIDA GGD RX counts by J2534 Open epoch")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--window-start", type=int, required=True)
    parser.add_argument("--window-end", type=int, required=True)
    parser.add_argument("--lookback-bytes", type=int, default=4 * 1024 * 1024)
    parser.add_argument("--expected-action-lines", type=int, required=True)
    parser.add_argument("--pid", default="00002710")
    args = parser.parse_args()
    pid = args.pid.upper()
    if (VALID_PID.fullmatch(pid) is None or args.window_start <= 0
            or args.window_end <= args.window_start
            or not 1 <= args.lookback_bytes <= 32 * 1024 * 1024
            or not 1 <= args.expected_action_lines <= 500000):
        print("B3A305_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    capture = runpy.run_path(
        str(Path(__file__).resolve().with_name("B3A300-Recover-VIDA-Gate-Window.py")),
        run_name="b3a305_import_capture",
    )["capture_historic"]
    lookback = min(args.lookback_bytes, args.window_start)
    try:
        with args.log.open("rb") as f:
            data, _, trimmed, start = capture(
                f, end_offset=args.window_end,
                window_bytes=args.window_end-args.window_start+lookback)
    except (OSError, ValueError):
        print("B3A305_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    print(f"B3A305_COMBINED_START={start}")
    print(f"B3A305_COMBINED_END={args.window_end}")
    print(f"B3A305_LEADING_PARTIAL_BYTES_DISCARDED={trimmed}")
    for row in audit(data, start_offset=start+trimmed,
                     action_start=args.window_start, action_end=args.window_end,
                     expected_action_lines=args.expected_action_lines, pid=pid):
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
