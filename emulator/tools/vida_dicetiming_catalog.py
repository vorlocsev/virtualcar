#!/usr/bin/env python3
"""Bounded metadata-only DiceTiming inventory for the VIDA research lab.

Never reads application rows, timing values, SQL definitions, VIN, J2534 or ECU
payloads. Names in original catalogs are used only to validate completeness;
no original table, column, identifier or connection string is emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

DATABASE = 'DiceTiming'
SCHEMA = 'virtualcar-vida-dicetiming-metadata-v1'
EXPORT_SCHEMA = 'virtualcar-vida-offline-sqlite-v1'
MAX_TABLES = 2000
MAX_COLUMNS = 30000
MAX_KEYS = 30000
DSN_RE = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
SHAPE_KEY_ENV = 'VIDA_DICETIMING_HMAC_KEY'
SHAPE_KEY_RE = re.compile(r'[0-9a-f]{64}\Z')
SHAPE_SCOPE = 'visible_normalized_catalog_identifiers_v1'
META = {
    '_vida_meta': ('key', 'value'),
    '_vida_tables': ('schema_name', 'table_name', 'rows_exported'),
    '_vida_columns': ('schema_name', 'table_name', 'column_name', 'system_type_id'),
}
SQL_TABLES = 'SELECT s.name, t.name FROM sys.tables AS t JOIN sys.schemas AS s ON t.schema_id = s.schema_id'
SQL_COLUMNS = ('SELECT s.name, t.name, c.name FROM sys.columns AS c '
               'JOIN sys.tables AS t ON c.object_id = t.object_id '
               'JOIN sys.schemas AS s ON s.schema_id = t.schema_id')
SQL_KEYS = ('SELECT fk.object_id, fkc.constraint_column_id, '
            'ss.name, st.name, sc.name, ts.name, tt.name, tc.name, '
            'fk.is_disabled, fk.is_not_trusted, '
            '(SELECT COUNT(*) FROM sys.index_columns AS ic '
            'WHERE ic.object_id = fk.referenced_object_id '
            'AND ic.index_id = fk.key_index_id AND ic.key_ordinal > 0) '
            'FROM sys.foreign_key_columns AS fkc '
            'JOIN sys.foreign_keys AS fk ON fk.object_id = fkc.constraint_object_id '
            'JOIN sys.tables AS st ON st.object_id = fkc.parent_object_id '
            'JOIN sys.schemas AS ss ON ss.schema_id = st.schema_id '
            'JOIN sys.columns AS sc ON sc.object_id = st.object_id '
            'AND sc.column_id = fkc.parent_column_id '
            'JOIN sys.tables AS tt ON tt.object_id = fkc.referenced_object_id '
            'JOIN sys.schemas AS ts ON ts.schema_id = tt.schema_id '
            'JOIN sys.columns AS tc ON tc.object_id = tt.object_id '
            'AND tc.column_id = fkc.referenced_column_id')


class DiceTimingError(ValueError):
    """Generic failures: never print source names, DSNs or paths."""


def _bounded(rows, maximum):
    if len(rows) > maximum:
        raise DiceTimingError('catalog too large')
    return rows


def _consume_bounded(cursor, maximum):
    """Drain a metadata cursor; fetchmany may legally return short batches."""
    rows = []
    while True:
        # One extra row is sufficient to detect overflow without unbounded reads.
        take = min(256, maximum + 1 - len(rows))
        batch = cursor.fetchmany(take)
        if not batch:
            return rows
        if len(batch) > take:
            raise DiceTimingError('invalid metadata cursor batch')
        rows.extend(batch)
        if len(rows) > maximum:
            raise DiceTimingError('catalog too large')


def _remember_table(tables, schema, name):
    if not isinstance(schema, str) or not isinstance(name, str) or not schema or not name:
        raise DiceTimingError('invalid catalog identity')
    key = schema.casefold(), name.casefold()
    if key in tables:
        raise DiceTimingError('duplicate catalog table')
    tables[key] = set()


def _remember_column(tables, schema, name, column):
    if not all(isinstance(x, str) and x for x in (schema, name, column)):
        raise DiceTimingError('invalid catalog column')
    key = schema.casefold(), name.casefold()
    if key not in tables or column.casefold() in tables[key]:
        raise DiceTimingError('orphan or duplicate catalog column')
    tables[key].add(column.casefold())


def _shape_hmac(tables, shape_key):
    # A private, 256-bit random HMAC key makes dictionary guessing of original
    # metadata identifiers impractical when the redacted report is shared.
    # Neither the key nor original names are included in the report.
    if type(shape_key) is not str or not SHAPE_KEY_RE.fullmatch(shape_key):
        raise DiceTimingError('invalid private schema HMAC key')
    rows = [[schema, table, sorted(columns)]
            for (schema, table), columns in sorted(tables.items())]
    canonical = json.dumps(['DiceTiming', SHAPE_SCOPE, rows],
                           ensure_ascii=True, separators=(',', ':')).encode('utf-8')
    return hmac.new(bytes.fromhex(shape_key), canonical, hashlib.sha256).hexdigest()


def _foreign_key_summary(rows, tables):
    """Count visible FK constraints once, not once per composite-key column."""
    identities = {}
    members = {}
    ordinals = {}
    expected_sizes = {}
    for row in rows:
        if len(row) != 11:
            raise DiceTimingError('invalid FK catalog row')
        (fk_id, ordinal, ss, st, sc, ts, tt, tc,
         disabled, untrusted, referenced_key_columns) = row
        if type(fk_id) is not int or fk_id <= 0:
            raise DiceTimingError('invalid FK catalog identifier')
        # SQL Server sys.foreign_key_columns.constraint_column_id is 1..n.
        # A missing prefix or interior ordinal indicates partial metadata.
        if type(ordinal) is not int or not 1 <= ordinal <= 32:
            raise DiceTimingError('invalid FK ordinal')
        if (type(referenced_key_columns) is not int or
                not 1 <= referenced_key_columns <= 32):
            raise DiceTimingError('invalid referenced key column count')
        if fk_id in expected_sizes and expected_sizes[fk_id] != referenced_key_columns:
            raise DiceTimingError('inconsistent referenced key column count')
        expected_sizes[fk_id] = referenced_key_columns
        if not all(isinstance(x, str) and x for x in (ss, st, sc, ts, tt, tc)):
            raise DiceTimingError('invalid FK metadata')
        # pyodbc maps SQL BIT to Python bool; accept canonical 0/1 ints too.
        if (type(disabled) not in (bool, int) or disabled not in (0, 1) or
                type(untrusted) not in (bool, int) or untrusted not in (0, 1)):
            raise DiceTimingError('invalid FK trust status')
        source, target = (ss.casefold(), st.casefold()), (ts.casefold(), tt.casefold())
        source_col, target_col = sc.casefold(), tc.casefold()
        if (source not in tables or target not in tables or
                source_col not in tables[source] or target_col not in tables[target]):
            raise DiceTimingError('unresolved FK metadata')
        identity = (source, target, bool(disabled), bool(untrusted))
        if fk_id in identities and identities[fk_id] != identity:
            raise DiceTimingError('conflicting FK catalog identity')
        identities[fk_id] = identity
        key = (source_col, target_col)
        pair_set = members.setdefault(fk_id, set())
        if key in pair_set:
            raise DiceTimingError('duplicate FK catalog column pair')
        pair_set.add(key)
        position_set = ordinals.setdefault(fk_id, set())
        if ordinal in position_set:
            raise DiceTimingError('duplicate FK ordinal')
        position_set.add(ordinal)
        # Each source/target column must occur once per constraint.
        if (len({src for src, _ in pair_set}) != len(pair_set) or
                len({dst for _, dst in pair_set}) != len(pair_set)):
            raise DiceTimingError('duplicate FK member column')
    for fk_id, positions in ordinals.items():
        if positions != set(range(1, len(positions) + 1)):
            raise DiceTimingError('noncontiguous FK ordinals')
        # Independently count key columns on the referenced unique index.
        # This also catches an otherwise-undetectable truncated FK suffix.
        if len(positions) != expected_sizes[fk_id]:
            raise DiceTimingError('incomplete referenced key column coverage')
    return {
        'constraint_count': len(identities),
        'disabled_constraint_count': sum(flags[2] for flags in identities.values()),
        'untrusted_constraint_count': sum(flags[3] for flags in identities.values()),
        'self_referencing_constraint_count': sum(flags[0] == flags[1]
                                                  for flags in identities.values()),
    }


def _finish(tables, foreign_key_count, backend, shape_key=None, fk_stats=None):
    if not tables or any(not columns for columns in tables.values()):
        raise DiceTimingError('incomplete metadata inventory')
    result = {
        'schema_version': SCHEMA,
        'status': 'metadata_only',
        'backend': backend,
        'database': DATABASE,
        'table_count': len(tables),
        'column_count': sum(len(columns) for columns in tables.values()),
        'declared_fk_column_count': foreign_key_count,
        'source_rows_read': False,
        'sql_definitions_read': False,
        'original_timing_values_read': False,
        'timing_profile_link_verified': False,
        'cross_database_snapshot_verified': False,
        'd2_baud_verified': False,
        'readvin_execution_verified': False,
        'client_vin_accepted': False,
        'physical_j2534_verified': False,
        'replay_approved': False,
    }
    if fk_stats is not None:
        if backend != 'sqlserver':
            raise DiceTimingError('incompatible FK catalog source')
        if (type(fk_stats) is not dict or
                set(fk_stats) != {'constraint_count', 'disabled_constraint_count',
                                  'untrusted_constraint_count',
                                  'self_referencing_constraint_count'}):
            raise DiceTimingError('invalid FK catalog summary')
        n = fk_stats['constraint_count']
        if (type(n) is not int or n < 0 or n > foreign_key_count or
                any(type(v) is not int or v < 0 or v > n for v in fk_stats.values())):
            raise DiceTimingError('inconsistent FK catalog summary')
        result['visible_fk_catalog'] = {
            'scope': 'sqlserver_visible_constraints_only',
            **fk_stats,
            'complete_metadata_visibility_verified': False,
            'referential_rows_verified': False,
        }
    if shape_key is not None:
        result['visible_schema_hmac_scope'] = SHAPE_SCOPE
        result['visible_schema_hmac_sha256'] = _shape_hmac(tables, shape_key)
    return result


def load_sqlite_export(folder: Path, *, shape_key=None):
    if shape_key is not None and (type(shape_key) is not str or not SHAPE_KEY_RE.fullmatch(shape_key)):
        raise DiceTimingError('invalid private schema HMAC key')
    if not folder.is_dir() or folder.is_symlink():
        raise DiceTimingError('invalid export folder')
    path = folder / (DATABASE + '.sqlite')
    if not path.is_file() or path.is_symlink():
        raise DiceTimingError('missing DiceTiming metadata export')
    if any(path.with_name(path.name + suffix).exists()
           or path.with_name(path.name + suffix).is_symlink()
           for suffix in ('-wal', '-shm', '-journal')):
        raise DiceTimingError('unclean exporter snapshot')
    try:
        with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro&immutable=1',
                                     uri=True, timeout=5)) as db:
            db.execute('PRAGMA query_only=ON')
            for table, required in META.items():
                objects = db.execute("PRAGMA table_list('" + table + "')").fetchmany(2)
                if (len(objects) != 1 or objects[0][0].casefold() != 'main'
                        or objects[0][1].casefold() != table.casefold()
                        or objects[0][2] != 'table'):
                    raise DiceTimingError('unsafe exporter object')
                cols = [c[0].casefold() for c in db.execute(
                    'SELECT * FROM "' + table + '" LIMIT 0').description]
                if len(cols) != len(set(cols)) or not set(required).issubset(cols):
                    raise DiceTimingError('invalid exporter schema')
            metadata = _bounded(db.execute('SELECT "key", "value" FROM "_vida_meta"')
                                .fetchmany(101), 100)
            if len(metadata) != len({row[0] for row in metadata}):
                raise DiceTimingError('duplicate exporter identity')
            identity = dict(metadata)
            if (identity.get('schema_version') != EXPORT_SCHEMA
                    or identity.get('source_database') != DATABASE
                    or identity.get('scope') != 'all_user_tables'):
                raise DiceTimingError('wrong exporter identity')
            table_rows = _bounded(db.execute(
                'SELECT "schema_name", "table_name", "rows_exported" '
                'FROM "_vida_tables"').fetchmany(MAX_TABLES + 1), MAX_TABLES)
            column_rows = _bounded(db.execute(
                'SELECT "schema_name", "table_name", "column_name", "system_type_id" '
                'FROM "_vida_columns"').fetchmany(MAX_COLUMNS + 1), MAX_COLUMNS)
    except sqlite3.DatabaseError:
        raise DiceTimingError('invalid exporter database') from None
    tables = {}
    for schema, name, count in table_rows:
        if type(count) is not int or count < 0:
            raise DiceTimingError('invalid exporter table count')
        _remember_table(tables, schema, name)
    for schema, name, column, type_id in column_rows:
        if type(type_id) is not int:
            raise DiceTimingError('invalid exporter column type')
        _remember_column(tables, schema, name, column)
    # Exporter does not record original FK metadata; zero means *unavailable*.
    return _finish(tables, 0, 'sqlite-export', shape_key)


def load_sqlserver(dsn: str, connector=None, *, shape_key=None):
    if shape_key is not None and (type(shape_key) is not str or not SHAPE_KEY_RE.fullmatch(shape_key)):
        raise DiceTimingError('invalid private schema HMAC key')
    if not isinstance(dsn, str) or not DSN_RE.fullmatch(dsn):
        raise DiceTimingError('invalid DSN')
    if connector is None:
        try:
            import pyodbc
        except ImportError:
            raise DiceTimingError('missing pyodbc') from None
        connector = pyodbc.connect
    connstr = ('DSN=' + dsn + ';DATABASE=' + DATABASE + ';Trusted_Connection=Yes;'
               'Encrypt=Yes;TrustServerCertificate=No;ApplicationIntent=ReadOnly;')
    try:
        db = connector(connstr, autocommit=True, timeout=8)
        try:
            db.timeout = 8
            cursor = db.cursor()
            identity = cursor.execute('SELECT DB_NAME()').fetchmany(2)
            if len(identity) != 1 or identity[0][0] != DATABASE:
                raise DiceTimingError('wrong SQL database')
            table_rows = _consume_bounded(cursor.execute(SQL_TABLES), MAX_TABLES)
            column_rows = _consume_bounded(cursor.execute(SQL_COLUMNS), MAX_COLUMNS)
            fk_rows = _consume_bounded(cursor.execute(SQL_KEYS), MAX_KEYS)
        finally:
            db.close()
    except DiceTimingError:
        raise
    except Exception:
        raise DiceTimingError('SQL catalog read failed') from None
    tables = {}
    for schema, name in table_rows:
        _remember_table(tables, schema, name)
    for schema, name, column in column_rows:
        _remember_column(tables, schema, name, column)
    fk_stats = _foreign_key_summary(fk_rows, tables)
    return _finish(tables, len(fk_rows), 'sqlserver', shape_key, fk_stats=fk_stats)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Owner-only VIDA DiceTiming metadata inventory')
    parser.add_argument('--backend', choices=('sqlite-export', 'sqlserver'), required=True)
    parser.add_argument('--folder', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        output = args.output.resolve()
        checkout = Path(__file__).resolve().parents[2]
        if (not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or output == checkout or checkout in output.parents):
            raise DiceTimingError('unsafe output location')
        if args.backend == 'sqlite-export':
            if args.folder is None or output == (args.folder / (DATABASE + '.sqlite')).resolve():
                raise DiceTimingError('unsafe input/output')
            result = load_sqlite_export(args.folder, shape_key=os.environ.get(SHAPE_KEY_ENV))
        else:
            if args.folder is not None:
                raise DiceTimingError('SQL Server cannot use folder')
            result = load_sqlserver(os.environ.get('VIDA_SQLSERVER_DSN', ''),
                                    shape_key=os.environ.get(SHAPE_KEY_ENV))
        with args.output.open('x', encoding='utf-8') as out:
            json.dump(result, out, sort_keys=True, indent=2)
            out.write('\n')
        print('DiceTiming metadata inventory complete; timing/baud/VIDA runtime unverified.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
