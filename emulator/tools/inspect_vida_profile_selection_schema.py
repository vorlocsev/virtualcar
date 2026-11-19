#!/usr/bin/env python3
"""Read-only metadata preflight for locating original VIDA profile selection joins.

Reads only immutable owner-local SQLite exporter catalog tables, never user
rows. Prints bounded schema identifiers, not profile IDs or values.
Do NOT treat this as a profile selection or ECU/ReadVin verification.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys

DATABASES = ("CarCom", "BaseData")
EXPORT_ID = "virtualcar-vida-offline-sqlite-v1"
MAX_TABLES = 1000
MAX_COLUMNS = 30000
MAX_CANDIDATES = 24
MAX_TABLE_COLUMNS = 48
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,127}\Z")
RELEVANT = re.compile(r"profile|model|engine|vehicle|variant|year|chassis|vindecode|partner", re.I)


class SchemaError(Exception):
    """No source identifiers, values or paths in error messages."""


def _ordinary_catalog(db: sqlite3.Connection) -> None:
    for name in ("_vida_meta", "_vida_tables", "_vida_columns"):
        rows = db.execute(
            "SELECT type,sql FROM sqlite_schema WHERE name=?", (name,)
        ).fetchmany(2)
        if (len(rows) != 1 or rows[0][0] != "table" or
                not isinstance(rows[0][1], str) or
                "VIRTUAL" in rows[0][1].upper()):
            raise SchemaError("invalid exporter catalog object")


def _read_one(folder: Path, name: str) -> dict:
    dbpath = folder / (name + ".sqlite")
    if dbpath.is_symlink() or not dbpath.is_file():
        raise SchemaError("missing or linked private SQLite copy")
    if any(Path(str(dbpath) + ext).exists() for ext in ("-wal", "-shm", "-journal")):
        raise SchemaError("uncheckpointed SQLite export sidecar")
    uri = dbpath.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        _ordinary_catalog(db)
        meta_rows = db.execute(
            'SELECT "key","value" FROM "_vida_meta"'
        ).fetchmany(65)
        if len(meta_rows) >= 65 or any(len(row) != 2 for row in meta_rows):
            raise SchemaError("invalid exporter identity")
        try:
            meta = dict(meta_rows)
        except (TypeError, ValueError):
            raise SchemaError("invalid exporter identity") from None
        if (len(meta) != len(meta_rows) or
                meta.get("schema_version") != EXPORT_ID or
                meta.get("source_database") != name or
                meta.get("scope") != "all_user_tables"):
            raise SchemaError("unexpected exporter identity")
        rows = db.execute(
            'SELECT "schema_name","table_name" FROM "_vida_tables"'
        ).fetchmany(MAX_TABLES + 1)
        cols = db.execute(
            'SELECT "schema_name","table_name","column_name" FROM "_vida_columns"'
        ).fetchmany(MAX_COLUMNS + 1)
        if not rows or len(rows) > MAX_TABLES or len(cols) > MAX_COLUMNS:
            raise SchemaError("unbounded exporter schema catalog")
        tables = {}
        for schema, table in rows:
            if (not isinstance(schema, str) or not isinstance(table, str) or
                    not NAME.fullmatch(schema) or not NAME.fullmatch(table)):
                raise SchemaError("invalid source schema identifier")
            key = (schema.casefold(), table.casefold())
            if key in tables:
                raise SchemaError("ambiguous catalog table")
            tables[key] = (schema, table)
        columns = {key: {} for key in tables}
        for schema, table, column in cols:
            if not all(isinstance(v, str) for v in (schema, table, column)) or not NAME.fullmatch(column):
                raise SchemaError("invalid column metadata")
            key = (schema.casefold(), table.casefold())
            if key not in tables:
                raise SchemaError("orphan source catalog column")
            ckey = column.casefold()
            if ckey in columns[key]:
                raise SchemaError("ambiguous catalog column")
            columns[key][ckey] = column
        if any(not values for values in columns.values()):
            raise SchemaError("empty source table column inventory")
        selected = [(schema, table, key) for key, (schema, table) in tables.items()
                    if RELEVANT.search(table)]
        selected.sort(key=lambda t: (t[1].casefold(), t[0].casefold()))
        result = []
        for schema, table, key in selected[:MAX_CANDIDATES]:
            c = sorted(columns[key].values(), key=str.casefold)
            result.append({
                "table": table,
                "schema": schema,
                "columns": c[:MAX_TABLE_COLUMNS],
                "columns_truncated": len(c) > MAX_TABLE_COLUMNS,
            })
        return {
            "catalog_table_count": len(tables),
            "profile_related_table_count": len(selected),
            "profile_related_tables_truncated": len(selected) > MAX_CANDIDATES,
            "profile_related_tables": result,
        }


def inspect(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("unsafe offline VIDA directory")
    databases = {name: _read_one(folder, name) for name in DATABASES}
    return {
        "schema_version": "virtualcar-vida-profile-selection-schema-inventory-v1",
        "status": "metadata_only",
        "source": "owner_local_immutable_sqlite_exports",
        "source_rows_read": False,
        "original_profile_identifiers_emitted": False,
        "xc90_v8_my2009_membership_verified": False,
        "profile_join_or_selection_verified": False,
        "runtime_vida_profile_selected": False,
        "readvin_accepted": False,
        "databases": databases,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Private VIDA BaseData/CarCom schema preflight, metadata-only")
    p.add_argument("--folder", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        print(json.dumps(inspect(args.folder), ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
