#!/usr/bin/env python3
"""B3A317: read-only provenance and shape audit of historical emulator F1xx positives.

Inventory existing ORIGINAL VIDA + VIRTUAL J2534 log up to immutable byte
offset 75759862. Use B3A316 expected 28 service-22 F1xx positives (12
CEM29 F110, 3 CEM29 F114, 13 CEM11 F114, zero F106) and exact fresh
VIDA 2339-line anchor as fail-closed checks. Trace each positive to the
currently active in-process PassThruOpen epoch, its historical Active INI
module directory vs CURRENT registry labels, request count within epoch,
data length, and available native source provenance markers.

No one-to-one TX/RX matching; many received messages may be delivered
later than their originating request, and a PID may be reused. Synthetic
marker in same epoch isn't definitive proof for each RX. F114's historical
29-bit positives are NOT evidence current source supports that route.
No raw bytes, VIN, hashes, private paths/INI contents or module loading.
Never writes files, executes J2534/VIDA or changes registry/DLL/INI.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re
import runpy
import sys
import argparse

TAG = re.compile(rb"^\[PID=([0-9A-Fa-f]{8}) ([A-Za-z0-9_.-]{1,64})\] (.*)$")
HEX = re.compile(rb"(?:[0-9A-Fa-f]{2})(?: [0-9A-Fa-f]{2})*\Z")
DIDS = ("F110", "F106", "F114")
ROUTES = {"CEM29": (0x18DA50F1, 0x18DAF150),
          "CEM11": (0x726, 0x72E)}
EXPECTED = {("CEM29", "F110"): 12, ("CEM29", "F106"): 0,
            ("CEM29", "F114"): 3, ("CEM11", "F110"): 0,
            ("CEM11", "F106"): 0, ("CEM11", "F114"): 13}
ORIGINAL_BEFORE = 75494985
ORIGINAL_END = 75759862
ORIGINAL_ANCHOR_PID = "00001130"
ORIGINAL_ANCHOR_LINES = 2339
OPEN = b"PassThruOpen -> device 1"
CLOSE = b"PassThruClose"
INI = b"Active INI: "
TX = b"TX (app request)"
RX = b"PassThruReadMsgs -> delivered"
CONFIGURED = b"Read-only configured ECU DID reply (not OEM verified)"
SYNTH_F114 = b"P3 CEM F114 VIN reply (synthetic lab data)"


def peer(name):
    return runpy.run_path(str(Path(__file__).resolve().with_name(name)),
                          run_name="b3a317_peer_import")


def raw_packet(msg: bytes, marker: bytes) -> bytes | None:
    if not msg.startswith(marker+b" "):
        return None
    raw = msg[len(marker)+1:].strip()
    if HEX.fullmatch(raw) is None:
        return None
    return bytes.fromhex(raw.decode("ascii"))


def audit(lines, *, source_dirs: dict[str, str], end: int,
          before: int = ORIGINAL_BEFORE,
          anchor_pid: str = ORIGINAL_ANCHOR_PID,
          anchor_lines: int = ORIGINAL_ANCHOR_LINES,
          expected: dict[tuple[str, str], int] = EXPECTED) -> list[str]:
    b306 = peer("B3A306-Audit-Active-GGD-Profile-Origins.py")
    b307 = peer("B3A307-Audit-J2534-Registry-Origins.py")
    decode_ini = b306["decode_log_path"]
    normalize_ini_dir = b307["canonical_dir_from_ini"]
    stats = Counter()
    pending = {}
    epoch_num = Counter()
    active = {}
    origins = {}
    counts = defaultdict(Counter)
    lengths = defaultdict(list)
    epoch_markers = defaultdict(Counter)
    pos_by_route_did = Counter()
    pos_groups = set()
    at = 0

    for original in lines:
        start, at = at, at+len(original)
        if at > end:
            stats["READ_PAST_FIXED_END"] += 1
            break
        if not original.endswith(b"\n"):
            stats["PARTIAL_LINE"] += 1
            continue
        in_anchor = before <= start < end
        if start < before < at:
            stats["ANCHOR_CROSSING"] += 1
        if in_anchor:
            stats["ANCHOR_COMPLETE"] += 1
        match = TAG.match(original.rstrip(b"\r\n"))
        if match is None:
            if in_anchor:
                stats["ANCHOR_UNTAGGED"] += 1
            continue
        if in_anchor:
            stats["ANCHOR_TAGGED"] += 1
            if (match.group(1).decode("ascii").upper() == anchor_pid
                    and match.group(2).upper() == b"IEXPLORE.EXE"):
                stats["ANCHOR_PID"] += 1
        if match.group(2).upper() != b"IEXPLORE.EXE":
            continue
        pid = match.group(1).decode("ascii").upper()
        body = match.group(3)

        if body.startswith(INI):
            pending[pid] = body[len(INI):]
            continue
        if body.startswith(OPEN):
            epoch_num[pid] += 1
            eid = (pid, epoch_num[pid])
            active[pid] = eid
            logged_path = decode_ini(pending.pop(pid, None))
            dirname = normalize_ini_dir(logged_path)
            origins[eid] = (
                "UNKNOWN" if dirname is None else
                source_dirs.get(dirname, "UNREGISTERED_OR_CHANGED"))
            continue
        if body.startswith(CLOSE):
            active[pid] = None
            continue

        eid = active.get(pid) or (pid, 0)
        if eid[1] == 0:
            origins.setdefault(eid, "NO_ACTIVE_OPEN_CAPTURED")
        if body.startswith(CONFIGURED):
            did = raw_packet(body, CONFIGURED)
            if did in (b"\xf1\x10", b"\xf1\x06", b"\xf1\x14"):
                epoch_markers[eid]["CONFIGURED_"+did.hex().upper()] += 1
            else:
                epoch_markers[eid]["CONFIGURED_UNATTRIBUTED"] += 1
            continue
        if body.startswith(SYNTH_F114):
            epoch_markers[eid]["SYNTH_F114"] += 1
            continue

        marker = TX if body.startswith(TX+b" ") else RX if body.startswith(RX+b" ") else None
        if marker is None:
            continue
        packet = raw_packet(body, marker)
        if packet is None or len(packet) < 7:
            continue
        identifier = int.from_bytes(packet[:4], "big")
        payload = packet[4:]
        for route, (req, resp) in ROUTES.items():
            if marker == TX:
                if identifier != req or payload[0] != 0x22 or len(payload) != 3:
                    continue
                did = payload[1:3].hex().upper()
                if did in DIDS:
                    counts[(eid, route, did)]["TX"] += 1
            else:
                if (identifier != resp or payload[0] != 0x62
                        or len(payload) < 3):
                    continue
                did = payload[1:3].hex().upper()
                if did in DIDS:
                    key = (eid, route, did)
                    counts[key]["POS"] += 1
                    lengths[key].append(len(payload)-3)
                    pos_by_route_did[(route, did)] += 1
                    pos_groups.add(key)

    anchor_ok = (stats["ANCHOR_TAGGED"] == anchor_lines and
                 stats["ANCHOR_PID"] == anchor_lines and
                 stats["ANCHOR_UNTAGGED"] == 0 and
                 stats["ANCHOR_CROSSING"] == 0 and
                 stats["READ_PAST_FIXED_END"] == 0 and at == end)
    positive_ok = all(pos_by_route_did.get(key, 0) == number
                      for key, number in expected.items())
    out = [
        "B3A317_ANCHOR_CENSUS_MATCH="+("TRUE" if anchor_ok else "FALSE"),
        f"B3A317_ANCHOR_TAGGED={stats['ANCHOR_TAGGED']}",
        f"B3A317_ANCHOR_EXPECTED={anchor_lines}",
        "B3A317_FULL_LOG_POSITIVE_CENSUS_MATCH="+
        ("TRUE" if positive_ok else "FALSE"),
        f"B3A317_POSITIVE_EPOCH_GROUPS={len(pos_groups)}",
        f"B3A317_FIXED_END={end}",
    ]
    for route in ROUTES:
        for did in DIDS:
            out.append(
                f"B3A317_TOTAL=route:{route},did:{did},"
                f"positive:{pos_by_route_did[(route,did)]},"
                f"expected:{expected.get((route,did),'NOT_SET')}")
    if not anchor_ok or not positive_ok:
        return out + ["B3A317_RESULT=ERROR_CENSUS_OR_TRUNCATED_LOG"]
    if len(pos_groups) > 256:
        return out + ["B3A317_RESULT=ERROR_TOO_MANY_GROUPS"]

    # Restrict epochs to those with positive replies. These output only
    # historic PID/epoch number, current origin registry label, event counts
    # and length bounds; the actual response body is never returned.
    for eid, route, did in sorted(pos_groups):
        c = counts[(eid, route, did)]
        size = lengths[(eid, route, did)]
        marks = epoch_markers[eid]
        # F114 synthetic marker has no DID data and may belong to CEM11;
        # count only on the epoch, not as direct proof of a CEM29 F114 RX.
        out.append(
            f"B3A317_POS_EPOCH=pid:{eid[0]},epoch:{eid[1]},"
            f"origin:{origins[eid]},route:{route},did:{did},"
            f"tx_in_epoch:{c['TX']},positive_in_epoch:{c['POS']},"
            f"data_len_min:{min(size)},data_len_max:{max(size)},"
            f"configured_did_marker_in_epoch:{marks['CONFIGURED_'+did]},"
            f"synthetic_f114_marker_in_epoch:{marks['SYNTH_F114']}"
        )
    out.extend((
        "B3A317_DATA_LENGTH_IS_NOT_PAYLOAD_OR_OEM_IDENTITY",
        "B3A317_MARKER_IN_SAME_EPOCH_NOT_PROOF_OF_PARTICULAR_RX_SOURCE",
        "B3A317_TX_IN_SAME_EPOCH_NOT_PROOF_OF_REQUEST_RESPONSE_PAIRING",
        "B3A317_MODULE_ORIGIN_IS_CURRENT_REGISTRY_DIRECTORY_MATCH_ONLY",
        "B3A317_HISTORICAL_29BIT_F114_DOES_NOT_PROVE_CURRENT_HANDLER",
        "B3A317_VIRTUAL_J2534_LOG_NOT_GENUINE_ECU_CAPTURE",
        "B3A317_VIDA_READVIN_CEM_IDENT_ACCEPTANCE=NOT_ASSESSED",
        "B3A317_NO_PRIVATE_BYTES_OR_WRITES=TRUE",
        "B3A317_RESULT=READ_ONLY_COMPLETE",
    ))
    return out


def main():
    ap = argparse.ArgumentParser(description="Read-only F1xx positive provenance by J2534 Open epoch")
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--end-offset", type=int, default=ORIGINAL_END)
    args = ap.parse_args()
    if args.end_offset != ORIGINAL_END:
        print("B3A317_RESULT=ERROR_UNSUPPORTED_OFFSET")
        return 2
    b316 = peer("B3A316-Audit-VIDA-F1xx-Historical-Positives.py")
    registry = peer("B3A310-Resolve-VIDA-J2534-Adapter-Label.py")["registry_labels_32"]
    state, entries = registry()
    print("B3A317_REG32_STATUS="+state)
    if state != "READ_OK":
        print("B3A317_RESULT=ERROR_REGISTRY_UNAVAILABLE")
        return 1
    try:
        output = audit(
            b316["bounded_lines"](args.log,args.end_offset),
            source_dirs=b316["source_classifications"](entries),
            end=args.end_offset)
    except (OSError, ValueError):
        print("B3A317_RESULT=ERROR_LOG_READ")
        return 1
    for item in output:
        print(item)
    return 0 if "B3A317_RESULT=READ_ONLY_COMPLETE" in output else 1


if __name__ == "__main__":
    sys.exit(main())
