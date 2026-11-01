#!/usr/bin/env python3
"""Check only synthetic evidence produced by verify_native_routes.ps1.

This is a native DLL regression gate, not an analyzer of arbitrary vehicle logs.
Neither passing nor delivered RX establishes diagnostic-client acceptance.
"""
import argparse
import json
from pathlib import Path
import sys

from audit_backend_evidence import audit


def verify(lines):
    report = audit(lines)
    if report['summary'] != {
            'requests': 13, 'sessions': 1, 'invalid_lines': 0,
            'statuses': {'unverified': 8, 'no_fixture': 2, 'unsupported': 3}}:
        raise ValueError('unexpected_synthetic_summary')
    # protocol, baud, route, status, reason, service, target, channel
    silent = ('unverified', 'explicit_no_response', None, None)
    expected = [('CAN', 500000, 'ECM', *silent, 1)] * 3
    expected += [('CAN', 125000, 'ECM', *silent, 2)] * 3
    expected += [('ISO15765', 500000, 'ECM', *silent, 3)]
    expected += [
        ('CAN', 125000, 'CEM', 'no_fixture', 'explicit_missing_profile', 'B9FB', '0x40', 2),
        ('CAN', 500000, 'CEM', 'no_fixture', 'explicit_missing_profile', 'B9FB', '0x50', 1),
        ('CAN', 250000, 'CEM', 'unsupported', 'unsupported_bus', 'B9FB', '0x50', 4),
        ('CAN', 500000, 'UNHANDLED', 'unsupported', 'unhandled_request', '22F114', None, 1),
        ('ISO15765', 500000, 'UNHANDLED', 'unsupported', 'unhandled_request', '22F114', None, 3),
        ('ISO15765', 500000, 'ECU_OTHER', *silent, 3),
    ]
    fields = ('protocol', 'baud_bps', 'route', 'status', 'reason', 'service', 'target', 'channel')
    for transaction, wanted in zip(report['transactions'], expected):
        if tuple(transaction[field] for field in fields) != wanted:
            raise ValueError('unexpected_synthetic_transaction')
        if (not transaction['terminal_seen'] or transaction['evidence_conflicts']
                or transaction['observed_routes'] != [transaction['route']]
                or transaction['elapsed_ms'] is None
                or any(transaction[field] for field in (
                    'rx_queued', 'rx_dequeued', 'rx_dropped', 'filter_dropped'))):
            raise ValueError('incomplete_or_conflicting_native_evidence')
    report['native_route_regression_verified'] = True
    report['evidence_scope'] = 'synthetic_native_dll_only'
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Isolated synthetic backend JSONL')
    parser.add_argument('--output', required=True, type=Path, help='New redacted audit path')
    args = parser.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise ValueError('same_file')
        with args.source.open(encoding='utf-8') as source:
            report = verify(source)
        with args.output.open('x', encoding='utf-8') as output:
            json.dump(report, output, indent=2)
            output.write('\n')
    except (OSError, ValueError):
        print('Native route evidence verification failed', file=sys.stderr)
        return 2
    print('PASS: synthetic native DLL route evidence; ECU identity remains unverified')
    return 0


if __name__ == '__main__':
    sys.exit(main())
