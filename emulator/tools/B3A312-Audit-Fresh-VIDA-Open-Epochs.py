#!/usr/bin/env python3
"""B3A312: read-only, exact-window attribution of fresh VIDA CEM traffic by device Open.

Original VIDA fresh capture [75494985,75759862), PID 00001130, expected
2339 tagged lines. Distinguish per-PassThruOpen epochs and whether each
epoch's Active INI directory matches the CURRENT registered 32-bit
FunctionLibrary directory for J2534 Diagnostic Lab 277.

A positive response recorded while an epoch was active is NOT packet-level
request/response correlation or proof of an OEM response. NRC31 has no DID
identifier. Current registry mappings are not historical binary provenance.
Never prints private paths, raw payloads, VIN, INI values, registry DLL names
or hashes; never modifies files, J2534, VIDA, ECU, registry or profile.
"""
from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(rb"^\[PID=([0-9A-Fa-f]{8}) ([A-Za-z0-9_.-]{1,64})\] (.*)$")
HEXDUMP = re.compile(rb"(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*\Z")
PID = re.compile(r"[0-9A-Fa-f]{8}\Z")
LABEL = re.compile(r"[A-Za-z0-9 _().-]{1,120}\Z")
DIDS = ("A45F", "DD02", "F110", "F114", "F106")
INI = b"Active INI: "
INIT = b"VirtualCar DLL initialized"
OPEN = b"PassThruOpen -> device 1"
CLOSE = b"PassThruClose"
TX_CONTEXT = b"TX context channel/protocol/flags/baud/time-us (BE)"
TX = b"TX (app request)"
RX = b"PassThruReadMsgs -> delivered"
LAB = {
    b"B3A274 LAB CEM50 GGD A45F synthetic positive": "A45F",
    b"B3A274 LAB CEM50 GGD DD02 synthetic positive": "DD02",
}


def peer(name: str):
    return runpy.run_path(
        str(Path(__file__).resolve().with_name(name)),
        run_name="b3a312_peer_import",
    )


def parse_packet(message: bytes, prefix: bytes, length: int | None = None) -> bytes | None:
    if not message.startswith(prefix + b" "):
        return None
    payload = message[len(prefix)+1:].strip()
    if HEXDUMP.fullmatch(payload) is None:
        return None
    data = bytes.fromhex(payload.decode("ascii"))
    return data if length is None or len(data) == length else None


def be32(payload: bytes, at: int) -> int:
    return int.from_bytes(payload[at:at+4], "big")


def resolve_current_dir(adapter_label: str) -> tuple[str, str | None]:
    if not LABEL.fullmatch(adapter_label):
        return "INVALID_LABEL", None
    b310 = peer("B3A310-Resolve-VIDA-J2534-Adapter-Label.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    status, reg = b310["registry_labels_32"]()
    if status != "READ_OK":
        return status, None
    paths = [p for name, p in reg if name == adapter_label]
    if len(paths) != 1:
        return "NO_UNIQUE_LABEL", None
    directory = b307["canonical_dir_from_dll"](paths[0])
    return ("READ_OK", directory) if directory is not None else ("INVALID_DLL_PATH", None)


def analyze(data: bytes, *, pid: str, selected_dir: str | None,
            expected_tagged_lines: int) -> list[str]:
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    decode = b306["decode_log_path"]
    from_ini = b307["canonical_dir_from_ini"]
    totals = Counter()
    groups: dict[int, Counter] = {}
    origins: dict[int, str] = {}
    epoch = 0
    active: int | None = None
    pending: bytes | None = None
    init_pending = False
    txctx = None

    for raw in data.splitlines(keepends=True):
        if not raw.endswith(b"\n"):
            totals["INCOMPLETE"] += 1
            continue
        msg = TAG.match(raw.rstrip(b"\r\n"))
        if msg is None:
            totals["UNTAGGED"] += 1
            continue
        totals["TAGGED"] += 1
        process = msg.group(2).upper()
        if msg.group(1).decode("ascii").upper() != pid or process != b"IEXPLORE.EXE":
            totals["OTHER_PID_OR_PROCESS"] += 1
            continue
        totals["SELECTED_PID_LINES"] += 1
        body = msg.group(3)
        # Native TX-context and TX lines are adjacent within a process.
        if not body.startswith(TX_CONTEXT + b" ") and not body.startswith(TX + b" "):
            txctx = None

        if body.startswith(INI):
            pending = body[len(INI):]
            continue
        if body.startswith(INIT):
            init_pending = True
            continue
        if body.startswith(OPEN):
            epoch += 1
            active = epoch
            groups[epoch] = Counter()
            current_dir = from_ini(decode(pending))
            if selected_dir is None or current_dir is None:
                origin = "UNKNOWN"
            else:
                origin = "SELECTED" if current_dir == selected_dir else "OTHER"
            origins[epoch] = origin
            groups[epoch]["INI_PRESENT"] = int(current_dir is not None)
            groups[epoch]["INIT_LINKED"] = int(init_pending)
            pending = None
            init_pending = False
            txctx = None
            continue
        if body.startswith(CLOSE):
            if active is not None:
                groups[active]["CLOSES"] += 1
            else:
                totals["CLOSE_NO_OPEN"] += 1
            active = None
            txctx = None
            continue
        if body.startswith(TX_CONTEXT + b" "):
            context = parse_packet(body, TX_CONTEXT, 20)
            txctx = (
                (be32(context, 4), be32(context, 8), be32(context, 12))
                if context is not None else None
            )
            if context is None:
                totals["MALFORMED_TX_CONTEXT"] += 1
            continue

        index = active if active is not None else 0
        stats = groups.setdefault(index, Counter())
        if body.startswith(TX + b" "):
            packet = parse_packet(body, TX)
            context = txctx
            txctx = None
            if packet is None or len(packet) < 7 or be32(packet, 0) != 0x18DA50F1 or packet[4] != 0x22:
                continue
            did = packet[5:7].hex().upper()
            stats["TX_"+did if did in DIDS else "TX_OTHER"] += 1
            if context is None:
                stats["TX_NO_CONTEXT"] += 1
            elif context[0] == 6 and context[2] == 500000 and context[1] & 0x100:
                stats["TX_ISO15765_500K_29BIT"] += 1
            else:
                stats["TX_BAD_CONTEXT"] += 1
            continue
        if body.startswith(RX + b" "):
            packet = parse_packet(body, RX)
            if packet is None or len(packet) < 7 or be32(packet, 0) != 0x18DAF150:
                continue
            payload = packet[4:]
            if payload[0] == 0x62 and len(payload) >= 3:
                did = payload[1:3].hex().upper()
                stats["POS_"+did if did in DIDS else "POS_OTHER"] += 1
            elif payload[:2] == b"\x7f\x22" and len(payload) >= 3:
                stats["NRC31" if payload[2] == 0x31 else "OTHER_NRC"] += 1
            continue
        for label, did in LAB.items():
            if body.startswith(label):
                stats["GENERATED_"+did] += 1
                break

    out = [
        "B3A312_EXACT_PID="+pid,
        f"B3A312_TAGGED_LINES={totals['TAGGED']}",
        f"B3A312_EXPECTED_TAGGED_LINES={expected_tagged_lines}",
        "B3A312_CENSUS_MATCH="+("TRUE" if totals["TAGGED"] == expected_tagged_lines else "FALSE"),
        f"B3A312_SELECTED_PID_LINES={totals['SELECTED_PID_LINES']}",
        f"B3A312_OTHER_PID_OR_PROCESS_LINES={totals['OTHER_PID_OR_PROCESS']}",
        f"B3A312_UNTAGGED_LINES={totals['UNTAGGED']}",
        f"B3A312_OPEN_EPOCHS={epoch}",
        "B3A312_SELECTED_DIRECTORY_RESOLVED="+("TRUE" if selected_dir else "FALSE"),
    ]
    if totals["TAGGED"] != expected_tagged_lines or totals["UNTAGGED"] or not totals["SELECTED_PID_LINES"]:
        return out + ["B3A312_RESULT=ERROR_ACTION_CENSUS_OR_PID"]
    for ep in sorted(groups):
        c = groups[ep]
        out.append(
            f"B3A312_EPOCH={ep},origin:{origins.get(ep,'NO_OPEN')},"
            f"ini_logged:{'TRUE' if c['INI_PRESENT'] else 'FALSE'},"
            f"init_linked:{'TRUE' if c['INIT_LINKED'] else 'FALSE'},"
            f"close:{c['CLOSES']},"
            f"cem22_tx:{sum(c['TX_'+did] for did in DIDS)+c['TX_OTHER']},"
            f"tx_iso15765_500k_29bit:{c['TX_ISO15765_500K_29BIT']},"
            f"tx_no_context:{c['TX_NO_CONTEXT']},tx_bad_context:{c['TX_BAD_CONTEXT']},"
            f"nrc31:{c['NRC31']},other_nrc:{c['OTHER_NRC']}"
        )
        for did in DIDS:
            out.append(
                f"B3A312_EPOCH_DID={ep},did:{did},tx:{c['TX_'+did]},"
                f"positive_delivered:{c['POS_'+did]},"
                f"lab_generated:{c['GENERATED_'+did]}"
            )
        out.append(
            f"B3A312_EPOCH_OTHER={ep},tx_other:{c['TX_OTHER']},"
            f"positive_other:{c['POS_OTHER']}"
        )
    out.extend((
        "B3A312_EPOCH_STATS=LOGGED_DURING_OPEN_NOT_REQUEST_RX_PAIRING",
        "B3A312_NRC31_PER_DID_ATTRIBUTION=NOT_PROVEN",
        "B3A312_REGISTERED_DIRECTORY_NOT_HISTORICAL_DLL_IDENTITY",
        "B3A312_GGD_LAB_POSITIVE_NOT_OEM_IDENT",
        "B3A312_VIDA_CEM_VISIBLE=OWNER_REPORTED",
        "B3A312_VIN_AND_GUI_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A312_NO_DLL_INI_REGISTRY_OR_VIDA_MUTATIONS=TRUE",
        "B3A312_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Read-only fresh VIDA CEM traffic grouped by PassThruOpen")
    ap.add_argument("--log", required=True, type=Path)
    ap.add_argument("--start-offset", required=True, type=int)
    ap.add_argument("--end-offset", required=True, type=int)
    ap.add_argument("--pid", default="00001130")
    ap.add_argument("--expected-tagged-lines", default=2339, type=int)
    ap.add_argument("--adapter-label", default="J2534 Diagnostic Lab 277")
    args = ap.parse_args()
    if (PID.fullmatch(args.pid.upper()) is None or
            not LABEL.fullmatch(args.adapter_label) or
            args.start_offset <= 0 or args.end_offset <= args.start_offset or
            args.end_offset-args.start_offset > 32*1024*1024 or
            args.expected_tagged_lines <= 0):
        print("B3A312_RESULT=ERROR_ARGUMENTS")
        return 2
    capture = peer("B3A300-Recover-VIDA-Gate-Window.py")["capture_historic"]
    try:
        with args.log.open("rb") as f:
            data, _, discarded, start = capture(
                f, end_offset=args.end_offset,
                window_bytes=args.end_offset-args.start_offset)
    except (OSError, ValueError):
        print("B3A312_RESULT=ERROR_LOG_OR_OFFSETS")
        return 1
    status, directory = resolve_current_dir(args.adapter_label)
    print("B3A312_LOG_START="+str(args.start_offset))
    print("B3A312_LOG_END="+str(args.end_offset))
    print("B3A312_LOG_COMPLETE_BYTES="+str(len(data)))
    print("B3A312_LOG_BOUNDARY_PARTIAL_BYTES="+str(discarded))
    print("B3A312_CURRENT_REG32_PROVIDER_STATUS="+status)
    if status != "READ_OK":
        print("B3A312_RESULT=ERROR_PROVIDER_NOT_RESOLVED")
        return 1
    for item in analyze(
            data, pid=args.pid.upper(), selected_dir=directory,
            expected_tagged_lines=args.expected_tagged_lines):
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
