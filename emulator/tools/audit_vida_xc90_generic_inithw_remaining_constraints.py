#!/usr/bin/env python3
"""Owner-private offline check of seven remaining CarCom T161 stored constraints.

For one XC90/MY2009/NULL-engine generic profile with a direct InitHw link,
compare seven remaining T161_Profile candidate dimension keys against 43
XC90/MY2009/B8444S exact profiles. Report only mutually exclusive counts,
never original IDs/names/values. NULL is not an asserted wildcard. Equal keys
are not a verified parentage or VIDA 2015A inheritance decision.
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
    MAX_INITHW_PER_PROFILE, _bounded, _one,
)
from audit_vida_basedata_xc90_general_inithw import _generic_ids
from audit_vida_xc90_generic_inithw_constraints import COMPAT_REQUIRED
from audit_vida_profile_fk_counts import SchemaError, _catalog, _physical, _quoted

DIMENSIONS = {
    "body": "fkT162_ProfileValue_Body",
    "chassis_from": "fkT162_ProfileValue_ChassisFrom",
    "chassis_to": "fkT162_ProfileValue_ChassisTo",
    "control_unit": "fkT162_ProfileValue_ControlUnit",
    "market": "fkT162_ProfileValue_Market",
    "steering": "fkT162_ProfileValue_Steering",
    "transmission": "fkT162_ProfileValue_Transmission",
}
EXT_REQUIRED = {
    **COMPAT_REQUIRED,
    "T161_Profile": (
        *COMPAT_REQUIRED["T161_Profile"], *DIMENSIONS.values(),
    ),
}
DIMENSION_KEYS = (
    "same_both_present",
    "different_both_present",
    "general_null",
    "exact_null_when_general_present",
)
MAX_DIRECT_LINKS = MAX_INITHW_PER_PROFILE


def _profile(db, table: str, identifier: str) -> tuple | None:
    cols = ('"id"', *(_quoted(col) for col in DIMENSIONS.values()))
    sql = (
        "SELECT " + ",".join(cols) + " FROM " + table +
        ' WHERE "identifier"=? LIMIT 3'
    )
    rows = db.execute(sql, (identifier,)).fetchmany(3)
    if not rows:
        return None
    if len(rows) != 1 or rows[0][0] is None:
        raise SchemaError("missing or ambiguous CarCom profile match")
    return rows[0]


def _aggregate(db, tables: dict, exact_ids: list, generic_ids: list) -> tuple[str, dict | None]:
    if len(exact_ids) != EXPECTED_EXACT or len(generic_ids) > 500:
        raise SchemaError("out of scope profile selection")
    p, h = tables["T161_Profile"], tables["T136_InitHw_Profile"]
    direct_sql = (
        'SELECT "fkT130_Init" FROM ' + h +
        ' WHERE "fkT161_Profile"=? LIMIT ' + str(MAX_DIRECT_LINKS + 1)
    )
    init_sql = (
        'SELECT "id" FROM ' + tables["T130_Init"] + ' WHERE "id"=? LIMIT 2'
    )

    generic_seen = set()
    init_candidates = []
    for key in generic_ids:
        row = _profile(db, p, _normalized_key(key))
        if row is None:
            return "generic_carcom_identifier_missing", None
        signature = (type(row[0]).__name__, row[0])
        if signature in generic_seen:
            return "generic_carcom_physical_key_ambiguous", None
        generic_seen.add(signature)
        links = _bounded(db, direct_sql, (row[0],), MAX_DIRECT_LINKS)
        if links:
            if len(links) != 1 or links[0][0] is None:
                return "generic_direct_inithw_link_not_unique", None
            _one(db, init_sql, (links[0][0],))
            init_candidates.append(row)
    if len(init_candidates) != 1:
        return "not_one_init_bearing_generic_profile", None
    generic = init_candidates[0]

    counts = {
        "exact_profiles_compared": 0,
        "generic_profiles_scanned": len(generic_ids),
        "generic_profiles_with_unique_direct_init": 1,
        "dimension_counts": {
            label: {name: 0 for name in DIMENSION_KEYS}
            for label in DIMENSIONS
        },
        "exact_profiles_all_seven_equal_or_generic_null": 0,
        "exact_profiles_with_one_or_more_filled_conflicts": 0,
        "exact_profiles_with_one_or_more_null_exact_against_filled_generic": 0,
    }
    seen_exact_keys = set()
    for raw in exact_ids:
        row = _profile(db, p, _normalized_key(raw))
        if row is None:
            raise SchemaError("missing matched exact CarCom profile")
        signature = (type(row[0]).__name__, row[0])
        if signature == (type(generic[0]).__name__, generic[0]) or signature in seen_exact_keys:
            raise SchemaError("overlapping or duplicate CarCom profile key")
        seen_exact_keys.add(signature)
        counts["exact_profiles_compared"] += 1
        any_conflict = False
        any_exact_null = False
        for index, label in enumerate(DIMENSIONS, 1):
            generic_val, exact_val = generic[index], row[index]
            if generic_val is None:
                cls = "general_null"
            elif exact_val is None:
                cls = "exact_null_when_general_present"
                any_exact_null = True
            elif generic_val == exact_val:
                cls = "same_both_present"
            else:
                cls = "different_both_present"
                any_conflict = True
            counts["dimension_counts"][label][cls] += 1
        counts["exact_profiles_all_seven_equal_or_generic_null"] += int(
            not any_conflict and not any_exact_null
        )
        counts["exact_profiles_with_one_or_more_filled_conflicts"] += int(any_conflict)
        counts["exact_profiles_with_one_or_more_null_exact_against_filled_generic"] += int(any_exact_null)

    if counts["exact_profiles_compared"] != EXPECTED_EXACT:
        raise SchemaError("unreconciled exact profile comparison")
    for groups in counts["dimension_counts"].values():
        if sum(groups.values()) != EXPECTED_EXACT:
            raise SchemaError("unreconciled stored dimension keys")
    for k in (
        "exact_profiles_all_seven_equal_or_generic_null",
        "exact_profiles_with_one_or_more_filled_conflicts",
        "exact_profiles_with_one_or_more_null_exact_against_filled_generic",
    ):
        if not 0 <= counts[k] <= EXPECTED_EXACT:
            raise SchemaError("invalid aggregate stored constraint coverage")
    return "remaining_seven_stored_constraint_classes_only", counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("invalid owner-private source folder")
    with ExitStack() as stack:
        base = _open_private(stack, folder, "BaseData")
        carcom = _open_private(stack, folder, "CarCom")
        bc = _catalog(base, "BaseData")
        cc = _catalog(carcom, "CarCom", EXT_REQUIRED)
        for table, columns in BASE_REQUIRED.items():
            if not set(x.casefold() for x in columns).issubset(bc[table]["cols"]):
                raise SchemaError("missing required BaseData columns")
        for table, columns in EXT_REQUIRED.items():
            if not set(x.casefold() for x in columns).issubset(cc[table]["cols"]):
                raise SchemaError("missing required CarCom columns")
        bt = _physical(base, bc, BASE_REQUIRED)
        ct = _physical(carcom, cc, EXT_REQUIRED)
        models = _candidate_keys(base, bt["VehicleModel"], bc["VehicleModel"]["rows"])
        y_state, year = _lookup(base, bt, "ModelYear", "2009")
        e_state, engine = _lookup(base, bt, "Engine", "B8444S")
        counts = None
        gate = "source_lookup_unresolved"
        if y_state == e_state == "one":
            chosen = [
                (model, ids) for model in models
                if (ids := _profile_ids(base, bt["VehicleProfile"], model, year, engine))
            ]
            if len(chosen) != 1:
                gate = "not_one_exact_profile_bearing_model"
            elif len(chosen[0][1]) != EXPECTED_EXACT:
                gate = "not_43_exact_profiles"
            elif not _compare(carcom, ct["T161_Profile"], chosen[0][1])[
                    "all_43_have_unique_exact_identifier_matches"]:
                gate = "not_43_unique_carcom_identifiers"
            else:
                model, exact_ids = chosen[0]
                generic_ids = _generic_ids(base, bt["VehicleProfile"], model, year)
                if set(_normalized_key(x).casefold() for x in exact_ids).intersection(
                    g.casefold() for g in generic_ids
                ):
                    raise SchemaError("overlap exact/general BaseData profiles")
                gate, counts = _aggregate(carcom, ct, exact_ids, generic_ids)
        return {
            "schema_version": "virtualcar-vida-xc90-43-generic-seven-dimensions-v1",
            "status": "owner_private_offline_stored_key_category_counts_only",
            "source": "immutable_owner_private_basedata_and_carcom_sqlite_exports",
            "gate": gate,
            "counts": counts,
            "source_rows_read": True,
            "source_writes_performed": False,
            "original_identifiers_or_values_emitted": False,
            "null_generic_constraint_is_wildcard_verified": False,
            "carcom_key_equality_is_original_sqlserver_fk_verified": False,
            "general_profile_parentage_verified": False,
            "vida_2015a_getinithwsettings_runtime_verified": False,
            "d2_baudrate_verified": False,
            "client_vin_accepted": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CarCom seven stored T161 dimensions: category-only owner audit"
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
