#!/usr/bin/env python3
"""Classify CarCom model/year/engine/folderLevel relations, never inheritance.

Private, immutable owner SQLite sources only. Re-derive the 43 exact XC90
MY2009 B8444S BaseData profiles and 43 exact CarCom identifier matches.
Compare their *stored* CarCom T161 keys with the unique XC90/MY2009/
NULL-engine profile that carries a direct T136 InitHw link. Returns bounded
counts only; source values, IDs, VIN, initializations and D2 speeds stay local.

A matching key or folderLevel ordering is NOT a demonstrated VIDA 2015A
GetInitHwSettings selection rule, inheritance path or live ECU response.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
from pathlib import Path
import re
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
from audit_vida_basedata_xc90_general_inithw import (
    INIT_REQUIRED, _generic_ids, MAX_GENERAL_CANDIDATES,
)
from audit_vida_profile_fk_counts import SchemaError, _catalog, _physical

PROFILE_FIELDS = {
    "model": "fkT162_ProfileValue_Model",
    "year": "fkT162_ProfileValue_Year",
    "engine": "fkT162_ProfileValue_Engine",
}
COMPAT_REQUIRED = {
    **INIT_REQUIRED,
    "T161_Profile": (
        *INIT_REQUIRED["T161_Profile"], "folderLevel",
    ),
}
MAX_RANK_ABS = 1_000_000
INT_LITERAL = re.compile(r"[+-]?[0-9]{1,7}\Z")


def _rank(value: object) -> int | None:
    if type(value) is int:
        result = value
    elif type(value) is str and INT_LITERAL.fullmatch(value):
        result = int(value)
    else:
        return None
    return result if -MAX_RANK_ABS <= result <= MAX_RANK_ABS else None


def _profile_query(db, table: str, profile_identifier: str) -> tuple | None:
    # Exactly four intentionally declared CarCom profile properties in addition
    # to physical id; no name/Id is ever emitted to caller's JSON.
    sql = (
        'SELECT "id","fkT162_ProfileValue_Model",'
        '"fkT162_ProfileValue_Year",'
        '"fkT162_ProfileValue_Engine","folderLevel" '
        'FROM ' + table + ' WHERE "identifier"=? LIMIT 3'
    )
    rows = db.execute(sql, (profile_identifier,)).fetchmany(3)
    if not rows:
        return None
    if len(rows) != 1 or rows[0][0] is None:
        raise SchemaError("missing or ambiguous matched CarCom profile")
    return rows[0]


def _summarize(carcom, tables: dict, exact_ids: list, general_ids: list) -> tuple[str, dict | None]:
    if len(exact_ids) != EXPECTED_EXACT or len(general_ids) > MAX_GENERAL_CANDIDATES:
        raise SchemaError("profile counts exceed approved scope")
    p, links = tables["T161_Profile"], tables["T136_InitHw_Profile"]
    qlink = ('SELECT "fkT130_Init" FROM ' + links +
             ' WHERE "fkT161_Profile"=? LIMIT ' +
             str(MAX_INITHW_PER_PROFILE + 1))
    matched_general = 0
    seen_general_keys = set()
    init_bearing: list[tuple] = []
    for raw in general_ids:
        row = _profile_query(carcom, p, _normalized_key(raw))
        if row is None:
            continue
        key_tag = (type(row[0]).__name__, row[0])
        if key_tag in seen_general_keys:
            raise SchemaError("duplicate matched generic CarCom profile")
        seen_general_keys.add(key_tag)
        matched_general += 1
        direct = _bounded(carcom, qlink, (row[0],), MAX_INITHW_PER_PROFILE)
        if direct:
            # Reject null target and duplicate/multiple links for this *one*
            # chosen general candidate; do not use an arbitrary first link.
            if len(direct) != 1 or direct[0][0] is None:
                return "general_direct_init_link_not_unique", None
            init_bearing.append(row)
    if matched_general != len(general_ids):
        return "general_carcom_identifier_missing", None
    if len(init_bearing) != 1:
        return "not_one_generic_init_bearing_profile", None

    generic = init_bearing[0]
    # Verify the unique direct T136 target really points to a single T130,
    # but never read any InitHw value or infer its runtime application.
    init_id = _one(
        carcom, qlink.replace('LIMIT ' + str(MAX_INITHW_PER_PROFILE + 1), 'LIMIT 2'),
        (generic[0],)
    )
    _one(
        carcom, 'SELECT "id" FROM ' + tables["T130_Init"] +
        ' WHERE "id"=? LIMIT 2', (init_id,)
    )
    counts = {
        "exact_profiles_compared": 0,
        "general_init_bearing_candidates": 1,
        "same_model_key_both_present": 0,
        "same_year_key_both_present": 0,
        "same_engine_key_both_present": 0,
        "different_model_key_both_present": 0,
        "different_year_key_both_present": 0,
        "different_engine_key_both_present": 0,
        "general_model_key_null": 0,
        "general_year_key_null": 0,
        "general_engine_key_null": 0,
        "exact_model_key_null_when_general_present": 0,
        "exact_year_key_null_when_general_present": 0,
        "exact_engine_key_null_when_general_present": 0,
        "exact_folderlevel_less_than_generic": 0,
        "exact_folderlevel_equal_generic": 0,
        "exact_folderlevel_greater_than_generic": 0,
        "folderlevel_not_comparable": 0,
    }
    seen_keys = set()
    general_rank = _rank(generic[4])
    for raw in exact_ids:
        row = _profile_query(carcom, p, _normalized_key(raw))
        if row is None:
            raise SchemaError("missing exact profile following 43-match check")
        tag = (type(row[0]).__name__, row[0])
        if tag in seen_keys or tag == (type(generic[0]).__name__, generic[0]):
            raise SchemaError("overlapping or duplicated source CarCom profile")
        seen_keys.add(tag)
        counts["exact_profiles_compared"] += 1
        for n, name in enumerate(("model", "year", "engine"), 1):
            general_value = generic[n]
            exact_value = row[n]
            if general_value is None:
                counts["general_" + name + "_key_null"] += 1
            elif exact_value is None:
                counts["exact_" + name + "_key_null_when_general_present"] += 1
            elif general_value == exact_value:
                counts["same_" + name + "_key_both_present"] += 1
            else:
                counts["different_" + name + "_key_both_present"] += 1
        exact_rank = _rank(row[4])
        if exact_rank is None or general_rank is None:
            counts["folderlevel_not_comparable"] += 1
        elif exact_rank < general_rank:
            counts["exact_folderlevel_less_than_generic"] += 1
        elif exact_rank == general_rank:
            counts["exact_folderlevel_equal_generic"] += 1
        else:
            counts["exact_folderlevel_greater_than_generic"] += 1
    if counts["exact_profiles_compared"] != EXPECTED_EXACT:
        raise SchemaError("unreconciled exact profile count")
    for dimension in PROFILE_FIELDS:
        total = sum(counts[prefix + dimension + suffix] for prefix, suffix in (
            ("same_", "_key_both_present"),
            ("different_", "_key_both_present"),
            ("general_", "_key_null"),
            ("exact_", "_key_null_when_general_present"),
        ))
        if total != EXPECTED_EXACT:
            raise SchemaError("unreconciled CarCom profile dimension")
    if sum(counts[k] for k in (
        "exact_folderlevel_less_than_generic",
        "exact_folderlevel_equal_generic",
        "exact_folderlevel_greater_than_generic",
        "folderlevel_not_comparable",
    )) != EXPECTED_EXACT:
        raise SchemaError("unreconciled folderLevel classes")
    return "carcom_stored_constraint_comparison_only", counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("unsafe offline source folder")
    with ExitStack() as stack:
        base = _open_private(stack, folder, "BaseData")
        carcom = _open_private(stack, folder, "CarCom")
        bc = _catalog(base, "BaseData")
        cc = _catalog(carcom, "CarCom", COMPAT_REQUIRED)
        for table, needed in BASE_REQUIRED.items():
            if not set(x.casefold() for x in needed).issubset(bc[table]["cols"]):
                raise SchemaError("missing BaseData evidence fields")
        for table, needed in COMPAT_REQUIRED.items():
            if not set(x.casefold() for x in needed).issubset(cc[table]["cols"]):
                raise SchemaError("missing CarCom evidence fields")
        bt = _physical(base, bc, BASE_REQUIRED)
        ct = _physical(carcom, cc, COMPAT_REQUIRED)
        models = _candidate_keys(base, bt["VehicleModel"], bc["VehicleModel"]["rows"])
        y_state, year = _lookup(base, bt, "ModelYear", "2009")
        e_state, engine = _lookup(base, bt, "Engine", "B8444S")
        gate, counts = "label_lookup_unresolved", None
        if y_state == e_state == "one":
            candidate_groups = [
                (model, ids) for model in models
                if (ids := _profile_ids(
                    base, bt["VehicleProfile"], model, year, engine
                ))
            ]
            if len(candidate_groups) != 1:
                gate = "not_one_exact_profile_bearing_model"
            elif len(candidate_groups[0][1]) != EXPECTED_EXACT:
                gate = "not_43_exact_profiles"
            elif not _compare(
                    carcom, ct["T161_Profile"], candidate_groups[0][1]
            )["all_43_have_unique_exact_identifier_matches"]:
                gate = "not_43_unique_carcom_identifiers"
            else:
                model, exact_ids = candidate_groups[0]
                generic_ids = _generic_ids(
                    base, bt["VehicleProfile"], model, year
                )
                if set(_normalized_key(x).casefold() for x in exact_ids).intersection(
                    g.casefold() for g in generic_ids
                ):
                    raise SchemaError("overlapping exact and generic profiles")
                gate, counts = _summarize(
                    carcom, ct, exact_ids, generic_ids
                )
        return {
            "schema_version": "virtualcar-vida-43-vs-generic-init-constraints-v1",
            "status": "owner_private_offline_stored_constraint_counts_only",
            "source": "owner_private_immutable_basedata_and_carcom_exports",
            "gate": gate,
            "counts": counts,
            "source_rows_read": True,
            "source_writes_performed": False,
            "exact_set_expected_count": EXPECTED_EXACT,
            "original_profile_ids_or_values_emitted": False,
            "only_carcom_stored_model_year_engine_keys_compared": True,
            "remaining_carcom_profile_dimensions_compared": False,
            "folderlevel_order_is_precedence_or_parentage_verified": False,
            "general_profile_is_runtime_ancestor_verified": False,
            "original_vida_2015a_getinithwsettings_verified": False,
            "d2_baudrate_verified": False,
            "original_vida_readvin_accepted": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Owner-private offline stored T161 constraints, not inheritance"
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
