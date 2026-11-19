#!/usr/bin/env python3
"""Owner-only, read-only XC90 MY2009 NULL-engine direct InitHw comparisons.

First independently matches 43 XC90/MY2009/B8444S BaseData profiles to
CarCom.T161_Profile. Separately selects BaseData XC90/MY2009 profiles whose
fkEngine is NULL, and counts ONLY their direct CarCom.T136_InitHw_Profile
links and the link-scoped InitValue rows. It does not infer that a generic
profile is an ancestor or that its settings are applied by VIDA 2015A.
No original IDs, names, settings, VIN or bus speeds leave the process.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import sys

from audit_vida_basedata_exact_labels import _lookup
from audit_vida_basedata_xc90_candidates import _candidate_keys
from audit_vida_basedata_carcom_43_equality import (
    BASE_REQUIRED, EXPECTED_EXACT, _open_private, _profile_ids,
    _compare, _normalized_key,
)
from audit_vida_basedata_carcom_43_direct_links import (
    CARCOM_REQUIRED, MAX_INITHW_PER_PROFILE,
    _bounded, _one,
)
from audit_vida_profile_fk_counts import SchemaError, _catalog, _physical, _quoted

INIT_REQUIRED = {
    **CARCOM_REQUIRED,
    "T130_Init": ("id",),
    "T131_InitValue": ("fkT130_Init", "fkT132_InitValueType", "initValue"),
    "T132_InitValueType": ("id", "name"),
}
MAX_GENERAL_CANDIDATES = 500
MAX_VALUES_PER_INIT = 128
MAX_UNIQUE_INITS = 500


def _generic_ids(db, table: str, model_id: object, year_id: object) -> list:
    sql = (
        'SELECT "Id" FROM ' + table +
        ' WHERE "fkVehicleModel"=? AND "fkModelYear"=? AND ' +
        '"fkEngine" IS NULL LIMIT ' + str(MAX_GENERAL_CANDIDATES + 1)
    )
    records = [row[0] for row in db.execute(sql, (model_id, year_id))]
    if len(records) > MAX_GENERAL_CANDIDATES:
        raise SchemaError("unbounded general profile candidate set")
    names = [_normalized_key(x) for x in records]
    if len(set(n.casefold() for n in names)) != len(names):
        raise SchemaError("duplicate BaseData general profile identifier")
    return names


def _summarize(db, tables: dict, names: list) -> dict:
    if len(names) > MAX_GENERAL_CANDIDATES:
        raise SchemaError("general set exceeds allowlist")
    p, h = tables["T161_Profile"], tables["T136_InitHw_Profile"]
    init, values, types = (
        tables["T130_Init"], tables["T131_InitValue"],
        tables["T132_InitValueType"],
    )
    profile_sql = 'SELECT "id" FROM ' + p + ' WHERE "identifier"=? LIMIT 3'
    links_sql = ('SELECT "fkT130_Init" FROM ' + h +
                 ' WHERE "fkT161_Profile"=? LIMIT ' +
                 str(MAX_INITHW_PER_PROFILE + 1))
    init_sql = 'SELECT "id" FROM ' + init + ' WHERE "id"=? LIMIT 3'
    rows_sql = ('SELECT "fkT132_InitValueType","initValue" FROM ' + values +
                ' WHERE "fkT130_Init"=? LIMIT ' + str(MAX_VALUES_PER_INIT + 1))
    type_sql = 'SELECT "name" FROM ' + types + ' WHERE "id"=? LIMIT 3'

    counts = {
        "general_source_profile_count": len(names),
        "general_carcom_unique_matches": 0,
        "general_carcom_missing": 0,
        "general_carcom_ambiguous": 0,
        "general_profiles_with_direct_inithw": 0,
        "general_profiles_without_direct_inithw": 0,
        "direct_inithw_link_rows": 0,
        "direct_inithw_null_target_rows": 0,
        "distinct_linked_init_rows": 0,
        "init_value_rows_on_distinct_linked_inits": 0,
        "init_value_nonnull_rows_on_distinct_linked_inits": 0,
        "init_type_name_baud_or_speed_lexical_rows": 0,
    }
    seen_carcom = set()
    linked_inits = set()
    for name in names:
        rows = db.execute(profile_sql, (name,)).fetchmany(3)
        if not rows:
            counts["general_carcom_missing"] += 1
            continue
        if len(rows) != 1 or rows[0][0] is None:
            counts["general_carcom_ambiguous"] += 1
            continue
        key = rows[0][0]
        tag = (type(key).__name__, key)
        if tag in seen_carcom:
            counts["general_carcom_ambiguous"] += 1
            continue
        seen_carcom.add(tag)
        counts["general_carcom_unique_matches"] += 1
        selected = _bounded(db, links_sql, (key,), MAX_INITHW_PER_PROFILE)
        counts["general_profiles_with_direct_inithw"] += int(bool(selected))
        counts["general_profiles_without_direct_inithw"] += int(not selected)
        counts["direct_inithw_link_rows"] += len(selected)
        for (init_id,) in selected:
            if init_id is None:
                counts["direct_inithw_null_target_rows"] += 1
                continue
            linked_inits.add((type(init_id).__name__, init_id))
            if len(linked_inits) > MAX_UNIQUE_INITS:
                raise SchemaError("unbounded linked InitHw set")

    for _, init_id in linked_inits:
        _one(db, init_sql, (init_id,))
        rows = _bounded(db, rows_sql, (init_id,), MAX_VALUES_PER_INIT)
        counts["init_value_rows_on_distinct_linked_inits"] += len(rows)
        for type_id, value in rows:
            if type_id is None:
                raise SchemaError("missing InitValue type reference")
            name = _one(db, type_sql, (type_id,))
            if not isinstance(name, str):
                raise SchemaError("invalid original InitValue type")
            counts["init_value_nonnull_rows_on_distinct_linked_inits"] += int(
                value is not None
            )
            normalized = name.casefold()
            counts["init_type_name_baud_or_speed_lexical_rows"] += int(
                "baud" in normalized or "speed" in normalized
            )
    counts["distinct_linked_init_rows"] = len(linked_inits)
    if (counts["general_source_profile_count"] !=
            counts["general_carcom_unique_matches"] +
            counts["general_carcom_missing"] +
            counts["general_carcom_ambiguous"] or
            counts["general_carcom_unique_matches"] !=
            counts["general_profiles_with_direct_inithw"] +
            counts["general_profiles_without_direct_inithw"] or
            counts["direct_inithw_null_target_rows"] >
            counts["direct_inithw_link_rows"] or
            counts["init_value_nonnull_rows_on_distinct_linked_inits"] >
            counts["init_value_rows_on_distinct_linked_inits"] or
            counts["init_type_name_baud_or_speed_lexical_rows"] >
            counts["init_value_rows_on_distinct_linked_inits"]):
        raise SchemaError("unreconciled general InitHw candidate counts")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("invalid offline export folder")
    with ExitStack() as stack:
        base = _open_private(stack, folder, "BaseData")
        carcom = _open_private(stack, folder, "CarCom")
        bc = _catalog(base, "BaseData")
        cc = _catalog(carcom, "CarCom", INIT_REQUIRED)
        for name, needed in BASE_REQUIRED.items():
            if not set(x.casefold() for x in needed).issubset(bc[name]["cols"]):
                raise SchemaError("missing source BaseData columns")
        for name, needed in INIT_REQUIRED.items():
            if not set(x.casefold() for x in needed).issubset(cc[name]["cols"]):
                raise SchemaError("missing source CarCom columns")
        bt = _physical(base, bc, BASE_REQUIRED)
        ct = _physical(carcom, cc, INIT_REQUIRED)

        models = _candidate_keys(
            base, bt["VehicleModel"], bc["VehicleModel"]["rows"]
        )
        ys, year_id = _lookup(base, bt, "ModelYear", "2009")
        es, engine_id = _lookup(base, bt, "Engine", "B8444S")
        gate = "source_lookup_unresolved"
        counts = None
        if ys == es == "one":
            candidates = [
                (model, ids) for model in models
                if (ids := _profile_ids(
                    base, bt["VehicleProfile"], model, year_id, engine_id
                ))
            ]
            if len(candidates) != 1:
                gate = "not_one_exact_profile_bearing_model"
            elif len(candidates[0][1]) != EXPECTED_EXACT:
                gate = "not_43_exact_profiles"
            elif not _compare(
                carcom, ct["T161_Profile"], candidates[0][1]
            )["all_43_have_unique_exact_identifier_matches"]:
                gate = "not_43_unique_carcom_identifiers"
            else:
                model, exact = candidates[0]
                generic = _generic_ids(
                    base, bt["VehicleProfile"], model, year_id
                )
                if set(_normalized_key(x).casefold() for x in exact).intersection(
                    x.casefold() for x in generic
                ):
                    raise SchemaError("overlapping exact and generic profiles")
                counts = _summarize(carcom, ct, generic)
                gate = "general_direct_inithw_counts_only"
        return {
            "schema_version": "virtualcar-vida-xc90-my2009-general-direct-inithw-v1",
            "status": "owner_private_general_profile_direct_only",
            "source": "owner_private_immutable_basedata_carcom_sqlite_exports",
            "source_rows_read": True,
            "source_writes_performed": False,
            "xc90_prefix_model_candidates": len(models),
            "year_lookup": ys,
            "engine_lookup": es,
            "gate": gate,
            "counts": counts,
            "original_profile_ids_names_settings_or_vin_exported": False,
            "general_candidates_are_ancestor_profiles_verified": False,
            "original_vida_2015a_inithw_runtime_selection_verified": False,
            "d2_baudrate_verified": False,
            "ggd_baudrate_may_be_copied_to_d2": False,
            "original_vida_readvin_accepted": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Owner-private XC90 MY2009 null-engine direct InitHw counts"
    )
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
