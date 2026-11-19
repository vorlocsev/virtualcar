#!/usr/bin/env python3
"""Aggregate-only BaseData VehicleProfile evidence for XC90-prefix candidates.

The source contains more than one XC90-prefixed VehicleModel description.
The tool counts model/year/engine profile relationships per candidate without
outputting model descriptions, IDs, VINs, or any private values. Counts are
sorted by numeric vector, not by source ID or private description. This is
NOT a recovered CarCom 43-profile selection or a VIDA runtime decision.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import sys
import time

from audit_vida_basedata_exact_labels import _lookup
from audit_vida_profile_fk_counts import (
    MAX_RUN_SECONDS, SchemaError, _catalog, _physical, _quoted,
)
from inspect_vida_basedata_model_labels import (
    MAX_DESCRIPTION_CHARS, MAX_MODEL_ROWS, PREFIX_XC90,
)

REQUIRED = {
    "VehicleProfile": ("Id", "fkVehicleModel", "fkModelYear", "fkEngine"),
    "VehicleModel": ("Id", "Description"),
    "ModelYear": ("Id", "Description"),
    "Engine": ("Id", "Description"),
}
MAX_CANDIDATES = 8
PROFILE_FIELDS = (
    "model_profiles_all_years",
    "model_profiles_year_2009_all_engines",
    "model_profiles_year_2009_engine_b8444s",
    "model_profiles_year_2009_engine_null",
    "model_profiles_year_null_engine_b8444s",
    "model_profiles_year_null_engine_null",
)


def _candidate_keys(db: sqlite3.Connection, model_table: str, row_count: int) -> list:
    if row_count > MAX_MODEL_ROWS:
        raise SchemaError("unbounded VehicleModel catalog")
    records = db.execute(
        "SELECT " + _quoted("Id") + "," + _quoted("Description") +
        " FROM " + model_table + " LIMIT ?",
        (MAX_MODEL_ROWS + 1,)
    ).fetchall()
    if len(records) != row_count:
        raise SchemaError("VehicleModel catalog row count changed")
    selected = []
    for key, label in records:
        if label is None:
            continue
        if not isinstance(label, str) or len(label) > MAX_DESCRIPTION_CHARS:
            raise SchemaError("invalid source model description")
        if PREFIX_XC90.match(label.strip().upper()):
            if key is None or isinstance(key, (bytes, bytearray, memoryview)):
                raise SchemaError("invalid matched model lookup key")
            selected.append(key)
            if len(selected) > MAX_CANDIDATES:
                raise SchemaError("too many model label candidates")
    if len(selected) != len(set(selected)):
        raise SchemaError("ambiguous matched model IDs")
    return selected


def _counts_for_model(db: sqlite3.Connection, profile_table: str,
                      model_key: object, year_key: object, engine_key: object) -> dict:
    model = _quoted("fkVehicleModel")
    year = _quoted("fkModelYear")
    engine = _quoted("fkEngine")
    sql = (
        "SELECT COUNT(*), "
        "COALESCE(SUM(CASE WHEN " + year + "=? THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN " + year + "=? AND " + engine + "=? "
        "THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN " + year + "=? AND " + engine + " IS NULL "
        "THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN " + year + " IS NULL AND " + engine + "=? "
        "THEN 1 ELSE 0 END),0), "
        "COALESCE(SUM(CASE WHEN " + year + " IS NULL AND " + engine + " IS NULL "
        "THEN 1 ELSE 0 END),0) "
        "FROM " + profile_table + " WHERE " + model + "=?"
    )
    values = db.execute(
        sql, (year_key, year_key, engine_key, year_key, engine_key, model_key)
    ).fetchone()
    if (values is None or len(values) != len(PROFILE_FIELDS) or
            any(type(v) is not int or v < 0 for v in values)):
        raise SchemaError("invalid numeric profile aggregate")
    all_count, year_count, exact_count, null_engine, null_year_engine, both_null = values
    if (not (0 <= exact_count + null_engine <= year_count <= all_count)
            or null_year_engine + both_null + year_count > all_count):
        raise SchemaError("inconsistent profile candidate counts")
    return dict(zip(PROFILE_FIELDS, values))


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("unsafe offline source directory")
    dbpath = folder / "BaseData.sqlite"
    if dbpath.is_symlink() or not dbpath.is_file():
        raise SchemaError("missing BaseData SQLite")
    if any(Path(str(dbpath) + ext).exists() for ext in ("-wal", "-shm", "-journal")):
        raise SchemaError("active source SQLite sidecar")
    uri = dbpath.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        start = time.monotonic()
        db.set_progress_handler(
            lambda: int(time.monotonic() - start >= MAX_RUN_SECONDS),
            20000,
        )
        catalog = _catalog(db, "BaseData")
        for table, required in REQUIRED.items():
            if not set(x.casefold() for x in required).issubset(catalog[table]["cols"]):
                raise SchemaError("missing exporter profile join columns")
        physical = _physical(db, catalog, REQUIRED)
        candidates = _candidate_keys(
            db, physical["VehicleModel"], catalog["VehicleModel"]["rows"]
        )
        year_state, year_key = _lookup(db, physical, "ModelYear", "2009")
        engine_state, engine_key = _lookup(db, physical, "Engine", "B8444S")
        result_counts = None
        if year_state == engine_state == "one" and candidates:
            vectors = [
                _counts_for_model(
                    db, physical["VehicleProfile"], key, year_key, engine_key
                ) for key in candidates
            ]
            # No arbitrary "model 1" linked to the secret Id/label;
            # sorted numerical vectors are deliberately not an identity map.
            result_counts = sorted(
                vectors, key=lambda v: tuple(v[field] for field in PROFILE_FIELDS),
                reverse=True,
            )
            if sum(v["model_profiles_all_years"] for v in result_counts) > catalog["VehicleProfile"]["rows"]:
                raise SchemaError("candidate rows exceed source table")
        return {
            "schema_version": "virtualcar-vida-basedata-xc90-candidate-counts-v1",
            "status": "candidate_profile_aggregate_only",
            "source": "owner_private_immutable_basedata_export",
            "source_rows_read": True,
            "source_writes_performed": False,
            "xc90_prefix_model_candidate_count": len(candidates),
            "year_description_lookup": year_state,
            "engine_description_lookup": engine_state,
            "candidate_count_vectors_sorted_numerically": result_counts,
            "candidate_counts_are_not_original_model_id_mapping": True,
            "private_model_labels_ids_or_profile_ids_emitted": False,
            "model_identity_resolved": False,
            "cross_database_profile_mapping_verified": False,
            "original_selection_of_43_reconstructed": False,
            "actual_vida_vehicle_profile_selection_verified": False,
            "original_vida_readvin_accepted": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Owner-only XC90 candidate model-year-engine counts")
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
