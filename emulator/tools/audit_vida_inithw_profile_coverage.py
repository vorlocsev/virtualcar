#!/usr/bin/env python3
"""Read-only, owner-local direct InitHw coverage for independently selected VIDA profiles.

Input: private newline-delimited T161_Profile.identifier sets, held only in
guest memory. Output: bounded aggregate counts with NO IDs, filenames, names,
VINs, original baud settings, or source rows. Comparison does NOT establish
inheritance, VIDA runtime priority, D2 route or an accepted VIN.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys

import audit_vida_carcom_inithw_aggregate as base

SCHEMA = "virtualcar-vida-profile-scoped-inithw-v1"
EXPECTED_EXACT = 43
MAX_GENERAL = 8
MAX_INPUT_BYTES = 16 * 1024
MAX_LINKS = 201


class CoverageError(Exception):
    """Sanitized only, never reveal owner-private profile strings."""


def _identifiers(path: Path, expected_min: int, expected_max: int) -> tuple[str, ...]:
    if path.is_symlink() or not path.is_file() or path.suffix.lower() != ".txt":
        raise CoverageError("unsafe private profile input")
    if not 0 < path.stat().st_size <= MAX_INPUT_BYTES:
        raise CoverageError("oversized or empty private profile input")
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except UnicodeError as exc:
        raise CoverageError("unsupported profile input encoding") from exc
    values = raw.splitlines()
    if not expected_min <= len(values) <= expected_max:
        raise CoverageError("unexpected private profile count")
    for value in values:
        if (not value or value != value.strip() or len(value) > 128 or
                any(ord(char) < 32 or ord(char) == 127 for char in value)):
            raise CoverageError("invalid private profile identifier")
    if len({x.casefold() for x in values}) != len(values):
        raise CoverageError("duplicate private profile identifier")
    return tuple(values)


def _summarize(db, tables: dict, names: tuple[str, ...]) -> dict:
    p = tables["T161_Profile"]["quoted"]
    h = tables["T136_InitHw_Profile"]["quoted"]
    v = tables["T131_InitValue"]["quoted"]
    ty = tables["T132_InitValueType"]["quoted"]
    matched = missing = ambiguous = with_direct = no_direct = multiple = 0
    link_count = null_links = duplicate_links = 0
    all_init_keys = set()

    for identifier in names:
        # A private identifier is ALWAYS bound as a parameter; never an SQL name.
        selected = db.execute(
            "SELECT \"id\" FROM " + p + " WHERE \"identifier\" = ?",
            (identifier,)
        ).fetchmany(3)
        if not selected:
            missing += 1
            continue
        if len(selected) != 1 or selected[0][0] is None:
            ambiguous += 1
            continue
        matched += 1
        local_rows = db.execute(
            "SELECT \"fkT130_Init\" FROM " + h + " WHERE \"fkT161_Profile\" = ?",
            (selected[0][0],)
        ).fetchmany(MAX_LINKS + 1)
        if len(local_rows) > MAX_LINKS:
            raise CoverageError("unbounded direct init links")
        if not local_rows:
            no_direct += 1
            continue
        with_direct += 1
        if len(local_rows) > 1:
            multiple += 1
        link_count += len(local_rows)
        local_keys = [row[0] for row in local_rows if row[0] is not None]
        null_links += len(local_rows) - len(local_keys)
        duplicate_links += len(local_keys) - len(set(local_keys))
        all_init_keys.update(local_keys)

    init_values = nonnull = lexical = distinct_types = 0
    if all_init_keys:
        if len(all_init_keys) > MAX_LINKS:
            raise CoverageError("unbounded selected init set")
        placeholders = ",".join("?" for _ in all_init_keys)
        # Only aggregate results leave SQLite, no actual setting name or value.
        sql = (
            "SELECT COUNT(*), "
            "COALESCE(SUM(CASE WHEN v.\"initValue\" IS NOT NULL THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(CASE WHEN EXISTS("
            " SELECT 1 FROM " + ty + " AS t "
            " WHERE t.\"id\" = v.\"fkT132_InitValueType\" AND ("
            " instr(lower(t.\"name\"),'baud')>0 OR "
            " instr(lower(t.\"name\"),'speed')>0"
            " )) THEN 1 ELSE 0 END),0), "
            "COUNT(DISTINCT v.\"fkT132_InitValueType\") "
            "FROM " + v + " AS v WHERE v.\"fkT130_Init\" IN (" + placeholders + ")"
        )
        init_values, nonnull, lexical, distinct_types = db.execute(
            sql, tuple(all_init_keys)
        ).fetchone()
    if matched + missing + ambiguous != len(names):
        raise CoverageError("unreconciled profile count")
    if matched != with_direct + no_direct or not (0 <= multiple <= with_direct):
        raise CoverageError("unreconciled coverage classes")
    if not (0 <= nonnull <= init_values and 0 <= lexical <= init_values):
        raise CoverageError("unreconciled init value counts")
    return {
        "input_profile_count": len(names),
        "unique_matched_profile_count": matched,
        "missing_profile_count": missing,
        "ambiguous_profile_count": ambiguous,
        "direct_init_profile_count": with_direct,
        "no_direct_init_profile_count": no_direct,
        "multiple_direct_init_profile_count": multiple,
        "direct_init_link_rows": link_count,
        "null_direct_init_links": null_links,
        "duplicate_direct_init_link_rows": duplicate_links,
        "distinct_linked_init_count": len(all_init_keys),
        "linked_init_value_rows": init_values,
        "linked_init_value_nonnull_rows": nonnull,
        "baud_or_speed_lexical_type_rows": lexical,
        "distinct_linked_value_types": distinct_types,
        "profile_parentage_or_inheritance_verified": False,
        "effective_d2_baudrate_verified": False,
    }


def audit(folder: Path, exact_file: Path, general_file: Path) -> dict:
    exact = _identifiers(exact_file, EXPECTED_EXACT, EXPECTED_EXACT)
    general = _identifiers(general_file, 1, MAX_GENERAL)
    if set(exact).intersection(general):
        raise CoverageError("overlapping profile selection groups")
    if (not folder.is_dir() or folder.is_symlink() or
            (folder / "CarCom.sqlite").is_symlink() or
            not (folder / "CarCom.sqlite").is_file()):
        raise CoverageError("untrusted owner-local database")
    dbpath = folder / "CarCom.sqlite"
    uri = dbpath.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        catalog = base._one_catalog(db)
        mapped = base._resolve_tables(db, catalog)
        report = {
            "schema_version": SCHEMA,
            "status": "owner_selected_profile_direct_coverage_only",
            "read_only": True,
            "owner_selection_provenance_independently_verified": False,
            "original_sql_server_collation_verified": False,
            "original_vida_get_inithw_settings_execution_verified": False,
            "original_profile_inheritance_priority_verified": False,
            "d2_baudrate_verified": False,
            "may_copy_ggd_rate_to_d2": False,
            "ecus_identified_on_wire": False,
            "client_vin_accepted": False,
            "replay_approved": False,
            "contains_original_profile_identifiers_names_values_or_vin": False,
            "fixed_exporter_tables_and_counts_checked": True,
            "exact_xc90_v8_my2009": _summarize(db, mapped, exact),
            "owner_selected_general_comparators": _summarize(db, mapped, general),
        }
        return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private VIDA direct InitHw profile coverage (counts only)")
    parser.add_argument("--folder", required=True, type=Path)
    parser.add_argument("--exact-profiles", required=True, type=Path)
    parser.add_argument("--general-profiles", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        checkout = Path(__file__).resolve().parents[2]
        output = args.output.resolve()
        if output == checkout or checkout in output.parents:
            raise CoverageError("output inside checkout")
        source_paths = (args.folder / "CarCom.sqlite", args.exact_profiles, args.general_profiles)
        if output in {p.resolve() for p in source_paths}:
            raise CoverageError("output aliases owner source")
        report = audit(args.folder, args.exact_profiles, args.general_profiles)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True, ensure_ascii=False, indent=2)
            stream.write("\n")
        print("Private profile coverage summarized; inheritance and D2 baud UNVERIFIED.")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
