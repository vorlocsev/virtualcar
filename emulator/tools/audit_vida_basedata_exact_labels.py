#!/usr/bin/env python3
"""Read-only, exact-label preflight for owner-private BaseData XC90/MY2009/V8.

Checks three descriptive lookup tables and counts ONLY matching profile rows.
Never prints lookup Id values, private descriptions, profile identifiers or VIN.
An exact label match does not establish 43 CarCom profiles or VIDA selection.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time

from audit_vida_profile_fk_counts import (
    MAX_RUN_SECONDS, SchemaError, _catalog, _physical, _quoted,
)

EXPECTED = (
    ("VehicleModel", "XC90", "model"),
    ("ModelYear", "2009", "year"),
    ("Engine", "B8444S", "engine"),
)
REQUIRED = {
    "VehicleProfile": ("Id", "fkVehicleModel", "fkModelYear", "fkEngine"),
    "VehicleModel": ("Id", "Description"),
    "ModelYear": ("Id", "Description"),
    "Engine": ("Id", "Description"),
}


def _lookup(db: sqlite3.Connection, tables: dict, table: str, value: str) -> tuple[str, object | None]:
    # Bounded rows, no string/Id ever emitted to caller report.
    sql = (
        "SELECT " + _quoted("Id") + " FROM " + tables[table] +
        " WHERE TRIM(" + _quoted("Description") + ") = ? COLLATE NOCASE LIMIT 3"
    )
    rows = db.execute(sql, (value,)).fetchall()
    if not rows:
        return "zero", None
    if len(rows) > 1 or rows[0][0] is None:
        return "multiple_or_invalid", None
    return "one", rows[0][0]


def _count(db: sqlite3.Connection, table: str, predicates: tuple[str, ...],
           params: tuple) -> int:
    sql = "SELECT COUNT(*) FROM " + table + " WHERE " + " AND ".join(predicates)
    result = db.execute(sql, params).fetchone()
    if result is None or type(result[0]) is not int or result[0] < 0:
        raise SchemaError("invalid profile aggregate count")
    return result[0]


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("invalid owner-private SQLite folder")
    dbpath = folder / "BaseData.sqlite"
    if dbpath.is_symlink() or not dbpath.is_file():
        raise SchemaError("missing BaseData SQLite copy")
    if any(Path(str(dbpath) + ext).exists() for ext in ("-wal", "-shm", "-journal")):
        raise SchemaError("active SQLite sidecar")
    uri = dbpath.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        started = time.monotonic()
        db.set_progress_handler(
            lambda: int(time.monotonic() - started >= MAX_RUN_SECONDS), 20000
        )
        catalog = _catalog(db, "BaseData")
        # The general FK tool needs only Id in lookup tables; this stage
        # additionally requires Description in original exporter metadata.
        for table, names in REQUIRED.items():
            if not set(x.casefold() for x in names).issubset(catalog[table]["cols"]):
                raise SchemaError("missing required original description column")
        tables = _physical(db, catalog, REQUIRED)
        hits = {}
        keys = {}
        for table, label, dimension in EXPECTED:
            status, key = _lookup(db, tables, table, label)
            hits[dimension] = status
            keys[dimension] = key
        selected_counts = None
        if all(x == "one" for x in hits.values()):
            profile = tables["VehicleProfile"]
            model = _quoted("fkVehicleModel")
            year = _quoted("fkModelYear")
            engine = _quoted("fkEngine")
            selected_counts = {
                "exact_model_year_engine_rows": _count(
                    db, profile,
                    (model + "=?", year + "=?", engine + "=?"),
                    (keys["model"], keys["year"], keys["engine"]),
                ),
                "model_year_with_null_engine_rows": _count(
                    db, profile,
                    (model + "=?", year + "=?", engine + " IS NULL"),
                    (keys["model"], keys["year"]),
                ),
                "model_year_all_engine_rows": _count(
                    db, profile, (model + "=?", year + "=?"),
                    (keys["model"], keys["year"]),
                ),
            }
            if (selected_counts["exact_model_year_engine_rows"] +
                    selected_counts["model_year_with_null_engine_rows"] >
                    selected_counts["model_year_all_engine_rows"]):
                raise SchemaError("inconsistent source profile counts")
        return {
            "schema_version": "virtualcar-vida-basedata-exact-label-preflight-v1",
            "status": "exact_label_preflight_only",
            "source": "owner_private_immutable_basedata_export",
            "source_rows_read": True,
            "source_writes_performed": False,
            "lookup_match_classes": hits,
            "counts": selected_counts,
            "only_exact_description_matching": True,
            "private_lookup_ids_or_descriptions_emitted": False,
            "cross_database_profile_mapping_verified": False,
            "original_selection_of_43_reconstructed": False,
            "actual_vida_vehicle_profile_selection_verified": False,
            "original_readvin_accepted": False,
            "profile_lists_written": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Owner-only immutable BaseData label preflight")
    parser.add_argument("--folder", type=Path, required=True)
    options = parser.parse_args(argv)
    try:
        print(json.dumps(audit(options.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
