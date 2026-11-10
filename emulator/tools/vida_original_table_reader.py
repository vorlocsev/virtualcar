#!/usr/bin/env python3
"""Owner-local, non-redacted read-only VIDA SQL Server table capture.

Preserves original names and row values as exposed by the DB driver. No
publish/upload, credential printing, write SQL, vehicle or ECU operations.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import re
import sys
import uuid

SCHEMA = 'virtualcar-vida-original-table-capture-v1'
DSN_RE = re.compile(r'[A-Za-z0-9_.-]{1,128}\Z')
DATABASE_RE = re.compile(r'[A-Za-z0-9_. -]{1,128}\Z')
MAX_ROWS = 5000
MAX_COLUMNS = 1024
MAX_OUTPUT_BYTES = 50 * 1024 * 1024
COLUMNS_SQL = (
    'SELECT c.column_id, c.name, ty.name FROM sys.columns AS c '
    'JOIN sys.tables AS t ON t.object_id = c.object_id '
    'JOIN sys.schemas AS s ON s.schema_id = t.schema_id '
    'JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id '
    'WHERE s.name = ? AND t.name = ? ORDER BY c.column_id'
)


class OriginalCaptureError(ValueError):
    """Fixed error categories, with no original values or connection strings."""


def _name(value):
    # SQL Server sysname permits spaces, punctuation and Unicode. Reject only
    # empty/control and overly long names; bracket-escape quote characters.
    if (type(value) is not str or not 1 <= len(value) <= 128
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        raise OriginalCaptureError('invalid SQL identifier')
    return value


def _identifier(value):
    return '[' + _name(value).replace(']', ']]') + ']'


def _encode(value):
    """Never redact, hash, trim or coerce unknown data into a lossy string."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise OriginalCaptureError('nonfinite SQL floating-point value')
        return {'format': 'ieee754-python-float-hex', 'value': value.hex()}
    if isinstance(value, (bytes, bytearray, memoryview)):
        return {'format': 'binary-base64',
                'value': base64.b64encode(bytes(value)).decode('ascii')}
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise OriginalCaptureError('nonfinite SQL decimal value')
        return {'format': 'decimal-text', 'value': str(value)}
    if isinstance(value, dt.datetime):
        return {'format': 'datetime-iso8601', 'value': value.isoformat()}
    if isinstance(value, dt.date):
        return {'format': 'date-iso8601', 'value': value.isoformat()}
    if isinstance(value, dt.time):
        return {'format': 'time-iso8601', 'value': value.isoformat()}
    if isinstance(value, uuid.UUID):
        return {'format': 'uuid-raw-hex', 'value': value.hex}
    raise OriginalCaptureError('unsupported SQL driver data type')


def _consume(cursor, maximum):
    result = []
    while True:
        count = min(128, maximum + 1 - len(result))
        batch = cursor.fetchmany(count)
        if not batch:
            return result
        if len(batch) > count:
            raise OriginalCaptureError('invalid cursor batch size')
        result.extend(batch)
        if len(result) > maximum:
            raise OriginalCaptureError('source exceeds requested row limit')


def capture(database, schema, table, *, dsn, max_rows=1000, connector=None):
    database, schema, table = (_name(x) for x in (database, schema, table))
    if (not DATABASE_RE.fullmatch(database) or
            type(dsn) is not str or not DSN_RE.fullmatch(dsn)
            or type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS):
        raise OriginalCaptureError('invalid capture options')
    if connector is None:
        try:
            import pyodbc
        except ImportError:
            raise OriginalCaptureError('pyodbc unavailable') from None
        connector = pyodbc.connect
    connstr = (f'DSN={dsn};DATABASE={database};Trusted_Connection=Yes;'
               'Encrypt=Yes;TrustServerCertificate=No;ApplicationIntent=ReadOnly;')
    try:
        db = connector(connstr, autocommit=True, timeout=8)
        try:
            db.timeout = 8
            cursor = db.cursor()
            dbname = _consume(cursor.execute('SELECT DB_NAME()'), 1)
            if len(dbname) != 1 or dbname[0][0] != database:
                raise OriginalCaptureError('unexpected SQL database identity')
            declared = _consume(cursor.execute(COLUMNS_SQL, schema, table), MAX_COLUMNS)
            if not declared:
                raise OriginalCaptureError('table not visible in SQL catalog')
            cols = []
            for expected_id, item in enumerate(declared, 1):
                if (len(item) != 3 or type(item[0]) is not int
                        or item[0] < expected_id or type(item[2]) is not str):
                    raise OriginalCaptureError('inconsistent SQL column metadata')
                cols.append({'column_id': item[0], 'name': _name(item[1]),
                             'sql_type': item[2]})
            if len({x['name'] for x in cols}) != len(cols):
                raise OriginalCaptureError('duplicate SQL column identity')
            # Escaped, catalog-confirmed identifiers; TOP value is strict int.
            sql = f'SELECT TOP ({max_rows + 1}) * FROM {_identifier(schema)}.{_identifier(table)}'
            cursor.execute(sql)
            actual = [field[0] for field in cursor.description]
            if actual != [x['name'] for x in cols]:
                raise OriginalCaptureError('data cursor column metadata drift')
            rows = _consume(cursor, max_rows)
        finally:
            db.close()
    except OriginalCaptureError:
        raise
    except Exception:
        raise OriginalCaptureError('owner-local SQL read failed') from None
    encoded = []
    for row in rows:
        if len(row) != len(cols):
            raise OriginalCaptureError('unexpected SQL row width')
        encoded.append([_encode(v) for v in row])
    return {
        'schema_version': SCHEMA,
        'source_database': database,
        'source_schema': schema,
        'source_table': table,
        'columns': cols,
        'rows': encoded,
        'row_count': len(encoded),
        'original_names_and_driver_values_not_anonymized': True,
        'full_table_extracted_within_row_limit': True,
        'raw_sql_server_type_roundtrip_verified': False,
        'transactional_snapshot_verified': False,
        'same_installation_provenance_verified': False,
        'vehicle_runtime_verified': False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description='Owner-local VIDA table reader, no anonymization')
    ap.add_argument('--database', required=True)
    ap.add_argument('--schema', required=True)
    ap.add_argument('--table', required=True)
    ap.add_argument('--max-rows', type=int, default=1000)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(argv)
    try:
        checkout = Path(__file__).resolve().parents[2]
        target = args.output.resolve()
        if (not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or target == checkout or checkout in target.parents):
            raise OriginalCaptureError('unsafe output directory')
        report = capture(args.database, args.schema, args.table,
                         dsn=os.environ.get('VIDA_SQLSERVER_DSN', ''),
                         max_rows=args.max_rows)
        content = (json.dumps(report, indent=2, ensure_ascii=False,
                              sort_keys=True, allow_nan=False) + '\n').encode('utf-8')
        if len(content) > MAX_OUTPUT_BYTES:
            raise OriginalCaptureError('source exceeds local output limit')
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
        print('Owner-local original VIDA table captured; source values not anonymized.')
        return 0
    except Exception as exc:
        print(json.dumps({'status': 'failed', 'error_class': type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
