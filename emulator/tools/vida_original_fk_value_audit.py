#!/usr/bin/env python3
"""Owner-local original-value FK comparison of existing VIDA table captures.

No anonymization or SQL execution. Uses exact *driver-returned* values and the
original named FK graph; no SQL collation, provenance or atomicity assertion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

from vida_original_schema_reader import _name

SCHEMA = 'virtualcar-vida-original-fk-value-audit-v1'
MAX_REPORT_BYTES = 50 * 1024 * 1024
MAX_REPORTS = 12
MAX_ROWS_PER_TABLE = 5000
MAX_RESULT_BYTES = 50 * 1024 * 1024
FORMATS = frozenset(('binary-base64', 'decimal-text', 'ieee754-python-float-hex',
                     'datetime-iso8601', 'date-iso8601', 'time-iso8601', 'uuid-raw-hex'))


class OriginalFKError(ValueError):
    """Never include a source table value or name in error messages."""


def _unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise OriginalFKError('duplicate JSON key')
        obj[key] = value
    return obj


def _reject_nonfinite(_):
    raise OriginalFKError('nonfinite JSON value')


def _read(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise OriginalFKError('unsafe original source report')
    data = path.read_bytes()
    if len(data) > MAX_REPORT_BYTES:
        raise OriginalFKError('oversized original source report')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_unique,
                           parse_constant=_reject_nonfinite)
    except (UnicodeError, ValueError, RecursionError):
        raise OriginalFKError('invalid original JSON report') from None
    return value, hashlib.sha256(data).hexdigest()


def _shape_schema(doc):
    if (type(doc) is not dict or
            doc.get('schema_version') != 'virtualcar-vida-original-schema-v1' or
            doc.get('original_identifiers_preserved') is not True or
            any(doc.get(flag) is not False for flag in
                ('original_user_rows_read', 'actual_row_joins_verified',
                 'complete_catalog_visibility_verified',
                 'transactional_snapshot_verified', 'runtime_readvin_verified',
                 'physical_j2534_verified'))):
        raise OriginalFKError('unsupported original schema claims')
    _name(doc.get('source_database'))
    tables = doc.get('tables')
    fks = doc.get('foreign_keys')
    if (type(tables) is not list or not 1 <= len(tables) <= 2000 or
            type(fks) is not list or len(fks) > 30000):
        raise OriginalFKError('invalid original schema inventory')
    by_name = {}
    for table in tables:
        if type(table) is not dict:
            raise OriginalFKError('invalid original table inventory')
        key = (_name(table.get('schema')), _name(table.get('name')))
        cols = table.get('columns')
        if (key in by_name or type(cols) is not list or not cols or
                len(cols) > 1024 or any(type(c) is not dict for c in cols)):
            raise OriginalFKError('invalid original table columns')
        names = [_name(c.get('name')) for c in cols]
        if len(set(names)) != len(names):
            raise OriginalFKError('duplicate original column name')
        by_name[key] = {c['name']: c for c in cols}
    for fk in fks:
        if type(fk) is not dict:
            raise OriginalFKError('invalid declared FK')
        source = (_name(fk.get('source_schema')), _name(fk.get('source_table')))
        target = (_name(fk.get('referenced_schema')), _name(fk.get('referenced_table')))
        members = fk.get('columns')
        if (source not in by_name or target not in by_name or
                type(members) is not list or not 1 <= len(members) <= 32):
            raise OriginalFKError('unresolved original FK')
        for index, member in enumerate(members, 1):
            if (type(member) is not dict or type(member.get('ordinal')) is not int or
                    member['ordinal'] != index or
                    member.get('source') not in by_name[source] or
                    member.get('referenced') not in by_name[target]):
                raise OriginalFKError('inconsistent original FK members')
    return by_name


def _cell_key(value):
    # Preserve the source value in results; build a strict, typed in-memory
    # lookup key. This is not a SQL collation-equivalence check.
    if value is None:
        return None
    if type(value) not in (str, bool, int, dict):
        raise OriginalFKError('unsupported original SQL cell representation')
    if type(value) is dict and (set(value) != {'format', 'value'} or
                                value.get('format') not in FORMATS or
                                type(value.get('value')) is not str):
        raise OriginalFKError('invalid typed original SQL cell')
    return json.dumps([type(value).__name__, value],
                      sort_keys=True, separators=(',', ':'), ensure_ascii=False)


def _table_capture(report, schema, by_name):
    if (type(report) is not dict or
            report.get('schema_version') != 'virtualcar-vida-original-table-capture-v1' or
            report.get('source_database') != schema['source_database'] or
            report.get('original_names_and_driver_values_not_anonymized') is not True or
            report.get('full_table_extracted_within_row_limit') is not True or
            any(report.get(flag) is not False for flag in
                ('raw_sql_server_type_roundtrip_verified',
                 'transactional_snapshot_verified',
                 'same_installation_provenance_verified',
                 'vehicle_runtime_verified'))):
        raise OriginalFKError('unsupported original row report claims')
    key = (_name(report.get('source_schema')), _name(report.get('source_table')))
    if key not in by_name:
        raise OriginalFKError('source table absent from original schema')
    cols = report.get('columns')
    rows = report.get('rows')
    count = report.get('row_count')
    if (type(cols) is not list or type(rows) is not list or
            type(count) is not int or count != len(rows) or
            count > MAX_ROWS_PER_TABLE or not cols or len(cols) != len(by_name[key])):
        raise OriginalFKError('incomplete original table capture')
    column_names = []
    for col in cols:
        if type(col) is not dict or set(col) != {'column_id', 'name', 'sql_type'}:
            raise OriginalFKError('invalid original column report')
        name = _name(col['name'])
        original = by_name[key].get(name)
        if (original is None or type(col['column_id']) is not int or
                col['column_id'] != original.get('column_id') or
                col['sql_type'] != original.get('sql_type')):
            raise OriginalFKError('original table shape disagrees with schema')
        column_names.append(name)
    if len(set(column_names)) != len(column_names):
        raise OriginalFKError('duplicate row-report columns')
    # Prevent a nominally complete report from hiding unsupported cells.
    for row in rows:
        if type(row) is not list or len(row) != len(cols):
            raise OriginalFKError('original row width mismatch')
        for cell in row:
            _cell_key(cell)
    return key, {name: index for index, name in enumerate(column_names)}, rows


def audit(schema, captures, source_digests):
    by_name = _shape_schema(schema)
    if (type(captures) is not list or not 2 <= len(captures) <= MAX_REPORTS or
            type(source_digests) is not dict or set(source_digests) != {'schema', 'tables'} or
            type(source_digests['schema']) is not str or
            type(source_digests['tables']) is not list or
            len(source_digests['tables']) != len(captures)):
        raise OriginalFKError('invalid source report binding')
    sources = {}
    for report, digest in zip(captures, source_digests['tables']):
        if type(digest) is not str or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise OriginalFKError('invalid original report SHA256')
        key, indices, rows = _table_capture(report, schema, by_name)
        if key in sources:
            raise OriginalFKError('duplicate original table report')
        sources[key] = (indices, rows)
    fks = []
    for fk in schema['foreign_keys']:
        src = (fk['source_schema'], fk['source_table'])
        dst = (fk['referenced_schema'], fk['referenced_table'])
        if src not in sources or dst not in sources:
            continue
        src_names = [m['source'] for m in fk['columns']]
        dst_names = [m['referenced'] for m in fk['columns']]
        src_indices, src_rows = sources[src]
        dst_indices, dst_rows = sources[dst]
        target = {}
        skipped_target_null = 0
        for row_id, row in enumerate(dst_rows):
            key = tuple(_cell_key(row[dst_indices[n]]) for n in dst_names)
            if None in key:
                skipped_target_null += 1
                continue
            if key in target:
                raise OriginalFKError('duplicate referenced key under exact driver representation')
            target[key] = row_id
        matches = []
        no_match = []
        skipped_null = 0
        for row_id, row in enumerate(src_rows):
            values = [row[src_indices[n]] for n in src_names]
            key = tuple(_cell_key(v) for v in values)
            if None in key:
                skipped_null += 1
                continue
            if key in target:
                matches.append({'source_row_index': row_id,
                                'referenced_row_index': target[key],
                                'original_key_values': values})
            else:
                no_match.append({'source_row_index': row_id,
                                 'original_key_values': values})
        fks.append({'original_fk_name': _name(fk.get('name')),
                    'source_schema': src[0], 'source_table': src[1],
                    'referenced_schema': dst[0], 'referenced_table': dst[1],
                    'column_mapping': fk['columns'],
                    'source_rows_examined': len(src_rows),
                    'referenced_rows_examined': len(dst_rows),
                    'source_null_key_rows': skipped_null,
                    'referenced_null_key_rows': skipped_target_null,
                    'literal_driver_value_matches': matches,
                    'literal_driver_value_unmatched': no_match,
                    'sql_collation_equivalence_verified': False,
                    'actual_database_fk_enforcement_verified': False})
    return {'schema_version': SCHEMA,
            'source_database': schema['source_database'],
            'source_schema_sha256': source_digests['schema'],
            'source_table_report_sha256': source_digests['tables'],
            'original_identifiers_and_key_values_preserved': True,
            'evaluated_fk_count': len(fks),
            'fk_literal_value_comparisons': fks,
            'source_byte_integrity_bound': True,
            'same_installation_provenance_verified': False,
            'transactional_snapshot_verified': False,
            'sql_collation_equivalence_verified': False,
            'database_row_join_verified': False,
            'selected_ecu_profile_verified': False,
            'd2_baud_verified': False,
            'getscript_readvin_runtime_verified': False,
            'client_vin_accepted': False,
            'physical_j2534_verified': False}


def main(argv=None):
    ap = argparse.ArgumentParser(description='Audit original, non-redacted FK values from local captures')
    ap.add_argument('--schema-report', type=Path, required=True)
    ap.add_argument('--table-report', type=Path, action='append', required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        root = Path(__file__).resolve().parents[2]
        paths = [args.schema_report, *args.table_report]
        resolved = [path.resolve() for path in paths]
        target = args.output.resolve()
        if (not 2 <= len(args.table_report) <= MAX_REPORTS or
                any(path == root or root in path.parents for path in resolved) or
                len(set(resolved)) != len(resolved) or target in resolved or
                target == root or root in target.parents or
                not args.output.parent.is_dir() or args.output.parent.is_symlink()):
            raise OriginalFKError('unsafe owner-local file selection')
        doc, digest = _read(args.schema_report)
        loaded = [_read(path) for path in args.table_report]
        result = audit(doc, [obj for obj, _ in loaded],
                       {'schema': digest, 'tables': [sha for _, sha in loaded]})
        encoded = (json.dumps(result, sort_keys=True, indent=2,
                              ensure_ascii=False, allow_nan=False) + '\n').encode('utf-8')
        if len(encoded) > MAX_RESULT_BYTES:
            raise OriginalFKError('original FK audit output too large')
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(encoded)
        print('Owner-local original FK value comparison complete; no SQL join or runtime attested.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
