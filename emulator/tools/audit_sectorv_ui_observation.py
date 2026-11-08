#!/usr/bin/env python3
"""Summarize a manually curated SectorV GUI observation from one offline VM run.

Not a screenshot parser, client log parser, J2534 trace or proof of OEM identity.
Free text, VIN, file paths, CAN frames and identifiers are rejected by schema.
No diagnostic or adapter APIs are used.
"""
import argparse
import json
from pathlib import Path

SCHEMA = "virtualcar-sectorv-ui-observation-v1"
OBSERVATIONS = {
    "adapter_listed": {"yes", "no", "unknown"},
    "adapter_selected": {"yes", "no", "unknown"},
    "connection": {"connected", "failed", "not_attempted", "unknown"},
    "ecu_list": {"populated", "empty", "not_opened", "unknown"},
    "vehicle_identity": {"displayed", "not_displayed", "unknown"},
    "error_category": {
        "none", "adapter_missing", "connect_error", "vin_read_failed",
        "vehicle_unrecognized", "timeout", "other", "unknown"
    },
}
KEYS = {
    "schema_version", "client", "scenario", "source", "run_scope",
    "read_only", "physical_adapter_disconnected", "observations"
}


def audit(raw):
    """Reject uncurated inputs; report only bounded, explicitly observed UI states."""
    if type(raw) is not dict or set(raw) != KEYS:
        raise ValueError("expected exactly the allowlisted top-level fields")
    if (raw["schema_version"] != SCHEMA or raw["client"] != "SectorV"
            or raw["scenario"] not in ("P2_MY2009_lab", "P2_MY2005_lab", "unknown_lab")
            or raw["source"] != "human_ui_observation"
            or raw["run_scope"] != "single_vm_client_run"
            or raw["read_only"] is not True
            or raw["physical_adapter_disconnected"] is not True):
        raise ValueError("only a single, isolated read-only SectorV GUI run is supported")
    observed = raw["observations"]
    if type(observed) is not dict or set(observed) != set(OBSERVATIONS):
        raise ValueError("GUI observation must have only six fixed categories")
    for key, choices in OBSERVATIONS.items():
        if type(observed[key]) is not str or observed[key] not in choices:
            raise ValueError("invalid GUI category: " + key)

    listed = observed["adapter_listed"]
    selected = observed["adapter_selected"]
    connection = observed["connection"]
    ecu_list = observed["ecu_list"]
    identity = observed["vehicle_identity"]
    error = observed["error_category"]
    if selected == "yes" and listed != "yes":
        raise ValueError("selected adapter must also be listed")
    if connection == "connected" and selected != "yes":
        raise ValueError("connected GUI must have an explicitly selected adapter")
    if (ecu_list == "populated" or identity == "displayed") and connection != "connected":
        raise ValueError("current-run ECU or identity observation needs a connected client")
    if error == "adapter_missing" and listed != "no":
        raise ValueError("adapter_missing contradicts adapter list")
    if error == "connect_error" and connection != "failed":
        raise ValueError("connect_error requires failed connection")
    if error == "none" and connection == "failed":
        raise ValueError("failed connection cannot report no error")

    if listed == "no":
        next_gate = "review_adapter_registration_and_client_provider_list"
    elif selected != "yes":
        next_gate = "confirm_explicit_canonical_adapter_selection"
    elif connection == "failed":
        next_gate = "review_same_run_j2534_connect_status"
    elif connection != "connected":
        next_gate = "observe_client_connect_state"
    elif identity != "displayed" and error == "vin_read_failed":
        next_gate = "review_same_run_vin_read_request_and_b9fb_delivery"
    elif identity != "displayed":
        next_gate = "review_same_run_b9fb_delivery_and_verified_fixture"
    elif ecu_list != "populated":
        next_gate = "review_same_run_ecu_identification_requests"
    else:
        next_gate = "independently_validate_displayed_identity_and_ecu_provenance"

    return {
        "schema_version": "virtualcar-sectorv-ui-observation-report-v1",
        "read_only": True,
        "contains_payload_data": False,
        "client": "SectorV",
        "scenario": raw["scenario"],
        "source": "human_ui_observation_unverified",
        "scope": "one_isolated_vm_client_run",
        "physical_adapter_disconnected_reported": True,
        "observed_gui_states": {key: observed[key] for key in OBSERVATIONS},
        "adapter_selected_in_gui": selected == "yes",
        "connection_displayed_in_gui": connection == "connected",
        "ecu_list_populated_in_gui": ecu_list == "populated",
        "vehicle_identity_displayed_in_gui": identity == "displayed",
        "vehicle_identity_validated_against_xc90_my2009": "not_verified",
        "ecu_identification_validated_against_oem_sources": "not_verified",
        "j2534_transaction_correlation": "not_established",
        "client_acceptance_e2e": "not_verified",
        "replay_approved": False,
        "first_next_gate": next_gate,
        "interpretation": (
            "GUI states are human observations, not proof of ECU authenticity, "
            "VIN validity or transaction-level correspondence with J2534. "
            "No identifiers or diagnostic payloads were collected."
        ),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Classify curated read-only SectorV UI states")
    parser.add_argument("input", type=Path, help="One locally curated fixed-schema JSON; not a screenshot or raw log")
    parser.add_argument("--output", type=Path, required=True, help="Create a new redacted JSON file")
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        parser.error("input and output must be different files")
    try:
        if args.input.stat().st_size > 8192:
            raise ValueError("input exceeds 8192 bytes")
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        report = audit(raw)
    except (OSError, UnicodeError, TypeError, ValueError) as exc:
        parser.error("invalid observation: " + type(exc).__name__)
    try:
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(report, output, indent=2, ensure_ascii=False)
            output.write("\n")
    except OSError as exc:
        parser.error("cannot exclusively create report: " + type(exc).__name__)
    print("SectorV UI observation classified; OEM identity/E2E acceptance NOT VERIFIED")


if __name__ == "__main__":
    main()
