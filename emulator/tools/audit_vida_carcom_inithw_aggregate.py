#!/usr/bin/env python3
"""VIDA CarCom: offline InitHw and bus-setting evidence, aggregate-only.

This tool reads only the eight approved tables in one private CarCom.sqlite copy,
plus exporter identity/table/column metadata. It emits counts, not source
rows or identifiers. A SQLite join is not proof of SQL Server FK semantics,
active VIDA script selection, an authentic MY2009 profile, or a bus reply.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys

SCHEMA = "virtualcar-vida-inithw-aggregate-joins-v1"
EXPORT_SCHEMA = "virtualcar-vida-offline-sqlite-v1"
TABLES = {
    "T136_InitHw_Profile": ("fkT161_Profile", "fkT130_Init"),
    "T161_Profile": ("id", "identifier", "folderLevel"),
    "T130_Init": ("id",),
    "T131_InitValue": ("fkT130_Init", "fkT132_InitValueType", "initValue", "sortOrder"),
    "T132_InitValueType": ("id", "name"),
    "T121_Config": ("id", "busRate", "fkT122_Protocol", "fkT123_Bus"),
    "T122_Protocol": ("id", "identifier"),
    "T123_Bus": ("id", "identifier"),
}
# The six owner-confirmed column SHAPES; target-row matching itself is unverified.
EDGES = (
    ("T136_InitHw_Profile", "fkT161_Profile", "T161_Profile", "id"),
    ("T136_InitHw_Profile", "fkT130_Init", "T130_Init", "id"),
    ("T131_InitValue", "fkT130_Init", "T130_Init", "id"),
    ("T131_InitValue", "fkT132_InitValueType", "T132_InitValueType", "id"),
    ("T121_Config", "fkT122_Protocol", "T122_Protocol", "id"),
    ("T121_Config", "fkT123_Bus", "T123_Bus", "id"),
)
VALUE_COLUMNS = (
    ("T161_Profile", "folderLevel"),
    ("T131_InitValue", "initValue"),
    ("T132_InitValueType", "name"),
    ("T121_Config", "busRate"),
)
MAX_CATALOG_TABLES = 1000
MAX_CATALOG_COLUMNS = 30000
MAX_APPROVED_ROWS = 1000000
_ALLOWED_SQLITE_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,127}\Z")
_ALLOWED_SCHEMA = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,30}\Z")


class AuditError(Exception):
    """Safe category only; never print input names, paths or SQL diagnostics."""


def _q(name):
    if not isinstance(name, str) or not _ALLOWED_SQLITE_NAME.fullmatch(name):
        raise AuditError("untrusted physical table or column identifier")
    return '"' + name + '"'


def _one_catalog(db):
    meta_rows = db.execute('SELECT "key","value" FROM "_vida_meta"').fetchmany(20)
    if len(meta_rows) != len({x[0] for x in meta_rows}):
        raise AuditError("duplicate or invalid exporter metadata")
    meta = dict(meta_rows)
    if (meta.get("schema_version") != EXPORT_SCHEMA
            or meta.get("source_database") != "CarCom"
            or meta.get("scope") != "all_user_tables"):
        raise AuditError("unexpected source database")
    declared = db.execute(
        'SELECT "schema_name","table_name","rows_exported" FROM "_vida_tables"'
    ).fetchmany(MAX_CATALOG_TABLES + 1)
    if not declared or len(declared) > MAX_CATALOG_TABLES:
        raise AuditError("invalid catalog size")
    rows = {}
    for schema, name, count in declared:
        if not isinstance(schema, str) or not isinstance(name, str):
            raise AuditError("invalid catalog schema")
        key = (schema.casefold(), name.casefold())
        if key in rows or type(count) is not int or count < 0:
            raise AuditError("ambiguous catalog metadata")
        rows[key] = count
    cols = db.execute(
        'SELECT "schema_name","table_name","column_name" FROM "_vida_columns"'
    ).fetchmany(MAX_CATALOG_COLUMNS + 1)
    if len(cols) > MAX_CATALOG_COLUMNS:
        raise AuditError("too many columns")
    colsets = {}
    for schema, name, column in cols:
        if not all(isinstance(x, str) for x in (schema, name, column)):
            raise AuditError("invalid column metadata")
        key = (schema.casefold(), name.casefold())
        if key not in rows:
            raise AuditError("orphaned metadata column")
        col = column.casefold()
        seen = colsets.setdefault(key, set())
        if col in seen:
            raise AuditError("ambiguous metadata column")
        seen.add(col)
    targets = {}
    for table, required in TABLES.items():
        hits = [(schema, n) for schema, n in rows if n == table.casefold()]
        if len(hits) != 1:
            raise AuditError("missing or ambiguous expected table")
        key = hits[0]
        schema = key[0]
        if not _ALLOWED_SCHEMA.fullmatch(schema):
            raise AuditError("unexpected schema name")
        if not set(c.casefold() for c in required).issubset(colsets.get(key, set())):
            raise AuditError("required source columns missing")
        if rows[key] > MAX_APPROVED_ROWS:
            raise AuditError("source table beyond bounded scope")
        targets[table] = (schema, rows[key])
    return targets


def _resolve_tables(db, catalog):
    physical = db.execute(
        "SELECT name FROM sqlite_schema WHERE type='table'"
    ).fetchall()
    actual = [row[0] for row in physical if isinstance(row[0], str)]
    result = {}
    for table, (schema, expected_count) in catalog.items():
        # Only narrow, predictable SQLServer-to-SQLite exporter conventions.
        candidates = {
            table.casefold(),
            (schema + "." + table).casefold(),
            (schema + "_" + table).casefold(),
            (schema + "__" + table).casefold(),
        }
        hits = [name for name in actual if name.casefold() in candidates]
        if len(hits) != 1:
            raise AuditError("physical name is missing or ambiguous")
        name = hits[0]
        quoted = _q(name)
        # The *actual* table columns must match the exporter metadata too.
        found_columns = [row[1] for row in db.execute(
            "PRAGMA table_xinfo(" + quoted + ")"
        ).fetchall()]
        if len(found_columns) != len({c.casefold() for c in found_columns}):
            raise AuditError("ambiguous physical columns")
        if not set(c.casefold() for c in TABLES[table]).issubset(
                set(c.casefold() for c in found_columns)):
            raise AuditError("physical table missing required columns")
        actual_count = db.execute("SELECT COUNT(*) FROM " + quoted).fetchone()[0]
        if type(actual_count) is not int or actual_count != expected_count:
            raise AuditError("source table count differs from exporter catalog")
        result[table] = {"quoted": quoted, "rows": actual_count}
    return result


def _count_edge(db, mappings, source, fk, target, pk):
    source_table = mappings[source]["quoted"]
    target_table = mappings[target]["quoted"]
    source_col, target_col = _q(fk), _q(pk)
    # GROUP BY target first to avoid multiplying source rows when a target
    # contains ambiguous duplicate IDs; materializes up to 1M key groups.
    sql = (
        "WITH target_keys AS (SELECT t." + target_col +
        " AS k, COUNT(*) AS hits FROM " + target_table +
        " AS t WHERE t." + target_col +
        " IS NOT NULL GROUP BY t." + target_col + ") "
        "SELECT COUNT(*), "
        "COALESCE(SUM(CASE WHEN s." + source_col +
        " IS NULL THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN s." + source_col +
        " IS NOT NULL AND target_keys.hits IS NULL THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN target_keys.hits=1 THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN target_keys.hits>1 THEN 1 ELSE 0 END),0) "
        "FROM " + source_table + " AS s "
        "LEFT JOIN target_keys ON s." + source_col + " = target_keys.k"
    )
    total, nulls, missing, unique, ambiguous = db.execute(sql).fetchone()
    if total != mappings[source]["rows"] or total != nulls + missing + unique + ambiguous:
        raise AuditError("unreconciled relationship count")
    # Count duplicate target keys themselves, not values, IDs or source rows.
    dupe = db.execute(
        "SELECT COUNT(*) FROM (SELECT " + target_col +
        " FROM " + target_table + " WHERE " + target_col +
        " IS NOT NULL GROUP BY " + target_col + " HAVING COUNT(*)>1)"
    ).fetchone()[0]
    return {"source_table": source, "target_table": target,
            "source_row_count": total, "null_source_fk_rows": nulls,
            "missing_target_rows": missing, "unique_match_rows": unique,
            "ambiguous_match_rows": ambiguous,
            "duplicate_target_key_groups": dupe,
            "join_executed_against_offline_export": True,
            "original_sql_server_fk_verified": False}


def _null_presence(db, mappings, table, col):
    """Only total/null counts, never returns a hardware setting or VIN."""
    qtable = mappings[table]["quoted"]
    qcol = _q(col)
    total, missing = db.execute(
        "SELECT COUNT(*), COALESCE(SUM(CASE WHEN " + qcol +
        " IS NULL THEN 1 ELSE 0 END),0) FROM " + qtable
    ).fetchone()
    if total != mappings[table]["rows"] or not 0 <= missing <= total:
        raise AuditError("unreconciled setting presence")
    return {"table": table, "column": col, "total_rows": total,
            "null_rows": missing, "non_null_rows": total - missing,
            "values_disclosed": False, "selected_profile_verified": False}


def audit(folder):
    if not folder.is_dir() or folder.is_symlink():
        raise AuditError("missing owner-local dataset")
    file = folder / "CarCom.sqlite"
    if file.is_symlink() or not file.is_file():
        raise AuditError("untrusted SQLite source path")
    uri = file.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        catalog = _one_catalog(db)
        mappings = _resolve_tables(db, catalog)
        edges = [_count_edge(db, mappings, *edge) for edge in EDGES]
        value_presence = [_null_presence(db, mappings, *v) for v in VALUE_COLUMNS]
        return {
            "schema_version": SCHEMA,
            "status": "offline_sqlite_aggregate_only",
            "scope": "CarCom_eight_allowlisted_hardware_tables_and_six_edges",
            "value_presence": value_presence,
            "hardware_init_profile_priority_verified": False,
            "d2_baudrate_verified": False,
            "selected_xc90_v8_my2009_profile_verified": False,
            "may_infer_d2_rate_from_ggd": False,
            "contains_source_rows_ids_names_vin_payloads_or_hashes": False,
            "read_only": True,
            "all_fixed_table_counts_match_export_catalog": True,
            "cross_database_transactional_snapshot_verified": False,
            "original_sql_server_fk_semantics_verified": False,
            "runtime_readvin_script_selected": False,
            "original_cem_response_verified": False,
            "xc90_v8_my2009_profile_verified": False,
            "client_vin_accepted": False,
            "replay_approved": False,
            "edges": edges,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local VIDA InitHw aggregate-only FK and null inspection")
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        checkout = Path(__file__).resolve().parents[2]
        output = args.output.resolve()
        if output == checkout or checkout in output.parents:
            raise AuditError("refusing output inside checkout")
        if output == (args.folder / "CarCom.sqlite").resolve():
            raise AuditError("output aliases source database")
        data = audit(args.folder)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        print("CarCom InitHw aggregate audit complete; original setting values NOT exported.")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
