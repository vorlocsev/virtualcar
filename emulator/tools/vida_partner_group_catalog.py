#!/usr/bin/env python3
"""Inspect owner-local, original VIDA BaseData metadata and optional table capture.

Reads only files already produced by VIDA Analyzer's original-schema/table
readers. Does NOT connect to SQL Server, infer VIN rules, emit a synthetic
identity, or claim original VIDA acceptance. Preserves original identifier
values in the PRIVATE report; never prints original content on errors.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

SCHEMA_FORMAT = 'virtualcar-vida-original-schema-v1'
TABLE_FORMAT = 'virtualcar-vida-original-table-capture-v1'
CONTEXT_FORMAT = 'virtualcar-vida-partner-group-selection-v1'
OUTPUT_FORMAT = 'virtualcar-vida-partner-group-catalog-v1'
DATABASE = 'BaseData'
TABLE = 'VINDecodeModel'
INTERESTING = ('VinStartPos', 'VinEndPos', 'VinCompare', 'fkVehicleModel',
               'fkModelYear', 'fkBodyStyle', 'fkPartnerGroup', 'ChassisNoFrom',
               'ChassisNoTo', 'YearCodePos', 'YearCode', 'ObjVersion')
MAX_BYTES_SCHEMA = 20 * 1024 * 1024
MAX_BYTES_ROWS = 50 * 1024 * 1024
MAX_ROWS = 5000


class CatalogEvidenceError(ValueError):
    pass


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogEvidenceError('duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(_):
    raise CatalogEvidenceError('nonfinite JSON')


def read_json(path: Path, max_bytes: int):
    if (path.is_symlink() or not path.is_file() or
            path.stat().st_size > max_bytes):
        raise CatalogEvidenceError('unsafe input file')
    raw = path.read_bytes()
    if len(raw) > max_bytes:
        raise CatalogEvidenceError('large input')
    try:
        return json.loads(raw.decode('utf-8'), object_pairs_hook=_unique,
                          parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError):
        raise CatalogEvidenceError('invalid JSON') from None


def _is_scalar(value):
    return type(value) in (type(None), int, str)


def _val_key(value):
    # Preserve exact JSON type (e.g. string "1002" != number 1002).
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _assert_schema(schema):
    if (type(schema) is not dict or schema.get('schema_version') != SCHEMA_FORMAT
            or schema.get('source_database') != DATABASE
            or schema.get('original_identifiers_preserved') is not True
            or schema.get('original_user_rows_read') is not False
            or schema.get('runtime_readvin_verified') is not False
            or type(schema.get('tables')) is not list
            or len(schema['tables']) > 2000
            or type(schema.get('foreign_keys')) is not list):
        raise CatalogEvidenceError('invalid original BaseData schema')
    matched = []
    for item in schema['tables']:
        if type(item) is not dict:
            raise CatalogEvidenceError('invalid table metadata')
        if item.get('schema') == 'dbo' and item.get('name') == TABLE:
            matched.append(item)
    if len(matched) > 1:
        raise CatalogEvidenceError('duplicate VINDecodeModel')
    tab = matched[0] if matched else None
    if tab is not None:
        cols = tab.get('columns')
        if type(cols) is not list or not cols:
            raise CatalogEvidenceError('invalid VINDecodeModel columns')
        names = []
        for c in cols:
            if type(c) is not dict or type(c.get('name')) is not str:
                raise CatalogEvidenceError('invalid VINDecodeModel column')
            names.append(c['name'])
        if len(names) != len(set(names)):
            raise CatalogEvidenceError('duplicate VINDecodeModel column')
    return tab


def _assert_capture(rows, schema_columns):
    if (type(rows) is not dict or rows.get('schema_version') != TABLE_FORMAT
            or rows.get('source_database') != DATABASE
            or rows.get('source_schema') != 'dbo'
            or rows.get('source_table') != TABLE
            or rows.get('original_names_and_driver_values_not_anonymized') is not True
            or rows.get('vehicle_runtime_verified') is not False
            or rows.get('same_installation_provenance_verified') is not False
            or type(rows.get('columns')) is not list
            or type(rows.get('rows')) is not list
            or len(rows['rows']) > MAX_ROWS
            or type(rows.get('row_count')) is not int
            or rows['row_count'] != len(rows['rows'])):
        raise CatalogEvidenceError('invalid VINDecodeModel capture')
    names = []
    for c in rows['columns']:
        if type(c) is not dict or type(c.get('name')) is not str:
            raise CatalogEvidenceError('invalid column capture')
        names.append(c['name'])
    if names != schema_columns:
        raise CatalogEvidenceError('schema/capture columns disagree')
    for row in rows['rows']:
        if type(row) is not list or len(row) != len(names):
            raise CatalogEvidenceError('invalid original row width')
    complete = rows.get('full_table_extracted_within_row_limit')
    subset = rows.get('selection_scope') == 'filtered_subset_only'
    if type(complete) is not bool or (complete and subset):
        raise CatalogEvidenceError('contradictory capture scope')
    if not complete and not (subset and rows.get('filtered_subset_complete_within_row_limit') is True
                            and rows.get('full_table_row_count_verified') is False):
        raise CatalogEvidenceError('incomplete capture without bounded scope')
    return names, 'full_table_within_capture_limit' if complete else 'filtered_subset_only'


def _assert_context(context):
    if context is None:
        return None
    if (type(context) is not dict or set(context) != {'schema_version', 'fkPartnerGroup_original'}
            or context['schema_version'] != CONTEXT_FORMAT
            or not _is_scalar(context['fkPartnerGroup_original'])):
        raise CatalogEvidenceError('invalid private group context')
    return context['fkPartnerGroup_original']


def inspect(schema, capture=None, context=None):
    table = _assert_schema(schema)
    selected = _assert_context(context)
    if table is None and capture is not None:
        raise CatalogEvidenceError('capture table absent from catalog')
    if table is None and context is not None:
        raise CatalogEvidenceError('group context without catalog table')
    columns = [col['name'] for col in table['columns']] if table else []
    col_presence = [{'column': name, 'present': name in columns} for name in INTERESTING]
    fks = []
    for fk in schema['foreign_keys']:
        if type(fk) is not dict:
            raise CatalogEvidenceError('invalid FK catalog')
        if (fk.get('source_schema') == 'dbo' and fk.get('source_table') == TABLE) or \
           (fk.get('referenced_schema') == 'dbo' and fk.get('referenced_table') == TABLE):
            fks.append(fk)
    scope = 'schema_only'
    groups = []
    total_rows = None
    group_value = None
    group_records = None
    group_field_present = 'fkPartnerGroup' in columns
    if capture is not None:
        names, scope = _assert_capture(capture, columns)
        total_rows = capture['row_count']
        if group_field_present:
            pos = names.index('fkPartnerGroup')
            count, values = Counter(), {}
            for r in capture['rows']:
                value = r[pos]
                if not _is_scalar(value):
                    raise CatalogEvidenceError('unsupported original partner group type')
                key = _val_key(value)
                count[key] += 1
                values[key] = value
            groups = [{'fkPartnerGroup_original': values[key], 'observed_rows': count[key]}
                      for key in sorted(count)]
            if context is not None:
                group_value = selected
                group_records = count.get(_val_key(selected), 0)
        elif context is not None:
            raise CatalogEvidenceError('requested group column not present')
    elif context is not None:
        raise CatalogEvidenceError('group context without row capture')

    return {
        'schema_version': OUTPUT_FORMAT,
        'source_database': DATABASE,
        'source_table': 'dbo.' + TABLE,
        'table_found_in_visible_catalog': table is not None,
        'source_scope': scope,
        'capture_row_count': total_rows,
        'original_column_names': columns,
        'original_column_presence': col_presence,
        'original_declared_fk_links': fks,
        'fkPartnerGroup_observed_row_counts': groups,
        'selected_partner_group_original': group_value,
        'selected_group_rows_in_this_capture': group_records,
        'original_data_modified_or_anonymized': False,
        'runtime_group_selection_verified': False,
        'vin_decode_semantics_verified': False,
        'vin_match_verified': False,
        'responsehandler_f114_verified': False,
        'vida_gui_vin_accepted': False,
        'ecu_identification_verified': False,
        'limitations': [
            'A visible table and column names do not prove that VIDA uses them in this installed runtime',
            'A matching Partner Group row is not a VIN decode and not proof of XC90 identity',
            'A zero count for a filtered subset is not proof of absence in the database',
            'Original schema and row export are not independently proven to be one SQL snapshot',
            'Original VINDecodeModel substring/year/chassis/priority and application decoder rules remain unverified',
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--schema', type=Path, required=True)
    ap.add_argument('--rows', type=Path)
    ap.add_argument('--group-context', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        inputs = [p for p in (args.schema, args.rows, args.group_context) if p is not None]
        if args.output.is_symlink() or any(p.resolve() == args.output.resolve() for p in inputs):
            raise CatalogEvidenceError('unsafe output')
        schema = read_json(args.schema, MAX_BYTES_SCHEMA)
        rows = read_json(args.rows, MAX_BYTES_ROWS) if args.rows else None
        context = read_json(args.group_context, 8192) if args.group_context else None
        report = inspect(schema, rows, context)
        with args.output.open('x', encoding='utf-8') as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
            fh.write('\n')
    except (CatalogEvidenceError, OSError, ValueError, UnicodeError, RecursionError):
        print('VIDA Partner Group offline audit failed', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
