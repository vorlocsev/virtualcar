#!/usr/bin/env python3
"""Owner-local, unmasked SQL Server FK value check using native SQL equality.

Only SELECT/EXISTS against a single explicitly selected original FK. Does not
change VIDA or authenticate original database provenance or vehicle runtime.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

from vida_original_table_reader import _encode, _identifier, _name

SCHEMA = 'virtualcar-vida-original-sql-fk-probe-v1'
DATABASE_RE = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
DSN_RE = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
MAX_ROWS = 5000
MAX_OUTPUT_BYTES = 50 * 1024 * 1024
STATUS_ALIAS = '__vida_fk_exists_result__'
FK_SQL = (
    'SELECT fk.object_id, fk.name, fkc.constraint_column_id, '
    'ss.name, st.name, sc.name, ts.name, tt.name, tc.name, '
    'fk.is_disabled, fk.is_not_trusted, '
    '(SELECT COUNT(*) FROM sys.index_columns AS ic '
    'WHERE ic.object_id = fk.referenced_object_id '
    'AND ic.index_id = fk.key_index_id AND ic.key_ordinal > 0) '
    'FROM sys.foreign_keys AS fk '
    'JOIN sys.foreign_key_columns AS fkc '
    'ON fk.object_id = fkc.constraint_object_id '
    'JOIN sys.tables AS st ON st.object_id = fk.parent_object_id '
    'JOIN sys.schemas AS ss ON ss.schema_id = st.schema_id '
    'JOIN sys.columns AS sc ON sc.object_id = st.object_id '
    'AND sc.column_id = fkc.parent_column_id '
    'JOIN sys.tables AS tt ON tt.object_id = fk.referenced_object_id '
    'JOIN sys.schemas AS ts ON ts.schema_id = tt.schema_id '
    'JOIN sys.columns AS tc ON tc.object_id = tt.object_id '
    'AND tc.column_id = fkc.referenced_column_id '
    'WHERE ss.name = ? AND st.name = ? AND fk.name = ? '
    'ORDER BY fkc.constraint_column_id'
)


class OriginalFKSQLProbeError(ValueError):
    """Fixed errors that cannot leak source values or connection strings."""


def _drain(cursor, maximum):
    rows = []
    while True:
        batch_size = min(128, maximum + 1 - len(rows))
        batch = cursor.fetchmany(batch_size)
        if not batch:
            return rows
        if len(batch) > batch_size:
            raise OriginalFKSQLProbeError('invalid SQL cursor batch')
        rows.extend(batch)
        if len(rows) > maximum:
            raise OriginalFKSQLProbeError('original table exceeds bounded row limit')


def _metadata(rows, expected_schema, expected_table, expected_fk):
    if not 1 <= len(rows) <= 32:
        raise OriginalFKSQLProbeError('no single visible bounded FK metadata')
    entries = []
    identity = None
    for row in rows:
        if len(row) != 12:
            raise OriginalFKSQLProbeError('invalid FK metadata width')
        (fk_id, name, ordinal, source_schema, source_table, source_column,
         target_schema, target_table, target_column, disabled, untrusted,
         referenced_key_count) = row
        if (type(fk_id) is not int or fk_id <= 0 or
                type(ordinal) is not int or not 1 <= ordinal <= 32 or
                type(referenced_key_count) is not int or
                not 1 <= referenced_key_count <= 32 or
                type(disabled) not in (bool, int) or disabled not in (0, 1) or
                type(untrusted) not in (bool, int) or untrusted not in (0, 1)):
            raise OriginalFKSQLProbeError('invalid FK metadata counts')
        for item in (name, source_schema, source_table, source_column,
                     target_schema, target_table, target_column):
            _name(item)
        fixed = (fk_id, name, source_schema, source_table, target_schema,
                 target_table, bool(disabled), bool(untrusted), referenced_key_count)
        if identity is None:
            identity = fixed
        if fixed != identity or (source_schema, source_table, name) != (
                expected_schema, expected_table, expected_fk):
            raise OriginalFKSQLProbeError('inconsistent or wrong FK metadata')
        entries.append((ordinal, source_column, target_column))
    entries.sort()
    if ([x[0] for x in entries] != list(range(1, len(entries) + 1)) or
            len(entries) != identity[-1] or
            len({x[1] for x in entries}) != len(entries) or
            len({x[2] for x in entries}) != len(entries) or
            any(x[1].casefold() == STATUS_ALIAS.casefold() for x in entries)):
        raise OriginalFKSQLProbeError('incomplete or duplicated FK members')
    return {'fk_object_id': identity[0], 'fk_name': identity[1],
            'source_schema': identity[2], 'source_table': identity[3],
            'target_schema': identity[4], 'target_table': identity[5],
            'is_disabled': identity[6], 'is_not_trusted': identity[7],
            'columns': [{'ordinal': pos, 'source': src, 'referenced': dst}
                        for pos, src, dst in entries]}


def _select_sql(metadata, max_rows):
    src = metadata['columns']
    projection = ', '.join('s.' + _identifier(x['source']) for x in src)
    null_test = ' OR '.join('s.' + _identifier(x['source']) + ' IS NULL' for x in src)
    equality = ' AND '.join('t.' + _identifier(x['referenced']) +
                            ' = s.' + _identifier(x['source']) for x in src)
    source_table = (_identifier(metadata['source_schema']) + '.' +
                    _identifier(metadata['source_table']))
    target_table = (_identifier(metadata['target_schema']) + '.' +
                    _identifier(metadata['target_table']))
    return (f'SELECT TOP ({max_rows + 1}) {projection}, '
            f'CASE WHEN ({null_test}) THEN -1 '
            f'WHEN EXISTS (SELECT 1 FROM {target_table} AS t WHERE {equality}) '
            f'THEN 1 ELSE 0 END AS [{STATUS_ALIAS}] FROM {source_table} AS s')


def capture(database, schema, table, fk_name, *, dsn, max_rows=1000, connector=None):
    if (type(database) is not str or not DATABASE_RE.fullmatch(database) or
            type(dsn) is not str or not DSN_RE.fullmatch(dsn) or
            type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS):
        raise OriginalFKSQLProbeError('invalid database, DSN or row limit')
    schema, table, fk_name = _name(schema), _name(table), _name(fk_name)
    if connector is None:
        try:
            import pyodbc
        except ImportError:
            raise OriginalFKSQLProbeError('pyodbc unavailable') from None
        connector = pyodbc.connect
    connection = (f'DSN={dsn};DATABASE={database};Trusted_Connection=Yes;'
                  'Encrypt=Yes;TrustServerCertificate=No;ApplicationIntent=ReadOnly;')
    try:
        db = connector(connection, autocommit=True, timeout=8)
        try:
            db.timeout = 15
            cur = db.cursor()
            identity = _drain(cur.execute('SELECT DB_NAME()'), 1)
            if len(identity) != 1 or identity[0][0] != database:
                raise OriginalFKSQLProbeError('SQL database identity mismatch')
            initial = _drain(cur.execute(FK_SQL, schema, table, fk_name), 32)
            metadata = _metadata(initial, schema, table, fk_name)
            cur.execute(_select_sql(metadata, max_rows))
            names = [field[0] for field in cur.description]
            if names != [x['source'] for x in metadata['columns']] + [STATUS_ALIAS]:
                raise OriginalFKSQLProbeError('live SQL projection changed')
            rows = _drain(cur, max_rows)
            # Detect observable FK catalog drift, but never promise an atomic
            # schema/data snapshot without a SQL transaction/isolation proof.
            current = _drain(cur.execute(FK_SQL, schema, table, fk_name), 32)
            if _metadata(current, schema, table, fk_name) != metadata:
                raise OriginalFKSQLProbeError('FK catalog changed during query')
        finally:
            db.close()
    except OriginalFKSQLProbeError:
        raise
    except Exception:
        raise OriginalFKSQLProbeError('original SQL read failed') from None
    matched, unmatched, null_keys = [], [], []
    for index, row in enumerate(rows):
        if len(row) != len(metadata['columns']) + 1:
            raise OriginalFKSQLProbeError('unexpected original SQL row width')
        values = [_encode(value) for value in row[:-1]]
        status = row[-1]
        if type(status) is not int or status not in (-1, 0, 1):
            raise OriginalFKSQLProbeError('invalid SQL FK status')
        item = {'source_result_row_index': index,
                'original_source_key_values': values}
        (null_keys if status == -1 else matched if status == 1 else unmatched).append(item)
    return {'schema_version': SCHEMA, 'source_database': database,
            'original_fk_metadata': metadata,
            'source_rows_examined': len(rows),
            'sql_exists_matches': matched,
            'sql_exists_unmatched': unmatched,
            'sql_null_key_rows': null_keys,
            'original_identifiers_and_values_not_anonymized': True,
            'native_sql_server_exists_evaluated': True,
            'source_complete_within_row_limit': True,
            'same_connection_database_identity_checked': True,
            'full_catalog_visibility_verified': False,
            'transactional_snapshot_verified': False,
            'fk_constraint_enforcement_verified': False,
            'getscript_readvin_runtime_verified': False,
            'client_vin_accepted': False,
            'physical_j2534_verified': False}


def main(argv=None):
    p = argparse.ArgumentParser(description='Local original VIDA FK SQL EXISTS probe')
    p.add_argument('--database', required=True)
    p.add_argument('--schema', required=True)
    p.add_argument('--table', required=True)
    p.add_argument('--foreign-key', required=True)
    p.add_argument('--max-rows', type=int, default=1000)
    p.add_argument('--output', required=True, type=Path)
    args = p.parse_args(argv)
    try:
        root = Path(__file__).resolve().parents[2]
        out = args.output.resolve()
        if (not args.output.parent.is_dir() or args.output.parent.is_symlink() or
                out == root or root in out.parents):
            raise OriginalFKSQLProbeError('unsafe owner-local output path')
        result = capture(args.database, args.schema, args.table, args.foreign_key,
                         dsn=os.environ.get('VIDA_SQLSERVER_DSN', ''),
                         max_rows=args.max_rows)
        encoded = (json.dumps(result, ensure_ascii=False, sort_keys=True,
                              indent=2, allow_nan=False) + '\n').encode('utf-8')
        if len(encoded) > MAX_OUTPUT_BYTES:
            raise OriginalFKSQLProbeError('original FK result exceeds output limit')
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(encoded)
        print('Owner-local native SQL FK equality checked; original values kept unchanged.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
