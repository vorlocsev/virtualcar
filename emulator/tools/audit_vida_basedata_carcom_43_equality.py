#!/usr/bin/env python3
"""Read-only, aggregate-only candidate BaseData-to-CarCom profile-ID equality.

Checks a publicly documented *candidate* equality:
BaseData.VehicleProfile.Id = CarCom.T161_Profile.identifier. Neither this
2014D research-port relation nor a count of 43 proves actual VIDA 2015A
profile selection, inherited CEM settings, ReadVin or ECU discovery.
No original IDs, labels, profiles, VIN or raw rows leave the process.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack, closing
import json
from pathlib import Path
import sqlite3
import sys
import time

from audit_vida_basedata_exact_labels import _lookup
from audit_vida_basedata_xc90_candidates import _candidate_keys
from audit_vida_profile_fk_counts import (
    MAX_RUN_SECONDS, SchemaError, _catalog, _physical, _quoted,
)

BASE_REQUIRED = {
    "VehicleProfile": ("Id", "fkVehicleModel", "fkModelYear", "fkEngine"),
    "VehicleModel": ("Id", "Description"),
    "ModelYear": ("Id", "Description"),
    "Engine": ("Id", "Description"),
}
CARCOM_REQUIRED = {
    "T161_Profile": ("id", "identifier",
                     "fkT162_ProfileValue_Model",
                     "fkT162_ProfileValue_Year",
                     "fkT162_ProfileValue_Engine"),
    "T162_ProfileValue": ("id",),
}
EXPECTED_EXACT = 43
MAX_MODEL_PROFILE_FETCH = 1001


def _open_private(stack: ExitStack, folder: Path, name: str) -> sqlite3.Connection:
    path = folder / (name + ".sqlite")
    if path.is_symlink() or not path.is_file():
        raise SchemaError("missing or linked private SQLite source")
    if any(Path(str(path) + ext).exists() for ext in ("-wal", "-shm", "-journal")):
        raise SchemaError("uncheckpointed SQLite source sidecar")
    con = stack.enter_context(closing(
        sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1",
                        uri=True, timeout=5)
    ))
    con.execute("PRAGMA query_only=ON")
    start = time.monotonic()
    con.set_progress_handler(
        lambda: int(time.monotonic() - start >= MAX_RUN_SECONDS), 20000
    )
    return con


def _profile_ids(db: sqlite3.Connection, profile: str, model: object,
                 year: object, engine: object) -> list:
    sql = (
        "SELECT " + _quoted("Id") + " FROM " + profile +
        " WHERE " + _quoted("fkVehicleModel") + "=? AND " +
        _quoted("fkModelYear") + "=? AND " +
        _quoted("fkEngine") + "=? LIMIT " + str(MAX_MODEL_PROFILE_FETCH)
    )
    return [row[0] for row in db.execute(sql, (model, year, engine))]


def _normalized_key(value: object) -> str:
    # BaseData.Id is an opaque private identifier. Decimals from integer
    # SQLite IDs are converted losslessly to their text representation.
    if type(value) is int and value >= 0:
        return str(value)
    if type(value) is str and (0 < len(value) <= 128 and
                               value == value.strip() and
                               not any(ord(c) < 32 or ord(c) == 127 for c in value)):
        return value
    raise SchemaError("unsupported or invalid source profile Id")


def _compare(db: sqlite3.Connection, table: str, private_ids: list) -> dict:
    if len(private_ids) != EXPECTED_EXACT:
        raise SchemaError("source set is not exactly 43")
    names = [_normalized_key(x) for x in private_ids]
    if len({x.casefold() for x in names}) != EXPECTED_EXACT:
        raise SchemaError("duplicate original selected profile identifiers")
    missing = ambiguous = unique = 0
    matched_keys = set()
    sql = ("SELECT " + _quoted("id") + " FROM " + table +
           " WHERE " + _quoted("identifier") + "=? LIMIT 3")
    for name in names:
        rows = db.execute(sql, (name,)).fetchall()
        if not rows:
            missing += 1
        elif len(rows) != 1 or rows[0][0] is None:
            ambiguous += 1
        else:
            key = (type(rows[0][0]).__name__, rows[0][0])
            if key in matched_keys:
                ambiguous += 1
            else:
                matched_keys.add(key)
                unique += 1
    if missing + ambiguous + unique != EXPECTED_EXACT:
        raise SchemaError("profile cross-reference does not reconcile")
    return {
        "source_profile_count": EXPECTED_EXACT,
        "carcom_exact_identifier_unique_matches": unique,
        "carcom_exact_identifier_missing": missing,
        "carcom_exact_identifier_ambiguous": ambiguous,
        "all_43_have_unique_exact_identifier_matches":
            unique == EXPECTED_EXACT and missing == 0 and ambiguous == 0,
    }


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("unsafe local source folder")
    with ExitStack() as stack:
        base = _open_private(stack, folder, "BaseData")
        carcom = _open_private(stack, folder, "CarCom")
        base_catalog = _catalog(base, "BaseData")
        carcom_catalog = _catalog(carcom, "CarCom")
        for label, catalog, required in (
            ("base", base_catalog, BASE_REQUIRED),
            ("carcom", carcom_catalog, CARCOM_REQUIRED),
        ):
            for table, columns in required.items():
                if not set(x.casefold() for x in columns).issubset(catalog[table]["cols"]):
                    raise SchemaError("missing source profile cross-reference column")
        base_tables = _physical(base, base_catalog, BASE_REQUIRED)
        carcom_tables = _physical(carcom, carcom_catalog, CARCOM_REQUIRED)
        model_candidates = _candidate_keys(
            base, base_tables["VehicleModel"],
            base_catalog["VehicleModel"]["rows"]
        )
        year_state, year_id = _lookup(base, base_tables, "ModelYear", "2009")
        engine_state, engine_id = _lookup(base, base_tables, "Engine", "B8444S")
        counts = None
        gate = "lookup_unresolved"
        if year_state == "one" and engine_state == "one":
            candidates = [
                ids for key in model_candidates
                if (ids := _profile_ids(
                    base, base_tables["VehicleProfile"], key, year_id, engine_id
                ))
            ]
            if len(candidates) != 1:
                gate = "no_unique_profile_bearing_model"
            elif len(candidates[0]) != EXPECTED_EXACT:
                gate = "candidate_profile_count_not_43"
            else:
                counts = _compare(
                    carcom, carcom_tables["T161_Profile"], candidates[0]
                )
                gate = "source_identifier_equality_classified"
        return {
            "schema_version": "virtualcar-vida-basedata-carcom-43-id-equality-v1",
            "status": "owner_private_offline_candidate_equality_only",
            "source": "immutable_local_basedata_and_carcom_exports",
            "source_rows_read": True,
            "source_writes_performed": False,
            "xc90_prefix_model_candidate_count": len(model_candidates),
            "year_lookup": year_state,
            "engine_lookup": engine_state,
            "cross_reference_gate": gate,
            "counts": counts,
            "candidate_equality_rule": "basedata_vehicleprofile_id_eq_carcom_t161_identifier",
            "candidate_equality_not_original_sqlserver_constraint": True,
            "original_profile_selection_provenance_verified": False,
            "same_as_prior_43_selection_verified": False,
            "carcom_profile_inheritance_verified": False,
            "original_vida_runtime_profile_selected": False,
            "original_vida_readvin_accepted": False,
            "original_private_ids_or_labels_exported": False,
            "private_profile_list_files_created": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Owner-private 43-profile ID equality count")
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
