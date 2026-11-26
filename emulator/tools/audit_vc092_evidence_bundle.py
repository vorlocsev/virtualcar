#!/usr/bin/env python3
"""VC092 offline bundle verification; never authorizes or executes a test.

Evidence digests establish local file consistency only. Owner claims, JSON
reports and screenshots cannot authenticate a VM or original VIDA runtime.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from audit_vc090d_readvin_evidence import read_frozen
from audit_vc090e_ecu_identification import load_json, validate_catalog

SCHEMA = "vc092-evidence-manifest-v1"
PHASES = ("Baseline", "InstallCancelled", "Installed", "RemoveCancelled", "Restored")
REG_ROLES = tuple("registration_" + p for p in PHASES)
SCHEMAS = {
    "native_preflight": "vc090-native-preflight-v1",
    **dict.fromkeys(REG_ROLES, "vc090b-registration-checkpoint-v1"),
    "binding": "vc090c-explicit-vida-binding-v1",
    "readvin": "vc090d-native-readvin-evidence-v1",
    "ecu": "vc090e-ecu-identification-evidence-v1",
    "catalog": "virtualcar-vida-t111-t122-sampled-join-v1",
}
MAX_JSON = 256 * 1024
MAX_DLL = 64 * 1024 * 1024
ROLES = set(SCHEMAS) | {"native_dll"}
CLAIMS = ("disposable_vm_snapshot", "owner_mutation_permission",
          "not_persistent_runner", "physical_adapter_disconnected",
          "same_session_reviewed")
NATIVE_GATES = ("source_and_managed_inventory", "fresh_native_build", "x86_export_contract",
                "native_silence_and_evidence", "synthetic_identity_replay", "can_ms_lifecycle",
                "registry32_preflight", "final_integrity")
FALSE_FLAGS = {
    "binding": ("selected_pid_is_authenticated_original_vida",
                "selected_process_is_authenticated_original_vida",
                "loaded_binary_memory_matches_disk_verified",
                "active_vida_diagnostic_config_loaded_verified",
                "effective_diagnostic_connection_mode_verified",
                "original_vida_script_selection_verified", "original_vida_j2534_tx_rx_verified",
                "original_vida_vin_accepted_verified", "ecu_identity_accepted_verified",
                "provider_selection_in_vida_gui_verified", "registry_install_remove_verified",
                "physical_adapter_examined"),
    "readvin": ("original_vida_process_authenticated", "loaded_module_identity_verified",
                "readvin_script_execution_verified", "original_vida_vin_accepted_verified",
                "ecu_identity_accepted_verified", "physical_j2534_verified"),
    "ecu": ("catalog_and_readout_same_run_verified", "selected_vehicle_profile_verified",
            "original_vida_client_authenticated", "actual_j2534_identification_exchange_verified",
            "original_vida_readvin_accepted", "original_vida_ecu_identification_accepted",
            "physical_j2534_verified"),
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def hash_text(value, n):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{%d}" % n, value):
        raise ValueError("invalid_fingerprint")
    return value.lower()


def manifest_fields(data, expected_head):
    if (type(data) is not dict or set(data) != {"schema", "source_sha", "native_sha256",
            "scope", "owner_claims", "files"} or data["schema"] != SCHEMA
            or data["scope"] not in ("synthetic", "owner_reviewed")):
        raise ValueError("invalid_manifest_scope")
    head = hash_text(data["source_sha"], 40)
    if head != hash_text(expected_head, 40):
        raise ValueError("unexpected_head")
    native = hash_text(data["native_sha256"], 64)
    claims = data["owner_claims"]
    if (type(claims) is not dict or set(claims) != set(CLAIMS)
            or any(type(v) is not bool for v in claims.values())):
        raise ValueError("invalid_owner_claims")
    files = data["files"]
    if type(files) is not dict or not set(files) <= ROLES:
        raise ValueError("invalid_roles")
    names = set()
    for role, entry in files.items():
        if type(entry) is not dict or set(entry) != {"file", "sha256"}:
            raise ValueError("invalid_file_entry")
        name = entry["file"]
        suffix = ".dll" if role == "native_dll" else ".json"
        if (type(name) is not str or not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,119}", name)
                or not name.lower().endswith(suffix) or name.casefold() in names
                or ".." in name):
            raise ValueError("invalid_or_duplicate_filename")
        names.add(name.casefold())
        hash_text(entry["sha256"], 64)
    return head, native, claims, files


def schema_check(role, report):
    if type(report) is not dict:
        raise ValueError("invalid_report")
    field = "schema_version" if role in ("binding", "catalog") else "schema"
    other = "schema" if field == "schema_version" else "schema_version"
    if report.get(field) != SCHEMAS[role] or other in report:
        raise ValueError("unexpected_report_schema")
    if any(report.get(flag) is not False for flag in FALSE_FLAGS.get(role, ())):
        raise ValueError("unsupported_runtime_claim")


def native_check(report, head, native, dll):
    if report is None:
        return "not_tested"
    if hash_text(report.get("source_sha"), 40) != head:
        return "source_mismatch"
    if report.get("status") != "pass":
        return "reported_failure"
    if (hash_text(report.get("native_dll_sha256"), 64) != native
            or type(report.get("native_dll_bytes")) is not int
            or report["native_dll_bytes"] < 256):
        return "candidate_mismatch"
    gates = report.get("gates")
    if (type(gates) is not dict or set(gates) != set(NATIVE_GATES)
            or any(v != "pass" for v in gates.values())
            or report.get("failed_stage") != ""
            or any(report.get(key) != "not_tested" for key in (
                "registration_install_remove", "vida_provider_selection",
                "vida_loaded_module_identity", "vida_readvin", "vida_t111", "vida_t122", "physical_j2534"))):
        raise ValueError("contradictory_native_claim")
    if dll is None:
        return "candidate_file_missing"
    if len(dll) != report["native_dll_bytes"] or digest(dll) != native:
        return "candidate_mismatch"
    return "reported_preflight_consistent"


def registration_check(reports, head, native):
    prior = None
    seen = []
    for phase, role in zip(PHASES, REG_ROLES):
        report = reports.get(role)
        if report is None:
            continue
        if (report.get("phase") != phase
                or report.get("canonical_present") is not (phase in ("Installed", "RemoveCancelled"))
                or report.get("ui_actions") != "owner_confirmation_required"
                or report.get("vida") != "not_tested" or report.get("physical_j2534") != "not_tested"):
            raise ValueError("invalid_registration_claim")
        if hash_text(report.get("source_sha"), 40) != head or hash_text(report.get("native_sha256"), 64) != native:
            return "candidate_mismatch", len(seen)
        views = []
        for key in ("registry32_other", "registry64"):
            view = report.get(key)
            if (type(view) is not dict or type(view.get("other_provider_count")) is not int
                    or not 0 <= view["other_provider_count"] <= 100000):
                raise ValueError("invalid_registry_view")
            views.append((hash_text(view.get("digest"), 64), view["other_provider_count"]))
        if prior is not None and views != prior:
            return "registry_snapshot_mismatch", len(seen)
        prior = views
        seen.append(phase)
    if seen != list(PHASES[:len(seen)]):
        return "checkpoint_gap", len(seen)
    if not seen:
        return "not_tested", 0
    return ("reported_checkpoints_consistent" if len(seen) == len(PHASES)
            else "partial_checkpoints"), len(seen)


def gate_value(report, key, choices, favorable):
    if report is None:
        return "not_tested"
    value = report.get(key)
    if value not in choices:
        raise ValueError("invalid_observation_gate")
    # Even the favorable category is only a report claim; these reports
    # have no common authenticated session ID or declared candidate hash.
    return "unbound_report_observation" if value == favorable else "review_required"


def reconcile(manifest, expected_head, files):
    head, native, claims, entries = manifest_fields(manifest, expected_head)
    if set(files) != set(entries):
        raise ValueError("missing_or_extra_evidence")
    reports = {}
    for role, raw in files.items():
        if len(raw) > (MAX_DLL if role == "native_dll" else MAX_JSON):
            raise ValueError("evidence_size")
        if digest(raw) != hash_text(entries[role]["sha256"], 64):
            raise ValueError("evidence_digest_mismatch")
        if role != "native_dll":
            reports[role] = load_json(raw)
            schema_check(role, reports[role])
    reg, count = registration_check(reports, head, native)
    native_state = native_check(reports.get("native_preflight"), head, native, files.get("native_dll"))
    binding = gate_value(reports.get("binding"), "candidate_binding_gate",
        ("snapshot_changed_or_unverifiable", "selected_provider_unavailable", "historical_or_different_binary",
         "binary_equivalence_unverified", "process_identity_unverified", "module_binding_unverified",
         "candidate_path_and_disk_bytes_observed"), "candidate_path_and_disk_bytes_observed")
    vin = gate_value(reports.get("readvin"), "native_evidence_gate",
        ("incomplete_or_ambiguous_native_evidence", "no_positive_identity_delivery_observed",
         "delivered_identity_differs", "matching_lab_identity_delivery_observed"), "matching_lab_identity_delivery_observed")
    ecu = gate_value(reports.get("ecu"), "readout_reconciliation_gate",
        ("no_module_observations", "same_run_not_reported", "reported_discrepancies_require_review",
         "reported_evidence_incomplete", "reported_categories_consistent_only"), "reported_categories_consistent_only")
    catalog = validate_catalog(reports.get("catalog"))
    # Environment assertions are explicitly NOT permission, and no amount
    # of imported evidence changes any actual runtime acceptance flag.
    env = ("owner_claims_only" if manifest["scope"] == "owner_reviewed" and all(claims.values())
           else "blocked_or_synthetic")
    return {
        "schema": "vc092-evidence-bundle-report-v1",
        "scope": manifest["scope"], "source_sha": head, "native_sha256": native,
        "evidence_sha256_by_role": {role: digest(raw) for role, raw in sorted(files.items())},
        "gates": {"environment": env, "native_preflight": native_state,
                  "registration": reg, "binding": binding, "readvin": vin, "ecu": ecu,
                  "catalog": catalog["status"], "file_integrity": "supplied_digests_match"},
        "registration_checkpoints": count, "registration_checkpoints_expected": len(PHASES),
        "catalog_sample": catalog,
        "owner_claims": claims,
        "same_runtime_session_verified": False,
        "vm_snapshot_verified": False,
        "registry_mutation_authorized_by_tool": False,
        "registration_install_remove_verified": False,
        "original_vida_provider_selection_verified": False,
        "loaded_module_identity_verified": False,
        "original_vida_readvin_verified": False,
        "original_vida_ecu_identification_verified": False,
        "original_catalog_coverage_verified": False,
        "physical_j2534_verified": False,
        "release_ready": False,
        "overall": "runtime_acceptance_not_verified",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--expected-head", required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        original = read_frozen(a.manifest, MAX_JSON)
        manifest = load_json(original)
        _, _, _, entries = manifest_fields(manifest, a.expected_head)
        paths = {role: a.manifest.parent / entry["file"] for role, entry in entries.items()}
        out = a.output
        repo = Path(__file__).resolve().parents[2]
        resolved = [a.manifest.resolve(), out.resolve(), *(path.resolve() for path in paths.values())]
        if (not out.is_absolute() or out.anchor.startswith("\\\\") or repo in out.resolve().parents
                or len(set(resolved)) != len(resolved)):
            raise ValueError("unsafe_output_or_alias")
        for part in out.parents:
            info = part.lstat()
            if part.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("reparse_output")
        limits = {role: MAX_DLL if role == "native_dll" else MAX_JSON for role in paths}
        raw = {role: read_frozen(path, limits[role]) for role, path in paths.items()}
        result = reconcile(manifest, a.expected_head, raw)
        if read_frozen(a.manifest, MAX_JSON) != original or any(
                read_frozen(path, limits[role]) != raw[role] for role, path in paths.items()):
            raise ValueError("evidence_changed")
        result["manifest_sha256"] = digest(original)
        with out.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (ValueError, TypeError, OSError, UnicodeError, RecursionError):
        p.exit(2, "ERROR: invalid, inconsistent or unreadable local evidence bundle\n")
    print("VC092_BUNDLE_INTEGRITY=PASS")
    print("VC092_RUNTIME_ACCEPTANCE=NOT_VERIFIED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
