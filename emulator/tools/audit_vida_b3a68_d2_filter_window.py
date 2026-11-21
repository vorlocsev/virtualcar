#!/usr/bin/env python3
"""B3A68: privacy-safe original-VIDA candidate filter audit for one B3A45 window.

Offline only: validates a prior B3A45 baseline and exact append prefix via
B3A63, then inspects same-text-PID native logger records. This cannot infer
which channel received a filter: source PassThruStartMsgFilter logs no channel.
No live VIDA, native DLL, vehicle, registry or installed INI access.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

from audit_vida_cem50_ps_same_pid_ini import _owner_lines
from audit_vida_b3a52_loaded_fixtures import _metadata

SCHEMA = "virtualcar-b3a68-original-d2-filter-window-v1"
PREFIX = re.compile(r"^\[PID=([0-9a-fA-F]{8}) ([A-Za-z0-9_.-]{1,48})\] ")
HEXBYTE = re.compile(r"^[0-9a-fA-F]{2}$")
LABEL_REQUEST = "P2 D2 request target/opcode/baud/flags (BE)"
LABEL_FILTER = "PassThruStartMsgFilter type / id (BE)"
LABEL_MASK = "  filter mask"
LABEL_PATTERN = "  filter pattern"
LABEL_CONNECT = "J2534 Connect result protocol/flags/baud/status (BE)"
LABEL_CONFIG = "J2534 SET_CONFIG channel/parameter/value/applied (BE)"
LABEL_INIT = "Active INI: "
# This is the lab/synthetic ResponseId from installed source INI, NOT an
# independently authenticated OEM/VIDA expected CAN response ID.
CEM40_LAB_RESPONSE_ID = 0x00800003
HOSTS = ("iexplore.exe", "java.exe", "vidamonitor.exe")


def _line(raw):
    if type(raw) is not str or len(raw) > 512:
        return None
    match = PREFIX.match(raw)
    if match is None:
        return None
    return int(match.group(1), 16), match.group(2).lower(), raw[match.end():]


def _hex_bytes(event, label, *, minlen=4, maxlen=12):
    if not event.startswith(label + " "):
        return None
    parts = event[len(label) + 1:].strip().split()
    if not minlen <= len(parts) <= maxlen or any(
            HEXBYTE.fullmatch(s) is None for s in parts):
        return None
    return bytes(int(s, 16) for s in parts)


def _connect_class(meta):
    protocol = int.from_bytes(meta[0:4], "big")
    baud = int.from_bytes(meta[8:12], "big")
    status = int.from_bytes(meta[12:16], "big")
    p = {5: "CAN", 6: "ISO15765", 0x8004: "CAN_PS",
         0x8005: "ISO15765_PS"}.get(protocol, "other")
    b = {125000: "125000", 500000: "500000"}.get(baud, "other")
    return p, b, ("success" if status == 0 else "nonzero_result")


def _base(host):
    return {
        "schema_version": SCHEMA,
        "evidence_scope": "owner_local_exact_B3A45_append_plus_bounded_prebaseline_tail",
        "host_exe_category": host,
        "status": "NOT_ASSESSED",
        "d2_40_b9fb_requests_in_append": 0,
        "native_logger_pid_groups_for_d2_40_b9fb": 0,
        "request_baud": "not_observed",
        "preceding_scope": "not_established",
        "connect_modes_preceding": [],
        "set_config_records_preceding": 0,
        "filter_start_records_preceding": 0,
        "complete_filter_mask_pattern_triplets": 0,
        "incomplete_filter_triplets": 0,
        "filter_type_counts": {"pass": 0, "block": 0, "flow": 0, "other": 0},
        "pass_filter_would_match_lab_id": 0,
        "block_filter_would_match_lab_id": 0,
        "pass_odd_bit_only_filter_candidate": 0,
        "pass_exact_lab_id_filter_candidate": 0,
        "actual_filter_channel_verified": False,
        "actual_filter_lifetime_verified": False,
        "process_creation_epoch_verified": False,
        "original_vida_filter_installer_attested": False,
        "actual_vida_readvin_verified": False,
        "j2534_rx_delivered_verified": False,
        "identity_or_oem_origin_verified": False,
        "source_path_pid_vin_frame_or_mask_values_exported": False,
        "limitations": [
            "Native StartMsgFilter records have type/id, mask and pattern, but NO channel identifier.",
            "Text PID and executable name do not independently authenticate a VIDA GUI session or process epoch.",
            "A preceding filter record is not proof that it remained installed during the request; StopMsgFilter is not logged.",
            "A CAN ID candidate match says nothing about the original VIDA-selected RX mask, 29-bit flags or channel.",
            "J1962_PINS parameter 0x8001 is deliberately redacted from native SET_CONFIG metadata.",
            "The configured CEM40 response CAN ID is a synthetic lab candidate, not an OEM-attested value.",
            "Old append windows may start after filter install, Open or Connect.",
        ],
    }


def analyze(history, appended, host="iexplore.exe"):
    """No raw source values leave this function; always fail closed."""
    if host not in HOSTS:
        raise ValueError("invalid host")
    result = _base(host)
    combined = history + appended
    offset = len(history)
    requests = []
    for i, raw in enumerate(appended):
        r = _line(raw)
        if r is None or r[1] != host:
            continue
        meta = _metadata(r[2], LABEL_REQUEST)
        if meta is None:
            continue
        target = int.from_bytes(meta[:4], "big")
        op = int.from_bytes(meta[4:8], "big")
        if target == 0x40 and op == 0xFB:
            requests.append((i + offset, r[0], int.from_bytes(meta[8:12], "big")))
    result["d2_40_b9fb_requests_in_append"] = len(requests)
    pids = {p for _, p, _ in requests}
    result["native_logger_pid_groups_for_d2_40_b9fb"] = len(pids)
    if not requests:
        result["status"] = "NO_D2_40_B9FB_REQUEST_IN_APPEND"
        return result
    if len(pids) != 1:
        result["status"] = "AMBIGUOUS_MULTIPLE_NATIVE_LOGGER_PIDS"
        return result
    if len(requests) != 1:
        result["status"] = "MULTIPLE_SAME_PID_REQUESTS_UNATTRIBUTABLE"
        return result
    request_index, pid, baud = requests[0]
    result["request_baud"] = str(baud) if baud in (125000, 500000) else "other"
    # Strongest available textual boundary: last source-coded "Active INI:"
    # for the same PID BEFORE the sole requested B9 FB. This is not a
    # process-creation-time attestation, nor a verified channel connection.
    starts = [
        i for i, raw in enumerate(combined[:request_index])
        if (r := _line(raw)) is not None and r[0] == pid
        and r[1] == host and r[2].startswith(LABEL_INIT)
    ]
    if starts:
        start = starts[-1] + 1
        result["preceding_scope"] = "after_last_same_text_pid_active_ini_marker"
    else:
        start = offset
        result["preceding_scope"] = "append_only_no_prior_active_ini_marker"
    scope = combined[start:request_index]
    connects = Counter()
    i = 0
    while i < len(scope):
        r = _line(scope[i])
        if r is None or r[0] != pid or r[1] != host:
            i += 1
            continue
        event = r[2]
        con = _metadata(event, LABEL_CONNECT)
        if con is not None:
            connects[_connect_class(con)] += 1
        if _metadata(event, LABEL_CONFIG) is not None:
            result["set_config_records_preceding"] += 1
        # This marker logs TWO big-endian U32 words (8 bytes), unlike
        # 16-byte D2 request/connect/config markers.
        filt = _hex_bytes(event, LABEL_FILTER, minlen=8, maxlen=8)
        if filt is not None:
            result["filter_start_records_preceding"] += 1
            ftype = int.from_bytes(filt[:4], "big")
            typ = {1: "pass", 2: "block", 3: "flow"}.get(ftype, "other")
            result["filter_type_counts"][typ] += 1
            # Fail closed if mask/pattern records were interleaved with
            # another PID or truncated by the baseline/line limit.
            mask = pattern = None
            if i + 2 < len(scope):
                r1, r2 = _line(scope[i + 1]), _line(scope[i + 2])
                if (r1 is not None and r2 is not None and
                        (r1[0], r1[1], r2[0], r2[1]) ==
                        (pid, host, pid, host)):
                    mask = _hex_bytes(r1[2], LABEL_MASK)
                    pattern = _hex_bytes(r2[2], LABEL_PATTERN)
            if mask is None or pattern is None or len(mask) != len(pattern):
                result["incomplete_filter_triplets"] += 1
            else:
                result["complete_filter_mask_pattern_triplets"] += 1
                mask_id = int.from_bytes(mask[:4], "big")
                pattern_id = int.from_bytes(pattern[:4], "big")
                same_id_candidate = (
                    (CEM40_LAB_RESPONSE_ID & mask_id) == (pattern_id & mask_id))
                if ftype == 1 and same_id_candidate:
                    result["pass_filter_would_match_lab_id"] += 1
                    if mask_id == 1 and pattern_id == 1 and len(mask) == 4:
                        result["pass_odd_bit_only_filter_candidate"] += 1
                    if mask_id == 0xFFFFFFFF and pattern_id == CEM40_LAB_RESPONSE_ID and len(mask) == 4:
                        result["pass_exact_lab_id_filter_candidate"] += 1
                if ftype == 2 and same_id_candidate:
                    result["block_filter_would_match_lab_id"] += 1
                i += 3
                continue
        i += 1
    result["connect_modes_preceding"] = [
        {"protocol": p, "baud_bps": b, "result": state, "count": n}
        for (p, b, state), n in sorted(connects.items())
    ]
    result["status"] = ("SAME_TEXT_PID_FILTER_CANDIDATES_NOT_CHANNEL_ATTESTED"
                        if result["complete_filter_mask_pattern_triplets"] else
                        "NO_COMPLETE_SAME_TEXT_PID_FILTER_BEFORE_REQUEST")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--virtual-log", required=True, type=Path)
    parser.add_argument("--private-baseline", required=True, type=Path)
    parser.add_argument("--host-exe", choices=HOSTS, default="iexplore.exe")
    args = parser.parse_args(argv)
    try:
        history, appended = _owner_lines(args.virtual_log, args.private_baseline)
        report = analyze(history, appended, host=args.host_exe)
    except (OSError, ValueError, UnicodeError, KeyError, json.JSONDecodeError):
        print("B3A68: SOURCE_OR_BASELINE_UNAVAILABLE; no source values displayed",
              file=sys.stderr)
        return 2
    for key, value in report.items():
        if key != "limitations":
            print(key + ":", json.dumps(value, ensure_ascii=False, sort_keys=True))
    print("B3A68: No proof of original VIDA channel-filter binding, RX or ReadVin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
