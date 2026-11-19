#!/usr/bin/env python3
"""Bounded read-only CarCom direct-default / direct-InitHw evidence for 43 profiles.

First proves exact BaseData.VehicleProfile.Id ↔ CarCom.T161_Profile.identifier
matches for 43 XC90-prefix / MY2009 / B8444S rows in owner-private immutable
SQLite exports. Then counts only direct T160 and T136 links to that exact set.
Does not select a VIDA runtime profile or resolve inherited InitHw.
No original identifiers, descriptions, component values or VIN leave process.
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
from audit_vida_profile_fk_counts import SchemaError, _catalog, _physical, _quoted

CARCOM_REQUIRED = {
    "T161_Profile": ("id", "identifier", "fkT162_ProfileValue_Model",
                     "fkT162_ProfileValue_Year", "fkT162_ProfileValue_Engine"),
    "T162_ProfileValue": ("id",),
    "T160_DefaultEcuVariant": ("fkT161_Profile", "fkT100_EcuVariant"),
    "T100_EcuVariant": ("id", "fkT101_Ecu"),
    "T101_Ecu": ("id", "identifier"),
    "T136_InitHw_Profile": ("fkT161_Profile", "fkT130_Init"),
}
MAX_DEFAULTS_PER_PROFILE = 32
MAX_INITHW_PER_PROFILE = 32


def _one(db, sql: str, args: tuple) -> object:
    rows = db.execute(sql, args).fetchmany(2)
    if len(rows) != 1 or len(rows[0]) != 1 or rows[0][0] is None:
        raise SchemaError("ambiguous or missing direct CarCom reference")
    return rows[0][0]


def _bounded(db, sql: str, args: tuple, limit: int) -> list:
    rows = db.execute(sql, args).fetchmany(limit + 1)
    if len(rows) > limit:
        raise SchemaError("unbounded direct CarCom associations")
    return rows


def _aggregate(carcom, tables: dict, identifiers: list) -> dict:
    if len(identifiers) != EXPECTED_EXACT:
        raise SchemaError("wrong exact profile count")
    qprofile = tables["T161_Profile"]
    qdefaults = tables["T160_DefaultEcuVariant"]
    qvariant = tables["T100_EcuVariant"]
    qecu = tables["T101_Ecu"]
    qinithw = tables["T136_InitHw_Profile"]
    profile_sql = (
        "SELECT " + _quoted("id") + " FROM " + qprofile +
        " WHERE " + _quoted("identifier") + "=? LIMIT 3"
    )
    default_sql = (
        "SELECT " + _quoted("fkT100_EcuVariant") +
        " FROM " + qdefaults + " WHERE " + _quoted("fkT161_Profile") +
        "=? LIMIT " + str(MAX_DEFAULTS_PER_PROFILE + 1)
    )
    inithw_sql = (
        "SELECT " + _quoted("fkT130_Init") +
        " FROM " + qinithw + " WHERE " + _quoted("fkT161_Profile") +
        "=? LIMIT " + str(MAX_INITHW_PER_PROFILE + 1)
    )
    variant_sql = (
        "SELECT " + _quoted("fkT101_Ecu") +
        " FROM " + qvariant + " WHERE " + _quoted("id") + "=? LIMIT 2"
    )
    ecu_sql = (
        "SELECT " + _quoted("identifier") +
        " FROM " + qecu + " WHERE " + _quoted("id") + "=? LIMIT 2"
    )
    counts = {
        "matched_exact_profile_count": 0,
        "profiles_with_direct_defaults": 0,
        "profiles_without_direct_defaults": 0,
        "direct_default_link_rows": 0,
        "direct_default_cem_rows": 0,
        "direct_default_ecm_rows": 0,
        "direct_default_other_ecu_rows": 0,
        "profiles_with_direct_inithw": 0,
        "profiles_without_direct_inithw": 0,
        "direct_inithw_link_rows": 0,
        "null_direct_inithw_target_rows": 0,
    }
    observed_profile_keys = set()
    for raw in identifiers:
        identifier = _normalized_key(raw)
        profile_key = _one(carcom, profile_sql, (identifier,))
        profile_key_tag = (type(profile_key).__name__, profile_key)
        if profile_key_tag in observed_profile_keys:
            raise SchemaError("duplicate matched CarCom profile")
        observed_profile_keys.add(profile_key_tag)
        counts["matched_exact_profile_count"] += 1
        defaults = _bounded(carcom, default_sql, (profile_key,), MAX_DEFAULTS_PER_PROFILE)
        inithw = _bounded(carcom, inithw_sql, (profile_key,), MAX_INITHW_PER_PROFILE)
        counts["profiles_with_direct_defaults"] += int(bool(defaults))
        counts["profiles_without_direct_defaults"] += int(not defaults)
        counts["profiles_with_direct_inithw"] += int(bool(inithw))
        counts["profiles_without_direct_inithw"] += int(not inithw)
        counts["direct_default_link_rows"] += len(defaults)
        counts["direct_inithw_link_rows"] += len(inithw)
        counts["null_direct_inithw_target_rows"] += sum(int(x[0] is None) for x in inithw)
        for (variant_key,) in defaults:
            if variant_key is None:
                raise SchemaError("null direct ECU variant key")
            ecu_key = _one(carcom, variant_sql, (variant_key,))
            ecu_name = _one(carcom, ecu_sql, (ecu_key,))
            if not isinstance(ecu_name, str):
                raise SchemaError("unexpected ECU identifier type")
            name = ecu_name.strip().upper()
            if name == "CEM":
                counts["direct_default_cem_rows"] += 1
            elif name == "ECM":
                counts["direct_default_ecm_rows"] += 1
            else:
                counts["direct_default_other_ecu_rows"] += 1

    if (counts["matched_exact_profile_count"] != EXPECTED_EXACT or
            counts["profiles_with_direct_defaults"] +
            counts["profiles_without_direct_defaults"] != EXPECTED_EXACT or
            counts["profiles_with_direct_inithw"] +
            counts["profiles_without_direct_inithw"] != EXPECTED_EXACT or
            counts["direct_default_link_rows"] !=
            counts["direct_default_cem_rows"] +
            counts["direct_default_ecm_rows"] +
            counts["direct_default_other_ecu_rows"]):
        raise SchemaError("unreconciled CarCom direct links")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("unsafe private export folder")
    with ExitStack() as stack:
        base = _open_private(stack, folder, "BaseData")
        carcom = _open_private(stack, folder, "CarCom")
        bc = _catalog(base, "BaseData")
        cc = _catalog(carcom, "CarCom")
        for table, required in BASE_REQUIRED.items():
            if not set(x.casefold() for x in required).issubset(bc[table]["cols"]):
                raise SchemaError("missing BaseData evidence columns")
        for table, required in CARCOM_REQUIRED.items():
            if not set(x.casefold() for x in required).issubset(cc[table]["cols"]):
                raise SchemaError("missing CarCom evidence columns")
        bt = _physical(base, bc, BASE_REQUIRED)
        ct = _physical(carcom, cc, CARCOM_REQUIRED)

        models = _candidate_keys(base, bt["VehicleModel"],
                                 bc["VehicleModel"]["rows"])
        year_state, year_key = _lookup(base, bt, "ModelYear", "2009")
        engine_state, engine_key = _lookup(base, bt, "Engine", "B8444S")
        gate = "lookup_unresolved"
        counts = None
        if year_state == engine_state == "one":
            candidate_groups = [
                ids for model_key in models
                if (ids := _profile_ids(base, bt["VehicleProfile"],
                                        model_key, year_key, engine_key))
            ]
            if len(candidate_groups) != 1:
                gate = "no_unique_profile_bearing_model"
            elif len(candidate_groups[0]) != EXPECTED_EXACT:
                gate = "source_exact_count_not_43"
            else:
                ids = candidate_groups[0]
                matching = _compare(carcom, ct["T161_Profile"], ids)
                if not matching["all_43_have_unique_exact_identifier_matches"]:
                    gate = "carcom_exact_identifier_equality_not_unique"
                else:
                    counts = _aggregate(carcom, ct, ids)
                    gate = "all_43_direct_links_counted"
        return {
            "schema_version": "virtualcar-vida-43-direct-default-inithw-v1",
            "status": "owner_private_offline_direct_links_only",
            "source": "immutable_basedata_carcom_sqlite_exports",
            "source_rows_read": True,
            "source_writes_performed": False,
            "xc90_prefix_model_candidate_count": len(models),
            "year_lookup": year_state,
            "engine_lookup": engine_state,
            "gate": gate,
            "counts": counts,
            "original_source_identifiers_or_values_emitted": False,
            "private_profile_lists_created": False,
            "same_as_previous_43_source_set_verified": False,
            "original_sqlserver_fk_semantics_verified": False,
            "effective_inithw_inheritance_verified": False,
            "effective_d2_baudrate_verified": False,
            "actual_selected_vida_profile_verified": False,
            "client_ecu_alive_verified": False,
            "original_vida_readvin_accepted": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private VIDA 43-profile direct CarCom link counts")
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed",
                          "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
