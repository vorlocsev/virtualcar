#!/usr/bin/env python3
"""B3A316: inventory F110/F106/F114 requests and positives in original VIDA J2534 log.

Read only a fixed prefix of SectorVVirtualCar.log, verifying the fresh original
VIDA anchor [75494985,75759862), 2339 tagged lines from IEXPLORE PID00001130.
Enumerate CEM29 (18DA50F1/18DAF150) and P3-style CEM11 (726/72E)
22 F1xx TX, 62 F1xx RX and 7F 22 31 RX, associated with per-PID Open epochs.
Track current 32-bit J2534 registry same-directory labels as metadata only.

This is a VIRTUAL-CAR DLL-produced trace, NOT a genuine physical OEM capture.
Even 62 F1xx positives would be evidence only of EMULATED log traffic.
A missing observed positive is negative evidence within this bounded log
and not proof the real CEM lacks support. NRC31 lacks individual DID identity.
An Active INI directory match is not proof of historical binary identity.
No VIN, raw packets, payload bytes, private paths, DLL names or hashes are
printed. Never starts VIDA/J2534, loads DLLs, or writes files/INI/registry.
"""
from __future__ import annotations
import argparse
from collections import Counter
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(rb"^\[PID=([a-fA-F0-9]{8}) ([A-Za-z0-9_.-]{1,64})\] (.*)$")
HEX = re.compile(rb"(?:[0-9a-fA-F]{2})(?: [0-9a-fA-F]{2})*\Z")
LABEL = re.compile(r"[A-Za-z0-9 _().-]{1,120}\Z")
DIDS = ("F110", "F106", "F114")
INIPREFIX = b"Active INI: "
OPEN = b"PassThruOpen -> device 1"
CLOSE = b"PassThruClose"
TX = b"TX (app request)"
RX = b"PassThruReadMsgs -> delivered"
ROUTES = {
    "CEM29": (0x18DA50F1, 0x18DAF150),
    "CEM11": (0x726, 0x72E),
}
DEFAULT_END = 75759862
ANCHOR_BEFORE = 75494985
ANCHOR_AFTER = 75759862
ANCHOR_PID = "00001130"
ANCHOR_LINES = 2339


def peer(name: str):
    return runpy.run_path(str(Path(__file__).resolve().with_name(name)),
                          run_name="b3a316_peer_import")


def parse_packet(line: bytes, marker: bytes) -> bytes | None:
    if not line.startswith(marker+b" "):
        return None
    raw = line[len(marker)+1:].strip()
    if HEX.fullmatch(raw) is None:
        return None
    return bytes.fromhex(raw.decode("ascii"))


def source_classifications(registry: list[tuple[str, str]]) -> dict[str, str]:
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    from_dll = b307["canonical_dir_from_dll"]
    dirs: dict[str, list[str]] = {}
    for label, dll in registry:
        directory = from_dll(dll)
        if directory is not None:
            dirs.setdefault(directory, []).append(label)
    return {directory: (names[0] if len(names) == 1 and
                        LABEL.fullmatch(names[0]) else "UNRESOLVED")
            for directory, names in dirs.items()}


def analyze_lines(lines, *, end: int, source_dirs: dict[str, str],
                  anchor_before: int = ANCHOR_BEFORE,
                  anchor_after: int = ANCHOR_AFTER,
                  anchor_pid: str = ANCHOR_PID,
                  expected_anchor_lines: int = ANCHOR_LINES) -> list[str]:
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    decode = b306["decode_log_path"]
    from_ini = b307["canonical_dir_from_ini"]

    totals = Counter()
    by_pid = {}
    pending_ini = {}
    pid_epoch = Counter()
    pid_active = {}
    epoch_source = {}
    stats = Counter()
    at = 0

    def classify_origin(pid):
        path = decode(pending_ini.pop(pid, None))
        dirname = from_ini(path)
        if dirname is None:
            return "UNKNOWN"
        return source_dirs.get(dirname, "UNREGISTERED_OR_CHANGED")

    for original in lines:
        beginning = at
        at += len(original)
        if at > end:
            totals["CROSSES_END"] += 1
            break
        if not original.endswith(b"\n"):
            totals["PARTIAL_LINE"] += 1
            continue
        in_anchor = anchor_before <= beginning < anchor_after
        if beginning < anchor_before < at:
            totals["ANCHOR_CROSSING_LINE"] += 1
        if in_anchor:
            totals["ANCHOR_COMPLETE_LINES"] += 1
        match = TAG.match(original.rstrip(b"\r\n"))
        if not match:
            if in_anchor:
                totals["ANCHOR_UNTAGGED"] += 1
            continue
        if in_anchor:
            totals["ANCHOR_TAGGED"] += 1
            if (match.group(1).decode("ascii").upper() == anchor_pid
                    and match.group(2).upper() == b"IEXPLORE.EXE"):
                totals["ANCHOR_SELECTED_PID_LINES"] += 1
        if match.group(2).upper() != b"IEXPLORE.EXE":
            continue
        totals["IEXPLORE_LINES"] += 1
        pid = match.group(1).decode("ascii").upper()
        by_pid[pid] = by_pid.get(pid, 0)+1
        body = match.group(3)
        if body.startswith(INIPREFIX):
            pending_ini[pid] = body[len(INIPREFIX):]
            continue
        if body.startswith(OPEN):
            pid_epoch[pid] += 1
            active = (pid, pid_epoch[pid])
            pid_active[pid] = active
            epoch_source[active] = classify_origin(pid)
            totals["IEXPLORE_OPENS"] += 1
            continue
        if body.startswith(CLOSE):
            pid_active[pid] = None
            totals["IEXPLORE_CLOSES"] += 1
            continue
        marker = TX if body.startswith(TX+b" ") else RX if body.startswith(RX+b" ") else None
        if marker is None:
            continue
        packet = parse_packet(body, marker)
        if packet is None or len(packet) < 7:
            if packet is None:
                totals["INVALID_PACKET_LOGS"] += 1
            continue
        cid = int.from_bytes(packet[:4], "big")
        service = packet[4:]
        matched_route = None
        for name, (req, resp) in ROUTES.items():
            if marker is TX and cid == req or marker is RX and cid == resp:
                matched_route = name
                break
        if matched_route is None:
            continue
        active = pid_active.get(pid)
        label = epoch_source.get(active, "NO_ACTIVE_OPEN_CAPTURED")
        if marker is TX:
            if service[0] == 0x22 and len(service) == 3:
                did = service[1:3].hex().upper()
                if did in DIDS:
                    stats[(matched_route, did, "TX", label)] += 1
        else:
            if service[0] == 0x62 and len(service) >= 3:
                did = service[1:3].hex().upper()
                if did in DIDS:
                    stats[(matched_route, did, "POSITIVE_DELIVERED", label)] += 1
            elif service[:3] == b"\x7f\x22\x31":
                stats[(matched_route, "UNKNOWN", "NRC31_DELIVERED", label)] += 1
    out = [
        f"B3A316_LOG_END_REQUESTED={end}",
        f"B3A316_BYTES_CONSUMED={min(at, end)}",
        f"B3A316_ANCHOR_START={anchor_before}",
        f"B3A316_ANCHOR_END={anchor_after}",
        f"B3A316_ANCHOR_TAGGED_LINES={totals['ANCHOR_TAGGED']}",
        f"B3A316_ANCHOR_EXPECTED_TAGGED_LINES={expected_anchor_lines}",
        f"B3A316_ANCHOR_PID_LINES={totals['ANCHOR_SELECTED_PID_LINES']}",
        "B3A316_ANCHOR_CENSUS_MATCH="+(
            "TRUE" if totals["ANCHOR_TAGGED"] == expected_anchor_lines
            and totals["ANCHOR_SELECTED_PID_LINES"] == expected_anchor_lines
            and totals["ANCHOR_UNTAGGED"] == 0
            and totals["ANCHOR_CROSSING_LINE"] == 0
            and totals["CROSSES_END"] == 0 else "FALSE"
        ),
        f"B3A316_IEXPLORE_UNIQUE_PIDS={len(by_pid)}",
        f"B3A316_IEXPLORE_OPENS={totals['IEXPLORE_OPENS']}",
        f"B3A316_IEXPLORE_CLOSES={totals['IEXPLORE_CLOSES']}",
        f"B3A316_INVALID_PACKET_LOGS={totals['INVALID_PACKET_LOGS']}",
    ]
    if out[7] != "B3A316_ANCHOR_CENSUS_MATCH=TRUE":
        return out + ["B3A316_RESULT=ERROR_ANCHOR_CENSUS"]
    for route in ROUTES:
        for did in DIDS:
            tx = sum(count for (r, d, kind, _), count in stats.items()
                     if (r, d, kind) == (route, did, "TX"))
            pos = sum(count for (r, d, kind, _), count in stats.items()
                      if (r, d, kind) == (route, did, "POSITIVE_DELIVERED"))
            out.append(f"B3A316_DID=route:{route},did:{did},tx:{tx},positive_delivered:{pos}")
        nrc = sum(count for (r, _, kind, _), count in stats.items()
                  if r == route and kind == "NRC31_DELIVERED")
        out.append(f"B3A316_ROUTE=route:{route},nrc31_delivered:{nrc},nrc_did_attribution:NOT_PROVEN")
    # Emit only explicitly observed positive provider groups. No raw bytes
    # or full original/private path or unique file fingerprint ever emitted.
    for (route, did, kind, origin), count in sorted(stats.items()):
        if kind == "POSITIVE_DELIVERED":
            out.append(f"B3A316_POSITIVE_GROUP=route:{route},did:{did},origin:{origin},count:{count}")
    out.extend((
        "B3A316_PROVENANCE=VIRTUAL_CAR_J2534_LOG_NOT_PHYSICAL_OEM_CAPTURE",
        "B3A316_CURRENT_REGISTRY_LABEL_NOT_HISTORICAL_BINARY_IDENTITY",
        "B3A316_PID_REUSE_OUTSIDE_ANCHOR_POSSIBLE",
        "B3A316_ZERO_POSITIVES_MEANS_NOT_FOUND_IN_THIS_LOG_ONLY",
        "B3A316_F106_DONOR_FLASH_MAP_NOT_ON_WIRE_RESPONSE",
        "B3A316_GUI_CEM_IDENT_AND_READVIN=NOT_ASSESSED",
        "B3A316_NO_PRIVATE_DATA_OR_MODULE_WRITES=TRUE",
        "B3A316_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def bounded_lines(path: Path, end: int):
    with path.open("rb") as f:
        f.seek(0, 2)
        if f.tell() < end:
            raise ValueError("log shorter than fixed end")
        f.seek(0)
        while f.tell() < end:
            line = f.readline()
            if not line:
                raise ValueError("log read terminated early")
            yield line


def main():
    parser = argparse.ArgumentParser(description="Read-only census of entire historical VirtualCar log F1xx positives")
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--end-offset", type=int, default=DEFAULT_END)
    args = parser.parse_args()
    if args.end_offset < ANCHOR_AFTER or args.end_offset > 96*1024*1024:
        print("B3A316_RESULT=ERROR_INVALID_END")
        return 2
    registry = peer("B3A310-Resolve-VIDA-J2534-Adapter-Label.py")["registry_labels_32"]
    status, entries = registry()
    print("B3A316_CURRENT_REG32_STATUS="+status)
    if status != "READ_OK":
        print("B3A316_RESULT=ERROR_REGISTRY_UNAVAILABLE")
        return 1
    try:
        output = analyze_lines(bounded_lines(args.log, args.end_offset),
                               end=args.end_offset,
                               source_dirs=source_classifications(entries))
    except (OSError, ValueError):
        print("B3A316_RESULT=ERROR_LOG_UNAVAILABLE_OR_TRUNCATED")
        return 1
    for line in output:
        print(line)
    return 0 if "B3A316_RESULT=READ_ONLY_COMPLETE" in output else 1


if __name__ == "__main__":
    sys.exit(main())
