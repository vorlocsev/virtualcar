#!/usr/bin/env python3
"""B3A304: distinguish J2534 device Open/Close epochs in the original VIDA log.

The original CEM_IDENT capture begins at 70691072, ends at 70899337 and
contains 1830 complete tagged lines. A 4-MiB read-only lookback recovers
the session before the window. Scan the combined FIXED byte range once to
preserve connection lifetime across the split log line. Only complete lines
beginning within the action window are counted as action events.

Outputs session/epoch/ConnectFlags/TxFlags/baud and synthetic lab-positive
counts, never private VIN, payloads, log lines or file paths. Source guard
matches require separately proven original ECU route, not just J2534 flags.
Do not infer proprietary OEM positive responses or VIDA GUI acceptance.
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
PID = re.compile(r"[0-9A-Fa-f]{8}\Z")
OPEN = b"PassThruOpen -> device 1"
CLOSE = b"PassThruClose"
CONN = b"J2534 scope channel_connect (BE)"
DISC = b"J2534 scope channel_disconnect (BE)"
DEV_CLOSE = b"J2534 scope channel_device_close (BE)"
TX_CTX = b"TX context channel/protocol/flags/baud/time-us (BE)"
TX = b"TX (app request)"
LAB = {
    b"B3A274 LAB CEM50 GGD A45F synthetic positive": "A45F",
    b"B3A274 LAB CEM50 GGD DD02 synthetic positive": "DD02",
}
DIDS = ("A45F", "DD02", "F110", "F114", "F106")


def parse_bytes(line: bytes, marker: bytes, count: int) -> bytes | None:
    if not line.startswith(marker + b" "):
        return None
    tail = line[len(marker)+1:].strip()
    if HEX.fullmatch(tail) is None:
        return None
    try:
        data = bytes.fromhex(tail.decode("ascii"))
    except ValueError:
        return None
    return data if len(data) == count else None


def u32(buffer: bytes, off: int) -> int:
    return int.from_bytes(buffer[off:off+4], "big")


def analyze(data: bytes, *, start_offset: int, action_start: int,
            action_end: int, pid: str, expected_action_lines: int) -> list[str]:
    stats = Counter()
    current_epoch = 0
    known_epoch_open = False
    device_open = False
    sessions: dict[int, tuple[int, int, int, int, int]] = {}
    # session maps channel -> (serial, epoch, native proto, baud, connect flags)
    tx_context: tuple[int, int, int, int] | None = None
    active: tuple | None = None
    group_tx = Counter()
    group_lab = Counter()
    action_open_epoch = Counter()
    action_close_epoch = Counter()
    action_lines = 0
    at = start_offset
    for raw in data.splitlines(keepends=True):
        begin, end = at, at + len(raw)
        at = end
        if not raw.endswith(b"\n"):
            stats["NONCOMPLETE_LINES"] += 1
            continue
        if begin < action_start < end:
            # Exact action capture B3A300 excluded this fragmented first line.
            stats["CROSSING_ACTION_BOUNDARY_LINES"] += 1
            continue
        action = action_start <= begin < action_end
        m = TAG.match(raw.rstrip(b"\r\n"))
        if not m or m.group(1).decode("ascii").upper() != pid or m.group(2).upper() != b"IEXPLORE.EXE":
            continue
        body = m.group(3)
        if action:
            action_lines += 1

        if body.startswith(OPEN):
            current_epoch += 1
            known_epoch_open = True
            device_open = True
            sessions.clear()
            tx_context = None
            active = None
            stats["OPEN_TOTAL"] += 1
            if action:
                stats["OPEN_ACTION"] += 1
                action_open_epoch[current_epoch] += 1
            continue
        if body == CLOSE:
            stats["CLOSE_TOTAL"] += 1
            if action:
                stats["CLOSE_ACTION"] += 1
                action_close_epoch[current_epoch] += 1
            device_open = False
            sessions.clear()
            tx_context = None
            active = None
            continue
        if body.startswith(CONN + b" "):
            parsed = parse_bytes(body, CONN, 32)
            if parsed is not None:
                ch, hi, lo, proto, baud, flags = (u32(parsed, off) for off in (0, 4, 8, 12, 16, 20))
                sessions[ch] = ((hi << 32) | lo, current_epoch, proto, baud, flags)
                stats["CONNECT_TOTAL"] += 1
            else:
                stats["MALFORMED_CONNECT"] += 1
            continue
        if body.startswith(DISC + b" ") or body.startswith(DEV_CLOSE + b" "):
            kind = DISC if body.startswith(DISC + b" ") else DEV_CLOSE
            parsed = parse_bytes(body, kind, 32)
            if parsed is not None:
                ch, hi, lo = (u32(parsed, off) for off in (0, 4, 8))
                serial = (hi << 32) | lo
                if ch in sessions and sessions[ch][0] == serial:
                    del sessions[ch]
            else:
                stats["MALFORMED_DISCONNECT"] += 1
            continue
        if body.startswith(TX_CTX + b" "):
            parsed = parse_bytes(body, TX_CTX, 20)
            tx_context = (
                (u32(parsed, 0), u32(parsed, 4), u32(parsed, 8), u32(parsed, 12))
                if parsed is not None else None
            )
            active = None
            if action and parsed is None:
                stats["MALFORMED_TX_CONTEXT_ACTION"] += 1
            continue
        if body.startswith(TX + b" "):
            parsed = parse_bytes(body, TX, 7)
            context = tx_context
            tx_context = None
            active = None
            if not action:
                continue
            if parsed is None:
                # Only count malformed for CEM22 when a marker is still usable.
                stats["OTHER_TX_OR_NONEXACT_SIZE"] += 1
                continue
            if u32(parsed, 0) != 0x18DA50F1 or parsed[4] != 0x22:
                continue
            did = parsed[5:7].hex().upper()
            if did not in DIDS:
                stats["OTHER_CEM22_DID"] += 1
                continue
            stats["DID_"+did+"_TX"] += 1
            if context is None:
                stats["MISSING_TX_CONTEXT_ACTION"] += 1
                ch, proto, txflags, baud = (0, 0, 0, 0)
            else:
                ch, proto, txflags, baud = context
            serial = "UNKNOWN"
            flags = "UNKNOWN"
            eligibility = "UNKNOWN"
            epoch = f"{current_epoch}" if known_epoch_open else "UNKNOWN"
            if ch in sessions:
                ser, ep, cproto, cbaud, cflags = sessions[ch]
                serial = str(ser)
                flags = f"0x{cflags:08X}"
                epoch = str(ep) if known_epoch_open else "UNKNOWN"
                eligibility = (
                    "TRUE" if (cproto == 6 and cbaud == 500000
                               and cflags == 0x100
                               and proto == 6 and baud == 500000)
                    else "FALSE"
                )
                if cproto != proto or cbaud != baud:
                    stats["ACTION_CHANNEL_CONTEXT_CONTRADICTIONS"] += 1
            else:
                stats["UNKNOWN_CHANNEL_ACTION"] += 1
            key = (epoch, ch, serial, flags, did, proto, baud, txflags, eligibility)
            group_tx[key] += 1
            active = key
            continue
        for marker, did in LAB.items():
            if body.startswith(marker):
                if action:
                    stats["LAB_"+did+"_ACTION"] += 1
                    if active is not None and active[4] == did:
                        group_lab[active] += 1
                    else:
                        stats["LAB_WITHOUT_SAME_ACTIVE_TX"] += 1
                break

    out = [
        f"B3A304_EXACT_PID={pid}",
        f"B3A304_ACTION_START_OFFSET={action_start}",
        f"B3A304_ACTION_END_OFFSET={action_end}",
        f"B3A304_ACTION_COMPLETE_PID_LINES={action_lines}",
        f"B3A304_ACTION_CENSUS_EXPECTED={expected_action_lines}",
        f"B3A304_ACTION_CENSUS_MATCH={'TRUE' if action_lines == expected_action_lines else 'FALSE'}",
        f"B3A304_PREWINDOW_OPEN_EVENTS={stats['OPEN_TOTAL']-stats['OPEN_ACTION']}",
        f"B3A304_PREWINDOW_CLOSE_EVENTS={stats['CLOSE_TOTAL']-stats['CLOSE_ACTION']}",
        f"B3A304_ACTION_OPEN_EVENTS={stats['OPEN_ACTION']}",
        f"B3A304_ACTION_CLOSE_EVENTS={stats['CLOSE_ACTION']}",
        f"B3A304_ACTION_OPEN_KNOWN_AT_END={'TRUE' if known_epoch_open else 'FALSE'}",
        f"B3A304_ACTION_CHANNEL_CONTEXT_CONTRADICTIONS={stats['ACTION_CHANNEL_CONTEXT_CONTRADICTIONS']}",
        f"B3A304_ACTION_MISSING_TX_CONTEXT={stats['MISSING_TX_CONTEXT_ACTION']}",
        f"B3A304_ACTION_UNKNOWN_CHANNEL={stats['UNKNOWN_CHANNEL_ACTION']}",
        f"B3A304_ACTION_LAB_WITHOUT_SAME_ACTIVE_TX={stats['LAB_WITHOUT_SAME_ACTIVE_TX']}",
        f"B3A304_CROSSING_BOUNDARY_LINES={stats['CROSSING_ACTION_BOUNDARY_LINES']}",
    ]
    if action_lines != expected_action_lines:
        out.append("B3A304_RESULT=ERROR_ACTION_CENSUS_MISMATCH")
        return out
    for did in DIDS:
        out.append(f"B3A304_DID_{did}_TX={stats['DID_'+did+'_TX']}")
    for did in ("A45F", "DD02"):
        out.append(f"B3A304_LAB_{did}_ACTION={stats['LAB_'+did+'_ACTION']}")
    for key, count in sorted(group_tx.items()):
        epoch, ch, serial, flags, did, proto, baud, txflags, eligible = key
        out.append(
            f"B3A304_GROUP=epoch:{epoch},channel:{ch},serial:{serial},"
            f"connect_flags:{flags},did:{did},proto:{proto},baud:{baud},"
            f"tx_flags:0x{txflags:08X},connect_only_guard:{eligible},"
            f"tx:{count},lab_generated:{group_lab[key]}"
        )
    out.extend((
        "B3A304_GLOBAL_GGD_LAB_SETTING=NOT_LOGGED_PER_OPEN",
        "B3A304_ECU_REQ_RESP_AT_TX=NOT_LOGGED",
        "B3A304_CONNECT_GUARD_IS_NOT_COMPLETE_LAB_GUARD",
        "B3A304_EPOCH_CAUSALITY=INVESTIGATE_NOT_ASSUMED",
        "B3A304_GUI_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A304_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="B3A304 original VIDA J2534 Open epoch / GGD lab timeline")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--window-start", required=True, type=int)
    p.add_argument("--window-end", required=True, type=int)
    p.add_argument("--lookback-bytes", type=int, default=4*1024*1024)
    p.add_argument("--pid", default="00002710")
    p.add_argument("--expected-action-lines", type=int, required=True)
    args = p.parse_args()
    pid = args.pid.upper()
    if (PID.fullmatch(pid) is None or not 1 <= args.lookback_bytes <= 32*1024*1024
            or args.window_start <= 0 or args.window_end <= args.window_start
            or not 1 <= args.expected_action_lines <= 500000):
        print("B3A304_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    from_peer = runpy.run_path(
        str(Path(__file__).resolve().with_name("B3A300-Recover-VIDA-Gate-Window.py")),
        run_name="b3a304_import_peer",
    )["capture_historic"]
    lookback = min(args.lookback_bytes, args.window_start)
    try:
        with args.log.open("rb") as stream:
            chunk, _, trimmed, start = from_peer(
                stream, end_offset=args.window_end,
                window_bytes=args.window_end-args.window_start+lookback)
    except (OSError, ValueError):
        print("B3A304_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    print(f"B3A304_COMBINED_START_OFFSET={start}")
    print(f"B3A304_COMBINED_END_OFFSET={args.window_end}")
    print(f"B3A304_PARTIAL_EDGE_BYTES_DISCARDED={trimmed}")
    # Existing helper trims the leading partial line, if any.
    for line in analyze(chunk, start_offset=start+trimmed,
                        action_start=args.window_start,
                        action_end=args.window_end, pid=pid,
                        expected_action_lines=args.expected_action_lines):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
