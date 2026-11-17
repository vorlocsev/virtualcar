#!/usr/bin/env python3
"""B3A311: read-only, bounded post-historical VIDA CEM log audit by PID.

The user visually confirmed "CEM displays in VIDA" while selecting
"J2534 Diagnostic Lab 277", but did not capture a successful exact BEFORE
offset. Therefore [70899337,75759862) is ONLY a post-historical-anchor
interval, NOT a single verified GUI action.

The native VirtualCar DLL logs Active INI (derived from its loaded DLL
directory) before PassThruOpen. Associate these within each process PID;
compare *directories only* with the CURRENT 32-bit FunctionLibrary entry
for an explicit adapter label. Tally UDS 22 request DIDs, RX positives,
NRC31 and LAB-generated A45F/DD02 by PID, never pair negative NRC to DID
without packet correlation or claim OEM/GUI ECU-ident acceptance.

No VIN, payload bytes, complete log lines, private paths, full registry
FunctionLibrary values, or hashes are output. No registry/INI/DLL writes,
no app launches, J2534 requests, VIDA SQL reads, jobs, or ECU traffic.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import ntpath
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(rb"^\[PID=([0-9a-fA-F]{8}) ([^]\r\n]{1,120})\] (.*)$")
HEX = re.compile(rb"^(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*$")
DIDS = ("A45F", "DD02", "F110", "F114", "F106")
VALID_LABEL = re.compile(r"[A-Za-z0-9 _().-]{1,120}\Z")
CTX = b"TX context channel/protocol/flags/baud/time-us (BE)"
TX = b"TX (app request)"
RX = b"PassThruReadMsgs -> delivered"
INI = b"Active INI: "
INIT = b"VirtualCar DLL initialized"
OPEN = b"PassThruOpen -> device 1"
LAB = {
    b"B3A274 LAB CEM50 GGD A45F synthetic positive": "A45F",
    b"B3A274 LAB CEM50 GGD DD02 synthetic positive": "DD02",
}


def peer(filename: str):
    return runpy.run_path(
        str(Path(__file__).resolve().with_name(filename)),
        run_name="b3a311_peer_import",
    )


def packet(body: bytes, marker: bytes) -> bytes | None:
    if not body.startswith(marker + b" "):
        return None
    h = body[len(marker) + 1:].strip()
    if HEX.fullmatch(h) is None:
        return None
    try:
        return bytes.fromhex(h.decode("ascii"))
    except ValueError:
        return None


def be32(data: bytes, off: int) -> int:
    return int.from_bytes(data[off:off + 4], "big")


def provider_dir(entries: list[tuple[str, str]], label: str) -> str | None:
    canonical_dir_from_dll = peer(
        "B3A307-Audit-J2534-Registry-Origins.py")["canonical_dir_from_dll"]
    matches = [canonical_dir_from_dll(dll) for entry, dll in entries
               if entry == label]
    if len(matches) != 1:
        return None
    return matches[0]


def scan(data: bytes, *, selected_dir: str | None) -> list[str]:
    decoder = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")["decode_log_path"]
    canonical_dir_from_ini = peer(
        "B3A307-Audit-J2534-Registry-Origins.py")["canonical_dir_from_ini"]

    per_pid: dict[str, Counter] = defaultdict(Counter)
    state: dict[str, dict] = defaultdict(
        lambda: {"pending_ini": None, "pending_init": False,
                 "txctx": None, "last_open": None})
    all_hosts = Counter()
    total = tagged = untagged = 0
    for raw in data.splitlines():
        total += 1
        match = TAG.match(raw.rstrip(b"\r\n"))
        if match is None:
            untagged += 1
            continue
        tagged += 1
        process = match.group(2).upper()
        all_hosts[process] += 1
        if process != b"IEXPLORE.EXE":
            continue
        pid = match.group(1).decode("ascii").upper()
        body = match.group(3)
        counts = per_pid[pid]
        counts["LINES"] += 1
        current = state[pid]
        # The native TX context is adjacent to the TX request. Reject any
        # intervening log event rather than inheriting a stale context.
        if not body.startswith(TX + b" "):
            current["txctx"] = None

        if body.startswith(INI):
            current["pending_ini"] = body[len(INI):]
            counts["INI_LOGS"] += 1
            continue
        if body.startswith(INIT):
            current["pending_init"] = True
            counts["INIT_LOGS"] += 1
            continue
        if body.startswith(OPEN):
            counts["OPENS"] += 1
            raw_ini = current["pending_ini"]
            ini_dir = canonical_dir_from_ini(decoder(raw_ini))
            if raw_ini is not None and ini_dir is not None:
                counts["OPEN_WITH_ACTIVE_INI"] += 1
            if selected_dir is None or ini_dir is None:
                counts["OPEN_ORIGIN_UNKNOWN"] += 1
                current["last_open"] = "UNKNOWN"
            elif ini_dir == selected_dir:
                counts["OPEN_ORIGIN_SELECTED_DIR"] += 1
                current["last_open"] = "SELECTED"
            else:
                counts["OPEN_ORIGIN_OTHER_DIR"] += 1
                current["last_open"] = "OTHER"
            if current["pending_init"]:
                counts["INIT_ATTACHED_TO_OPEN"] += 1
            current["pending_ini"] = None
            current["pending_init"] = False
            current["txctx"] = None
            continue
        if body.startswith(b"PassThruClose"):
            counts["CLOSES"] += 1
            current["txctx"] = None
            continue

        if body.startswith(CTX + b" "):
            value = packet(body, CTX)
            current["txctx"] = (
                (be32(value, 4), be32(value, 8), be32(value, 12))
                if value is not None and len(value) == 20 else None
            )
            if current["txctx"] is None:
                counts["INVALID_TX_CONTEXT"] += 1
            continue

        if body.startswith(TX + b" "):
            value = packet(body, TX)
            ctx = current["txctx"]
            current["txctx"] = None
            if value is None or len(value) < 7 or be32(value, 0) != 0x18DA50F1:
                continue
            if value[4] != 0x22:
                continue
            did = value[5:7].hex().upper()
            if did in DIDS:
                counts["TX_" + did] += 1
            else:
                counts["TX_OTHER_DID"] += 1
            counts["CEM22_TX"] += 1
            if ctx is None:
                counts["CEM22_TX_MISSING_CONTEXT"] += 1
            else:
                proto, txflags, baud = ctx
                if proto == 6 and baud == 500000 and txflags & 0x100:
                    counts["CEM22_TX_ISO15765_500K_29BIT"] += 1
            continue

        if body.startswith(RX + b" "):
            value = packet(body, RX)
            if value is None or len(value) < 7 or be32(value, 0) != 0x18DAF150:
                continue
            payload = value[4:]
            if payload[0] == 0x62 and len(payload) >= 3:
                did = payload[1:3].hex().upper()
                key = "RX_POS_" + did if did in DIDS else "RX_OTHER_POS"
                counts[key] += 1
            elif payload[:2] == b"\x7F\x22" and len(payload) >= 3:
                key = "RX_NRC31" if payload[2] == 0x31 else "RX_OTHER_NRC"
                counts[key] += 1
            continue

        for marker, did in LAB.items():
            if body.startswith(marker):
                counts["LAB_" + did] += 1
                break

    result = [
        f"B3A311_COMPLETE_LINES={total}",
        f"B3A311_TAGGED_LINES={tagged}",
        f"B3A311_UNTAGGED_LINES={untagged}",
        f"B3A311_IEXPLORE_PID_COUNT={len(per_pid)}",
        f"B3A311_IEXPLORE_LINES={sum(c['LINES'] for c in per_pid.values())}",
        "B3A311_SELECTED_ADAPTER_DIRECTORY_FROM_CURRENT_REGISTRY=" +
        ("RESOLVED" if selected_dir else "UNRESOLVED"),
    ]
    for pid, c in sorted(per_pid.items(), key=lambda p: (-p[1]["LINES"], p[0])):
        result.extend((
            f"B3A311_PID={pid},lines:{c['LINES']},opens:{c['OPENS']},"
            f"ini_to_open:{c['OPEN_WITH_ACTIVE_INI']},"
            f"selected_origin_opens:{c['OPEN_ORIGIN_SELECTED_DIR']},"
            f"other_origin_opens:{c['OPEN_ORIGIN_OTHER_DIR']},"
            f"unknown_origin_opens:{c['OPEN_ORIGIN_UNKNOWN']},"
            f"cem22_tx:{c['CEM22_TX']},"
            f"cem22_tx_iso15765_500k_29bit:{c['CEM22_TX_ISO15765_500K_29BIT']},"
            f"nrc31:{c['RX_NRC31']}",
        ))
        for did in DIDS:
            result.append(
                f"B3A311_PID_DID={pid},did:{did},tx:{c['TX_' + did]},"
                f"positive_delivered:{c['RX_POS_' + did]},"
                f"lab_generated:{c['LAB_' + did]}"
            )
        result.append(
            f"B3A311_PID_OTHER={pid},other_tx:{c['TX_OTHER_DID']},"
            f"other_positive:{c['RX_OTHER_POS']},"
            f"other_nrc:{c['RX_OTHER_NRC']},"
            f"cem22_tx_no_context:{c['CEM22_TX_MISSING_CONTEXT']}"
        )
    result.extend((
        "B3A311_WINDOW=POST_HISTORICAL_ANCHOR_NOT_SINGLE_GUI_ACTION",
        "B3A311_NO_PER_REQUEST_NRC_ATTRIBUTION=TRUE",
        "B3A311_REGISTERED_DIRECTORY_MATCH_NOT_EXACT_DLL_PROOF",
        "B3A311_CEM_VISIBLE=USER_OBSERVATION_ONLY",
        "B3A311_VIN_READ_SUCCESS=NOT_ASSESSED",
        "B3A311_CEM_IDENT_FIELDS_SUCCESS=NOT_ASSESSED",
        "B3A311_NO_REGISTRY_DLL_INI_WRITES=TRUE",
        "B3A311_RESULT=READ_ONLY_COMPLETE",
    ))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description="Post-anchor read-only VIDA CEM and provider audit")
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--start-offset", type=int, required=True)
    ap.add_argument("--end-offset", type=int, required=True)
    ap.add_argument("--adapter-label", default="J2534 Diagnostic Lab 277")
    args = ap.parse_args()
    if (args.start_offset < 1 or args.end_offset <= args.start_offset
            or args.end_offset-args.start_offset > 32*1024*1024
            or VALID_LABEL.fullmatch(args.adapter_label) is None):
        print("B3A311_RESULT=ERROR_INVALID_ARGUMENT")
        return 2
    capture = peer("B3A300-Recover-VIDA-Gate-Window.py")["capture_historic"]
    registry = peer("B3A310-Resolve-VIDA-J2534-Adapter-Label.py")["registry_labels_32"]
    try:
        with args.log.open("rb") as stream:
            data, _, discarded, start = capture(
                stream, end_offset=args.end_offset,
                window_bytes=args.end_offset-args.start_offset)
    except (OSError, ValueError):
        print("B3A311_RESULT=ERROR_LOG_OFFSETS_OR_READ")
        return 1
    status, entries = registry()
    selected_dir = provider_dir(entries, args.adapter_label) if status == "READ_OK" else None
    print(f"B3A311_WINDOW_START={args.start_offset}")
    print(f"B3A311_WINDOW_END={args.end_offset}")
    print(f"B3A311_BYTES_REQUESTED={args.end_offset-args.start_offset}")
    print(f"B3A311_COMPLETE_LINE_BYTES={len(data)}")
    print(f"B3A311_PARTIAL_BYTES_TRIMMED={discarded}")
    print(f"B3A311_REG32_STATUS={status}")
    for line in scan(data, selected_dir=selected_dir):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
