#!/usr/bin/env python3
"""Private/offline VIDA *schema-only* CarCom to ReadVin relationship preflight.

Reads only previously exported _vida_meta, _vida_tables, and _vida_columns
metadata from three owner-local SQLite files. NEVER queries source user tables,
XML/ZIP/BLOB, original SQL definitions, data values, or live VIDA. Every emitted
name comes from the fixed allowlists below. Candidate edges are column-shape
hypotheses only, not verified joins or authenticated vehicle profiles.
"""
from __future__ import annotations
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

SCHEMA = "virtualcar-vida-carcom-schema-preflight-v2"
EXPORT_SCHEMA = "virtualcar-vida-offline-sqlite-v1"
MAX_TABLES = 1000
MAX_COLUMNS = 30000

# Only exporter-owned catalog tables; never inspect proprietary source tables.
# Checking the actual cursor schema avoids SQLite's double-quoted-string
# fallback silently returning a missing identifier as a string literal.
METADATA_COLUMNS = {
    "_vida_meta": ("key", "value"),
    "_vida_tables": ("schema_name", "table_name", "rows_exported"),
    "_vida_columns": ("schema_name", "table_name", "column_name", "system_type_id"),
}

# Original PR #200's research catalog schema, not yet confirmed on this owner's
# SQLite exporter. Unknown original columns are counted but never printed.
TABLES = {
    "CarCom": {
        "T111_Service": ("id", "service", "mode", "fkT122_Protocol"),
        "T122_Protocol": ("id", "identifier"),
        "T110_Service_EcuVariant": ("fkT100_EcuVariant", "fkT111_Service"),
        "T100_EcuVariant": ("id", "identifier", "fkT101_Ecu"),
        "T101_Ecu": ("id",),
        "T160_DefaultEcuVariant": ("fkT161_Profile", "fkT100_EcuVariant"),
        "T161_Profile": ("id", "identifier", "folderLevel"),
        # Candidate setting lookup from independently published VIDA 2014D
        # research. These are allowlisted *names*, not observed target schema.
        "T121_Config": ("id", "busRate", "addressSize", "fkT122_Protocol", "fkT123_Bus"),
        "T123_Bus": ("id", "identifier"),
        "T130_Init": ("id",),
        "T131_InitValue": ("fkT130_Init", "fkT132_InitValueType", "initValue", "sortOrder"),
        "T132_InitValueType": ("id", "name"),
        "T136_InitHw_Profile": ("fkT161_Profile", "fkT130_Init"),
    },
    "DiagSwdlRepository": {
        "ScriptType": ("id", "description"),
        "Script": ("id",),
        "ScriptContent": (),
        "ScriptProfileMap": ("fkProfile", "fkScript"),
    },
    "BaseData": {},
}

# Exact source/target/column hints, not actual FK constraints or matched rows.
CANDIDATE_EDGES = (
    ("CarCom", "T111_Service", "fkT122_Protocol", "T122_Protocol", "id"),
    ("CarCom", "T110_Service_EcuVariant", "fkT111_Service", "T111_Service", "id"),
    ("CarCom", "T110_Service_EcuVariant", "fkT100_EcuVariant", "T100_EcuVariant", "id"),
    ("CarCom", "T100_EcuVariant", "fkT101_Ecu", "T101_Ecu", "id"),
    ("CarCom", "T160_DefaultEcuVariant", "fkT161_Profile", "T161_Profile", "id"),
    ("CarCom", "T160_DefaultEcuVariant", "fkT100_EcuVariant", "T100_EcuVariant", "id"),
)

# Distinct optional hardware/init *column shape* hypotheses from
# spnda/volvo_vida_db/scripts/carcom.py@get_hw_settings (2014D port).
# Never promote them to real baud, gateway or a chosen profile.
HARDWARE_CANDIDATE_EDGES = (
    ("CarCom", "T136_InitHw_Profile", "fkT161_Profile", "T161_Profile", "id"),
    ("CarCom", "T136_InitHw_Profile", "fkT130_Init", "T130_Init", "id"),
    ("CarCom", "T131_InitValue", "fkT130_Init", "T130_Init", "id"),
    ("CarCom", "T131_InitValue", "fkT132_InitValueType", "T132_InitValueType", "id"),
    ("CarCom", "T121_Config", "fkT122_Protocol", "T122_Protocol", "id"),
    ("CarCom", "T121_Config", "fkT123_Bus", "T123_Bus", "id"),
)


class PreflightError(Exception):
    """Generic errors; private input strings never appear in error output."""


def _read_catalog(path: Path, expected: str) -> tuple[dict, dict]:
    if not path.is_file() or path.is_symlink():
        raise PreflightError("missing or redirected database")
    # An immutable SQLite open ignores an active WAL or rollback journal.
    # Refuse partial/inconsistent single-file exporter snapshots.
    if any(path.with_name(path.name + suffix).exists()
           or path.with_name(path.name + suffix).is_symlink()
           for suffix in ("-wal", "-shm", "-journal")):
        raise PreflightError("incomplete SQLite exporter snapshot")
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        # SQLite permits SELECT "missing_name" to return a string literal on
        # some builds. Verify the real columns first, without reading any rows.
        for table, required in METADATA_COLUMNS.items():
            try:
                # Fixed catalog identifiers must be ordinary main tables.
                # A view or virtual table could indirectly read user payloads.
                entries = db.execute("PRAGMA table_list('" + table + "')").fetchmany(2)
                if (len(entries) != 1 or entries[0][0].casefold() != 'main'
                        or entries[0][1].casefold() != table.casefold()
                        or entries[0][2] != 'table'):
                    raise PreflightError("unsafe exporter catalog object type")
                cursor = db.execute(f'SELECT * FROM "{table}" LIMIT 0')
                actual = tuple(field[0].casefold() for field in cursor.description)
            except sqlite3.DatabaseError:
                raise PreflightError("invalid exporter metadata schema") from None
            if len(actual) != len(set(actual)) or not all(
                    col.casefold() in actual for col in required):
                raise PreflightError("invalid exporter metadata schema")
        meta_rows = db.execute('SELECT "key", "value" FROM "_vida_meta"').fetchall()
        if len(meta_rows) != len({k for k, _ in meta_rows}):
            raise PreflightError("ambiguous export identity")
        meta = dict(meta_rows)
        if (meta.get("schema_version") != EXPORT_SCHEMA
                or meta.get("source_database") != expected
                or meta.get("scope") != "all_user_tables"):
            raise PreflightError("unexpected export identity")

        table_rows = db.execute(
            'SELECT "schema_name", "table_name", "rows_exported" FROM "_vida_tables"'
        ).fetchmany(MAX_TABLES + 1)
        if not table_rows or len(table_rows) > MAX_TABLES:
            raise PreflightError("invalid table catalog size")
        observed = {}
        for schema, table, count in table_rows:
            if (not isinstance(schema, str) or not isinstance(table, str)
                    or not isinstance(count, int) or count < 0):
                raise PreflightError("invalid table metadata")
            key = (schema.casefold(), table.casefold())
            if key in observed:
                raise PreflightError("ambiguous table catalog")
            observed[key] = count
        column_rows = db.execute(
            'SELECT "schema_name", "table_name", "column_name", "system_type_id" '
            'FROM "_vida_columns"'
        ).fetchmany(MAX_COLUMNS + 1)
        if len(column_rows) > MAX_COLUMNS:
            raise PreflightError("excessive catalog columns")
        columns = {}
        for schema, table, col, system_type_id in column_rows:
            if (not isinstance(schema, str) or not isinstance(table, str)
                    or not isinstance(col, str) or not isinstance(system_type_id, int)):
                raise PreflightError("invalid column metadata")
            key = (schema.casefold(), table.casefold())
            if key not in observed:
                raise PreflightError("orphaned catalog column")
            names = columns.setdefault(key, set())
            norm = col.casefold()
            if norm in names:
                raise PreflightError("ambiguous catalog column")
            names.add(norm)
        # Every exported user table must have visible catalog columns.
        # Missing columns are an incomplete export, not an absent profile.
        if any(not columns.get(key) for key in observed):
            raise PreflightError("incomplete table column inventory")
        # Fail closed on duplicate *fixed* table matches across SQL schemas.
        fixed = {}
        for name, wanted in TABLES[expected].items():
            hits = [(key, count) for key, count in observed.items()
                    if key[1] == name.casefold()]
            if len(hits) > 1:
                raise PreflightError("ambiguous fixed table across schemas")
            if not hits:
                fixed[name] = {"present": False, "declared_rows": None,
                               "column_count": 0, "expected_columns_present": [],
                               "expected_columns_missing": list(wanted)}
                continue
            key, count = hits[0]
            have = columns.get(key, set())
            fixed[name] = {"present": True, "declared_rows": count,
                           "column_count": len(have),
                           "expected_columns_present": [col for col in wanted
                                                        if col.casefold() in have],
                           "expected_columns_missing": [col for col in wanted
                                                        if col.casefold() not in have]}
        return {"export_scope_verified": True, "catalog_table_count": len(observed),
                "catalog_column_count": len(column_rows), "fixed_tables": fixed}, fixed


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise PreflightError("missing or redirected folder")
    parts, fixed = {}, {}
    for db in TABLES:
        parts[db], fixed[db] = _read_catalog(folder / (db + ".sqlite"), db)
    edges = []
    for db, source, source_col, target, target_col in CANDIDATE_EDGES:
        left, right = fixed[db][source], fixed[db][target]
        plausible = (left["present"] and right["present"]
                     and source_col in left["expected_columns_present"]
                     and target_col in right["expected_columns_present"])
        edges.append({"source_table": source, "target_table": target,
                      "column_shape_present": plausible,
                      "data_join_verified": False, "referential_integrity_verified": False})
    hardware_edges = []
    for db, source, source_col, target, target_col in HARDWARE_CANDIDATE_EDGES:
        left, right = fixed[db][source], fixed[db][target]
        plausible = (left["present"] and right["present"]
                     and source_col in left["expected_columns_present"]
                     and target_col in right["expected_columns_present"])
        hardware_edges.append({
            "source_table": source,
            "target_table": target,
            "column_shape_present": plausible,
            "data_join_verified": False,
            "referential_integrity_verified": False,
        })
    # A complete-looking route is necessary but not sufficient to resolve
    # inherited InitHw settings: profile selection and folderLevel precedence
    # still require source rows and original implementation verification.
    hw_value_shape = (
        all(edge["column_shape_present"] for edge in hardware_edges[:4])
        and "folderLevel" in fixed["CarCom"]["T161_Profile"]["expected_columns_present"]
        and "initValue" in fixed["CarCom"]["T131_InitValue"]["expected_columns_present"]
        and "name" in fixed["CarCom"]["T132_InitValueType"]["expected_columns_present"]
    )
    return {"schema_version": SCHEMA, "status": "schema_only",
            "read_only": True, "contains_source_rows": False,
            "contains_original_column_names_outside_allowlist": False,
            "contains_vin_or_carcom_payload": False,
            "cross_database_transactional_snapshot_verified": False,
            "getscript_runtime_selection_verified": False,
            "readvin_service_link_verified": False,
            "xc90_v8_my2009_profile_verified": False,
            "client_vin_accepted": False,
            "replay_approved": False,
            "hardware_init_value_column_shape_present": hw_value_shape,
            "hardware_init_profile_priority_verified": False,
            "d2_baud_from_original_data_verified": False,
            "d2_baud_inferred_from_ggd_forbidden": True,
            "databases": parts, "edge_shape_candidates": edges,
            "hardware_edge_shape_candidates": hardware_edges}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only VIDA metadata-only T111/T122 schema preflight")
    parser.add_argument("--folder", required=True, type=Path,
                        help="private 9-database export folder")
    parser.add_argument("--output", required=True, type=Path,
                        help="new private redacted JSON outside checkout")
    args = parser.parse_args(argv)
    # Export from the checkout is forbidden even if output is itself redacted:
    # avoid an accidental git add of a result derived from proprietary data.
    checkout = Path(__file__).resolve().parents[2]
    try:
        output = args.output.resolve()
        if output == checkout or checkout in output.parents:
            raise PreflightError("output inside checkout")
        input_files = [args.folder / (name + ".sqlite") for name in TABLES]
        if output in [p.resolve() for p in input_files]:
            raise PreflightError("output aliases input")
        result = audit(args.folder)
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, sort_keys=True, indent=2)
            f.write("\n")
        print("VIDA CarCom schema preflight complete; actual joins and VIN remain unverified.")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
