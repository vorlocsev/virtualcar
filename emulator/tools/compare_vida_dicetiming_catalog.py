#!/usr/bin/env python3
"""Compare aggregate-only redacted DiceTiming SQL Server and SQLite reports.

Matching totals are *not* matching schemas, same-installation provenance,
profile timing, SQL FK coverage, D2 baud, J2534, or ReadVin execution.
"""
from __future__ import annotations

import argparse
import hmac
import json
import re
from pathlib import Path
import sys

INPUT_SCHEMA = 'virtualcar-vida-dicetiming-metadata-v1'
SCHEMA = 'virtualcar-vida-dicetiming-count-compare-v1'
MAX_BYTES = 128 * 1024
HMAC_SCOPE = 'visible_normalized_catalog_identifiers_v1'
HMAC_RE = re.compile(r'[0-9a-f]{64}\Z')
NEGATIVE = (
    'source_rows_read', 'sql_definitions_read', 'original_timing_values_read',
    'timing_profile_link_verified', 'cross_database_snapshot_verified',
    'd2_baud_verified', 'readvin_execution_verified', 'client_vin_accepted',
    'physical_j2534_verified', 'replay_approved',
)


class CompareError(ValueError):
    """Never include private input text or paths in exceptions."""


def _no_duplicates(pairs):
    obj = {}
    for name, value in pairs:
        if name in obj:
            raise CompareError('duplicate JSON key')
        obj[name] = value
    return obj


def _reject_nonfinite(_):
    raise CompareError('nonfinite JSON number')


def _read(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_BYTES:
        raise CompareError('unsafe input report')
    try:
        raw = path.read_bytes()
        if len(raw) > MAX_BYTES:
            raise CompareError('oversized input report')
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_no_duplicates,
                          parse_constant=_reject_nonfinite)
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise CompareError('invalid redacted input report') from None


def _count(value, maximum):
    if type(value) is not int or not 0 <= value <= maximum:
        raise CompareError('invalid bounded metadata count')
    return value


def _validate(report, backend):
    if (type(report) is not dict or report.get('schema_version') != INPUT_SCHEMA or
            report.get('backend') != backend or
            report.get('database') != 'DiceTiming' or
            report.get('status') != 'metadata_only'):
        raise CompareError('unexpected DiceTiming report schema')
    if any(report.get(flag) is not False for flag in NEGATIVE):
        raise CompareError('unverified runtime evidence flag')
    tables = _count(report.get('table_count'), 2000)
    columns = _count(report.get('column_count'), 30000)
    fks = _count(report.get('declared_fk_column_count'), 30000)
    if tables < 1 or columns < tables or (backend == 'sqlite-export' and fks != 0):
        raise CompareError('inconsistent catalog totals')
    fingerprint = report.get('visible_schema_hmac_sha256')
    scope = report.get('visible_schema_hmac_scope')
    if fingerprint is None and scope is None:
        pass
    elif (type(fingerprint) is not str or not HMAC_RE.fullmatch(fingerprint)
          or scope != HMAC_SCOPE):
        raise CompareError('invalid optional DiceTiming schema HMAC')
    return tables, columns, fks, fingerprint


def compare(sqlite_report, sqlserver_report):
    sqlite_tables, sqlite_columns, _, left_hmac = _validate(sqlite_report, 'sqlite-export')
    sql_tables, sql_columns, sql_fk_count, right_hmac = _validate(sqlserver_report, 'sqlserver')
    same_tables = sqlite_tables == sql_tables
    same_columns = sqlite_columns == sql_columns
    if (left_hmac is None) != (right_hmac is None):
        raise CompareError('incomplete optional HMAC source pair')
    if left_hmac is None:
        fingerprint = 'not_tested'
        fingerprint_equal = None
    else:
        fingerprint_equal = hmac.compare_digest(left_hmac, right_hmac)
        if fingerprint_equal and not (same_tables and same_columns):
            raise CompareError('contradictory DiceTiming digest and count claims')
        fingerprint = 'matched' if fingerprint_equal else 'mismatched'
    return {
        'schema_version': SCHEMA,
        'status': 'aggregate_count_comparison_only',
        'database': 'DiceTiming',
        'table_counts_equal': same_tables,
        'column_counts_equal': same_columns,
        'aggregate_counts_equal': same_tables and same_columns,
        'visible_schema_hmac_comparison': fingerprint,
        'visible_schema_hmac_equal': fingerprint_equal,
        'sqlite_table_count': sqlite_tables,
        'sqlserver_table_count': sql_tables,
        'sqlite_column_count': sqlite_columns,
        'sqlserver_column_count': sql_columns,
        'sqlserver_declared_fk_column_count': sql_fk_count,
        'sqlite_fk_metadata_available': False,
        'schema_equivalence_verified': False,
        'same_installation_provenance_verified': False,
        'referential_rows_verified': False,
        'timing_profile_link_verified': False,
        'original_timing_values_read': False,
        'd2_baud_verified': False,
        'readvin_execution_verified': False,
        'client_vin_accepted': False,
        'replay_approved': False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sqlite-report', required=True, type=Path)
    parser.add_argument('--sqlserver-report', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        inputs = (args.sqlite_report, args.sqlserver_report)
        checkout = Path(__file__).resolve().parents[2]
        output = args.output.resolve()
        paths = [p.resolve() for p in inputs]
        if (not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or checkout == output or checkout in output.parents
                or output in paths or paths[0] == paths[1]):
            raise CompareError('unsafe comparison destination')
        result = compare(_read(inputs[0]), _read(inputs[1]))
        with args.output.open('x', encoding='utf-8') as stream:
            json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write('\n')
        print('DiceTiming aggregate counts compared; no timing or profile proof.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
