#!/usr/bin/env python3
"""B3A302: why some native GGD lab A45F/DD02 requests do not generate positives.

Read only the fixed B3A300 original VIDA J2534 log window, now known to contain
IEXPLORE.EXE PID 00002710 and 1830 tagged lines. The B3A301 'flag29' value
was TX *message* flags; native answer_ggd_cem50_lab() checks c->flags from
PassThruConnect, not message TxFlags. Here both fields are reported separately.

Native source evidence:
- J2534 scope channel_connect (BE): 8 x u32 (id, serial_hi, serial_lo,
  protocol, baud, CONNECT FLAGS, filter_id, filter_type).
- TX context channel/protocol/flags/baud/time-us (BE): 5 x u32
  (id, wire_protocol, TX FLAGS, baud, timestamp_us).
- Logs are ordered inside one lock; the lab positive log is emitted within
  the same TX processing call, before any next TX context.

No raw CAN frames, VIN, chassis, proprietary response bytes, path names or
log lines are printed. No file modification, SQL writes, VIDA/ECU/J2534
operations, registry changes, CI jobs, or emulator execution.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(r"^\[PID=([0-9A-Fa-f]{8}) ([^\]]+)\] (.*)$")
HEXDUMP = re.compile(r"^(?:[0-9a-fA-F]{2})(?: [0-9a-fA-F]{2})*$")
PID = re.compile(r"[0-9A-Fa-f]{8}\Z")
CONNECT = "J2534 scope channel_connect (BE)"
DISCONNECT = "J2534 scope channel_disconnect (BE)"
TX_CONTEXT = "TX context channel/protocol/flags/baud/time-us (BE)"
TX = "TX (app request)"
LAB_LOGS = {
    "B3A274 LAB CEM50 GGD A45F synthetic positive": "A45F",
    "B3A274 LAB CEM50 GGD DD02 synthetic positive": "DD02",
}
DIDS = {"A45F", "DD02", "F110", "F114", "F106"}


def hex_tail(body: str, prefix: str) -> bytes | None:
    if not body.startswith(prefix + " "):
        return None
    tail = body[len(prefix) + 1:].strip()
    if not HEXDUMP.fullmatch(tail):
        return None
    return bytes.fromhex(tail)


def u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset+4], "big")


def group_label(key: tuple) -> str:
    did, channel, serial, conn_flags, tx_flags, baud, protocol, eligible = key
    flags = "UNKNOWN" if conn_flags is None else f"0x{conn_flags:08X}"
    return (f"did:{did},channel:{channel},serial:{serial},"
            f"connect_flags:{flags},tx_flags:0x{tx_flags:08X},"
            f"baud:{baud},protocol:{protocol},lab_guard:{eligible}")


def audit(text: str, pid: str) -> list[str]:
    counts = Counter()
    # (channel -> serial, protocol, baud, connection flags); if capture begins
    # after connection, NEVER assume flags from TxFlags.
    channels: dict[int, tuple[int, int, int, int]] = {}
    tx_context: tuple[int, int, int, int] | None = None
    active: tuple | None = None
    requests: Counter[tuple] = Counter()
    positive_generated: Counter[tuple] = Counter()
    unmatched: Counter[tuple] = Counter()

    for line in text.splitlines():
        m = TAG.match(line)
        if not m or m.group(1).upper() != pid or m.group(2).upper() != "IEXPLORE.EXE":
            continue
        counts["PID_LINES"] += 1
        body = m.group(3)

        if body.startswith(CONNECT + " "):
            raw = hex_tail(body, CONNECT)
            if raw is None or len(raw) != 32:
                counts["MALFORMED_CONNECT"] += 1
            else:
                ch, hi, lo, proto, baud, flags = (u32(raw, k) for k in (0, 4, 8, 12, 16, 20))
                channels[ch] = ((hi << 32) | lo, proto, baud, flags)
                counts["CONNECT"] += 1
            tx_context = None
            active = None
            continue

        if body.startswith(DISCONNECT + " "):
            raw = hex_tail(body, DISCONNECT)
            if raw is not None and len(raw) == 32:
                ch, hi, lo = (u32(raw, k) for k in (0, 4, 8))
                serial = (hi << 32) | lo
                if ch in channels and channels[ch][0] == serial:
                    del channels[ch]
                counts["DISCONNECT"] += 1
            else:
                counts["MALFORMED_DISCONNECT"] += 1
            tx_context = None
            active = None
            continue

        if body.startswith(TX_CONTEXT + " "):
            raw = hex_tail(body, TX_CONTEXT)
            if raw is not None and len(raw) == 20:
                tx_context = (u32(raw, 0), u32(raw, 4),
                              u32(raw, 8), u32(raw, 12))
                counts["TX_CONTEXT"] += 1
            else:
                tx_context = None
                counts["MALFORMED_TX_CONTEXT"] += 1
            active = None
            continue

        if body.startswith(TX + " "):
            raw = hex_tail(body, TX)
            context = tx_context
            tx_context = None
            active = None
            if raw is None or len(raw) < 5:
                counts["MALFORMED_TX"] += 1
                continue
            if u32(raw, 0) != 0x18DA50F1 or len(raw) < 7 or raw[4] != 0x22:
                continue
            did = raw[5:7].hex().upper()
            if did not in DIDS:
                counts["OTHER_CEM22_DIDS"] += 1
                continue
            counts[f"DID_{did}_TX"] += 1
            if context is None:
                counts["CEM22_MISSING_TX_CONTEXT"] += 1
                continue
            ch, proto, tx_flags, baud = context
            if len(raw) != 7:
                counts["NON_EXACT_3BYTE_REQ"] += 1
            known = channels.get(ch)
            if known is None:
                serial = "UNKNOWN"
                conn_flags = None
                eligible = "UNKNOWN"
                counts["UNKNOWN_CONNECT_CONTEXT"] += 1
            else:
                serial_num, conn_proto, conn_baud, conn_flags = known
                serial = str(serial_num)
                if conn_proto != proto or conn_baud != baud:
                    counts["CHANNEL_CONTEXT_CONTRADICTION"] += 1
                eligible = (
                    "TRUE" if (conn_proto == 6 and conn_baud == 500000
                               and conn_flags == 0x100 and len(raw) == 7)
                    else "FALSE"
                )
            key = (did, ch, serial, conn_flags, tx_flags, baud, proto, eligible)
            requests[key] += 1
            active = key
            continue

        if body.startswith("Unmatched request ID / protocol, no response"):
            if active is not None:
                unmatched[active] += 1
                counts["UNMATCHED_CEM_REQUEST"] += 1
            continue

        for prefix, did in LAB_LOGS.items():
            if body.startswith(prefix):
                counts[f"LAB_{did}_GENERATED"] += 1
                if active is not None and active[0] == did:
                    positive_generated[active] += 1
                else:
                    counts["LAB_LOG_WITHOUT_ACTIVE_SAME_DID"] += 1
                break

    out = [
        f"B3A302_EXACT_PID={pid}",
        f"B3A302_PID_LINES={counts['PID_LINES']}",
        f"B3A302_CONNECT={counts['CONNECT']}",
        f"B3A302_DISCONNECT={counts['DISCONNECT']}",
        f"B3A302_MALFORMED_CONNECT={counts['MALFORMED_CONNECT']}",
        f"B3A302_MALFORMED_DISCONNECT={counts['MALFORMED_DISCONNECT']}",
        f"B3A302_TX_CONTEXT={counts['TX_CONTEXT']}",
        f"B3A302_MALFORMED_TX_CONTEXT={counts['MALFORMED_TX_CONTEXT']}",
        f"B3A302_CEM22_MISSING_TX_CONTEXT={counts['CEM22_MISSING_TX_CONTEXT']}",
        f"B3A302_UNKNOWN_CONNECT_CONTEXT={counts['UNKNOWN_CONNECT_CONTEXT']}",
        f"B3A302_CHANNEL_CONTEXT_CONTRADICTION={counts['CHANNEL_CONTEXT_CONTRADICTION']}",
        f"B3A302_NON_EXACT_3BYTE_REQ={counts['NON_EXACT_3BYTE_REQ']}",
        f"B3A302_OTHER_CEM22_DIDS={counts['OTHER_CEM22_DIDS']}",
        f"B3A302_LAB_LOG_WITHOUT_ACTIVE_SAME_DID={counts['LAB_LOG_WITHOUT_ACTIVE_SAME_DID']}",
        f"B3A302_UNMATCHED_CEM_REQUEST={counts['UNMATCHED_CEM_REQUEST']}",
    ]
    for did in sorted(DIDS):
        out.append(f"B3A302_DID_{did}_TX={counts[f'DID_{did}_TX']}")
    for did in ("A45F", "DD02"):
        out.append(f"B3A302_LAB_{did}_GENERATED={counts[f'LAB_{did}_GENERATED']}")
    for key, n in sorted(requests.items(), key=lambda kv: group_label(kv[0])):
        out.append(f"B3A302_GROUP={group_label(key)},tx:{n},"
                   f"lab_generated:{positive_generated[key]},"
                   f"unmatched:{unmatched[key]}")
    out.extend((
        "B3A302_GUARD=CHANNEL_CONNECT_FLAGS_NOT_TX_FLAGS",
        "B3A302_LAB_GUARD_TRUE_IS_NOT_PROOF_OF_OEM_DID_CONTENT",
        "B3A302_GENERATION_IS_NOT_J2534_DELIVERY",
        "B3A302_GUI_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A302_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="B3A302 CEM GGD connect vs TX flag audit")
    p.add_argument("--log", type=Path, required=True)
    p.add_argument("--end-offset", type=int, required=True)
    p.add_argument("--window-bytes", type=int, required=True)
    p.add_argument("--pid", default="00002710")
    p.add_argument("--expected-tagged-lines", type=int, required=True)
    args = p.parse_args()
    pid = args.pid.upper()
    if (not PID.fullmatch(pid) or args.end_offset < args.window_bytes
            or not 1 <= args.window_bytes <= 32*1024*1024
            or not 1 <= args.expected_tagged_lines <= 500000):
        print("B3A302_RESULT=ERROR_INVALID_ARGUMENT")
        return 2

    capture = runpy.run_path(
        str(Path(__file__).resolve().with_name("B3A300-Recover-VIDA-Gate-Window.py")),
        run_name="b3a302_import_capture")["capture_historic"]
    census = runpy.run_path(
        str(Path(__file__).resolve().with_name("B3A299-Audit-VIDA-Log-PID-Census.py")),
        run_name="b3a302_import_census")["scan_bytes"]
    try:
        with args.log.open("rb") as stream:
            sample, _, discarded, start = capture(
                stream, end_offset=args.end_offset, window_bytes=args.window_bytes)
    except (OSError, ValueError):
        print("B3A302_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    hosts, total, untagged = census(sample)
    tagged = sum(hosts.values())
    if tagged != args.expected_tagged_lines or hosts[(pid, "IEXPLORE.EXE")] == 0:
        print("B3A302_RESULT=ERROR_CENSUS_OR_PID_MISMATCH")
        return 1
    print(f"B3A302_ANCHORED_WINDOW_START={start}")
    print(f"B3A302_ANCHORED_WINDOW_END={args.end_offset}")
    print(f"B3A302_DISCARDED_PARTIAL_LINE_BYTES={discarded}")
    print(f"B3A302_TAGGED_LINES={tagged}")
    print(f"B3A302_UNTAGGED_LINES={untagged}")
    for line in audit(sample.decode("latin-1"), pid):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
