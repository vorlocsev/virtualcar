#!/usr/bin/env python3
"""B3A142: bounded, read-only CEM D2 request/outcome correlation in a native log.

A textual PID/host marker is not proof of which process loaded J2534.
No raw source line, PID, VIN, CAN frame, response ID or source path is printed.
Only a capped tail of the source log is read. No DLL, VIDA or INI access.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

SCHEMA = 'virtualcar-b3a142-cem-d2-window-v1'
DEFAULT_TAIL_BYTES = 8 * 1024 * 1024
MAX_TAIL_BYTES = 16 * 1024 * 1024
MAX_REQUEST_SPAN = 1024
_LOG_LINE = re.compile(r'^\[PID=([0-9A-Fa-f]{8}) ([^\]\r\n]{1,100})\] (.*)$')
_HEX_BYTE = re.compile(r'(?<![0-9A-Fa-f])[0-9A-Fa-f]{2}(?![0-9A-Fa-f])')
_REQUEST_MARKER = 'P2 D2 request target/opcode/baud/flags (BE)'


def _decode_request(body):
    if not body.startswith(_REQUEST_MARKER):
        return None
    values = _HEX_BYTE.findall(body[len(_REQUEST_MARKER):])
    if len(values) != 16:
        return 'malformed'
    b = bytes(int(v, 16) for v in values)
    return (int.from_bytes(b[:4], 'big'), int.from_bytes(b[4:8], 'big'),
            int.from_bytes(b[8:12], 'big'))


def _route(target, opcode, baud):
    if target == 0x40 and opcode in (0xF0, 0xFB):
        suffix = 'B9F0' if opcode == 0xF0 else 'B9FB'
        return 'CEM_40/' + suffix + ('/125k' if baud == 125000 else '/other_baud')
    if target == 0x50 and opcode in (0xF0, 0xFB):
        suffix = 'B9F0' if opcode == 0xF0 else 'B9FB'
        return 'CEM_50/' + suffix + ('/500k' if baud == 500000 else '/other_baud')
    return 'OTHER_D2'


def _outcome(record):
    c = record['markers']
    if c['bus_reject']:
        return 'strict_bus_rejected'
    if c['no_fixture']:
        return 'missing_validated_fixture'
    if c['no_target']:
        return 'no_matching_target_fixture'
    if c['staged'] and c['d2_delivered']:
        return 'native_d2_delivered_not_vida_accepted'
    if c['staged'] and c['clear_rx']:
        return 'staged_then_clear_rx_seen_not_causal_proof'
    if c['staged']:
        return 'staged_not_delivered_in_bounded_span'
    return 'no_categorized_outcome'


def audit_lines(lines, *, tail_truncated=False):
    """Classify same-textual-prefix events until next D2 request, not an ECU session.

    This is observational: overlapping J2534 channels under one host prefix,
    truncated logs and unlogged status codes prevent exact causality.
    """
    active = {}
    results = []
    totals = Counter()
    n_malformed = 0
    parsed = 0

    def end(key, reason):
        r = active.pop(key, None)
        if r is not None:
            r['boundary'] = reason
            r['outcome'] = _outcome(r)
            results.append(r)

    for line in lines:
        m = _LOG_LINE.match(line)
        if not m:
            continue
        key = (m.group(1).upper(), m.group(2).upper())  # private, never exported
        body = m.group(3)
        event = _decode_request(body)
        if event == 'malformed':
            n_malformed += 1
            end(key, 'malformed_next_request')
            continue
        if event is not None:
            parsed += 1
            end(key, 'next_d2_request_same_logger_prefix')
            target, opcode, baud = event
            route = _route(target, opcode, baud)
            totals[route] += 1
            if route == 'OTHER_D2':
                continue
            active[key] = {
                'route': route,
                'span_lines': 0,
                'markers': Counter(),
                'boundary': '',
            }
            continue
        r = active.get(key)
        if r is None:
            continue
        r['span_lines'] += 1
        if r['span_lines'] > MAX_REQUEST_SPAN:
            end(key, 'max_span_exhausted')
            continue
        markers = r['markers']
        if body.startswith('P2 D2 strict route rejected'):
            markers['bus_reject'] += 1
        elif body.startswith('P2 D2 read command: no validated response fixture'):
            markers['no_fixture'] += 1
        elif body.startswith('P2 D2 command: no recorded ECU fixture for target'):
            markers['no_target'] += 1
        elif body.startswith('P2 D2 read-only recorded frames staged'):
            markers['staged'] += 1
        elif body.startswith('P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)'):
            markers['d2_delivered'] += 1
        elif body.startswith('PassThruReadMsgs -> delivered'):
            markers['generic_rx_delivered'] += 1
        elif body.startswith('RX discarded by installed J2534 filter'):
            markers['filter_drop'] += 1
        elif body.startswith('J2534 CLEAR_RX_BUFFER:'):
            markers['clear_rx'] += 1
        elif body.startswith('P2 D2 stale queued frames dropped'):
            markers['stale_drop'] += 1
        elif body.startswith('PassThruReadMsgs timeout:'):
            markers['timeout_sample'] += 1
    for key in list(active):
        end(key, 'end_of_log_tail')

    by_route = {}
    for route in ('CEM_40/B9F0/125k', 'CEM_40/B9FB/125k',
                  'CEM_50/B9F0/500k', 'CEM_50/B9FB/500k',
                  'CEM_40/B9F0/other_baud', 'CEM_40/B9FB/other_baud',
                  'CEM_50/B9F0/other_baud', 'CEM_50/B9FB/other_baud'):
        found = [r for r in results if r['route'] == route]
        outcome_counts = Counter(r['outcome'] for r in found)
        marker_totals = Counter()
        for r in found:
            marker_totals.update(r['markers'])
        by_route[route] = {
            'request_count': totals[route],
            'categorized_outcomes': dict(sorted(outcome_counts.items())),
            'bounded_same_logger_prefix_markers': dict(sorted(marker_totals.items())),
            'end_of_tail_or_span_censored_requests': sum(
                r['boundary'] in ('end_of_log_tail', 'max_span_exhausted')
                for r in found),
        }
    return {
        'schema': SCHEMA,
        'scope': 'bounded_native_log_tail_same_textual_logger_prefix_not_j2534_session_attestation',
        'source_tail_truncated': bool(tail_truncated),
        'd2_request_markers_parsed': parsed,
        'malformed_request_metadata': n_malformed,
        'other_target_d2_request_count': totals['OTHER_D2'],
        'cem_routes': by_route,
        'client_return_status_verified': False,
        'actual_vida_process_binding_verified': False,
        'actual_vida_network_or_ecu_identification': 'NOT_PROVEN',
        'has_private_paths_vin_pid_can_frames_or_response_ids': False,
        'cautions': [
            'Generic RX delivery is not a D2 CEM reply.',
            'Same PID/host text and the next-request boundary do not prove a J2534 channel or VIDA session.',
            'A staged D2 reply is not proof of a delivered or VIDA-accepted reply.',
            'CLEAR_RX_BUFFER markers do not independently establish causality.',
        ],
    }


def tail_lines(path, max_bytes):
    """Read a capped tail; discard partial first line when seeking."""
    with path.open('rb') as f:
        f.seek(0, 2)
        size = f.tell()
        truncated = size > max_bytes
        if truncated:
            f.seek(size - max_bytes)
            f.readline()  # discard possibly incomplete first line
        else:
            f.seek(0)
        data = f.read(max_bytes)
    return data.decode('utf-8-sig', errors='replace').splitlines(), truncated


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-log', type=Path, required=True)
    p.add_argument('--tail-bytes', type=int, default=DEFAULT_TAIL_BYTES)
    args = p.parse_args(argv)
    try:
        if not 1024 <= args.tail_bytes <= MAX_TAIL_BYTES:
            raise ValueError('tail cap')
        if args.native_log.is_symlink() or not args.native_log.is_file():
            raise ValueError('source not regular file')
        lines, truncated = tail_lines(args.native_log, args.tail_bytes)
        output = audit_lines(lines, tail_truncated=truncated)
    except (OSError, ValueError, UnicodeError):
        print('B3A142: NATIVE_LOG_UNAVAILABLE_OR_INVALID', file=sys.stderr)
        return 2
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
