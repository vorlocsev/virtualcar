#!/usr/bin/env python3
"""Offline, source-linked audit of SectorV Hardware client log events.

ReadRoute is identified by its literal P2 hardware CAN. This does NOT
prove CEM authorization, same-session native evidence or decoded identity.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

SCHEMA = 'b3a319-sectorv-client-hardware-path-v1'
MAX_ROWS = 100000
MAX_LINE = 2048
PREFIX = re.compile('^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3} [+-][0-9]{2}:[0-9]{2} ' + re.escape('[client] '))
CONNECT = re.compile(
    '^P2 hardware CAN (500k|125k) comm=0x(50|40) '
    'protocol=0x([0-9A-Fa-f]{1,8}) flags=0x([0-9A-Fa-f]{1,8}) '
    'connect=(-?[0-9]{1,10})$')
RX = re.compile(
    '^P2 (VIN|hardware-session) RX v3 comm=0x(50|40): '
    'result=(received|no-reply|partial), observed=([0-9]{1,8}), '
    'ignored=([0-9]{1,8}), matched=([0-9]{1,8}), elapsedMs=([0-9]{1,8})[.]$')
FALLBACK = ('P2 hardware comm=0x50: diagnostic reply incomplete; '
            'trying the other P2 CAN route after cleanup.')
FAILURE = 'P2 automatic identification failed at Hardware:'


def classify(lines):
    conns, responses = Counter(), Counter()
    marker = invalid = fallback = failed = oversized = checked = 0
    for index, line in enumerate(lines):
        if index >= MAX_ROWS:
            raise ValueError('too_many_rows')
        if len(line) > MAX_LINE:
            oversized += 1
            continue
        line = line.strip().lstrip(chr(65279))
        prefix = PREFIX.match(line)
        if prefix is None:
            continue
        checked += 1
        event = line[prefix.end():]
        if event.startswith('P2 hardware CAN '):
            m = CONNECT.fullmatch(event)
            if m is None:
                invalid += 1
                continue
            speed, route, protocol, _flags, code = m.groups()
            n = int(code)
            if not -100000 <= n <= 100000:
                invalid += 1
                continue
            marker += 1
            result = 'connect_0' if n == 0 else ('connect_25' if n == 25 else 'connect_other')
            conns[(route, speed, '0x%X' % int(protocol, 16), result)] += 1
            continue
        m = RX.fullmatch(event)
        if m is not None:
            phase, route, outcome, observed, ignored, matched, elapsed = m.groups()
            nobs, nign, nm, ms = map(int, (observed, ignored, matched, elapsed))
            if max(nobs, nign, nm, ms) > 1000000:
                continue
            responses[(phase, route, outcome)] += 1
            if phase == 'hardware-session' and outcome == 'no-reply' and nobs == nm == 0 and ms > 0:
                responses[(phase, route, 'timeout_no_frames')] += 1
            continue
        if event == FALLBACK:
            fallback += 1
        if event.startswith(FAILURE):
            failed += 1
    return {
        'schema_version': SCHEMA,
        'source_binding': {
            'client_executable': 'SectorV.exe',
            'method': 'ClientP2HardwareJ2534Probe.ReadRoute',
            'il_token': '0x060012FA',
            'client_path_observed': bool(marker),
            'confidence': 'source_bound_literal_observed' if marker else 'not_attributable',
            'm30855f_path_executed': 'unknown',
        },
        'route_connect_counts': [
            {'route': '0x' + route, 'baud': 500000 if speed == '500k' else 125000,
             'protocol': protocol, 'result': result, 'count': count}
            for (route, speed, protocol, result), count in sorted(conns.items())
        ],
        'client_rx_counts': [
            {'phase': phase, 'route': '0x' + route, 'result': outcome, 'count': count}
            for (phase, route, outcome), count in sorted(responses.items())
        ],
        'fallback_50_to_40_log_count': fallback,
        'hardware_failure_log_count': failed,
        'unmatched_hardware_connect_lines': invalid,
        'oversized_rows_ignored': oversized,
        'client_lines_checked': checked,
        'hardware_session_accepted': False,
        'oem_hardware_identity_verified': False,
        'ecu_identification_verified': False,
        'native_and_client_cross_process_link_verified': False,
        'limitations': [
            'The distinctive ReadRoute log proves code-path use, not a valid ECU reply.',
            'No unique M30855F evidence: alternate path remains unknown, not false.',
            'One client file is not an authenticated transaction spanning other logs.',
            'Connect result zero is not proof of CEM authorization.',
            'VIN transport receipt is not OEM vehicle-identity acceptance.',
            'No VIN, CAN payload, PID, key, original timestamp or private path is exported.',
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description='Source-linked, read-only Hardware path audit')
    parser.add_argument('--client', required=True)
    args = parser.parse_args(argv)
    try:
        path = Path(args.client)
        if not path.is_file() or path.stat().st_size > MAX_ROWS * MAX_LINE:
            raise ValueError('invalid_input')
        with path.open('r', encoding='utf-8-sig', errors='replace') as reader:
            report = classify(reader)
    except (OSError, ValueError):
        parser.exit(2, 'ERROR: invalid_or_unreadable_bounded_input' + chr(10))
    print(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
