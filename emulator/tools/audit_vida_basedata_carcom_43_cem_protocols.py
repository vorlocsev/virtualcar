#!/usr/bin/env python3
"""Count CEM protocol/busRate-presence rows for 43 privately matched Volvo profiles.

Only two owner-private immutable SQLite copies are read. Real identifiers,
vehicle VIN, bus rates, CAN IDs, addresses and ECU variant keys stay in memory.
A direct CEM default is *catalog* evidence; no live ECU/VIDA runtime is proved.
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
    BASE_REQUIRED, EXPECTED_EXACT, _open_private, _profile_ids, _compare,
    _normalized_key,
)
from audit_vida_basedata_carcom_43_direct_links import (
    CARCOM_REQUIRED, MAX_DEFAULTS_PER_PROFILE, _one, _bounded,
)
from audit_vida_profile_fk_counts import SchemaError, _catalog, _physical, _quoted

CONFIG_REQUIRED = {
    **CARCOM_REQUIRED,
    "T120_Config_EcuVariant": ("fkT100_EcuVariant", "fkT121_Config"),
    "T121_Config": ("id", "fkT122_Protocol", "busRate"),
    "T122_Protocol": ("id", "identifier"),
}
MAX_CONFIGS_PER_CEM_VARIANT = 32


def _summarize(db, tables: dict, private_ids: list) -> dict:
    if len(private_ids) != EXPECTED_EXACT:
        raise SchemaError("incorrect selected BaseData profile count")
    p, d = tables["T161_Profile"], tables["T160_DefaultEcuVariant"]
    v, e = tables["T100_EcuVariant"], tables["T101_Ecu"]
    bridge = tables["T120_Config_EcuVariant"]
    cfg, proto = tables["T121_Config"], tables["T122_Protocol"]
    profile_sql = 'SELECT "id" FROM ' + p + ' WHERE "identifier"=? LIMIT 3'
    defaults_sql = ('SELECT "fkT100_EcuVariant" FROM ' + d +
                    ' WHERE "fkT161_Profile"=? LIMIT ' +
                    str(MAX_DEFAULTS_PER_PROFILE + 1))
    ecu_key_sql = 'SELECT "fkT101_Ecu" FROM ' + v + ' WHERE "id"=? LIMIT 2'
    ecu_name_sql = 'SELECT "identifier" FROM ' + e + ' WHERE "id"=? LIMIT 2'
    config_links_sql = ('SELECT "fkT121_Config" FROM ' + bridge +
                        ' WHERE "fkT100_EcuVariant"=? LIMIT ' +
                        str(MAX_CONFIGS_PER_CEM_VARIANT + 1))
    config_row_sql = ('SELECT "fkT122_Protocol","busRate" FROM ' + cfg +
                      ' WHERE "id"=? LIMIT 3')
    proto_sql = 'SELECT "identifier" FROM ' + proto + ' WHERE "id"=? LIMIT 2'
    counts = {
        "matched_source_profiles": 0,
        "direct_cem_default_rows": 0,
        "cem_defaults_without_configs": 0,
        "cem_defaults_with_configs": 0,
        "cem_config_link_rows": 0,
        "cem_config_duplicate_refs_within_variant": 0,
        "cem_d2_config_rows": 0,
        "cem_d2_null_busrate_rows": 0,
        "cem_d2_nonnull_busrate_rows": 0,
        "cem_ggd_config_rows": 0,
        "cem_ggd_null_busrate_rows": 0,
        "cem_ggd_nonnull_busrate_rows": 0,
        "cem_other_protocol_config_rows": 0,
        "cem_other_protocol_null_busrate_rows": 0,
        "cem_other_protocol_nonnull_busrate_rows": 0,
    }
    seen_profiles = set()
    for source_id in private_ids:
        profile_key = _one(db, profile_sql, (_normalized_key(source_id),))
        key_tag = (type(profile_key).__name__, profile_key)
        if key_tag in seen_profiles:
            raise SchemaError("duplicate matched source profile")
        seen_profiles.add(key_tag)
        counts["matched_source_profiles"] += 1
        default_rows = _bounded(
            db, defaults_sql, (profile_key,), MAX_DEFAULTS_PER_PROFILE
        )
        for (variant_id,) in default_rows:
            if variant_id is None:
                raise SchemaError("missing CEM default variant reference")
            ecu_key = _one(db, ecu_key_sql, (variant_id,))
            ecu_name = _one(db, ecu_name_sql, (ecu_key,))
            if not isinstance(ecu_name, str):
                raise SchemaError("invalid source ECU identifier type")
            if ecu_name.strip().upper() != "CEM":
                continue
            counts["direct_cem_default_rows"] += 1
            config_rows = _bounded(
                db, config_links_sql, (variant_id,), MAX_CONFIGS_PER_CEM_VARIANT
            )
            counts["cem_defaults_with_configs"] += int(bool(config_rows))
            counts["cem_defaults_without_configs"] += int(not config_rows)
            counts["cem_config_link_rows"] += len(config_rows)
            config_keys = set()
            for (config_id,) in config_rows:
                if config_id is None:
                    raise SchemaError("missing CEM config link")
                tag = (type(config_id).__name__, config_id)
                counts["cem_config_duplicate_refs_within_variant"] += int(tag in config_keys)
                config_keys.add(tag)
                config_items = db.execute(
                    config_row_sql, (config_id,)
                ).fetchmany(3)
                if len(config_items) != 1 or config_items[0][0] is None:
                    raise SchemaError("missing or ambiguous CEM config reference")
                proto_id, bus_rate = config_items[0]
                protocol_name = _one(db, proto_sql, (proto_id,))
                if not isinstance(protocol_name, str):
                    raise SchemaError("invalid protocol identifier type")
                protocol = protocol_name.strip().upper()
                family = "d2" if protocol == "D2" else (
                    "ggd" if protocol == "GGD" else "other_protocol")
                counts["cem_" + family + "_config_rows"] += 1
                suffix = "_null_busrate_rows" if bus_rate is None else "_nonnull_busrate_rows"
                counts["cem_" + family + suffix] += 1
    if (counts["matched_source_profiles"] != EXPECTED_EXACT or
            counts["cem_defaults_with_configs"] +
            counts["cem_defaults_without_configs"] !=
            counts["direct_cem_default_rows"] or
            counts["cem_config_link_rows"] !=
            counts["cem_d2_config_rows"] +
            counts["cem_ggd_config_rows"] +
            counts["cem_other_protocol_config_rows"] or
            counts["cem_config_duplicate_refs_within_variant"] >
            counts["cem_config_link_rows"]):
        raise SchemaError("inconsistent CEM source counts")
    for family in ("d2", "ggd", "other_protocol"):
        if (counts["cem_" + family + "_config_rows"] !=
                counts["cem_" + family + "_null_busrate_rows"] +
                counts["cem_" + family + "_nonnull_busrate_rows"]):
            raise SchemaError("inconsistent protocol busRate-presence counts")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("unsafe owner-private offline folder")
    with ExitStack() as stack:
        base = _open_private(stack, folder, "BaseData")
        carcom = _open_private(stack, folder, "CarCom")
        bc = _catalog(base, "BaseData")
        cc = _catalog(carcom, "CarCom", CONFIG_REQUIRED)
        for table, cols in BASE_REQUIRED.items():
            if not set(x.casefold() for x in cols).issubset(bc[table]["cols"]):
                raise SchemaError("missing BaseData profile columns")
        for table, cols in CONFIG_REQUIRED.items():
            if not set(x.casefold() for x in cols).issubset(cc[table]["cols"]):
                raise SchemaError("missing CarCom configuration columns")
        bt = _physical(base, bc, BASE_REQUIRED)
        ct = _physical(carcom, cc, CONFIG_REQUIRED)
        models = _candidate_keys(base, bt["VehicleModel"],
                                  bc["VehicleModel"]["rows"])
        ys, year = _lookup(base, bt, "ModelYear", "2009")
        es, engine = _lookup(base, bt, "Engine", "B8444S")
        gate, result = "source_lookup_unresolved", None
        if ys == es == "one":
            groups = [
                ids for model in models
                if (ids := _profile_ids(base, bt["VehicleProfile"],
                                        model, year, engine))
            ]
            if len(groups) != 1:
                gate = "not_one_profile_bearing_model"
            elif len(groups[0]) != EXPECTED_EXACT:
                gate = "not_43_exact_profiles"
            elif not _compare(carcom, ct["T161_Profile"], groups[0])[
                    "all_43_have_unique_exact_identifier_matches"]:
                gate = "not_43_unique_carcom_identifiers"
            else:
                result = _summarize(carcom, ct, groups[0])
                gate = "exact_cem_direct_config_categories_counted"
        return {
            "schema_version": "virtualcar-vida-43-cem-direct-config-presence-v1",
            "status": "owner_private_offline_cem_configuration_counts_only",
            "source": "owner_private_immutable_basedata_and_carcom_exports",
            "source_rows_read": True,
            "source_writes_performed": False,
            "source_exact_model_candidate_count": len(models),
            "year_label_lookup": ys,
            "engine_label_lookup": es,
            "gate": gate,
            "counts": result,
            "original_profile_identifiers_ecu_keys_or_bus_rates_exported": False,
            "original_vida_runtime_profile_selected": False,
            "source_default_cem_is_live_ecu": False,
            "source_d2_bus_rate_missing_value_inferred": False,
            "effective_inherited_hardware_settings_verified": False,
            "source_snapshot_vs_original_sqlserver_verified": False,
            "same_as_previous_private_43_selection_verified": False,
            "original_vida_readvin_accepted": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Owner-private offline CEM D2/GGD config row categories only"
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
