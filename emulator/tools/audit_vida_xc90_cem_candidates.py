#!/usr/bin/env python3
"""Private offline CarCom XC90 V8 MY2009 CEM default-candidate evidence.

Requires the 43 separately attested exact CarCom.T161_Profile identifiers and
1..8 owner-selected general comparator identifiers. The profile-generation
label is a catalog hint, not an input to the join or a selected ECU profile.
Returns only bounded aggregate counts. Never returns original IDs, VIN, CAN
payloads, config addresses, bus speeds or original source records.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys

SCHEMA = "virtualcar-xc90-v8-carcom-cem-candidates-v1"
EXPORT_SCHEMA = "virtualcar-vida-offline-sqlite-v1"
# Source column names are from existing original-CarCom schema research.
# Unknown layouts fail closed rather than guessing a name or alias.
TABLES = {
    "T161_Profile": ("id", "identifier"),
    "T160_DefaultEcuVariant": ("fkT161_Profile", "fkT100_EcuVariant"),
    "T100_EcuVariant": ("id", "fkT101_Ecu"),
    "T101_Ecu": ("id", "identifier"),
    "T120_Config_EcuVariant": ("fkT100_EcuVariant", "fkT121_Config"),
    "T121_Config": ("id", "fkT122_Protocol", "busRate"),
    "T122_Protocol": ("id", "identifier"),
}
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.]{0,127}\Z")
MAX_PROFILE_BYTES = 16 * 1024
MAX_ROWS = 1_000_000
MAX_LINKS_PER_PROFILE = 32
MAX_CONFIGS_PER_VARIANT = 32
MAX_METADATA_TABLES = 1_000
MAX_METADATA_COLUMNS = 30_000


class EvidenceError(Exception):
    """Never emit original profile strings or SQL details in messages."""


def quote(name: str) -> str:
    if not isinstance(name, str) or not IDENTIFIER.fullmatch(name):
        raise EvidenceError("unsafe schema identifier")
    return '"' + name + '"'


def load_identifiers(path: Path, low: int, high: int) -> tuple[str, ...]:
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".txt":
        raise EvidenceError("invalid owner-private input")
    if not 0 < path.stat().st_size <= MAX_PROFILE_BYTES:
        raise EvidenceError("invalid owner-private input size")
    try:
        records = path.read_text(encoding="utf-8-sig").splitlines()
    except UnicodeError as exc:
        raise EvidenceError("unsupported owner-private encoding") from exc
    if not low <= len(records) <= high or any(
        not v or v != v.strip() or len(v) > 128 or
        any(ord(c) < 32 or ord(c) == 127 for c in v) for v in records
    ):
        raise EvidenceError("invalid owner-private profile selection")
    if len({v.casefold() for v in records}) != len(records):
        raise EvidenceError("duplicate owner-private profiles")
    return tuple(records)


def resolve_tables(db: sqlite3.Connection) -> dict[str, str]:
    # Verify exporter identity and catalog before accessing source user rows.
    # Exporter catalog objects must be ordinary, trusted tables. Reject
    # virtual tables/views (including FTS) before reading their contents.
    for cat in ("_vida_meta", "_vida_tables", "_vida_columns"):
        schema = db.execute("SELECT type,sql FROM sqlite_schema WHERE name=?", (cat,)).fetchall()
        if len(schema) != 1 or schema[0][0] != "table" or not isinstance(schema[0][1], str) or "VIRTUAL" in schema[0][1].upper():
            raise EvidenceError("unsafe exporter catalog object")
    meta_rows = db.execute('SELECT "key", "value" FROM "_vida_meta"').fetchmany(32)
    if len(meta_rows) != len({k for k, _ in meta_rows}):
        raise EvidenceError("ambiguous exporter identity")
    meta = dict(meta_rows)
    if (meta.get("schema_version") != EXPORT_SCHEMA or
        meta.get("source_database") != "CarCom" or
        meta.get("scope") != "all_user_tables"):
        raise EvidenceError("wrong exporter dataset")
    entries = db.execute('SELECT "schema_name", "table_name", "rows_exported" FROM "_vida_tables"').fetchmany(MAX_METADATA_TABLES + 1)
    columns = db.execute('SELECT "schema_name", "table_name", "column_name" FROM "_vida_columns"').fetchmany(MAX_METADATA_COLUMNS + 1)
    if not entries or len(entries) > MAX_METADATA_TABLES or len(columns) > MAX_METADATA_COLUMNS:
        raise EvidenceError("unbounded exporter catalog")
    declared: dict[tuple[str, str], int] = {}
    for schema, table, count in entries:
        if (not isinstance(schema, str) or not isinstance(table, str) or
            not IDENTIFIER.fullmatch(schema) or not IDENTIFIER.fullmatch(table) or
            type(count) is not int or count < 0 or count > MAX_ROWS):
            raise EvidenceError("invalid exporter table")
        key = (schema.casefold(), table.casefold())
        if key in declared:
            raise EvidenceError("duplicate exporter table")
        declared[key] = count
    recorded: dict[tuple[str, str], set[str]] = {}
    for schema, table, column in columns:
        if not isinstance(schema, str) or not isinstance(table, str) or not isinstance(column, str) or not IDENTIFIER.fullmatch(column):
            raise EvidenceError("invalid exporter column")
        key = (schema.casefold(), table.casefold())
        if key not in declared:
            raise EvidenceError("orphan exporter column")
        names = recorded.setdefault(key, set())
        if column.casefold() in names:
            raise EvidenceError("duplicate exporter column")
        names.add(column.casefold())
    physical = [r[0] for r in db.execute("SELECT name FROM sqlite_schema WHERE type='table'")]
    result: dict[str, str] = {}
    for name, required in TABLES.items():
        keys = [key for key in declared if key[1] == name.casefold()]
        if len(keys) != 1:
            raise EvidenceError("missing or ambiguous required CarCom table")
        schema, lower = keys[0]
        if not {x.casefold() for x in required}.issubset(recorded.get(keys[0], set())):
            raise EvidenceError("missing required catalog columns")
        candidates = {name.casefold(), f"{schema}.{name}".casefold(), f"{schema}_{name}".casefold(), f"{schema}__{name}".casefold()}
        physical_matches = [x for x in physical if isinstance(x, str) and x.casefold() in candidates]
        if len(physical_matches) != 1:
            raise EvidenceError("ambiguous physical CarCom mapping")
        physical_name = physical_matches[0]
        q = quote(physical_name)
        col_names = [r[1] for r in db.execute("PRAGMA table_xinfo(" + q + ")")]
        if (len(col_names) != len({v.casefold() for v in col_names}) or
            not {x.casefold() for x in required}.issubset({x.casefold() for x in col_names})):
            raise EvidenceError("physical columns do not match exporter")
        if db.execute("SELECT COUNT(*) FROM " + q).fetchone()[0] != declared[keys[0]]:
            raise EvidenceError("physical row count differs from exporter")
        result[name] = q
    return result


def unique_one(db: sqlite3.Connection, sql: str, args: tuple) -> tuple:
    rows = db.execute(sql, args).fetchmany(2)
    if len(rows) != 1 or rows[0] is None or any(v is None for v in rows[0]):
        raise EvidenceError("missing or ambiguous linked CarCom row")
    return rows[0]


def bounded(db: sqlite3.Connection, sql: str, args: tuple, max_rows: int) -> list[tuple]:
    rows = db.execute(sql, args).fetchmany(max_rows + 1)
    if len(rows) > max_rows:
        raise EvidenceError("unbounded CarCom links")
    return rows


def summarize(db: sqlite3.Connection, tables: dict[str, str], names: tuple[str, ...]) -> dict:
    p, d = tables["T161_Profile"], tables["T160_DefaultEcuVariant"]
    v, ecu = tables["T100_EcuVariant"], tables["T101_Ecu"]
    bridge, cfg, proto = tables["T120_Config_EcuVariant"], tables["T121_Config"], tables["T122_Protocol"]
    counts = {
        "input_profiles": len(names), "profiles_with_defaults": 0,
        "profiles_without_defaults": 0, "direct_default_variant_rows": 0,
        "default_cem_variant_rows": 0, "default_other_ecu_rows": 0,
        "cem_variants_without_config": 0, "cem_config_rows": 0,
        "cem_d2_config_rows": 0, "cem_ggd_config_rows": 0,
        "cem_other_protocol_config_rows": 0,
        "cem_config_missing_bitrate_rows": 0,
    }
    for name in names:
        pid, = unique_one(db, f'SELECT "id" FROM {p} WHERE "identifier" = ?', (name,))
        defaults = bounded(db,
                           f'SELECT "fkT100_EcuVariant" FROM {d} WHERE "fkT161_Profile" = ?',
                           (pid,), MAX_LINKS_PER_PROFILE)
        if defaults:
            counts["profiles_with_defaults"] += 1
        else:
            counts["profiles_without_defaults"] += 1
        counts["direct_default_variant_rows"] += len(defaults)
        for (variant_id,) in defaults:
            if variant_id is None:
                raise EvidenceError("missing linked variant id")
            ecu_id, = unique_one(db, f'SELECT "fkT101_Ecu" FROM {v} WHERE "id" = ?', (variant_id,))
            ecu_name, = unique_one(db, f'SELECT "identifier" FROM {ecu} WHERE "id" = ?', (ecu_id,))
            if not isinstance(ecu_name, str) or ecu_name.strip().upper() != "CEM":
                counts["default_other_ecu_rows"] += 1
                continue
            counts["default_cem_variant_rows"] += 1
            configs = bounded(db,
                f'SELECT "fkT121_Config" FROM {bridge} WHERE "fkT100_EcuVariant" = ?',
                (variant_id,), MAX_CONFIGS_PER_VARIANT)
            if not configs:
                counts["cem_variants_without_config"] += 1
            for (cfg_id,) in configs:
                if cfg_id is None:
                    raise EvidenceError("missing linked config id")
                # Nullable busRate is intentional (D2 rows in original research).
                row = bounded(db, f'SELECT "fkT122_Protocol", "busRate" FROM {cfg} WHERE "id" = ?', (cfg_id,), 2)
                if len(row) != 1 or row[0][0] is None:
                    raise EvidenceError("missing or ambiguous linked config")
                proto_id, bus_rate = row[0]
                protocol, = unique_one(db, f'SELECT "identifier" FROM {proto} WHERE "id" = ?', (proto_id,))
                counts["cem_config_rows"] += 1
                if bus_rate is None:
                    counts["cem_config_missing_bitrate_rows"] += 1
                if isinstance(protocol, str) and protocol.strip().upper() == "D2":
                    counts["cem_d2_config_rows"] += 1
                elif isinstance(protocol, str) and protocol.strip().upper() == "GGD":
                    counts["cem_ggd_config_rows"] += 1
                else:
                    counts["cem_other_protocol_config_rows"] += 1
    if counts["input_profiles"] != counts["profiles_with_defaults"] + counts["profiles_without_defaults"]:
        raise EvidenceError("unreconciled profile aggregation")
    if counts["direct_default_variant_rows"] != counts["default_cem_variant_rows"] + counts["default_other_ecu_rows"]:
        raise EvidenceError("unreconciled ECU default aggregation")
    if counts["cem_config_rows"] != (counts["cem_d2_config_rows"] + counts["cem_ggd_config_rows"] + counts["cem_other_protocol_config_rows"]):
        raise EvidenceError("unreconciled protocol aggregation")
    return counts


def audit(folder: Path, exact_path: Path, general_path: Path) -> dict:
    exact = load_identifiers(exact_path, 43, 43)
    general = load_identifiers(general_path, 1, 8)
    if {x.casefold() for x in exact}.intersection(x.casefold() for x in general):
        raise EvidenceError("overlapping private profile groups")
    if folder.is_symlink() or not folder.is_dir():
        raise EvidenceError("unsafe CarCom folder")
    dbpath = folder / "CarCom.sqlite"
    if dbpath.is_symlink() or not dbpath.is_file():
        raise EvidenceError("unsafe CarCom file")
    if any(Path(str(dbpath) + suffix).exists() for suffix in ("-wal", "-shm", "-journal")):
        raise EvidenceError("potentially uncheckpointed SQLite copy")
    uri = dbpath.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        tables = resolve_tables(db)
        exact_out = summarize(db, tables, exact)
        general_out = summarize(db, tables, general)
    return {
        "schema_version": SCHEMA,
        "status": "owner_private_offline_carcom_default_candidate_counts_only",
        "vehicle_catalog_hint": {"model": "XC90", "model_year": 2009,
                                 "engine": "B8444S", "generation": "P2-Restyling",
                                 "platform_family": "P2"},
        "catalog_hint_is_not_carcom_profile_binding": True,
        "source": "owner_local_immutable_sqlite_export",
        "carcom_links_observed_in_source_copy": True,
        "owner_profile_selection_provenance_verified": False,
        "original_sql_server_fk_semantics_verified": False,
        "source_snapshot_consistent_with_original_sql_verified": False,
        "profile_parentage_or_effective_inithw_verified": False,
        "cem_hardware_h_l_verified": False,
        "d2_baudrate_from_null_inferred": False,
        "client_ecu_alive_verified": False,
        "actual_selected_vida_profile_verified": False,
        "original_vida_readvin_accepted": False,
        "response_fixture_selection_approved": False,
        "contains_owner_identifiers_vin_payloads_or_config_values": False,
        "exact_xc90_v8_my2009": exact_out,
        "general_profile_comparators": general_out,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only private CarCom XC90 CEM candidate aggregate")
    parser.add_argument("--folder", type=Path, required=True)
    parser.add_argument("--exact-profiles", type=Path, required=True)
    parser.add_argument("--general-profiles", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        repo = Path(__file__).resolve().parents[2]
        outputs = [args.folder / "CarCom.sqlite", args.exact_profiles, args.general_profiles]
        resolved_output = args.output.resolve()
        if resolved_output == repo or repo in resolved_output.parents:
            raise EvidenceError("output inside checkout")
        if resolved_output in {x.resolve() for x in outputs}:
            raise EvidenceError("source output alias")
        data = audit(args.folder, args.exact_profiles, args.general_profiles)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(data, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.write("\n")
        print("Completed aggregate-only CarCom candidate analysis; no ECU selected.")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
