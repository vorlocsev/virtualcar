#!/usr/bin/env python3
"""Metadata-only offline VIDA catalog audit. No original user-table reads.

Only approved fixed paths and _vida_* exporter catalog tables are queried.
Matches against SQL module definitions are literal text evidence, NOT proof
that VIDA runs that diagnostic request or recognizes the virtual vehicle.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

DATABASES = (
    "DiagSwdlRepository", "CarCom", "BaseData", "DiagSwdlSession",
    "DiceTiming", "ImageRepository", "EPC", "servicerep_ru-RU", "AccessServer",
)
FOCUS = frozenset(("DiagSwdlRepository", "CarCom", "BaseData", "DiagSwdlSession"))
TERMS = {
    "ReadVin": "readvin", "GetScript": "getscript",
    "VehicleIdentity": "vehicleidentity", "VIN": "vin",
    "CEM": "cem", "XC90": "xc90", "F114": "f114",
    "B9FB": "b9fb", "AddVIN": "addvin", "SetX40Serial": "setx40serial",
}
ROLES = {
    "Script": "script", "ScriptType": "scripttype",
    "Vehicle": "vehicle", "VehicleType": "vehicletype",
    "Ecu": "ecu", "Unit": "unit",
}
ALLOWED_COLUMN_HINTS = frozenset((
    "id", "name", "description", "language", "languageid", "scriptid",
    "scripttypeid", "script", "xml", "zip", "content", "data", "payload",
    "binary", "vehicleid", "vin", "ecu", "ecuaddress", "address",
))
EXPECTED_SCHEMA = "virtualcar-vida-offline-sqlite-v1"


class CatalogError(Exception):
    """Safe error kind: never include private SQL data in console output."""


def _read_one(path: Path, expected: str) -> dict:
    if not path.is_file() or path.is_symlink():
        raise CatalogError("missing database or redirected path")
    # Full-export SQLite uses journal_mode DELETE. The copy is immutable here.
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        meta = dict(db.execute('SELECT "key","value" FROM "_vida_meta"'))
        if meta.get("schema_version") != EXPECTED_SCHEMA:
            raise CatalogError("export schema mismatch")
        if meta.get("source_database") != expected:
            raise CatalogError("database identity mismatch")
        if meta.get("scope") != "all_user_tables":
            raise CatalogError("partial export unsupported")

        tables = list(db.execute(
            'SELECT "schema_name","table_name","rows_exported" FROM "_vida_tables"'
        ))
        if not tables or any(not isinstance(t[2], int) or t[2] < 0 for t in tables):
            raise CatalogError("invalid catalog")
        roles = {role: 0 for role in ROLES}
        for _, table_name, _ in tables:
            for role, literal in ROLES.items():
                if table_name.casefold() == literal:
                    roles[role] += 1

        columns, blobs = 0, 0
        role_columns = {r: set() for r in ROLES}
        for _, table_name, col_name, stid in db.execute(
            'SELECT "schema_name","table_name","column_name","system_type_id" '
            'FROM "_vida_columns"'
        ):
            columns += 1
            if int(stid) in (34, 165, 173, 189):
                blobs += 1
            for role, literal in ROLES.items():
                if table_name.casefold() == literal and col_name.casefold() in ALLOWED_COLUMN_HINTS:
                    role_columns[role].add(col_name.casefold())

        fk = db.execute('SELECT count(*) FROM "_vida_foreign_keys"').fetchone()[0]
        idx = db.execute('SELECT count(*) FROM "_vida_indexes"').fetchone()[0]
        hits = {k: {"module_names": 0, "module_bodies": 0} for k in TERMS}
        module_count, unavailable = 0, 0
        for module_name, definition in db.execute(
            'SELECT "module_name","definition" FROM "_vida_modules"'
        ):
            module_count += 1
            unavailable += int(definition is None)
            # No original SQL source escapes this Python process.
            name = module_name.casefold()
            body = definition.casefold() if definition is not None else ""
            for term, literal in TERMS.items():
                hits[term]["module_names"] += int(literal in name)
                hits[term]["module_bodies"] += int(literal in body)

        result = {
            "tables": len(tables),
            "exported_rows": sum(row[2] for row in tables),
            "catalog_columns": columns,
            "binary_columns": blobs,
            "foreign_key_columns": fk,
            "index_key_columns": idx,
            "sql_modules": module_count,
            "sql_definitions_unavailable": unavailable,
        }
        if expected in FOCUS:
            result["known_role_table_counts"] = roles
            result["known_role_column_hints"] = {
                r: sorted(names) for r, names in role_columns.items() if names
            }
            result["literal_sql_module_hits"] = {
                term: count for term, count in hits.items()
                if count["module_names"] or count["module_bodies"]
            }
        return result


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise CatalogError("missing dataset directory")
    by_db = {name: _read_one(folder / (name + ".sqlite"), name) for name in DATABASES}
    return {
        "schema_version": "virtualcar-vida-offline-catalog-audit-v1",
        "status": "catalog-audited",
        "contains_source_records": False,
        "contains_vin_values": False,
        "contains_sql_definitions": False,
        "contains_raw_xml_or_zip": False,
        "read_only": True,
        "verified_hashes_in_this_audit": False,
        "database_count": len(by_db),
        "table_count": sum(x["tables"] for x in by_db.values()),
        "declared_row_count": sum(x["exported_rows"] for x in by_db.values()),
        "source_database_transactional_snapshot_verified": False,
        "sql_modules_executable_in_sqlite": False,
        "runtime_vehicle_identification_proven": False,
        "literal_matches_are_not_executed_requests": True,
        "databases": by_db,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Read-only VIDA SQLite catalog audit")
    parser.add_argument("--folder", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        # Never expose OS exception text, SQL definitions or original data.
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
