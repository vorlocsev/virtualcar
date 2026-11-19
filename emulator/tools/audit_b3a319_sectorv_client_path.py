#!/usr/bin/env python3
"""Source-backed, read-only classification of bounded SectorV client logs.

The unique `P2 hardware CAN ` literal was located at SectorV.exe IL token
0x060012FA (ClientP2HardwareJ2534Probe.ReadRoute). It establishes code-path
execution but never authenticates a CEM, J2534 provider or client session.
Only fixed categories/counts leave this tool. Input is never modified.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

SCHEMA = 'b3a319-sectorv-client-hardware-path-v1'
MAX_ROWS = 100000
MAX_LINE = 2048
PREFIX = re.compile(r'^d{4}-dd-dd dd:dd:dd.d{3} [+-]dd:dd [client] ')
HARDWARE_CAN = re.compile(
    r'^P2 hardware CAN (500k|125k) comm=0x(50|40) '
    r'protocol=0x([0-9A-Fa-f]{1,8}) flags=0x([0-9A-Fa-f]{1,8}) '
    r'connect=(-?d{1,10})$')
RX = re.compile(
    r'^P2 (VIN|hardware-session) RX v3 comm=0x(50|40): '
    r'result=(received|no-reply|partial), observed=(d{1,8}), '
    r'ignored=(d{1,8}), matched=(d{1,8}), elapsedMs=(d{1,8}).$')
FALLBACK = (
    'P2 hardware comm=0x50: diagnostic reply incomplete; '
    'trying the other P2 CAN route after cleanup.')
FAILURE_PREFIX = 'P2 automatic identification failed at Hardware:'


def classify(lines):
    route_connections = Counter()
    rx = Counter()
    invalid_hardware_lines = 0
    readroute_logs = 0
    fallback_seen = 0
    failures = 0
    oversized = 0
    client_lines = 0
    for i, line in enumerate(lines):
        if i >= MAX_ROWS:
            raise ValueError('too_many_rows')
        if len(line) > MAX_LINE:
            oversized += 1
            continue
        text = line.strip().lstrip('﻿')
        match = PREFIX.match(text)
        if not match:
            continue
        client_lines += 1
        payload = text[match.end():]
        if payload.startswith('P2 hardware CAN '):
            m = HARDWARE_CAN.fullmatch(payload)
            if not m:
                invalid_hardware_lines += 1
                continue
            speed, route, protocol, _flags, connect = m.groups()
            # Sanitized categorical metadata only. Never include flags,
            # originating route-string or unbounded connect values.
            code = int(connect)
            if code < -100000 or code > 100000:
                invalid_hardware_lines += 1
                continue
            readroute_logs += 1
            status = 'connect_0' if code == 0 else ('connect_25' if code == 25 else 'connect_other')
            route_connections[(route, speed, f'0x{int(protocol,16):X}', status)] += 1
            continue
        m = RX.fullmatch(payload)
        if m:
            phase, route, result, observed, ignored, matched, elapsed = m.groups()
            nobs, nign, nmatch, ms = map(int, (observed, ignored, matched, elapsed))
            if nobs > 1000000 or nign > 1000000 or nmatch > 1000000 or ms > 1000000:
                continue
            rx[(phase, route, result)] += 1
            if phase == 'hardware-session' and result == 'no-reply' and nobs == nmatch == 0 and ms > 0:
                rx[(phase, route, 'timeout_no_frames')] += 1
            continue
        if payload == FALLBACK:
            fallback_seen += 1
        if payload.startswith(FAILURE_PREFIX):
            failures += 1
    return {
        'schema_version': SCHEMA,
        'source_binding': {
            'client_executable': 'SectorV.exe',
            'method': 'ClientP2HardwareJ2534Probe.ReadRoute',
            'il_token': '0x060012FA',
            'literal': 'P2 hardware CAN ',
            'client_path_observed': bool(readroute_logs),
            'confidence': 'source_bound_literal_observed' if readroute_logs else 'not_attributable',
            'm30855f_path_executed': 'unknown',
        },
        'route_connect_counts': [
            {'route': f'0x{r}', 'baud': 500000 if s == '500k' else 125000,
             'protocol': p, 'result': status, 'count': count}
            for (r, s, p, status), count in sorted(route_connections.items())
        ],
        'client_rx_counts': [
            {'phase': ph, 'route': f'0x{route}', 'result': res, 'count': count}
            for (ph, route, res), count in sorted(rx.items())
        ],
        'fallback_50_to_40_log_count': fallback_seen,
        'hardware_failure_log_count': failures,
        'unmatched_hardware_connect_lines': invalid_hardware_lines,
        'oversized_rows_ignored': oversized,
        'client_lines_checked': client_lines,
        'hardware_session_accepted': False,
        'oem_hardware_identity_verified': False,
        'ecu_identification_verified': False,
        'native_and_client_cross_process_link_verified': False,
        'limitations': [
            'Unique source-literal proves this client method logged the hardware CAN attempt, not its success.',
            'Absence of the unique literal does not prove the alternate M30855F code path ran.',
            'Distinct log rows or process snippets may belong to different sessions.',
            'J2534 connect=0 is a protocol-call result, not an accepted ECU reply.',
            'VIN transport delivery is not decoded vehicle identity acceptance.',
            'No raw frames, VIN, keys, PID, paths or original timestamps are exported.',
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description='Read-only SectorV Hardware client-method provenance audit')
    p.add_argument('--client', required=True)
    args = p.parse_args(argv)
    try:
        path = Path(args.client)
        if not path.is_file() or path.stat().st_size > MAX_ROWS * MAX_LINE:
            raise ValueError('invalid_or_excessive_input')
        with path.open('r', encoding='utf-8-sig', errors='replace') as stream:
            output = classify(stream)
    except (OSError, ValueError):
        p.exit(2, 'ERROR: invalid_or_unreadable_bounded_input
')
    print(json.dumps(output, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
