#!/usr/bin/env python3
"""B3A301: CEM GGD ISO15765 DID requests grouped by effective J2534 baud.

Read-only replay of historical B3A300 fixed-offset original VIDA capture.
The native DLL logs TX context (channel, protocol, flags, baud, time-us)
immediately before each TX in the same serialized PassThruWriteMsgs call.
We associate adjacent TX-context to TX, not RX to individual requests.

Outputs only diagnostic DID IDs, connection metadata and counts: NEVER VIN,
arbitrary payload, raw frame, log text or private file path. No file writes,
VIDA/SQL/J2534 operations, ECU writes, or registry modifications.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import runpy
import sys

PREFIX = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([^\]]+)\] (.*)$")
HEXDUMP = re.compile(r"^(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*$")
VALID_PID = re.compile(r"[0-9A-Fa-f]{8}\Z")
CTX_NAME = "TX context channel/protocol/flags/baud/time-us (BE)"
TX_NAME = "TX (app request)"
RX_NAME = "PassThruReadMsgs -> delivered"


def imported(filename: str):
    return runpy.run_path(str(Path(__file__).resolve().with_name(filename)),
                          run_name="b3a301_import_only")


def hex_data(message: str, prefix: str) -> bytes | None:
    if not message.startswith(prefix + " "):
        return None
    raw = message[len(prefix) + 1:].strip()
    if not HEXDUMP.fullmatch(raw):
        return None
    return bytes.fromhex(raw)


def be32(b: bytes, p: int) -> int:
    return int.from_bytes(b[p:p+4], "big")


def audit(text: str, pid: str) -> list[str]:
    counts = Counter()
    tx_by_did_baud: Counter[tuple[str, str, str, str]] = Counter()
    tx_by_did = Counter()
    positives = Counter()
    nrc = Counter()
    pending_context = None

    for line in text.splitlines():
        m = PREFIX.match(line)
        if not m or m.group(1).upper() != pid or m.group(2).upper() != "IEXPLORE.EXE":
            continue
        counts["PID_LINES"] += 1
        msg = m.group(3)
        if msg.startswith(CTX_NAME + " "):
            ctx = hex_data(msg, CTX_NAME)
            if ctx is not None and len(ctx) == 20:
                pending_context = (
                    str(be32(ctx, 12)),   # baud
                    str(be32(ctx, 4)),    # native wire protocol
                    "TRUE" if be32(ctx, 8) & 0x100 else "FALSE", # CAN_29BIT_ID flag
                )
                counts["VALID_TX_CONTEXT"] += 1
            else:
                pending_context = None
                counts["INVALID_TX_CONTEXT"] += 1
            continue

        if msg.startswith(TX_NAME + " "):
            packet = hex_data(msg, TX_NAME)
            # In native source, context and TX are adjacent. Do not reuse a
            # context for a second TX or silently infer an unknown baud.
            ctx = pending_context
            pending_context = None
            if packet is None or len(packet) < 5:
                counts["TX_MALFORMED_OR_TOO_SHORT"] += 1
                continue
            if be32(packet, 0) != 0x18DA50F1 or packet[4] != 0x22:
                continue
            if len(packet) < 7:
                counts["CEM22_SHORT_REQUEST"] += 1
                continue
            did = packet[5:7].hex().upper()
            if ctx is None:
                counts["CEM22_TX_WITHOUT_CONTEXT"] += 1
                ctx = ("UNKNOWN", "UNKNOWN", "UNKNOWN")
            tx_by_did_baud[(did, *ctx)] += 1
            tx_by_did[did] += 1
            counts["CEM22_TOTAL_TX"] += 1
            if len(packet) != 7:
                counts["CEM22_NONSTANDARD_REQUEST_LENGTH"] += 1
            continue

        if msg.startswith(RX_NAME + " "):
            packet = hex_data(msg, RX_NAME)
            if packet is None or len(packet) < 7:
                continue
            if be32(packet, 0) != 0x18DAF150:
                continue
            if packet[4] == 0x62:
                positives[packet[5:7].hex().upper()] += 1
                counts["CEM22_POSITIVE_TOTAL_DELIVERED"] += 1
            elif packet[4:6] == b"\x7f\x22":
                nrc[f"{packet[6]:02X}"] += 1
                counts["CEM22_NEGATIVE_TOTAL_DELIVERED"] += 1
            continue

        if msg.startswith("B3A274 LAB CEM50 GGD A45F synthetic positive"):
            counts["A45F_LAB_POSITIVE_GENERATED"] += 1
        elif msg.startswith("B3A274 LAB CEM50 GGD DD02 synthetic positive"):
            counts["DD02_LAB_POSITIVE_GENERATED"] += 1

    result = [
        f"B3A301_EXACT_PID={pid}",
        f"B3A301_PID_LINES={counts['PID_LINES']}",
        f"B3A301_CEM22_TOTAL_TX={counts['CEM22_TOTAL_TX']}",
        f"B3A301_VALID_TX_CONTEXT={counts['VALID_TX_CONTEXT']}",
        f"B3A301_INVALID_TX_CONTEXT={counts['INVALID_TX_CONTEXT']}",
        f"B3A301_CEM22_TX_WITHOUT_CONTEXT={counts['CEM22_TX_WITHOUT_CONTEXT']}",
        f"B3A301_CEM22_SHORT_REQUEST={counts['CEM22_SHORT_REQUEST']}",
        f"B3A301_CEM22_NONSTANDARD_REQUEST_LENGTH={counts['CEM22_NONSTANDARD_REQUEST_LENGTH']}",
        "B3A301_TX_BAUD_IS_EFFECTIVE_NATIVE_J2534_CONTEXT",
    ]
    for (did, baud, proto, flag29), n in sorted(tx_by_did_baud.items()):
        result.append(f"B3A301_TX=did:{did},baud:{baud},proto:{proto},flag29:{flag29},count:{n}")
    for did in sorted(set(tx_by_did) | set(positives)):
        result.append(
            f"B3A301_DID={did},tx:{tx_by_did[did]},positive_delivered:{positives[did]}"
        )
    for code, n in sorted(nrc.items()):
        result.append(f"B3A301_NRC=service:22,code:{code},delivered:{n}")
    result.extend((
        f"B3A301_A45F_LAB_POSITIVE_GENERATED={counts['A45F_LAB_POSITIVE_GENERATED']}",
        f"B3A301_DD02_LAB_POSITIVE_GENERATED={counts['DD02_LAB_POSITIVE_GENERATED']}",
        "B3A301_NRC_TO_DID_ATTRIBUTION=NOT_PROVEN",
        "B3A301_TX_TO_RX_PAIRING=NOT_ATTEMPTED",
        "B3A301_GUI_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A301_RESULT=READ_ONLY_COMPLETE",
    ))
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="B3A301 read-only CEM GGD request vs J2534 baud audit")
    p.add_argument("--log", required=True, type=Path)
    p.add_argument("--end-offset", required=True, type=int)
    p.add_argument("--window-bytes", required=True, type=int)
    p.add_argument("--pid", default="00002710")
    p.add_argument("--expected-tagged-lines", type=int, required=True)
    args = p.parse_args()
    pid = args.pid.upper()
    if (VALID_PID.fullmatch(pid) is None
            or not 1 <= args.window_bytes <= 32 * 1024 * 1024
            or args.end_offset < args.window_bytes
            or not 1 <= args.expected_tagged_lines <= 500000):
        print("B3A301_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    capture_historic = imported("B3A300-Recover-VIDA-Gate-Window.py")["capture_historic"]
    scan_bytes = imported("B3A299-Audit-VIDA-Log-PID-Census.py")["scan_bytes"]
    try:
        with args.log.open("rb") as stream:
            data, _, discarded, start = capture_historic(
                stream, end_offset=args.end_offset,
                window_bytes=args.window_bytes)
    except (OSError, ValueError):
        print("B3A301_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1

    hosts, _, _ = scan_bytes(data)
    total = sum(hosts.values())
    selected = hosts[(pid, "IEXPLORE.EXE")]
    print(f"B3A301_ANCHORED_WINDOW_START={start}")
    print(f"B3A301_ANCHORED_WINDOW_END={args.end_offset}")
    print(f"B3A301_DISCARDED_PARTIAL_LINE_BYTES={discarded}")
    print(f"B3A301_TAGGED_LINES={total}")
    print(f"B3A301_EXACT_HOST_LINES={selected}")
    if total != args.expected_tagged_lines or not selected:
        print("B3A301_RESULT=ERROR_CENSUS_OR_PID_MISMATCH")
        return 1
    for row in audit(data.decode("latin-1"), pid):
        print(row)
    return 0


if __name__ == "__main__":
    sys.exit(main())
