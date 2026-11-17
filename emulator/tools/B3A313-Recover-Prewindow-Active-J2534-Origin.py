#!/usr/bin/env python3
"""B3A313: find pre-BEFORE J2534 Open origin for original VIDA epoch 0.

Read-only reconstruction from bounded prior original J2534 log records.
Use fixed exact action bytes [75494985,75759862), PID 00001130, 2339
tagged lines; inspect up to 16MiB of prior complete lines for the most
recent PassThruOpen/PassThruClose and Active INI origin in that same PID.
Compare its directory to CURRENT 32-bit J2534 provider registry entries
and report a unique safe provider label if matched. This is *not* proof
of the historic loaded DLL file's exact binary identity nor proof of
original VIDA GUI acceptance or a particular read response's causality.

Do not output private INI paths, VIN, ECU payloads, raw frames, registry
DLL values or hashes. Do not write files, invoke VIDA/J2534 or edit registry.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(rb"^\[PID=([0-9A-Fa-f]{8}) ([A-Za-z0-9_.-]{1,64})\] (.*)$")
HEX = re.compile(rb"(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*\Z")
PID = re.compile(r"[0-9A-Fa-f]{8}\Z")
LABEL = re.compile(r"[A-Za-z0-9 _().-]{1,120}\Z")
INI = b"Active INI: "
INIT = b"VirtualCar DLL initialized"
OPEN = b"PassThruOpen -> device 1"
CLOSE = b"PassThruClose"
TX = b"TX (app request)"
RX = b"PassThruReadMsgs -> delivered"


def peer(name):
    return runpy.run_path(
        str(Path(__file__).resolve().with_name(name)),
        run_name="b3a313_peer_import",
    )


def raw_packet(body: bytes, prefix: bytes):
    if not body.startswith(prefix+b" "):
        return None
    payload = body[len(prefix)+1:].strip()
    if HEX.fullmatch(payload) is None:
        return None
    return bytes.fromhex(payload.decode("ascii"))


def resolve_pre_origin(records: bytes, *, data_begin: int, action_start: int,
                       action_end: int, pid: str, expected_action_lines: int,
                       reg_status: str, providers: list[tuple[str, str]],
                       selected_label: str) -> list[str]:
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    decode = b306["decode_log_path"]
    ini_dir = b307["canonical_dir_from_ini"]
    dll_dir = b307["canonical_dir_from_dll"]

    stats = Counter()
    pre_active = False
    pre_open_seen = False
    pre_open_dir = None
    pre_init = False
    pending_path = None
    last_pre_open_linked_ini = False
    last_pre_open_linked_init = False
    snapshot = None
    prefix_open_seen = False

    at = data_begin
    for raw in records.splitlines(keepends=True):
        row_start, row_end = at, at+len(raw)
        at = row_end
        if not raw.endswith(b"\n"):
            stats["INCOMPLETE"] += 1
            continue
        # Conservatively refuse to treat a split boundary line as an action.
        if row_start < action_start < row_end:
            stats["BOUNDARY_CROSSING"] += 1
            continue
        if row_start >= action_end:
            continue
        action = row_start >= action_start
        if action:
            stats["ACTION_COMPLETE"] += 1
        match = TAG.match(raw.rstrip(b"\r\n"))
        if not match:
            if action:
                stats["ACTION_UNTAGGED"] += 1
            continue
        if action:
            stats["ACTION_TAGGED"] += 1
        is_selected = (match.group(1).decode("ascii").upper() == pid
                       and match.group(2).upper() == b"IEXPLORE.EXE")
        if not is_selected:
            if action:
                stats["ACTION_OTHER_PID"] += 1
            continue
        if action:
            stats["ACTION_SELECTED_PID"] += 1
        body = match.group(3)

        # Capture the exact state at the BEFORE offset, before processing
        # the first action record. The action can have no Open initially.
        if action and snapshot is None:
            snapshot = (pre_open_seen, pre_active, pre_open_dir,
                        last_pre_open_linked_ini, last_pre_open_linked_init)

        if body.startswith(INI):
            pending_path = body[len(INI):]
            if not action:
                stats["PRE_INI_LOGS"] += 1
            continue
        if body.startswith(INIT):
            pre_init = True
            continue
        if body.startswith(OPEN):
            if action:
                prefix_open_seen = True
                stats["ACTION_OPEN"] += 1
                continue
            pre_open_seen = True
            pre_active = True
            pre_open_dir = ini_dir(decode(pending_path))
            last_pre_open_linked_ini = pre_open_dir is not None
            last_pre_open_linked_init = pre_init
            stats["PRE_OPEN"] += 1
            pending_path = None
            pre_init = False
            continue
        if body.startswith(CLOSE):
            if action:
                stats["ACTION_CLOSE"] += 1
            else:
                stats["PRE_CLOSE"] += 1
                pre_active = False
            continue

        # Prefix of the new action before any in-window device Open:
        # independently reconcile the epoch0 counts published by B3A312.
        if action and not prefix_open_seen:
            if body.startswith(TX+b" "):
                pkt = raw_packet(body, TX)
                if (pkt is not None and len(pkt) == 7
                        and int.from_bytes(pkt[:4], "big") == 0x18DA50F1
                        and pkt[4] == 0x22):
                    did = pkt[5:7].hex().upper()
                    if did in ("A45F", "DD02"):
                        stats["PREFIX_TX_"+did] += 1
            elif body.startswith(RX+b" "):
                pkt = raw_packet(body, RX)
                if (pkt is not None and len(pkt) >= 7
                        and int.from_bytes(pkt[:4], "big") == 0x18DAF150
                        and pkt[4] == 0x62):
                    did = pkt[5:7].hex().upper()
                    if did in ("A45F", "DD02"):
                        stats["PREFIX_RX_POS_"+did] += 1
    if snapshot is None:
        snapshot = (pre_open_seen, pre_active, pre_open_dir,
                    last_pre_open_linked_ini, last_pre_open_linked_init)
    seen, active, directory, ini_found, init_linked = snapshot

    state = "OPEN" if seen and active else "CLOSED" if seen else "NOT_FOUND_IN_LOOKBACK"
    if not active:
        status = "NOT_ASSESSED_CLOSED_OR_MISSING"
    elif directory is None:
        status = "UNKNOWN_NO_ACTIVE_INI"
    elif reg_status != "READ_OK":
        status = "REGISTRY_UNAVAILABLE"
    else:
        status = "CURRENT_REGISTRY_DIR_LOOKUP_AVAILABLE"

    matches = []
    selected_matches = []
    if active and directory is not None and reg_status == "READ_OK":
        matches = [label for label, path in providers
                   if dll_dir(path) == directory]
        selected_matches = [label for label in matches if label == selected_label]
    safe_name = (matches[0] if len(matches) == 1 and
                 LABEL.fullmatch(matches[0]) else
                 "UNRESOLVED" if len(matches) != 1 else "REDACTED")
    out = [
        f"B3A313_SELECTED_PID={pid}",
        f"B3A313_PREWINDOW_OPEN_COUNT={stats['PRE_OPEN']}",
        f"B3A313_PREWINDOW_CLOSE_COUNT={stats['PRE_CLOSE']}",
        f"B3A313_PREWINDOW_ACTIVE_AT_ACTION_START={state}",
        f"B3A313_PREWINDOW_LAST_OPEN_INI_RECORDED={'TRUE' if ini_found else 'FALSE'}",
        f"B3A313_PREWINDOW_LAST_OPEN_INIT_LINKED={'TRUE' if init_linked else 'FALSE'}",
        f"B3A313_PREWINDOW_ACTIVE_ORIGIN_STATUS={status}",
        f"B3A313_PREWINDOW_CURRENT_REGISTRY_MATCHES={len(matches)}",
        f"B3A313_PREWINDOW_CURRENT_PROVIDER_LABEL={safe_name}",
        f"B3A313_PREWINDOW_SAME_CURRENT_DIRECTORY_AS_SELECTED={'TRUE' if selected_matches else 'FALSE' if active and directory and reg_status=='READ_OK' else 'UNKNOWN'}",
        f"B3A313_ACTION_TAGGED_LINES={stats['ACTION_TAGGED']}",
        f"B3A313_ACTION_EXPECTED_TAGGED_LINES={expected_action_lines}",
        f"B3A313_ACTION_CENSUS_MATCH={'TRUE' if stats['ACTION_TAGGED']==expected_action_lines else 'FALSE'}",
        f"B3A313_ACTION_SELECTED_PID_LINES={stats['ACTION_SELECTED_PID']}",
        f"B3A313_ACTION_OPEN_COUNT={stats['ACTION_OPEN']}",
        f"B3A313_ACTION_BOUNDARY_CROSSING_LINES={stats['BOUNDARY_CROSSING']}",
        f"B3A313_PREFIX_BEFORE_FIRST_ACTION_OPEN_TX_A45F={stats['PREFIX_TX_A45F']}",
        f"B3A313_PREFIX_BEFORE_FIRST_ACTION_OPEN_TX_DD02={stats['PREFIX_TX_DD02']}",
        f"B3A313_PREFIX_BEFORE_FIRST_ACTION_OPEN_RX_POS_A45F={stats['PREFIX_RX_POS_A45F']}",
        f"B3A313_PREFIX_BEFORE_FIRST_ACTION_OPEN_RX_POS_DD02={stats['PREFIX_RX_POS_DD02']}",
    ]
    if stats["ACTION_TAGGED"] != expected_action_lines or stats["ACTION_UNTAGGED"] or not stats["ACTION_SELECTED_PID"]:
        out.append("B3A313_RESULT=ERROR_ACTION_CENSUS")
        return out
    out.extend((
        "B3A313_PREFIX_RESULTS=EVENT_COUNTS_NOT_TX_TO_RX_PACKET_PAIRING",
        "B3A313_ORIGIN_FROM_LOG_NOT_HISTORICAL_BINARY_SHA",
        "B3A313_CURRENT_REGISTRY_NOT_HISTORICAL_PROVIDER_SELECTION_PROOF",
        "B3A313_SAME_PID_IN_LOOKBACK_NOT_PROOF_OF_PROCESS_IDENTITY_OVER_TIME",
        "B3A313_LAB_SYNTHETIC_POSITIVE_NOT_OEM_CEM_IDENT",
        "B3A313_GUI_CEM_IDENT_READVIN_ACCEPTANCE=NOT_ASSESSED",
        "B3A313_NO_REGISTRY_DLL_INI_OR_VIDA_MUTATIONS=TRUE",
        "B3A313_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main():
    ap = argparse.ArgumentParser(description="B3A313 safe prewindow J2534 origin")
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--start-offset", type=int, required=True)
    ap.add_argument("--end-offset", type=int, required=True)
    ap.add_argument("--pid", default="00001130")
    ap.add_argument("--expected-action-lines", type=int, default=2339)
    ap.add_argument("--lookback-bytes", type=int, default=16777216)
    ap.add_argument("--adapter-label", default="J2534 Diagnostic Lab 277")
    args = ap.parse_args()
    if (not PID.fullmatch(args.pid.upper()) or
            not LABEL.fullmatch(args.adapter_label) or
            args.start_offset <= 0 or args.end_offset <= args.start_offset or
            args.end_offset-args.start_offset > 32*1024*1024 or
            not 1 <= args.lookback_bytes <= 32*1024*1024 or
            args.expected_action_lines <= 0):
        print("B3A313_RESULT=ERROR_ARGUMENTS")
        return 2
    capture = peer("B3A300-Recover-VIDA-Gate-Window.py")["capture_historic"]
    b310 = peer("B3A310-Resolve-VIDA-J2534-Adapter-Label.py")
    try:
        with args.log.open("rb") as stream:
            lookback = min(args.start_offset, args.lookback_bytes)
            data, _, trimmed, begin = capture(
                stream, end_offset=args.end_offset,
                window_bytes=args.end_offset-args.start_offset+lookback)
    except (OSError, ValueError):
        print("B3A313_RESULT=ERROR_LOG_OR_OFFSETS")
        return 1
    status, entries = b310["registry_labels_32"]()
    print("B3A313_READ_START="+str(begin))
    print("B3A313_READ_END="+str(args.end_offset))
    print("B3A313_LEADING_PARTIAL_BYTES_DISCARDED="+str(trimmed))
    print("B3A313_ACTION_START="+str(args.start_offset))
    print("B3A313_ACTION_END="+str(args.end_offset))
    print("B3A313_CURRENT_REG32_STATUS="+status)
    for item in resolve_pre_origin(
            data, data_begin=begin+trimmed,
            action_start=args.start_offset, action_end=args.end_offset,
            pid=args.pid.upper(), expected_action_lines=args.expected_action_lines,
            reg_status=status, providers=entries, selected_label=args.adapter_label):
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
