#!/usr/bin/env python3
"""Owner-local VIDA SQL Server schema reader with original identifiers intact.

Queries only system catalogs. Preserves original table, column, FK and index
names; publishes nothing. It does not attest catalog visibility or row joins.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

SCHEMA = 'virtualcar-vida-original-schema-v1'
DSN_RE = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
DATABASE_RE = re.compile(r'[A-Za-z0-9_. -]{1,128}\Z')
MAX_TABLES, MAX_COLUMNS, MAX_FOREIGN_KEY_MEMBERS, MAX_INDEX_MEMBERS = 2000, 30000, 30000, 30000
MAX_OUTPUT_BYTES = 20 * 1024 * 1024
TABLES_SQL = (
    'SELECT s.name, t.name, t.object_id FROM sys.tables AS t '
    'JOIN sys.schemas AS s ON s.schema_id = t.schema_id '
    'WHERE t.is_ms_shipped = 0 ORDER BY s.name, t.name, t.object_id'
)
COLUMNS_SQL = (
    'SELECT c.object_id, c.column_id, c.name, ty.name, c.max_length, '
    'c.precision, c.scale, c.is_nullable, c.is_identity, c.is_computed, c.collation_name '
    'FROM sys.columns AS c JOIN sys.tables AS t ON t.object_id = c.object_id '
    'JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id '
    'WHERE t.is_ms_shipped = 0 ORDER BY c.object_id, c.column_id'
)
INDEXES_SQL = (
    'SELECT i.object_id, i.index_id, i.name, i.is_primary_key, '
    'i.is_unique_constraint, ic.key_ordinal, ic.column_id '
    'FROM sys.indexes AS i JOIN sys.index_columns AS ic '
    'ON ic.object_id = i.object_id AND ic.index_id = i.index_id '
    'WHERE i.is_unique = 1 AND ic.key_ordinal > 0 '
    'ORDER BY i.object_id, i.index_id, ic.key_ordinal'
)
FOREIGN_KEYS_SQL = (
    'SELECT fk.object_id, fk.name, fkc.constraint_column_id, '
    'fk.parent_object_id, fkc.parent_column_id, fk.referenced_object_id, '
    'fkc.referenced_column_id, fk.key_index_id, fk.is_disabled, '
    'fk.is_not_trusted, fk.delete_referential_action_desc, '
    'fk.update_referential_action_desc '
    'FROM sys.foreign_keys AS fk JOIN sys.foreign_key_columns AS fkc '
    'ON fkc.constraint_object_id = fk.object_id '
    'ORDER BY fk.object_id, fkc.constraint_column_id'
)


class OriginalSchemaError(ValueError):
    """Sanitized error categories; never echo original identifiers or values."""


def _name(value):
    if (type(value) is not str or not 1 <= len(value) <= 128 or
            any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        raise OriginalSchemaError('invalid original SQL catalog name')
    return value


def _positive(value):
    if type(value) is not int or value <= 0:
        raise OriginalSchemaError('invalid original SQL catalog identifier')
    return value


def _integer(value, low=0, high=2**31-1):
    if type(value) is not int or not low <= value <= high:
        raise OriginalSchemaError('invalid original SQL catalog numeric field')
    return value


def _bit(value):
    if type(value) not in (int, bool) or value not in (0, 1):
        raise OriginalSchemaError('invalid original SQL bit field')
    return bool(value)


def _read_bounded(cursor, maximum):
    result = []
    while True:
        count = min(256, maximum + 1 - len(result))
        batch = cursor.fetchmany(count)
        if not batch:
            return result
        if len(batch) > count:
            raise OriginalSchemaError('invalid SQL cursor batch')
        result.extend(batch)
        if len(result) > maximum:
            raise OriginalSchemaError('original catalog exceeds limit')


def _group_members(entries, name, ordinal):
    """Check the complete set of 1-based ordered positions, not cursor order."""
    values = [entry[ordinal] for entry in entries]
    if any(type(v) is not int or not 1 <= v <= 32 for v in values):
        raise OriginalSchemaError('invalid key member ordinal')
    if set(values) != set(range(1, len(values) + 1)):
        raise OriginalSchemaError('missing or duplicate key member ordinal')
    return sorted(entries, key=lambda row: row[ordinal])


def parse(database, table_rows, column_rows, index_rows, fk_rows):
    """Build complete original-identifier graph from bounded catalog rows."""
    database = _name(database)
    tables = {}
    for row in table_rows:
        if len(row) != 3:
            raise OriginalSchemaError('invalid SQL table record')
        schema, name, object_id = row
        schema, name, object_id = _name(schema), _name(name), _positive(object_id)
        if object_id in tables or any(x['schema'] == schema and x['name'] == name
                                      for x in tables.values()):
            raise OriginalSchemaError('duplicate original SQL table')
        tables[object_id] = {'schema': schema, 'name': name, 'object_id': object_id,
                             'columns': [], 'unique_indexes': []}
    if not tables:
        raise OriginalSchemaError('no original SQL tables visible')
    column_by_id = {}
    for row in column_rows:
        if len(row) != 11:
            raise OriginalSchemaError('invalid SQL column record')
        (object_id, column_id, name, sql_type, max_length, precision, scale,
         nullable, identity, computed, collation) = row
        object_id, column_id = _positive(object_id), _positive(column_id)
        if object_id not in tables or (object_id, column_id) in column_by_id:
            raise OriginalSchemaError('orphan or duplicate SQL column')
        if collation is not None:
            _name(collation)
        entry = {'column_id': column_id, 'name': _name(name), 'sql_type': _name(sql_type),
                 'max_length': _integer(max_length, -1, 2**31-1),
                 'precision': _integer(precision, 0, 255),
                 'scale': _integer(scale, 0, 255), 'is_nullable': _bit(nullable),
                 'is_identity': _bit(identity), 'is_computed': _bit(computed),
                 'collation_name': collation}
        if any(c['name'] == name for c in tables[object_id]['columns']):
            raise OriginalSchemaError('duplicate original SQL column name')
        column_by_id[object_id, column_id] = entry
        tables[object_id]['columns'].append(entry)
    if any(not x['columns'] for x in tables.values()):
        raise OriginalSchemaError('incomplete original SQL column inventory')
    for table in tables.values():
        table['columns'].sort(key=lambda x: x['column_id'])
    index_groups = {}
    for row in index_rows:
        if len(row) != 7:
            raise OriginalSchemaError('invalid SQL unique index record')
        object_id, index_id, idxname, pk, uq, pos, col_id = row
        object_id, index_id, col_id = _positive(object_id), _positive(index_id), _positive(col_id)
        if object_id not in tables or (object_id, col_id) not in column_by_id:
            raise OriginalSchemaError('unresolved SQL index column')
        identity = (_name(idxname), _bit(pk), _bit(uq))
        key = (object_id, index_id)
        if key in index_groups and index_groups[key]['identity'] != identity:
            raise OriginalSchemaError('inconsistent SQL index identity')
        index_groups.setdefault(key, {'identity': identity, 'rows': []})['rows'].append((pos, col_id))
    unique_keys = {}
    for (object_id, index_id), item in sorted(index_groups.items()):
        members = _group_members(item['rows'], 'index', 0)
        col_ids = [row[1] for row in members]
        if len(set(col_ids)) != len(col_ids):
            raise OriginalSchemaError('duplicate SQL index member')
        name, primary, constraint = item['identity']
        index = {'index_id': index_id, 'name': name, 'is_primary_key': primary,
                 'is_unique_constraint': constraint,
                 'columns': [column_by_id[object_id, col]['name'] for col in col_ids]}
        unique_keys[object_id, index_id] = col_ids
        tables[object_id]['unique_indexes'].append(index)
    fk_groups = {}
    for row in fk_rows:
        if len(row) != 12:
            raise OriginalSchemaError('invalid SQL foreign-key record')
        (fk_id, name, ordinal, source, source_col, target, target_col, key_index,
         disabled, untrusted, on_delete, on_update) = row
        fk_id = _positive(fk_id)
        source, source_col, target, target_col = map(_positive, (source, source_col, target, target_col))
        key_index = _positive(key_index)
        if ((source, source_col) not in column_by_id or
                (target, target_col) not in column_by_id):
            raise OriginalSchemaError('unresolved original SQL foreign-key column')
        identity = (_name(name), source, target, key_index, _bit(disabled),
                    _bit(untrusted), _name(on_delete), _name(on_update))
        if fk_id in fk_groups and fk_groups[fk_id]['identity'] != identity:
            raise OriginalSchemaError('inconsistent SQL foreign-key identity')
        fk_groups.setdefault(fk_id, {'identity': identity, 'rows': []})['rows'].append(
            (ordinal, source_col, target_col))
    fks = []
    for fk_id, item in sorted(fk_groups.items()):
        name, source, target, key_index, disabled, untrusted, on_delete, on_update = item['identity']
        members = _group_members(item['rows'], 'foreign key', 0)
        sources = [row[1] for row in members]
        targets = [row[2] for row in members]
        if len(set(sources)) != len(sources) or len(set(targets)) != len(targets):
            raise OriginalSchemaError('duplicate SQL foreign-key member')
        if unique_keys.get((target, key_index)) != targets:
            raise OriginalSchemaError('referenced SQL unique index disagrees with FK')
        fks.append({'object_id': fk_id, 'name': name,
                    'source_schema': tables[source]['schema'],
                    'source_table': tables[source]['name'],
                    'referenced_schema': tables[target]['schema'],
                    'referenced_table': tables[target]['name'],
                    'referenced_key_index_id': key_index,
                    'is_disabled': disabled, 'is_not_trusted': untrusted,
                    'on_delete': on_delete, 'on_update': on_update,
                    'columns': [{'ordinal': row[0],
                                 'source': column_by_id[source, row[1]]['name'],
                                 'referenced': column_by_id[target, row[2]]['name']}
                                for row in members]})
    return {'schema_version': SCHEMA, 'source_database': database,
            'original_identifiers_preserved': True,
            'tables': sorted(tables.values(), key=lambda x: (x['schema'], x['name'])),
            'foreign_keys': fks,
            'original_user_rows_read': False, 'actual_row_joins_verified': False,
            'complete_catalog_visibility_verified': False,
            'transactional_snapshot_verified': False, 'runtime_readvin_verified': False,
            'physical_j2534_verified': False}


def capture(database, *, dsn, connector=None):
    database = _name(database)
    if (not DATABASE_RE.fullmatch(database) or
            type(dsn) is not str or not DSN_RE.fullmatch(dsn)):
        raise OriginalSchemaError('invalid SQL DSN')
    if connector is None:
        try:
            import pyodbc
        except ImportError:
            raise OriginalSchemaError('pyodbc unavailable') from None
        connector = pyodbc.connect
    conn = (f'DSN={dsn};DATABASE={database};Trusted_Connection=Yes;'
            'Encrypt=Yes;TrustServerCertificate=No;ApplicationIntent=ReadOnly;')
    try:
        db = connector(conn, autocommit=True, timeout=8)
        try:
            db.timeout = 8
            cur = db.cursor()
            check = _read_bounded(cur.execute('SELECT DB_NAME()'), 1)
            if len(check) != 1 or check[0][0] != database:
                raise OriginalSchemaError('wrong original SQL database')
            results = [_read_bounded(cur.execute(query), limit) for query, limit in
                       ((TABLES_SQL, MAX_TABLES), (COLUMNS_SQL, MAX_COLUMNS),
                        (INDEXES_SQL, MAX_INDEX_MEMBERS),
                        (FOREIGN_KEYS_SQL, MAX_FOREIGN_KEY_MEMBERS))]
        finally:
            db.close()
    except OriginalSchemaError:
        raise
    except Exception:
        raise OriginalSchemaError('original SQL catalog read failed') from None
    return parse(database, *results)


def main(argv=None):
    ap = argparse.ArgumentParser(description='Owner-local unmasked VIDA SQL schema inventory')
    ap.add_argument('--database', required=True)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        checkout = Path(__file__).resolve().parents[2]
        target = args.output.resolve()
        if (not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or target == checkout or checkout in target.parents):
            raise OriginalSchemaError('unsafe original schema output')
        report = capture(args.database, dsn=os.environ.get('VIDA_SQLSERVER_DSN', ''))
        data = (json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
        if len(data) > MAX_OUTPUT_BYTES:
            raise OriginalSchemaError('original schema output too large')
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
        print('Owner-local original VIDA schema written with original names intact.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
