#!/usr/bin/env python3
"""Read-only VIDA identification boundary audit from a manually reviewed summary.

This never executes VIDA and must not be fed actual VIN, diagnostic payloads
or raw personal client logs. A synthetic summary cannot prove client behavior.
"""
import argparse
import json
from pathlib import Path

SCHEMA = "virtualcar-vida-identity-boundary-v1"
STAGES = {
    "b9fb_transport": ("not_observed", "complete", "invalid", "partial"),
    "identify_script": ("not_observed", "returned_empty", "returned_identity", "failed"),
    "vin_resolver": ("not_observed", "invalid", "empty_profile", "profile_created"),
    "ecu_identification": ("not_observed", "attempted", "response_seen"),
}
TOP_KEYS = {"schema_version", "application", "run_scope", "evidence_source", "stages", "is_x40"}


def audit(data):
    """Return categorical evidence only, never raw identity or inferred vehicle acceptance."""
    if type(data) is not dict or set(data) != TOP_KEYS:
        raise ValueError("unexpected input fields")
    if (data["schema_version"] != SCHEMA or data["application"] != "VIDA2015A"
            or data["run_scope"] != "same_client_run"
            or data["evidence_source"] != "human_reviewed_lab_summary"):
        raise ValueError("invalid evidence scope")
    stages = data["stages"]
    if type(stages) is not dict or set(stages) != set(STAGES):
        raise ValueError("expected four stage observations")
    for name, allowed in STAGES.items():
        if type(stages[name]) is not str or stages[name] not in allowed:
            raise ValueError("invalid stage observation")
    if type(data["is_x40"]) not in (bool, type(None)):
        raise ValueError("is_x40 requires true, false or null")
    if stages["identify_script"] != "returned_identity" and data["is_x40"] is not None:
        raise ValueError("unknown X40 flag when identity not returned")
    if stages["identify_script"] == "returned_identity" and data["is_x40"] is None:
        raise ValueError("actual identity branch must state observed IsX40 flag")

    script = stages["identify_script"]
    branch = {
        "not_observed": "not_observed",
        "returned_empty": "vin_exception_branch",
        "returned_identity": "vehicle_identity_constructor_branch",
        "failed": "failed_without_confirmed_identity",
    }[script]
    # Mirrors only the observed IsIdentityVin = !IsX40 expression.
    # An IsIdentityVin property is not a verified WMI/VIN/vehicle profile.
    is_identity_vin_property = (
        not data["is_x40"] if script == "returned_identity" else None
    )
    return {
        "schema_version": "virtualcar-vida-identity-boundary-report-v1",
        "application": "VIDA2015A",
        "source_evidence_independently_verified": False,
        "same_client_run_reported": True,
        "b9fb_transport_observation": stages["b9fb_transport"],
        "script_identity_observation": script,
        "identifyvehicle_il_branch": branch,
        "is_identity_vin_property": is_identity_vin_property,
        "identity_trimming_rule": "trailing_CR_LF_only",
        "vin_resolver_observation": stages["vin_resolver"],
        "ecu_identification_observation": stages["ecu_identification"],
        "direct_b9fb_to_identity_script_dependency": "not_proven",
        "direct_identifyvehicle_to_resolvevin_dependency": "not_observed_in_method",
        "vin_validated_by_observed_run": "unknown",
        "vehicle_profile_confirmed": "unknown",
        "sectorv_normal_mode_predicate": "unknown",
        "vehicle_identity_verified_for_xc90_my2009": False,
        "replay_approved": False,
        "limitations": [
            "Transport delivery alone cannot establish an identity-script result.",
            "VIDA IdentifyVehicle consumes a distinct script output; no direct B9FB call is established at this entry point.",
            "IsIdentityVin reflects !IsX40; it does not validate a genuine VIN.",
            "ResolveVin invokes VinValidator and a database lookup on a separate path.",
            "The inputs are manually curated categories, NOT proof supplied by executing VIDA.",
            "No raw VIN, payload, source path, vehicle numbers or test fixture data are emitted.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Offline, privacy-safe VIDA identity boundary audit")
    p.add_argument("input", type=Path, help="Manually reviewed categorical JSON, not raw logs")
    p.add_argument("--output", type=Path, required=True, help="New output JSON (never overwrite)")
    a = p.parse_args(argv)
    if a.input.resolve() == a.output.resolve():
        p.error("input and output must differ")
    try:
        summary = json.loads(a.input.read_text(encoding="utf-8"))
        result = audit(summary)
    except (OSError, ValueError, TypeError) as exc:
        p.error("invalid evidence: " + type(exc).__name__)
    try:
        with a.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except OSError as exc:
        p.error("cannot create exclusive output: " + type(exc).__name__)
    print("VIDA identification boundary audited; vehicle acceptance UNVERIFIED")


if __name__ == "__main__":
    main()
