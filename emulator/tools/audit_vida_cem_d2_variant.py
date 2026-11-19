#!/usr/bin/env python3
"""Owner-local, read-only CarCom lookup for the XC90 V8 MY2009 D2 CEM candidate.

Output preserves exact source configuration/service values, but never VIN, SQL
credentials, XML, full database tables, or arbitrary profile identifiers.
The result is catalogue evidence only, NOT proof of an ECU in a real vehicle.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

import audit_vida_carcom_aggregate_joins as base

SCHEMA = "virtualcar-vida-cem-d2-variant-local-v1"
CANDIDATE = "31296075 AA"  # DriveRAP: diagnostic candidate, not VIN match
EXTRA_TABLES = {
    "T120_Config_EcuVariant": ("fkT100_EcuVariant", "fkT121_Config"),
    "T121_Config": ("id", "commAddress", "busRate", "canIdTX", "canIdRX",
                    "fkT122_Protocol", "fkT123_Bus"),
    "T123_Bus": ("id", "identifier"),
}
MAX_ROUTES = 64
MAX_SERVICES = 256


class VariantAuditError(Exception):
    """No private schema names, SQL values, or paths in CLI errors."""


def _resolve_extra(db: sqlite3.Connection) -> dict:
    catalog = db.execute(
        'SELECT "schema_name","table_name","rows_exported" FROM "_vida_tables"'
    ).fetchmany(base.MAX_CATALOG_TABLES + 1)
    columns = db.execute(
        'SELECT "schema_name","table_name","column_name" FROM "_vida_columns"'
    ).fetchmany(base.MAX_CATALOG_COLUMNS + 1)
    if len(catalog) > base.MAX_CATALOG_TABLES or len(columns) > base.MAX_CATALOG_COLUMNS:
        raise VariantAuditError("catalog_too_large")
    physical = [x[0] for x in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")]
    result = {}
    for table, required in EXTRA_TABLES.items():
        matches = [(s, c) for s, n, c in catalog
                   if isinstance(n, str) and n.casefold() == table.casefold()]
        if len(matches) != 1:
            raise VariantAuditError("missing_or_ambiguous_extra_table")
        schema, expected_count = matches[0]
        if not isinstance(schema, str) or not base._ALLOWED_SCHEMA.fullmatch(schema):
            raise VariantAuditError("invalid_schema")
        if type(expected_count) is not int or not 0 <= expected_count <= base.MAX_APPROVED_ROWS:
            raise VariantAuditError("invalid_table_count")
        cols = [c for s, n, c in columns if isinstance(s, str) and
                isinstance(n, str) and s.casefold() == schema.casefold() and
                n.casefold() == table.casefold()]
        if not all(isinstance(c, str) for c in cols):
            raise VariantAuditError("invalid_column_metadata")
        if len(cols) != len({c.casefold() for c in cols}):
            raise VariantAuditError("duplicate_column_metadata")
        if not {c.casefold() for c in required}.issubset({c.casefold() for c in cols}):
            raise VariantAuditError("missing_required_column")
        expected_names = {table.casefold(), (schema + "." + table).casefold(),
                          (schema + "_" + table).casefold(),
                          (schema + "__" + table).casefold()}
        candidates = [n for n in physical if isinstance(n, str) and
                      n.casefold() in expected_names]
        if len(candidates) != 1:
            raise VariantAuditError("missing_or_ambiguous_physical_table")
        quoted = base._q(candidates[0])
        actual_cols = [r[1] for r in db.execute("PRAGMA table_xinfo(" + quoted + ")")]
        if len(actual_cols) != len({c.casefold() for c in actual_cols}):
            raise VariantAuditError("duplicate_physical_columns")
        if not {c.casefold() for c in required}.issubset({c.casefold() for c in actual_cols}):
            raise VariantAuditError("missing_physical_column")
        if db.execute("SELECT COUNT(*) FROM " + quoted).fetchone()[0] != expected_count:
            raise VariantAuditError("export_count_mismatch")
        result[table] = {"quoted": quoted}
    return result


def _value(v):
    if v is None:
        return None
    if type(v) is int and -(2 ** 63) <= v < 2 ** 63:
        return v
    if type(v) is str and len(v) <= 64 and all(32 <= ord(c) <= 126 for c in v):
        return v
    raise VariantAuditError("unexpected_source_value_type")


def _unique_id(db, table):
    if db.execute('SELECT 1 FROM ' + table +
                  ' GROUP BY "id" HAVING COUNT(*)>1 LIMIT 1').fetchone():
        raise VariantAuditError("duplicate_reference_key")


def inspect(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise VariantAuditError("invalid_private_folder")
    source = folder / "CarCom.sqlite"
    if not source.is_file() or source.is_symlink():
        raise VariantAuditError("invalid_private_source")
    if any(Path(str(source) + s).exists() for s in ("-wal", "-shm", "-journal")):
        raise VariantAuditError("uncheckpointed_export_sidecar")
    with closing(sqlite3.connect(source.resolve().as_uri() +
                                 "?mode=ro&immutable=1", uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        tables = base._resolve_tables(db, base._one_catalog(db))
        tables.update(_resolve_extra(db))
        for t in ("T100_EcuVariant", "T111_Service", "T121_Config",
                  "T122_Protocol", "T123_Bus"):
            _unique_id(db, tables[t]["quoted"])
        def get(table):
            return tables[table]["quoted"]
        ev, cfg, mapping = (get(t) for t in ("T100_EcuVariant", "T121_Config",
                                            "T120_Config_EcuVariant"))
        pro, bus = get("T122_Protocol"), get("T123_Bus")
        service, service_map, defaults = (get(t) for t in
            ("T111_Service", "T110_Service_EcuVariant", "T160_DefaultEcuVariant"))
        matches = db.execute('SELECT "id" FROM ' + ev +
                             ' WHERE "identifier"=? LIMIT 2', (CANDIDATE,)).fetchall()
        if len(matches) > 1:
            raise VariantAuditError("ambiguous_variant_identifier")
        report = {
            "schema_version": SCHEMA,
            "candidate": CANDIDATE,
            "vehicle": "XC90 MY2009 B8444S - catalog applicability only",
            "source": "owner_local_CarCom_sqlite_export",
            "source_is_original_sql_server": False,
            "read_only": True,
            "variant_found_in_export": bool(matches),
            "default_profile_link_count": 0,
            "routes": [],
            "services": [],
            "selected_by_live_vida": False,
            "exact_vehicle_variant_verified": False,
            "d2_speed_verified_by_client": False,
            "ecu_response_verified": False,
            "security_access_verified": False,
            "replay_approved": False,
        }
        if not matches:
            return report
        key = matches[0][0]
        if key is None:
            raise VariantAuditError("null_variant_key")
        count = db.execute('SELECT COUNT(*) FROM ' + defaults +
                           ' WHERE "fkT100_EcuVariant"=?', (key,)).fetchone()[0]
        if type(count) is not int or not 0 <= count <= base.MAX_APPROVED_ROWS:
            raise VariantAuditError("invalid_profile_count")
        report["default_profile_link_count"] = count
        config_rows = db.execute(
            'SELECT c."commAddress",c."busRate",c."canIdTX",c."canIdRX",'
            'p."identifier",b."identifier" FROM ' + mapping +
            ' AS m JOIN ' + cfg + ' AS c ON c."id"=m."fkT121_Config"'
            ' LEFT JOIN ' + pro + ' AS p ON p."id"=c."fkT122_Protocol"'
            ' LEFT JOIN ' + bus + ' AS b ON b."id"=c."fkT123_Bus"'
            ' WHERE m."fkT100_EcuVariant"=? ORDER BY c."id" LIMIT ?',
            (key, MAX_ROUTES + 1)
        ).fetchall()
        if len(config_rows) > MAX_ROUTES:
            raise VariantAuditError("route_limit")
        report["routes"] = [
            dict(zip(("comm_address", "bus_rate", "can_id_tx", "can_id_rx",
                      "protocol", "bus"), map(_value, row)))
            for row in config_rows
        ]
        service_rows = db.execute(
            'SELECT s."service",s."mode",p."identifier" FROM ' + service_map +
            ' AS l JOIN ' + service + ' AS s ON s."id"=l."fkT111_Service"'
            ' LEFT JOIN ' + pro + ' AS p ON p."id"=s."fkT122_Protocol"'
            ' WHERE l."fkT100_EcuVariant"=? ORDER BY s."id" LIMIT ?',
            (key, MAX_SERVICES + 1)
        ).fetchall()
        if len(service_rows) > MAX_SERVICES:
            raise VariantAuditError("service_limit")
        report["services"] = [
            dict(zip(("service", "mode", "protocol"), map(_value, row)))
            for row in service_rows
        ]
        return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Owner-local exact CEM D2 catalog lookup")
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        checkout = Path(__file__).resolve().parents[2]
        output = args.output.resolve()
        if output == checkout or checkout in output.parents:
            raise VariantAuditError("output_inside_checkout")
        if output == (args.folder / "CarCom.sqlite").resolve():
            raise VariantAuditError("output_overlaps_source")
        if args.output.is_symlink() or args.output.exists():
            raise VariantAuditError("existing_output")
        report = inspect(args.folder)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
        print("Local CEM D2 catalog lookup complete; report stays private.")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
