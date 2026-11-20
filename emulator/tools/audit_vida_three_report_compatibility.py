#!/usr/bin/env python3
"""Fail-closed comparison of three *redacted*, independent VIDA evidence reports.

B3A332 XML candidate, B3A333 name-matched module snapshot and B3A334
Procmon file-I/O summaries cannot establish a shared session. They contain no
trusted process identity, file identity or common capture ID. This tool never
promotes compatible observations to original VIDA runtime / VIN acceptance.
"""
import argparse
import json
from pathlib import Path
import sys

SCHEMA = "virtualcar-vida-three-report-compatibility-v1"
INPUT_SCHEMAS = {
    "xml": "virtualcar-vida-connection-config-candidate-v1",
    "module": "virtualcar-vida-process-binding-operator-v1",
    "procmon": "virtualcar-vida-procmon-config-read-v1",
}
MAX_REPORT_BYTES = 65536
MODES = frozenset((
    "J2534DiagnosticConnection", "DiCEDiagnosticConnection",
    "VirtualDiagnosticConnection", "NoCommConnection", "unrecognized_mode",
))
MODULE_NAMES = frozenset(("iexplore", "java", "VidaMonitor", "w3wp"))
MODULE_STATES = frozenset((
    "registered_library_loaded_in_name_matched_client",
    "registered_library_not_in_enumerated_modules",
    "registered_library_unknown",
    "registered_library_path_unverifiable",
    "client_not_observed_in_local_snapshot",
    "client_module_list_unavailable",
    "client_process_listing_unavailable",
    "multiple_client_name_matches",
))
DLL_COMPARE = frozenset((
    "exact_bytes_at_snapshot", "different_bytes_at_snapshot",
    "comparison_unverifiable", "not_compared",
))
PE_STATES = frozenset((
    "x86_pe32_header", "other_pe", "invalid_pe", "not_compared", "unverifiable",
))
IO_CATEGORIES = frozenset((
    "multiple_candidate_paths_read", "multiple_name_matched_processes_read",
    "read_after_same_pid_path_open",
    "read_without_prior_matching_open_in_export", "open_only_no_read_in_export",
    "failed_candidate_io_only", "no_matching_candidate_file_io",
))
BUCKETS = frozenset(("zero", "one", "multiple"))
FLAG_PAIRS = {
    "xml": (
        "client_or_server_config_path_selected_at_runtime_verified",
        "original_vida_process_loaded_this_file_verified",
        "actual_diagnostic_connection_mode_verified",
        "j2534_connect_or_messages_verified",
        "original_vida_readvin_executed_verified",
        "original_vida_vin_accepted_verified",
        "ecu_identity_accepted_verified",
    ),
    "module": (
        "selected_process_is_authenticated_original_vida",
        "loaded_binary_memory_matches_disk_verified",
        "active_vida_diagnostic_config_loaded_verified",
        "effective_diagnostic_connection_mode_verified",
        "original_vida_script_selection_verified",
        "original_vida_j2534_tx_rx_verified",
        "original_vida_vin_accepted_verified",
        "ecu_identity_accepted_verified",
    ),
    "procmon": (
        "csv_complete_unfiltered_capture_verified",
        "csv_chronological_order_verified",
        "original_vida_process_authenticity_verified",
        "original_vida_effective_config_path_verified",
        "diagnostic_xml_parsed_by_client_verified",
        "effective_diagnostic_connection_mode_verified",
        "paired_with_live_module_snapshot_verified",
        "original_vida_getscript_readvin_verified",
        "original_vida_j2534_tx_rx_verified",
        "original_vida_vin_accepted_verified",
        "ecu_identity_accepted_verified",
    ),
}


class ReportError(Exception):
    """Fixed error: never print user-provided source material."""


def _required(report, key, kind):
    value = report.get(key)
    if kind == "bool":
        if type(value) is not bool:
            raise ReportError("invalid_report_field")
    elif kind == "int":
        if type(value) is not int or not 0 <= value <= 300000:
            raise ReportError("invalid_report_counter")
    elif kind == "str":
        if not isinstance(value, str):
            raise ReportError("invalid_report_field")
    return value


def _category(report, key, permitted):
    value = _required(report, key, "str")
    if value not in permitted:
        raise ReportError("invalid_report_category")
    return value


def _false_flags(report, role):
    for key in FLAG_PAIRS[role]:
        if _required(report, key, "bool") is not False:
            raise ReportError("unsupported_positive_attestation")


def validate(role, report):
    if role not in INPUT_SCHEMAS or not isinstance(report, dict):
        raise ReportError("invalid_report")
    if report.get("schema_version") != INPUT_SCHEMAS[role]:
        raise ReportError("wrong_report_schema")
    _false_flags(report, role)
    if role == "xml":
        mode = _category(report, "mode_candidate", MODES)
        if _required(report, "use_client_settings_candidate", "bool") not in (
                True, False):
            raise ReportError("invalid_xml_report")
        if (report.get("mode_if_this_file_was_loaded") != mode or
                _required(report, "no_comm_candidate_if_loaded", "bool")
                != (mode == "NoCommConnection") or
                _required(report, "j2534_candidate_if_loaded", "bool")
                != (mode == "J2534DiagnosticConnection") or
                _required(report, "xml_structure_read_only", "bool") is not True):
            raise ReportError("inconsistent_xml_candidate_report")
        return {"mode": mode,
                "use_client_settings": report["use_client_settings_candidate"]}
    if role == "module":
        name = _category(report, "selected_process_name_category",
                         MODULE_NAMES)
        state = _category(report, "registered_virtual_module_observation",
                          MODULE_STATES)
        comparison = _category(report, "installed_vs_reference_dll",
                               DLL_COMPARE)
        pe = _category(report, "reference_dll_pe32", PE_STATES)
        loaded = state == "registered_library_loaded_in_name_matched_client"
        if (_required(
                report,
                "registered_dll_module_path_seen_in_name_matched_process",
                "bool") != loaded or
                _required(report, "client_started_by_audit", "bool") is not False or
                _required(report, "physical_adapter_examined", "bool") is not False):
            raise ReportError("inconsistent_module_report")
        if report.get("scope") != "operator_requested_current_host_name_match_only":
            raise ReportError("unsupported_module_scope")
        return {"name": name.casefold() + ".exe", "state": state, "comparison": comparison,
                "pe": pe, "loaded": loaded}
    process = _category(report, "selected_process_name_category",
                        frozenset(name + ".exe" for name in MODULE_NAMES))
    category = _category(report, "file_io_category", IO_CATEGORIES)
    opens = _required(report, "candidate_createfile_success_events", "int")
    reads = _required(report, "candidate_readfile_success_events", "int")
    after = _required(
        report, "candidate_readfile_after_prior_same_pid_path_open_events", "int")
    without = _required(
        report, "candidate_readfile_without_prior_matching_open_events", "int")
    failed = _required(report, "candidate_file_io_failed_events", "int")
    read_path_bucket = _category(
        report, "distinct_read_candidate_paths_bucket", BUCKETS)
    read_process_bucket = _category(
        report, "distinct_name_matched_processes_with_successful_reads_bucket",
        BUCKETS)
    opened_bucket = _category(report, "distinct_opened_candidate_paths_bucket",
                              BUCKETS)
    _category(report, "distinct_name_matched_processes_with_candidate_io_bucket",
              BUCKETS)
    if (_required(report, "candidate_csv_structure_parsed", "bool") is not True
            or report.get("source_scope")
            != "one_owner_selected_existing_procmon_csv"
            or after + without != reads or after > reads or after > 0 and opens == 0
            or (read_path_bucket == "zero") != (reads == 0)
            or (read_process_bucket == "zero") != (reads == 0)
            or (opened_bucket == "zero") != (opens == 0)):
        raise ReportError("inconsistent_procmon_counts")
    if (category == "no_matching_candidate_file_io" and
            (opens or reads or failed)):
        raise ReportError("inconsistent_procmon_category")
    if (category == "open_only_no_read_in_export" and
            not (opens > 0 and reads == 0)):
        raise ReportError("inconsistent_procmon_category")
    if (category == "failed_candidate_io_only" and
            not (failed > 0 and reads == 0 and opens == 0)):
        raise ReportError("inconsistent_procmon_category")
    if category in ("multiple_candidate_paths_read",
                    "multiple_name_matched_processes_read") and reads < 2:
        raise ReportError("inconsistent_procmon_category")
    if category == "read_after_same_pid_path_open" and after == 0:
        raise ReportError("inconsistent_procmon_category")
    if category == "read_without_prior_matching_open_in_export" and (
            reads == 0 or after != 0):
        raise ReportError("inconsistent_procmon_category")
    return {"name": process, "category": category, "reads": reads,
            "read_bucket": read_path_bucket,
            "read_process_bucket": read_process_bucket}


def compare(xml, module, procmon):
    a = validate("xml", xml)
    b = validate("module", module)
    c = validate("procmon", procmon)
    same_name_category = b["name"] == c["name"]
    file_read = c["reads"] > 0
    file_unambiguous_category = (
        c["read_bucket"] == "one" and c["read_process_bucket"] == "one")
    module_match = b["loaded"] and b["comparison"] == "exact_bytes_at_snapshot"
    pe32 = b["pe"] == "x86_pe32_header"

    if not same_name_category:
        category = "candidate_process_name_categories_differ"
    elif not file_read:
        category = "no_successful_candidate_file_read_in_export"
    elif not file_unambiguous_category:
        category = "candidate_file_or_process_read_ambiguous"
    elif not b["loaded"]:
        category = "registered_virtual_module_not_observed_in_candidate"
    elif not module_match or not pe32:
        category = "virtual_module_reference_not_equivalent_and_pe32_checked"
    elif a["mode"] == "NoCommConnection":
        category = "no_comm_xml_candidate_coexists_with_virtual_module"
    elif a["mode"] == "J2534DiagnosticConnection":
        category = "j2534_xml_candidate_and_virtual_module_compatible_only"
    else:
        category = "other_xml_mode_candidate_coexists_with_virtual_module"

    return {
        "schema_version": SCHEMA,
        "source_scope": "three_independent_redacted_input_reports_only",
        "xml_mode_candidate": a["mode"],
        "xml_use_client_settings_candidate": a["use_client_settings"],
        "module_name_category": b["name"],
        "procmon_process_name_category": c["name"],
        "process_name_categories_match": same_name_category,
        "registered_dll_path_seen_in_name_matched_client": b["loaded"],
        "registered_vs_reference_disk_bytes_match": module_match,
        "reference_pe32_header_observed": pe32,
        "procmon_successful_candidate_read_observed": file_read,
        "procmon_single_read_path_and_name_matched_pid_buckets":
            file_unambiguous_category,
        "candidate_observation_compatibility": category,
        "same_host_and_capture_window_verified": False,
        "same_process_identity_across_reports_verified": False,
        "same_config_file_path_between_xml_and_procmon_verified": False,
        "complete_original_procmon_capture_verified": False,
        "authenticated_original_vida_executable_verified": False,
        "original_vida_read_xml_and_loaded_dll_in_one_process_verified": False,
        "effective_original_vida_diagnostic_connection_mode_verified": False,
        "original_vida_getscript_readvin_executed_verified": False,
        "original_vida_j2534_tx_rx_verified": False,
        "original_vida_vin_accepted_verified": False,
        "ecu_identity_accepted_verified": False,
        "private_path_pid_vin_raw_report_values_exported": False,
        "next_gate": "independently_prove_process_file_and_capture_session_identity",
        "limitations": [
            "These independent redacted reports contain no shared trusted run or process ID.",
            "Matching a process name category does not link processes or hosts.",
            "Procmon same-name ReadFile does not tie the read path to the input XML.",
            "A registered DLL module and a NoCommConnection XML candidate can coexist.",
            "Even compatible candidates do not establish an effective VIDA runtime mode.",
            "ReadVin, actual J2534 TX/RX, GUI VIN and ECU acceptance remain untested.",
        ],
    }


def _unique_pairs(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise ReportError("duplicate_json_key")
        out[key] = value
    return out


def read_report(path):
    if (not isinstance(path, Path) or path.suffix.lower() != ".json"
            or path.is_symlink() or not path.is_file()):
        raise ReportError("invalid_input_report_path")
    try:
        before = path.stat()
        if not 0 < before.st_size <= MAX_REPORT_BYTES:
            raise ReportError("invalid_report_size")
        data = path.read_bytes()
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (
                after.st_size, after.st_mtime_ns):
            raise ReportError("report_changed_during_read")
        return json.loads(data.decode("utf-8-sig"),
                          object_pairs_hook=_unique_pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(
                              ReportError("nonfinite_json_value")))
    except ReportError:
        raise
    except (OSError, UnicodeError, ValueError, TypeError, RecursionError):
        raise ReportError("invalid_input_report") from None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline compatibility of three separate VIDA evidence reports")
    parser.add_argument("--xml-report", type=Path, required=True)
    parser.add_argument("--module-report", type=Path, required=True)
    parser.add_argument("--procmon-report", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = compare(read_report(args.xml_report),
                         read_report(args.module_report),
                         read_report(args.procmon_report))
    except ReportError:
        print("ERROR: VIDA_THREE_REPORT_PROVENANCE_NOT_VERIFIED", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
