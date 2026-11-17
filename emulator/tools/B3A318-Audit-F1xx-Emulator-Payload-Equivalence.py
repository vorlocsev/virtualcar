#!/usr/bin/env python3
"""B3A318: compare historical virtual J2534 CEM F1xx positive payload shapes.

Read-only original VIDA + *virtual J2534* log prefix ending at exact offset
75759862. Fail closed unless owner-confirmed B3A317 whole-log totals
(CEM29 F110=12, F106=0, F114=3; CEM11 F110=0, F106=0, F114=13)
and recent action 2339/2339 PID00001130 match exactly.

In memory only, compare complete data fields after positive 62 F1 xx:
for each route/DID/length/source show number of distinct byte sequences,
count of most repeated sequence, and whether the sequence is constant.
Additionally compare F114 same-length fields between CEM29 and CEM11.
No raw payload, VIN, private paths, hashes, byte digests or fingerprint
strings are logged or persisted. Equal bytes are NOT genuine Volvo OEM
evidence; values may be emulator fixtures or synthetic lab responses.
Never runs VIDA/J2534, loads DLLs, or writes any files/INI/registry.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import re
import runpy
import sys

TAG = re.compile(rb"^\[PID=([0-9A-Fa-f]{8}) ([A-Za-z0-9_.-]{1,64})\] (.*)$")
ORIGINAL_BEFORE = 75494985
ORIGINAL_END = 75759862
ORIGINAL_PID = "00001130"
ORIGINAL_ANCHOR_LINES = 2339
EXPECTED = {
    ("CEM29", "F110"): 12, ("CEM29", "F106"): 0, ("CEM29", "F114"): 3,
    ("CEM11", "F110"): 0, ("CEM11", "F106"): 0, ("CEM11", "F114"): 13,
}
ROUTES = {"CEM29": 0x18DAF150, "CEM11": 0x72E}
INI = b"Active INI: "
OPEN = b"PassThruOpen -> device 1"
CLOSE = b"PassThruClose"
RX = b"PassThruReadMsgs -> delivered"


def peer(name):
    return runpy.run_path(
        str(Path(__file__).resolve().with_name(name)),
        run_name="b3a318_peer_import")


def analyze(lines, *, source_dirs: dict[str,str], end: int,
            before: int = ORIGINAL_BEFORE, anchor_pid: str = ORIGINAL_PID,
            anchor_lines: int = ORIGINAL_ANCHOR_LINES,
            expected: dict[tuple[str,str],int] = EXPECTED):
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    b317 = peer("B3A317-Audit-F1xx-Positive-Open-Origins.py")
    decode_ini = b306["decode_log_path"]
    norm_dir = b307["canonical_dir_from_ini"]
    packet_from_log = b317["raw_packet"]
    pending = {}
    current_open = {}
    open_number = Counter()
    active_origin = {}
    totals = Counter()
    payloads: dict[tuple[str,str,int,str],Counter] = defaultdict(Counter)
    fields: dict[tuple[str,int],set[bytes]] = defaultdict(set)
    at = 0
    for line in lines:
        begin, at = at, at + len(line)
        if at > end:
            totals["PAST_END"] += 1
            break
        if not line.endswith(b"\n"):
            totals["NONCOMPLETE"] += 1
            continue
        in_anchor = before <= begin < end
        if begin < before < at:
            totals["BOUNDARY_SPLIT"] += 1
        if in_anchor:
            totals["ANCHOR_COMPLETE"] += 1
        match = TAG.match(line.rstrip(b"\r\n"))
        if match is None:
            if in_anchor:
                totals["ANCHOR_UNTAGGED"] += 1
            continue
        if in_anchor:
            totals["ANCHOR_TAGGED"] += 1
            if (match.group(1).decode("ascii").upper() == anchor_pid
                    and match.group(2).upper() == b"IEXPLORE.EXE"):
                totals["ANCHOR_PID"] += 1
        if match.group(2).upper() != b"IEXPLORE.EXE":
            continue
        pid = match.group(1).decode("ascii").upper()
        body = match.group(3)
        if body.startswith(INI):
            pending[pid] = body[len(INI):]
            continue
        if body.startswith(OPEN):
            open_number[pid] += 1
            eid = (pid, open_number[pid])
            current_open[pid] = eid
            dirname = norm_dir(decode_ini(pending.pop(pid,None)))
            active_origin[eid] = ("UNKNOWN" if dirname is None
                                  else source_dirs.get(dirname,"UNREGISTERED_OR_CHANGED"))
            continue
        if body.startswith(CLOSE):
            current_open[pid] = None
            continue
        if not body.startswith(RX+b" "):
            continue
        packet = packet_from_log(body, RX)
        if packet is None or len(packet) < 7:
            continue
        canid = int.from_bytes(packet[:4], "big")
        data = packet[4:]
        if len(data) < 3 or data[0] != 0x62 or data[1] != 0xF1:
            continue
        did = data[1:3].hex().upper()
        if did not in ("F110","F106","F114"):
            continue
        for route, response_id in ROUTES.items():
            if canid != response_id:
                continue
            total_key = (route,did)
            totals[total_key] += 1
            payload = data[3:]
            if len(payload) > 4096:
                totals["EXCESSIVE_FIELD_LENGTH"] += 1
                continue
            eid = current_open.get(pid)
            origin = active_origin.get(eid,"NO_ACTIVE_OPEN_CAPTURED")
            key = (route,did,len(payload),origin)
            payloads[key][payload] += 1
            if did == "F114":
                fields[(route,len(payload))].add(payload)
    anchor_ok = (totals["ANCHOR_TAGGED"] == anchor_lines
                 and totals["ANCHOR_PID"] == anchor_lines
                 and totals["ANCHOR_UNTAGGED"] == 0
                 and totals["BOUNDARY_SPLIT"] == 0
                 and totals["PAST_END"] == 0
                 and at == end)
    totals_ok = (all(totals[key] == count for key,count in expected.items())
                 and not totals["EXCESSIVE_FIELD_LENGTH"]
                 and sum(sum(v.values()) for v in payloads.values()) ==
                 sum(expected.values()))
    out = [
        "B3A318_ANCHOR_CENSUS_MATCH="+("TRUE" if anchor_ok else "FALSE"),
        "B3A318_POSITIVE_CENSUS_MATCH="+("TRUE" if totals_ok else "FALSE"),
        f"B3A318_ANCHOR_PID_LINES={totals['ANCHOR_PID']}",
        f"B3A318_EXPECTED_ANCHOR_LINES={anchor_lines}",
        f"B3A318_FIXED_END={end}",
    ]
    for route in ROUTES:
        for did in ("F110","F106","F114"):
            out.append(f"B3A318_TOTAL=route:{route},did:{did},"
                       f"positive:{totals[(route,did)]},expected:{expected.get((route,did),'NOT_SET')}")
    if not (anchor_ok and totals_ok):
        return out + ["B3A318_RESULT=ERROR_ANCHOR_OR_POSITIVE_CENSUS"]
    if len(payloads) > 256:
        return out + ["B3A318_RESULT=ERROR_TOO_MANY_GROUPS"]
    for (route,did,length,origin), samples in sorted(payloads.items()):
        count = sum(samples.values())
        variants = len(samples)
        most_common = max(samples.values())
        out.append(
            f"B3A318_PAYLOAD_GROUP=route:{route},did:{did},"
            f"data_len:{length},origin:{origin},"
            f"positive_count:{count},distinct_byte_patterns:{variants},"
            f"most_repeated_pattern_count:{most_common},"
            f"all_fields_identical:{'TRUE' if variants == 1 else 'FALSE'}")
    for length in sorted({size for _,size in fields}):
        a = fields.get(("CEM29",length),set())
        b = fields.get(("CEM11",length),set())
        if a and b:
            out.append(
                f"B3A318_F114_CROSSROUTE_LENGTH={length},"
                f"CEM29_variants:{len(a)},CEM11_variants:{len(b)},"
                f"shared_exact_byte_patterns:{len(a & b)}")
    out.extend((
        "B3A318_BYTE_EQUALITY_MEANS_EMULATED_FIXTURE_CONSISTENCY_NOT_OEM",
        "B3A318_NO_PACKET_DIGESTS_RAW_BYTES_VIN_OR_PRIVATE_PATHS_EMITTED",
        "B3A318_CURRENT_REGISTRY_LABEL_NOT_HISTORIC_BINARY_PROOF",
        "B3A318_VIDA_READVIN_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A318_NO_DLL_INI_REGISTRY_OR_VIDA_WRITES=TRUE",
        "B3A318_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main():
    p=argparse.ArgumentParser(description="Original VIDA virtual J2534 historical F1xx byte-equality audit")
    p.add_argument("--log",required=True,type=Path)
    p.add_argument("--end-offset",type=int,default=ORIGINAL_END)
    args=p.parse_args()
    if args.end_offset != ORIGINAL_END:
        print("B3A318_RESULT=ERROR_UNSUPPORTED_END_OFFSET")
        return 2
    b316=peer("B3A316-Audit-VIDA-F1xx-Historical-Positives.py")
    b310=peer("B3A310-Resolve-VIDA-J2534-Adapter-Label.py")
    status,entries=b310["registry_labels_32"]()
    print("B3A318_CURRENT_REG32_STATUS="+status)
    if status!="READ_OK":
        print("B3A318_RESULT=ERROR_REGISTRY_UNAVAILABLE")
        return 1
    try:
        results=analyze(b316["bounded_lines"](args.log,args.end_offset),
                        source_dirs=b316["source_classifications"](entries),
                        end=args.end_offset)
    except (OSError,ValueError):
        print("B3A318_RESULT=ERROR_LOG_READ")
        return 1
    for row in results:
        print(row)
    return 0 if "B3A318_RESULT=READ_ONLY_COMPLETE" in results else 1


if __name__=="__main__":
    sys.exit(main())
