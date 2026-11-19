#!/usr/bin/env python3
"""Count fixed profile FK relations in owner-private immutable VIDA SQLite exports.

No profile identifiers, VIN, source rows, names/values, or cross-database
join keys are output. This is NOT recreation of the XC90 V8 MY2009 43 profiles.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time

from inspect_vida_profile_selection_schema import (
    EXPORT_ID, MAX_COLUMNS, MAX_TABLES, NAME, SchemaError, _ordinary_catalog,
)

EDGES = {
    "BaseData": (
        ("VehicleProfile", "fkVehicleModel", "VehicleModel", "Id", "vehicle_model"),
        ("VehicleProfile", "fkModelYear", "ModelYear", "Id", "model_year"),
        ("VehicleProfile", "fkEngine", "Engine", "Id", "engine"),
    ),
    "CarCom": (
        ("T161_Profile", "fkT162_ProfileValue_Model", "T162_ProfileValue", "id", "model"),
        ("T161_Profile", "fkT162_ProfileValue_Year", "T162_ProfileValue", "id", "year"),
        ("T161_Profile", "fkT162_ProfileValue_Engine", "T162_ProfileValue", "id", "engine"),
    ),
}
NEEDED = {
    "BaseData": {
        "VehicleProfile": ("Id", "fkVehicleModel", "fkModelYear", "fkEngine"),
        "VehicleModel": ("Id",),
        "ModelYear": ("Id",),
        "Engine": ("Id",),
    },
    "CarCom": {
        "T161_Profile": ("id", "fkT162_ProfileValue_Model",
                         "fkT162_ProfileValue_Year", "fkT162_ProfileValue_Engine"),
        "T162_ProfileValue": ("id",),
    },
}
MAX_REQUIRED_ROWS = 1_000_000
MAX_RUN_SECONDS = 90


def _quoted(name: str) -> str:
    if not isinstance(name, str) or not NAME.fullmatch(name):
        raise SchemaError("unsafe schema identifier")
    return '"' + name + '"'


def _catalog(db: sqlite3.Connection, name: str) -> dict:
    _ordinary_catalog(db)
    meta_rows = db.execute(
        'SELECT "key","value" FROM "_vida_meta"').fetchmany(65)
    if not meta_rows or len(meta_rows) >= 65:
        raise SchemaError("invalid exporter identity")
    meta = dict(meta_rows)
    if (len(meta) != len(meta_rows) or
            meta.get("schema_version") != EXPORT_ID or
            meta.get("source_database") != name or
            meta.get("scope") != "all_user_tables"):
        raise SchemaError("unexpected exporter identity")
    rows = db.execute(
        'SELECT "schema_name","table_name","rows_exported" FROM "_vida_tables"'
    ).fetchmany(MAX_TABLES + 1)
    cols = db.execute(
        'SELECT "schema_name","table_name","column_name" FROM "_vida_columns"'
    ).fetchmany(MAX_COLUMNS + 1)
    if not rows or len(rows) > MAX_TABLES or len(cols) > MAX_COLUMNS:
        raise SchemaError("unbounded exporter catalog")
    all_tables = {}
    for schema, table, count in rows:
        if (not isinstance(schema, str) or not isinstance(table, str)
                or not NAME.fullmatch(schema) or not NAME.fullmatch(table)
                or type(count) is not int or count < 0):
            raise SchemaError("invalid table catalog row")
        key = (schema.casefold(), table.casefold())
        if key in all_tables:
            raise SchemaError("ambiguous source table")
        all_tables[key] = {"schema": schema, "table": table, "rows": count, "cols": set()}
    for schema, table, col in cols:
        if (not isinstance(schema, str) or not isinstance(table, str)
                or not isinstance(col, str) or not NAME.fullmatch(col)):
            raise SchemaError("invalid column catalog")
        key = (schema.casefold(), table.casefold())
        if key not in all_tables:
            raise SchemaError("orphan column catalog")
        values = all_tables[key]["cols"]
        if col.casefold() in values:
            raise SchemaError("duplicate source column")
        values.add(col.casefold())
    if any(not v["cols"] for v in all_tables.values()):
        raise SchemaError("missing source column inventory")
    selected = {}
    for table, needed in NEEDED[name].items():
        candidates = [v for k, v in all_tables.items() if k[1] == table.casefold()]
        if len(candidates) != 1:
            raise SchemaError("missing or ambiguous required table")
        entry = candidates[0]
        if entry["rows"] > MAX_REQUIRED_ROWS:
            raise SchemaError("source table exceeds bounded scope")
        if not set(x.casefold() for x in needed).issubset(entry["cols"]):
            raise SchemaError("required source column absent")
        selected[table] = entry
    return selected


def _physical(db: sqlite3.Connection, catalog: dict, needed: dict) -> dict:
    rows = db.execute(
        "SELECT name,type FROM sqlite_schema WHERE type IN ('table','view')"
    ).fetchall()
    result = {}
    for table, entry in catalog.items():
        schema = entry["schema"]
        candidates = {
            table.casefold(),
            (schema + "." + table).casefold(),
            (schema + "_" + table).casefold(),
            (schema + "__" + table).casefold(),
        }
        hits = [(n, t) for n, t in rows if isinstance(n, str) and n.casefold() in candidates]
        if len(hits) != 1 or hits[0][1] != "table":
            raise SchemaError("missing or non-ordinary source table")
        physical = hits[0][0]
        q = _quoted(physical)
        # Reject virtual/shadow/view and unexpected columns before user SELECT.
        details = db.execute("PRAGMA table_list(" + q + ")").fetchall()
        if (len(details) != 1 or details[0][1] != physical or
                details[0][2] != "table" or details[0][0] != "main"):
            raise SchemaError("unsupported physical SQLite object")
        actual_columns = db.execute("PRAGMA table_xinfo(" + q + ")").fetchall()
        if (not actual_columns or any(r[6] != 0 for r in actual_columns)
                or len(actual_columns) != len({r[1].casefold() for r in actual_columns})):
            raise SchemaError("unexpected source physical columns")
        if not set(x.casefold() for x in needed[table]).issubset(
                {r[1].casefold() for r in actual_columns}):
            raise SchemaError("required physical column absent")
        count = db.execute("SELECT COUNT(*) FROM " + q).fetchone()[0]
        if type(count) is not int or count != entry["rows"]:
            raise SchemaError("catalog and physical source row counts disagree")
        result[table] = q
    return result


def _count_edge(db: sqlite3.Connection, tables: dict, edge: tuple) -> dict:
    source, fk, target, pk, label = edge
    s, t = tables[source], tables[target]
    qs, qp = _quoted(fk), _quoted(pk)
    # Group target first: duplicate IDs never multiply the source-row count.
    sql = (
        "WITH target_keys AS (SELECT " + qp + " AS key, COUNT(*) AS hits "
        " FROM " + t + " WHERE " + qp + " IS NOT NULL GROUP BY " + qp + ") "
        " SELECT COUNT(*), "
        " COALESCE(SUM(CASE WHEN s." + qs + " IS NULL THEN 1 ELSE 0 END),0), "
        " COALESCE(SUM(CASE WHEN s." + qs + " IS NOT NULL "
        " AND target_keys.hits IS NULL THEN 1 ELSE 0 END),0), "
        " COALESCE(SUM(CASE WHEN target_keys.hits=1 THEN 1 ELSE 0 END),0), "
        " COALESCE(SUM(CASE WHEN target_keys.hits>1 THEN 1 ELSE 0 END),0) "
        " FROM " + s + " AS s "
        " LEFT JOIN target_keys ON s." + qs + "=target_keys.key"
    )
    all_rows, null_fk, missing, unique, ambiguous = db.execute(sql).fetchone()
    if (any(type(x) is not int or x < 0 for x in (all_rows, null_fk, missing, unique, ambiguous))
            or null_fk + missing + unique + ambiguous != all_rows):
        raise SchemaError("inconsistent scoped profile FK totals")
    return {
        "dimension": label, "source_rows": all_rows,
        "null_fk_rows": null_fk, "missing_target_rows": missing,
        "unique_target_rows": unique, "ambiguous_target_rows": ambiguous,
        "all_source_keys_unambiguous": missing == 0 and ambiguous == 0,
        "original_sqlserver_fk_verified": False,
        "xc90_v8_my2009_profile_selected": False,
    }


def _read_one(folder: Path, name: str) -> dict:
    dbpath = folder / (name + ".sqlite")
    if dbpath.is_symlink() or not dbpath.is_file():
        raise SchemaError("missing owner SQLite copy")
    if any(Path(str(dbpath) + ext).exists() for ext in ("-wal", "-shm", "-journal")):
        raise SchemaError("offline export has active sidecar")
    uri = dbpath.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        started = time.monotonic()
        db.set_progress_handler(lambda: int(time.monotonic() - started >= MAX_RUN_SECONDS), 20000)
        catalog = _catalog(db, name)
        physical = _physical(db, catalog, NEEDED[name])
        edges = [_count_edge(db, physical, e) for e in EDGES[name]]
        for e in edges:
            if e["source_rows"] != catalog[EDGES[name][0][0]]["rows"]:
                raise SchemaError("source profile count mismatch")
        return {
            "profile_table_rows": catalog[EDGES[name][0][0]]["rows"],
            "candidate_fk_edges": edges,
        }


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("unsafe offline export directory")
    results = {name: _read_one(folder, name) for name in ("BaseData", "CarCom")}
    return {
        "schema_version": "virtualcar-vida-profile-fk-aggregates-v1",
        "status": "offline_sqlite_aggregate_only",
        "source": "owner_private_immutable_sqlite_export",
        "original_identifiers_exported": False,
        "cross_database_profile_mapping_verified": False,
        "original_selection_of_43_reconstructed": False,
        "exact_xc90_v8_my2009_profile_verified": False,
        "effective_cem_protocol_or_baud_verified": False,
        "runtime_vida_readvin_accepted": False,
        "source_writes_performed": False,
        "databases": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Private VIDA profile FK aggregate audit; count-only")
    ap.add_argument("--folder", type=Path, required=True)
    args = ap.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
