#!/usr/bin/env python3
"""VIDA schema graph v1: metadata-only, privacy-safe SQL Server / SQLite audit.

No queries against VIDA user tables, VIN, XML, SQL definitions or ECU payloads.
Relationships are *declared* (SQL Server FK) or *shape candidates*, never verified
record joins or evidence of a successful VIN read.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import re
import sqlite3
import sys

from audit_vida_carcom_schema_links import (
    CANDIDATE_EDGES, EXPORT_SCHEMA, HARDWARE_CANDIDATE_EDGES, TABLES
)

SCHEMA = "virtualcar-vida-unified-catalog-v1"
MAX_TABLES = 2000
MAX_COLUMNS = 30000
MAX_KEYS = 30000
META = {
    "_vida_meta": ("key", "value"),
    "_vida_tables": ("schema_name", "table_name", "rows_exported"),
    "_vida_columns": ("schema_name", "table_name", "column_name", "system_type_id"),
}
DSN_RE = re.compile(r"[A-Za-z0-9_.-]{1,128}\Z")

# All queries read system catalogs only. No dynamic SQL from source metadata.
SQL_TABLES = """
SELECT s.name, t.name
FROM sys.tables AS t JOIN sys.schemas AS s ON t.schema_id = s.schema_id
"""
SQL_COLUMNS = """
SELECT s.name, t.name, c.name
FROM sys.columns AS c
JOIN sys.tables AS t ON t.object_id = c.object_id
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
"""
SQL_KEYS = """
SELECT ss.name, st.name, sc.name, ts.name, tt.name, tc.name,
       fk.is_disabled, fk.is_not_trusted
FROM sys.foreign_key_columns AS fkc
JOIN sys.foreign_keys AS fk ON fk.object_id = fkc.constraint_object_id
JOIN sys.tables AS st ON st.object_id = fkc.parent_object_id
JOIN sys.schemas AS ss ON ss.schema_id = st.schema_id
JOIN sys.columns AS sc ON sc.object_id = st.object_id
                       AND sc.column_id = fkc.parent_column_id
JOIN sys.tables AS tt ON tt.object_id = fkc.referenced_object_id
JOIN sys.schemas AS ts ON ts.schema_id = tt.schema_id
JOIN sys.columns AS tc ON tc.object_id = tt.object_id
                       AND tc.column_id = fkc.referenced_column_id
"""


class AnalyzerError(Exception):
    """Report only generic errors; never echo DB connection strings or names."""


def _rows(cursor, sql, maximum):
    result = cursor.execute(sql).fetchmany(maximum + 1)
    if len(result) > maximum:
        raise AnalyzerError("metadata catalog exceeds limit")
    return result


def _insert_table(tables, schema, table):
    if not isinstance(schema, str) or not isinstance(table, str) or not schema or not table:
        raise AnalyzerError("invalid metadata table identity")
    key = (schema.casefold(), table.casefold())
    if key in tables:
        raise AnalyzerError("duplicate metadata table")
    tables[key] = set()


def _insert_column(tables, schema, table, column):
    if not isinstance(schema, str) or not isinstance(table, str) or not isinstance(column, str):
        raise AnalyzerError("invalid metadata column")
    key = (schema.casefold(), table.casefold())
    if key not in tables or not column:
        raise AnalyzerError("orphaned metadata column")
    norm = column.casefold()
    if norm in tables[key]:
        raise AnalyzerError("duplicate metadata column")
    tables[key].add(norm)


def _metadata_table_shape(db, name, required):
    # SQLite may interpret SELECT "missing_column" as a STRING LITERAL.
    # Check the cursor schema using zero-row reads before any quoted SELECT.
    try:
        actual = [field[0].casefold()
                  for field in db.execute('SELECT * FROM "' + name + '" LIMIT 0').description]
    except sqlite3.DatabaseError:
        raise AnalyzerError("invalid exporter catalog schema") from None
    if len(actual) != len(set(actual)) or not all(c in actual for c in required):
        raise AnalyzerError("invalid exporter catalog schema")


def load_sqlite_export(folder: Path):
    if not folder.is_dir() or folder.is_symlink():
        raise AnalyzerError("invalid export directory")
    inventories = {}
    for database in TABLES:
        path = folder / (database + ".sqlite")
        if not path.is_file() or path.is_symlink():
            raise AnalyzerError("invalid export database")
        with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1",
                                     uri=True, timeout=5)) as db:
            db.execute("PRAGMA query_only=ON")
            for name, columns in META.items():
                _metadata_table_shape(db, name, columns)
            meta = _rows(db, 'SELECT "key", "value" FROM "_vida_meta"', 100)
            if len(meta) != len({row[0] for row in meta}):
                raise AnalyzerError("duplicate exporter identity")
            values = dict(meta)
            if (values.get("schema_version") != EXPORT_SCHEMA
                    or values.get("source_database") != database
                    or values.get("scope") != "all_user_tables"):
                raise AnalyzerError("invalid exporter identity")
            table_rows = _rows(
                db, 'SELECT "schema_name", "table_name", "rows_exported" FROM "_vida_tables"',
                MAX_TABLES)
            column_rows = _rows(
                db, 'SELECT "schema_name", "table_name", "column_name", "system_type_id" '
                    'FROM "_vida_columns"', MAX_COLUMNS)
            tables = {}
            for schema, name, count in table_rows:
                if not isinstance(count, int) or count < 0:
                    raise AnalyzerError("invalid exporter row count")
                _insert_table(tables, schema, name)
            for schema, table, column, type_id in column_rows:
                if not isinstance(type_id, int):
                    raise AnalyzerError("invalid exporter column type")
                _insert_column(tables, schema, table, column)
            inventories[database] = {"tables": tables, "keys": []}
    return inventories


def load_sqlserver(dsn: str, connector=None):
    if not isinstance(dsn, str) or not DSN_RE.fullmatch(dsn):
        raise AnalyzerError("invalid DSN name")
    if connector is None:
        try:
            import pyodbc
        except ImportError:
            raise AnalyzerError("pyodbc is not installed") from None
        connector = pyodbc.connect
    inventories = {}
    for database in TABLES:
        # Trusted auth, encrypted transport, no passwords in command-line args.
        # ReadOnly intent is advisory: enforce SELECT-only permissions for this account.
        connection_string = (
            f"DSN={dsn};DATABASE={database};Trusted_Connection=Yes;"
            "Encrypt=Yes;TrustServerCertificate=No;ApplicationIntent=ReadOnly;"
        )
        try:
            db = connector(connection_string, autocommit=True, timeout=8)
            try:
                cursor = db.cursor()
                table_rows = _rows(cursor, SQL_TABLES, MAX_TABLES)
                column_rows = _rows(cursor, SQL_COLUMNS, MAX_COLUMNS)
                key_rows = _rows(cursor, SQL_KEYS, MAX_KEYS)
            finally:
                db.close()
        except AnalyzerError:
            raise
        except Exception:
            raise AnalyzerError("SQL Server metadata read failed") from None
        tables = {}
        for schema, table in table_rows:
            _insert_table(tables, schema, table)
        for schema, table, column in column_rows:
            _insert_column(tables, schema, table, column)
        keys = []
        for ss, st, sc, ts, tt, tc, disabled, untrusted in key_rows:
            if not all(isinstance(x, str) and x for x in (ss, st, sc, ts, tt, tc)):
                raise AnalyzerError("invalid SQL Server key metadata")
            if (ss.casefold(), st.casefold()) not in tables or (
                    ts.casefold(), tt.casefold()) not in tables:
                raise AnalyzerError("orphaned SQL Server key metadata")
            keys.append((ss.casefold(), st.casefold(), sc.casefold(),
                         ts.casefold(), tt.casefold(), tc.casefold(),
                         bool(disabled), bool(untrusted)))
        inventories[database] = {"tables": tables, "keys": keys}
    return inventories


def render(inventories, backend: str):
    if set(inventories) != set(TABLES):
        raise AnalyzerError("incomplete database inventory")
    result = {
        "schema_version": SCHEMA, "backend": backend, "status": "metadata_only",
        "source_rows_read": False, "original_xml_sql_read": False,
        "cross_database_snapshot_verified": False, "record_joins_verified": False,
        "selected_vehicle_profile_verified": False, "d2_baud_verified": False,
        "readvin_execution_verified": False, "client_vin_accepted": False,
        "replay_approved": False, "databases": {}, "edges": []
    }
    resolved = {}
    for database, hints in TABLES.items():
        tables = inventories[database]["tables"]
        fixed = {}
        for name, required in hints.items():
            matches = [(key, cols) for key, cols in tables.items()
                       if key[1] == name.casefold()]
            if len(matches) > 1:
                raise AnalyzerError("ambiguous known table across SQL schemas")
            columns = matches[0][1] if matches else set()
            fixed[name] = {
                "present": bool(matches), "column_count": len(columns),
                "known_columns_present": [c for c in required if c.casefold() in columns],
                "known_columns_missing": [c for c in required if c.casefold() not in columns],
            }
        resolved[database] = fixed
        result["databases"][database] = {
            "table_count": len(tables),
            "column_count": sum(len(cols) for cols in tables.values()),
            "declared_fk_column_count": len(inventories[database]["keys"]),
            "known_tables": fixed,
        }
    for kind, hints in (
        ("service_shape", CANDIDATE_EDGES),
        ("hardware_shape", HARDWARE_CANDIDATE_EDGES),
    ):
        for database, src, src_col, dst, dst_col in hints:
            left, right = resolved[database][src], resolved[database][dst]
            present = (left["present"] and right["present"]
                       and src_col in left["known_columns_present"]
                       and dst_col in right["known_columns_present"])
            result["edges"].append({
                "database": database, "source": src, "target": dst,
                "source_column": src_col, "target_column": dst_col,
                "evidence": kind, "column_shape_present": present,
                "referential_rows_verified": False,
            })
    # Return only pre-approved table/column identifiers. Unknown proprietary
    # table/column names from catalog discovery never reach JSON.
    for database, entry in inventories.items():
        known = {name.casefold(): (name, {c.casefold() for c in cols})
                 for name, cols in TABLES[database].items()}
        for _, src, sc, _, dst, dc, disabled, untrusted in entry["keys"]:
            if src not in known or dst not in known:
                continue
            src_name, src_cols = known[src]
            dst_name, dst_cols = known[dst]
            if sc not in src_cols or dc not in dst_cols:
                continue
            # Verify full known-table presence; do not infer matches from bare names.
            if not (resolved[database][src_name]["present"]
                    and resolved[database][dst_name]["present"]):
                continue
            src_column = next(c for c in TABLES[database][src_name] if c.casefold() == sc)
            dst_column = next(c for c in TABLES[database][dst_name] if c.casefold() == dc)
            result["edges"].append({
                "database": database, "source": src_name, "target": dst_name,
                "source_column": src_column, "target_column": dst_column,
                "evidence": "sqlserver_declared_fk",
                "fk_disabled": disabled, "fk_untrusted": untrusted,
                "referential_rows_verified": False,
            })
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="Offline read-only VIDA schema inventory")
    ap.add_argument("--backend", choices=("sqlite-export", "sqlserver"), required=True)
    ap.add_argument("--folder", type=Path, help="Owner-local SQLite export copies")
    ap.add_argument("--output", type=Path, required=True, help="New private JSON outside Git")
    args = ap.parse_args(argv)
    try:
        checkout = Path(__file__).resolve().parents[2]
        out = args.output.resolve()
        if out == checkout or checkout in out.parents:
            raise AnalyzerError("output inside repository")
        if not args.output.parent.is_dir():
            raise AnalyzerError("output parent is missing")
        if args.backend == "sqlite-export":
            if args.folder is None:
                raise AnalyzerError("missing SQLite folder")
            if out in {(args.folder / (db + ".sqlite")).resolve() for db in TABLES}:
                raise AnalyzerError("output aliases input")
            inventories = load_sqlite_export(args.folder)
        else:
            if args.folder is not None:
                raise AnalyzerError("SQL Server backend does not use a folder")
            inventories = load_sqlserver(os.environ.get("VIDA_SQLSERVER_DSN", ""))
        report = render(inventories, args.backend)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True, indent=2)
            stream.write("\n")
        print("VIDA schema graph generated (metadata only; VIN acceptance unverified).")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
