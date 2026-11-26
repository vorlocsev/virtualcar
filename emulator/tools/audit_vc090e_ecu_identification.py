#!/usr/bin/env python3
"""VC090E offline ECU readout evidence reconciliation.

T111_Service -> T122_Protocol is catalog reference coverage, not an
executed script or ECU response. Owner-transcribed module observations
remain owner claims. No live SQL, J2534, VIDA, or registry access.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from audit_vc090d_readvin_evidence import read_frozen
from audit_vida_t111_t122_aggregate import SCHEMA as CATALOG_SCHEMA, SAMPLE_LIMIT

SCHEMA = "vc090e-ecu-observation-v1"
MAX_JSON = 256 * 1024
MAX_MODULES = 256
TOKEN = re.compile(r"[A-Za-z0-9_.-]{1,64}")
STATES = {"alive", "not_alive", "not_present", "not_observed"}
ROUTES = {"positive_identification", "no_reply", "negative_response", "not_observed"}
PROFILE = {"in_configuration", "not_in_configuration", "unknown"}
LOOKUP = {"matched_variant", "default_variant", "not_observed"}
TOP_KEYS = {"schema", "evidence_source", "same_run", "modules"}
ROW_KEYS = {"module", "profile", "readout", "transport", "catalog_lookup"}
CATALOG_FALSE = ("catalog_visibility_complete_verified", "all_rows_verified",
                 "selected_vehicle_profile_verified", "readvin_execution_verified",
                 "d2_baud_verified", "client_vin_accepted", "ecu_identification_verified",
                 "replay_approved")


def unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate_json_key")
        out[key] = value
    return out


def reject_constant(value):
    raise ValueError("nonfinite_json")


def load_json(raw):
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                      parse_constant=reject_constant)


def validate_catalog(report):
    if report is None:
        return {"status": "not_supplied", "sampled_rows": 0,
                "matching_references": 0, "unmatched_references": 0, "null_references": 0}
    if (type(report) is not dict or report.get("schema_version") != CATALOG_SCHEMA
            or report.get("status") != "sampled_reference_coverage_only"
            or report.get("source_database") != "CarCom"
            or report.get("source_table") != "T111_Service"
            or report.get("target_table") != "T122_Protocol"
            or type(report.get("sample_bound")) is not int
            or report["sample_bound"] != SAMPLE_LIMIT
            or any(report.get(flag) is not False for flag in CATALOG_FALSE)):
        raise ValueError("invalid_catalog_scope")
    n, matched, missed, nulls = (report.get(key) for key in (
        "sampled_service_rows", "matching_reference_rows",
        "unmatched_reference_rows", "null_reference_rows"))
    if (any(type(x) is not int or not 0 <= x <= SAMPLE_LIMIT for x in
            (n, matched, missed, nulls)) or matched + missed + nulls != n
            or report.get("sample_nonempty") is not (n > 0)):
        raise ValueError("invalid_catalog_counts")
    status = ("empty_sample" if n == 0 else
              "unmatched_references_observed" if missed else
              "null_references_observed" if nulls else "sample_all_references_matched")
    return {"status": status, "sampled_rows": n, "matching_references": matched,
            "unmatched_references": missed, "null_references": nulls}


def audit(summary, catalog=None):
    coverage = validate_catalog(catalog)
    if (type(summary) is not dict or set(summary) != TOP_KEYS
            or summary["schema"] != SCHEMA
            or summary["evidence_source"] not in ("synthetic", "owner_reviewed")
            or type(summary["same_run"]) is not bool
            or type(summary["modules"]) is not list
            or len(summary["modules"]) > MAX_MODULES):
        raise ValueError("invalid_observation_scope")
    seen = set()
    counts = Counter()
    cross = {state: Counter() for state in sorted(STATES)}
    for row in summary["modules"]:
        if type(row) is not dict or set(row) != ROW_KEYS:
            raise ValueError("invalid_module_fields")
        module = row["module"]
        if (type(module) is not str or not TOKEN.fullmatch(module)
                or module.casefold() in seen):
            raise ValueError("invalid_or_duplicate_module_token")
        seen.add(module.casefold())
        for field, allowed in (("profile", PROFILE), ("readout", STATES),
                               ("transport", ROUTES), ("catalog_lookup", LOOKUP)):
            if type(row[field]) is not str or row[field] not in allowed:
                raise ValueError("invalid_module_category")
        state, transport = row["readout"], row["transport"]
        cross[state][transport] += 1
        counts["readout_" + state] += 1
        counts["profile_" + row["profile"]] += 1
        counts["lookup_" + row["catalog_lookup"]] += 1
        # Unknown/not-observed is not a negative observation. A default
        # CarCom variant is never used as evidence of an actual response.
        if state == "alive":
            if transport == "positive_identification":
                counts["alive_with_reported_positive_identification"] += 1
            elif transport == "not_observed":
                counts["alive_transport_unobserved"] += 1
            else:
                counts["alive_without_positive_identification"] += 1
        elif state == "not_alive":
            if transport == "not_observed":
                counts["not_alive_transport_unobserved"] += 1
            if transport == "positive_identification":
                counts["not_alive_with_reported_positive_identification"] += 1
            if row["catalog_lookup"] == "default_variant":
                counts["not_alive_default_variant"] += 1
        elif state == "not_present":
            if transport == "positive_identification":
                counts["not_present_with_reported_positive_identification"] += 1
            if row["profile"] == "in_configuration":
                counts["not_present_but_in_configuration"] += 1
            elif row["profile"] == "unknown":
                counts["not_present_configuration_unobserved"] += 1
        if state in ("alive", "not_alive") and row["profile"] == "not_in_configuration":
            counts["readout_outside_reported_configuration"] += 1
        elif state in ("alive", "not_alive") and row["profile"] == "unknown":
            counts["readout_configuration_unobserved"] += 1
        if state == "not_observed" and transport == "positive_identification":
            counts["positive_identification_without_readout"] += 1
    discrepancy_keys = (
        "alive_without_positive_identification",
        "not_alive_with_reported_positive_identification",
        "not_present_with_reported_positive_identification",
        "not_present_but_in_configuration",
        "readout_outside_reported_configuration")
    gap_keys = ("alive_transport_unobserved", "not_alive_transport_unobserved",
                "readout_configuration_unobserved", "not_present_configuration_unobserved",
                "positive_identification_without_readout", "readout_not_observed")
    if not seen:
        gate = "no_module_observations"
    elif not summary["same_run"]:
        gate = "same_run_not_reported"
    elif any(counts[k] for k in discrepancy_keys):
        gate = "reported_discrepancies_require_review"
    elif any(counts[k] for k in gap_keys):
        gate = "reported_evidence_incomplete"
    else:
        gate = "reported_categories_consistent_only"
    return {
        "schema": "vc090e-ecu-identification-evidence-v1",
        "evidence_source": summary["evidence_source"],
        "same_run_reported": summary["same_run"],
        "catalog_reference_coverage": coverage,
        "module_count": len(seen),
        "readout_counts": {state: counts["readout_" + state] for state in sorted(STATES)},
        "transport_by_readout": {state: {route: cross[state][route] for route in sorted(ROUTES)}
                                 for state in sorted(STATES)},
        "profile_counts": {key: counts["profile_" + key] for key in sorted(PROFILE)},
        "catalog_lookup_counts": {key: counts["lookup_" + key] for key in sorted(LOOKUP)},
        "reported_alive_with_positive_identification": counts["alive_with_reported_positive_identification"],
        "reported_not_alive_default_variant": counts["not_alive_default_variant"],
        "discrepancies": {key: counts[key] for key in discrepancy_keys},
        "evidence_gaps": {key: counts[key] for key in gap_keys},
        "readout_reconciliation_gate": gate,
        "catalog_and_readout_same_run_verified": False,
        "selected_vehicle_profile_verified": False,
        "original_vida_client_authenticated": False,
        "actual_j2534_identification_exchange_verified": False,
        "original_vida_readvin_accepted": False,
        "original_vida_ecu_identification_accepted": False,
        "physical_j2534_verified": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", type=Path, required=True)
    parser.add_argument("--catalog-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        paths = [args.observations] + ([args.catalog_report] if args.catalog_report else [])
        out = args.output
        repo = Path(__file__).resolve().parents[2]
        if (not out.is_absolute() or out.anchor.startswith("\\\\")
                or repo in out.resolve().parents):
            raise ValueError("external_output_required")
        for part in out.parents:
            info = part.lstat()
            if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("reparse_output")
        if len({p.resolve() for p in paths + [out]}) != len(paths) + 1:
            raise ValueError("source_alias")
        original = [read_frozen(p, MAX_JSON) for p in paths]
        result = audit(load_json(original[0]),
                       load_json(original[1]) if len(original) == 2 else None)
        if any(read_frozen(p, MAX_JSON) != raw for p, raw in zip(paths, original)):
            raise ValueError("source_changed")
        with out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError):
        parser.exit(2, "ERROR: invalid or unreadable local evidence\n")
    print("VC090E_CATALOG=" + result["catalog_reference_coverage"]["status"])
    print("VC090E_READOUT=" + result["readout_reconciliation_gate"])
    print("VC090E_ORIGINAL_VIDA_ECU_IDENTIFICATION=NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
