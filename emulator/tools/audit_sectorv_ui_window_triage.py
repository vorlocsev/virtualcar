#!/usr/bin/env python3
"""Strict, redacted triage of one bounded J2534 window and curated SectorV GUI states.

This does NOT correlate raw requests, prove that the two files came from one
Windows process, start SectorV, load a J2534 DLL or validate an OEM VIN.
The operator's same-run assertion is recorded as an assertion, not a fact.
"""
import argparse
import json
from pathlib import Path
import sys

from audit_sectorv_fresh_window import REPORT_SCHEMA as WINDOW_SCHEMA, SERVICES, STATUSES
from audit_j2534_connect import STATUS as CONNECT_STATUS
from audit_sectorv_ui_observation import audit as audit_gui

SCHEMA = "virtualcar-sectorv-ui-window-triage-v1"
MAX_WINDOW_FILE = 512 * 1024
MAX_UI_FILE = 8192
GATES = frozenset((
    "establish_isolated_same_run_evidence",
    "resolve_provider_endpoint_change",
    "obtain_provider_endpoint_evidence",
    "obtain_bounded_j2534_window_evidence",
    "verify_j2534_provider_and_connect",
    "review_absent_b9fb_in_bounded_j2534_window",
    "review_discarded_j2534_line_boundaries",
    "review_b9fb_without_observed_rx",
    "review_client_vin_failure_after_unlinked_rx",
    "review_identity_display_without_oem_validation",
    "review_ecu_identification_after_ui_identity",
    "review_incomplete_gui_or_transport_evidence",
))
MAX_MODULE_FILE = 4096
MODULE_SCHEMA = "virtualcar-sectorv-process-binding-operator-v1"
MODULE_FIELDS = frozenset((
    "schema_version", "scope", "observation", "installed_vs_reference_dll",
    "next_safe_gate", "name_matched_executable_authenticity",
    "operator_same_run_pairing", "registered_provider_unchanged_during_run",
    "reference_dll_pe32", "client_was_launched_by_audit",
    "accepted_vin_or_ecu",
))
MODULE_OBSERVATIONS = frozenset((
    "client_not_observed_in_local_snapshot",
    "client_process_listing_unavailable",
    "multiple_client_name_matches", "registered_library_unknown",
    "registered_library_path_unverifiable",
    "registered_library_loaded_in_name_matched_client",
    "registered_library_not_in_enumerated_modules",
    "client_module_list_unavailable",
))
MODULE_COMPARISONS = frozenset((
    "exact_bytes_at_snapshot", "different_bytes_at_snapshot",
    "comparison_unverifiable", "not_compared",
))


def _module_next_gate(observation, comparison):
    """Mirror the fixed-category PS5.1 operator script, not a process attestation."""
    if comparison == "different_bytes_at_snapshot":
        return "resolve_reference_vs_registered_dll_difference"
    if observation in (
            "client_not_observed_in_local_snapshot",
            "client_process_listing_unavailable"):
        return "observe_client_with_gui_open"
    if observation != "registered_library_loaded_in_name_matched_client":
        return "verify_registered_dll_in_client_module_list"
    if comparison == "not_compared":
        return "collect_gui_evidence_without_reference_attestation"
    if comparison != "exact_bytes_at_snapshot":
        return "verify_reference_and_registered_dll_equivalence"
    return "collect_same_run_redacted_j2534_and_gui_evidence"


def _check_module_snapshot(value):
    """Reject spoofed provenance, free text, paths, hashes and forged next gates."""
    if type(value) is not dict or set(value) != MODULE_FIELDS:
        raise ValueError("unexpected operator module snapshot fields")
    if (value["schema_version"] != MODULE_SCHEMA
            or value["scope"] != "operator_requested_current_host_snapshot_only"
            or type(value["observation"]) is not str
            or value["observation"] not in MODULE_OBSERVATIONS
            or type(value["installed_vs_reference_dll"]) is not str
            or value["installed_vs_reference_dll"] not in MODULE_COMPARISONS
            or value["name_matched_executable_authenticity"] != "not_verified"
            or value["operator_same_run_pairing"] != "not_independently_attested"
            or value["registered_provider_unchanged_during_run"] != "not_verified"
            or value["reference_dll_pe32"] != "not_assessed_by_this_tool"
            or value["client_was_launched_by_audit"] is not False
            or value["accepted_vin_or_ecu"] != "not_verified"):
        raise ValueError("operator snapshot has unsupported provenance")
    if value["next_safe_gate"] != _module_next_gate(
            value["observation"], value["installed_vs_reference_dll"]):
        raise ValueError("operator snapshot next gate contradicts observations")


B9_BUCKETS = ("zero", "one_to_twelve", "thirteen", "fourteen_plus")
PROVIDER_CONSISTENCY = frozenset((
    "same_at_endpoints_only", "changed_between_endpoints",
    "provider_state_changed", "not_verified",
))
WINDOW_FIELDS = frozenset((
    "schema_version", "source", "read_only_audit", "contains_raw_can_or_vin",
    "operator_one_run_confirmed", "cross_log_transaction_attribution",
    "client_ui_result", "client_vehicle_identity_accepted", "replay_approved",
    "connect", "discovery", "backend", "next_gate", "note",
    "windows", "registered_provider",
))


def _uint(value, ceiling=1_000_000):
    if type(value) is not int or not 0 <= value <= ceiling:
        raise ValueError("invalid bounded count")
    return value


def _check_status_counts(values, allowed, expected):
    """Only bounded, allowlisted status counts may support a triage decision."""
    if type(values) is not dict or not set(values).issubset(allowed):
        raise ValueError("invalid status vocabulary")
    if sum(_uint(value) for value in values.values()) != expected:
        raise ValueError("status counts do not match summary")


def _check_window(report):
    """Validate the actual v2 redacted report shape, never trust raw JSON."""
    if type(report) is not dict or set(report) != WINDOW_FIELDS:
        raise ValueError("unrecognized window fields")
    if (report["schema_version"] != WINDOW_SCHEMA
            or report["source"] != "local_bounded_append_only"
            or report["read_only_audit"] is not True
            or report["contains_raw_can_or_vin"] is not False
            or type(report["operator_one_run_confirmed"]) is not bool
            or report["cross_log_transaction_attribution"] != "not_established"
            or report["client_ui_result"] != "not_observed_by_this_tool"
            or report["client_vehicle_identity_accepted"] != "not_verified"
            or report["replay_approved"] is not False):
        raise ValueError("window provenance cannot be trusted")
    windows = report["windows"]
    if type(windows) is not dict or set(windows) != {"j2534", "backend"}:
        raise ValueError("invalid append windows")
    meta_keys = {"new_bytes", "complete_lines", "dropped_first",
                 "dropped_last", "source_present", "prefix_verified"}
    for value in windows.values():
        if type(value) is not dict or set(value) != meta_keys:
            raise ValueError("invalid append metadata")
        _uint(value["new_bytes"], 16 * 1024 * 1024)
        _uint(value["complete_lines"], 16 * 1024 * 1024)
        if value["complete_lines"] > value["new_bytes"]:
            raise ValueError("invalid line accounting")
        for key in ("dropped_first", "dropped_last",
                    "source_present", "prefix_verified"):
            if type(value[key]) is not bool:
                raise ValueError("invalid append provenance")
        if not value["source_present"] and (
                value["new_bytes"] or value["complete_lines"]
                or value["prefix_verified"] or value["dropped_first"]
                or value["dropped_last"]):
            raise ValueError("missing log cannot contain appended evidence")
        if value["dropped_first"] and not value["prefix_verified"]:
            raise ValueError("first boundary drop requires an existing prefix")
        if value["dropped_last"] and not value["new_bytes"]:
            raise ValueError("last boundary drop requires appended bytes")

    provider = report["registered_provider"]
    if type(provider) is not dict or set(provider) != {
            "baseline_category", "postrun_category",
            "binary_endpoint_consistency", "loaded_in_sectorv_client",
            "during_run_immutability", "same_guest_independently_attested"}:
        raise ValueError("unexpected provider metadata")
    if (provider["binary_endpoint_consistency"] not in PROVIDER_CONSISTENCY
            or provider["loaded_in_sectorv_client"] != "not_observed"
            or provider["during_run_immutability"] != "not_verified"
            or provider["same_guest_independently_attested"] is not False):
        raise ValueError("provider claims exceed evidence")
    from audit_sectorv_fresh_window import PROVIDER_STATES
    if (provider["baseline_category"] not in PROVIDER_STATES
            or provider["postrun_category"] not in PROVIDER_STATES):
        raise ValueError("invalid provider category")
    if provider["binary_endpoint_consistency"] == "same_at_endpoints_only" and (
            provider["baseline_category"] != "installed_library_x86"
            or provider["postrun_category"] != "installed_library_x86"):
        raise ValueError("stable endpoints require verified x86 endpoints")

    discovery = report["discovery"]
    if type(discovery) is not dict or set(discovery) != {
            "transactions", "statuses", "d2", "p3_count"}:
        raise ValueError("unexpected discovery shape")
    transactions = _uint(discovery["transactions"])
    if _uint(discovery["p3_count"]) > transactions:
        raise ValueError("P3 count exceeds transactions")
    _check_status_counts(discovery["statuses"], STATUSES, transactions)
    d2 = discovery["d2"]
    if type(d2) is not dict or set(d2) != {"0x40", "0x50"}:
        raise ValueError("unknown CEM target")
    d2_requests = 0
    d2_status_totals = {status: 0 for status in STATUSES}
    for target in ("0x40", "0x50"):
        group = d2[target]
        if type(group) is not dict or set(group) != set(SERVICES):
            raise ValueError("unknown D2 service")
        for service in SERVICES:
            item = group[service]
            if type(item) is not dict or set(item) != {
                    "requests", "statuses", "rx_frame_buckets",
                    "known_can_500k", "unknown_protocol_or_baud"}:
                raise ValueError("unexpected D2 group fields")
            count = _uint(item["requests"])
            d2_requests += count
            _uint(item["known_can_500k"])
            _uint(item["unknown_protocol_or_baud"])
            # One request cannot be both known CAN/500k and unknown.
            if (item["known_can_500k"] + item["unknown_protocol_or_baud"] > count):
                raise ValueError("mutually exclusive route counts overlap")
            _check_status_counts(item["statuses"], STATUSES, count)
            for status, n in item["statuses"].items():
                d2_status_totals[status] += n
            buckets = item["rx_frame_buckets"]
            if type(buckets) is not dict or set(buckets) != set(B9_BUCKETS):
                raise ValueError("invalid RX bucket schema")
            if sum(_uint(v) for v in buckets.values()) != count:
                raise ValueError("invalid RX bucket total")
    # D2 and P3 are mutually exclusive classifications of one J2534 TX.
    if d2_requests + discovery["p3_count"] > transactions:
        raise ValueError("D2 and P3 exceed discovery transaction total")
    if any(n > discovery["statuses"].get(status, 0)
           for status, n in d2_status_totals.items()):
        raise ValueError("D2 status counts contradict discovery total")
    connect = report["connect"]
    if type(connect) is not dict or set(connect) != {"attempts", "statuses"}:
        raise ValueError("invalid connect summary")
    attempts = _uint(connect["attempts"])
    _check_status_counts(connect["statuses"],
                         frozenset(CONNECT_STATUS.values()) | {"other_error"},
                         attempts)
    backend = report["backend"]
    if type(backend) is not dict or set(backend) != {
            "requests", "invalid_lines", "statuses", "d2_probe_coverage"}:
        raise ValueError("invalid backend summary")
    backend_requests = _uint(backend["requests"])
    invalid_lines = _uint(backend["invalid_lines"])
    _check_status_counts(backend["statuses"], STATUSES, backend_requests)
    probes = backend["d2_probe_coverage"]
    expected = {f"D2_{target}_{service}" for target in ("40", "50")
                for service in SERVICES}
    if type(probes) is not dict or set(probes) != expected:
        raise ValueError("invalid backend probe keys")
    backend_probe_requests = 0
    backend_probe_statuses = {status: 0 for status in STATUSES}
    for probe in probes.values():
        if type(probe) is not dict or set(probe) != {"requests", "statuses"}:
            raise ValueError("invalid backend probe shape")
        count = _uint(probe["requests"])
        backend_probe_requests += count
        _check_status_counts(probe["statuses"], STATUSES, count)
        for status, n in probe["statuses"].items():
            backend_probe_statuses[status] += n
    # The backend assigns at most one trusted allowlisted probe per TX.
    if backend_probe_requests > backend_requests:
        raise ValueError("backend probe coverage double-counted requests")
    if any(n > backend["statuses"].get(status, 0)
           for status, n in backend_probe_statuses.items()):
        raise ValueError("backend probe status contradicts summary")
    if ((attempts or transactions) and
            report["windows"]["j2534"]["complete_lines"] == 0):
        raise ValueError("J2534 counts without appended log lines")
    if ((backend_requests or invalid_lines) and
            report["windows"]["backend"]["complete_lines"] == 0):
        raise ValueError("backend counts without appended log lines")


def triage(window, gui_observation, *, operator_pair_confirmed=False,
           module_snapshot=None):
    """Keep optional module observation separate from VIN and transaction proof."""
    if type(operator_pair_confirmed) is not bool:
        raise ValueError("pairing flag must be boolean")
    _check_window(window)
    if module_snapshot is not None:
        _check_module_snapshot(module_snapshot)
    ui = audit_gui(gui_observation)
    raw_gui_source = gui_observation["source"]
    eligible = (window["operator_one_run_confirmed"] is True
                and raw_gui_source == "human_ui_observation"
                and gui_observation["run_scope"] == "single_vm_client_run"
                and gui_observation["read_only"] is True
                and gui_observation["physical_adapter_disconnected"] is True)
    if operator_pair_confirmed and not eligible:
        raise ValueError("same-run assertion lacks both independently curated sources")
    pair = "operator_asserted_not_independently_verified" if operator_pair_confirmed else "unpaired"
    observed = ui["observed_gui_states"]
    provider = window["registered_provider"]["binary_endpoint_consistency"]
    cem40 = window["discovery"]["d2"]["0x40"]["B9FB"]
    cem50 = window["discovery"]["d2"]["0x50"]["B9FB"]
    requests = cem40["requests"] + cem50["requests"]
    nonzero_rx = sum(cem["rx_frame_buckets"][bucket]
                     for cem in (cem40, cem50) for bucket in B9_BUCKETS[1:])
    jmeta = window["windows"]["j2534"]
    partial_lines_discarded = jmeta["dropped_first"] or jmeta["dropped_last"]
    if not operator_pair_confirmed:
        gate = "establish_isolated_same_run_evidence"
    elif provider in ("changed_between_endpoints", "provider_state_changed"):
        gate = "resolve_provider_endpoint_change"
    elif provider != "same_at_endpoints_only":
        gate = "obtain_provider_endpoint_evidence"
    elif observed["connection"] != "connected":
        gate = "verify_j2534_provider_and_connect"
    elif (not window["windows"]["j2534"]["source_present"]
          or window["windows"]["j2534"]["complete_lines"] == 0):
        gate = "obtain_bounded_j2534_window_evidence"
    elif observed["vehicle_identity"] == "displayed":
        gate = ("review_ecu_identification_after_ui_identity"
                if observed["ecu_list"] != "populated"
                else "review_identity_display_without_oem_validation")
    elif requests == 0 and partial_lines_discarded:
        # A dropped TX or matching context line must never become "no B9FB".
        gate = "review_discarded_j2534_line_boundaries"
    elif requests == 0:
        gate = "review_absent_b9fb_in_bounded_j2534_window"
    elif nonzero_rx == 0:
        gate = "review_b9fb_without_observed_rx"
    elif observed["error_category"] == "vin_read_failed":
        gate = "review_client_vin_failure_after_unlinked_rx"
    else:
        gate = "review_incomplete_gui_or_transport_evidence"
    if gate not in GATES:
        raise ValueError("invalid triage category")
    result = {
        "schema_version": SCHEMA,
        "inputs": ("redacted_window_gui_and_operator_module_categories"
                   if module_snapshot is not None
                   else "redacted_bounded_window_and_curated_gui_categories"),
        "read_only": True,
        "contains_raw_can_vin_paths_or_hashes": False,
        "run_pairing": pair,
        "same_guest_independently_attested": False,
        "transaction_level_correlation": "not_established",
        "j2534_binary_loaded_in_gui_client": "not_verified",
        "provider_endpoint_consistency": provider,
        "provider_unchanged_during_run": "not_verified",
        "gui_connection_state": observed["connection"],
        "gui_error_category": observed["error_category"],
        "gui_vehicle_identity_displayed": observed["vehicle_identity"] == "displayed",
        "gui_ecu_list_populated": observed["ecu_list"] == "populated",
        "j2534_discarded_partial_boundary_lines": partial_lines_discarded,
        "b9fb_request_count_in_window": requests,
        "b9fb_requests_with_nonzero_rx_in_window": nonzero_rx,
        "client_vehicle_identity_accepted": "not_verified",
        "oem_vin_and_ecu_verified": False,
        "replay_approved": False,
        "first_next_gate": gate,
    }
    if module_snapshot is not None:
        # This was a snapshot of a *name-matched* process on the caller's
        # host. Neither the host/session nor genuine executable identity
        # is independently authenticated. Do not alter the original
        # transport/GUI gate or set j2534_binary_loaded_in_gui_client.
        result["operator_module_snapshot"] = {
            "observation": module_snapshot["observation"],
            "reference_byte_comparison": module_snapshot["installed_vs_reference_dll"],
            "next_safe_gate": module_snapshot["next_safe_gate"],
            "same_guest_or_run_attested": False,
            "client_executable_authenticity": "not_verified",
            "module_used_for_j2534_requests": "not_verified",
        }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-report", type=Path, required=True)
    parser.add_argument("--ui-observation", type=Path, required=True)
    parser.add_argument("--module-snapshot", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--operator-same-run-confirmed", action="store_true")
    args = parser.parse_args(argv)
    try:
        from audit_sectorv_fresh_window import _external_output
        sources = [args.window_report, args.ui_observation]
        if args.module_snapshot is not None:
            sources.append(args.module_snapshot)
        if len({p.resolve() for p in sources}) != len(sources):
            raise ValueError("duplicate input source")
        _external_output(args.output, tuple(sources))
        if (args.window_report.stat().st_size > MAX_WINDOW_FILE
                or args.ui_observation.stat().st_size > MAX_UI_FILE
                or (args.module_snapshot is not None
                    and args.module_snapshot.stat().st_size > MAX_MODULE_FILE)):
            raise ValueError("input size exceeded")
        win = json.loads(args.window_report.read_text(encoding="utf-8"))
        gui = json.loads(args.ui_observation.read_text(encoding="utf-8"))
        module = (json.loads(args.module_snapshot.read_text(encoding="utf-8"))
                  if args.module_snapshot is not None else None)
        result = triage(win, gui, operator_pair_confirmed=args.operator_same_run_confirmed,
                        module_snapshot=module)
        with args.output.open("x", encoding="utf-8") as output:
            json.dump(result, output, ensure_ascii=False, indent=2)
            output.write("\n")
        print("Read-only SectorV triage ready; client VIN and ECU acceptance NOT verified.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError):
        # No private path, raw log, UI free text or untrusted exception message.
        print("SectorV triage stopped: invalid or unverified input", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
