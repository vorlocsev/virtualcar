#!/usr/bin/env python3
"""Offline exact-path/PID candidate VIDA config I/O check, private by design.

This improves on B3A335's redacted three-report comparison by inspecting
the original *owner-selected* Procmon CSV and local XML in the same offline
invocation. Equality of a logged PID/path is NOT authentication of VIDA,
an OS file handle, the file's bytes at capture time or an effective mode.
"""
import argparse
import csv
import io
import json
import os
from pathlib import Path
import sys

import audit_vida_connection_config_candidate as xml_audit
import audit_vida_procmon_config_read as procmon

SCHEMA = "virtualcar-vida-exact-config-source-candidate-v1"


class SourceError(Exception):
    """Error vocabulary is intentionally not emitted to console."""


def _pid(raw):
    value = str(raw)
    if not value.isascii() or not value.isdecimal():
        raise SourceError("invalid_selected_pid")
    number = int(value)
    if not 1 <= number <= 0xFFFFFFFF:
        raise SourceError("invalid_selected_pid")
    return number


def analyze_text(text, process_name, pid, selected_path, xml_report):
    """Compare private exact path and PID without returning either value."""
    name = procmon._process_name(process_name)
    selected_pid = _pid(pid)
    selected = procmon._candidate_path(selected_path)
    if selected is None:
        raise SourceError("invalid_selected_xml_path")
    if (not isinstance(xml_report, dict) or
            xml_report.get("schema_version") != xml_audit.SCHEMA or
            xml_report.get("original_vida_vin_accepted_verified") is not False or
            xml_report.get("actual_diagnostic_connection_mode_verified") is not False or
            xml_report.get("xml_structure_read_only") is not True or
            xml_report.get("mode_candidate") not in (
                *xml_audit.MODES, "unrecognized_mode")):
        raise SourceError("untrusted_xml_candidate")
    if not isinstance(text, str) or not 0 < len(text) <= procmon.MAX_BYTES:
        raise SourceError("invalid_csv_size")
    csv.field_size_limit(procmon.MAX_FIELD)
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        if (not reader.fieldnames or
                len(reader.fieldnames) != len(set(reader.fieldnames)) or
                not procmon.REQUIRED.issubset(reader.fieldnames)):
            raise SourceError("invalid_csv_columns")
        open_pending = False
        exact_open = exact_read = read_after_open = failed_exact = 0
        same_pid_other_path_reads = other_pid_exact_path_reads = 0
        examined = 0
        for row in reader:
            examined += 1
            if (examined > procmon.MAX_ROWS or not isinstance(row, dict)
                    or None in row or not all(
                        isinstance(row.get(k), str) for k in procmon.REQUIRED)):
                raise SourceError("invalid_csv_row")
            if row["Process Name"].casefold() != name:
                continue
            if row["Operation"] not in ("CreateFile", "ReadFile", "CloseFile"):
                continue
            path = procmon._candidate_path(row["Path"])
            if path is None:
                continue
            # Do not accept an invalid PID on any relevant config record
            # even when it is not the operator-selected PID.
            record_pid = _pid(row["PID"])
            is_exact = path == selected
            is_selected_pid = record_pid == selected_pid
            if not is_exact:
                if (is_selected_pid and row["Operation"] == "ReadFile"
                        and row["Result"] == "SUCCESS"):
                    same_pid_other_path_reads += 1
                continue
            if not is_selected_pid:
                if row["Operation"] == "ReadFile" and row["Result"] == "SUCCESS":
                    other_pid_exact_path_reads += 1
                continue
            if row["Result"] != "SUCCESS":
                if row["Operation"] in ("CreateFile", "ReadFile"):
                    failed_exact += 1
                continue
            if row["Operation"] == "CreateFile":
                exact_open += 1
                open_pending = True
            elif row["Operation"] == "ReadFile":
                exact_read += 1
                if open_pending:
                    read_after_open += 1
            else:
                # No OS handle ID is present in this CSV. This is merely a
                # conservative same-PID/path row-order heuristic.
                open_pending = False
    except (csv.Error, UnicodeError, ValueError, OverflowError):
        raise SourceError("invalid_csv") from None

    if exact_read:
        if same_pid_other_path_reads:
            category = "selected_pid_read_multiple_candidate_config_paths"
        elif other_pid_exact_path_reads:
            category = "selected_config_path_read_by_multiple_name_matched_pids"
        elif read_after_open:
            category = "selected_pid_exact_path_read_after_open_rows"
        else:
            category = "selected_pid_exact_path_read_without_open_row"
    elif other_pid_exact_path_reads:
        category = "selected_config_read_only_by_different_pid"
    elif same_pid_other_path_reads:
        category = "selected_pid_read_only_other_config_path"
    elif exact_open:
        category = "selected_pid_exact_path_open_only"
    elif failed_exact:
        category = "selected_pid_exact_path_io_failed_only"
    else:
        category = "no_selected_pid_exact_path_io_in_export"

    return {
        "schema_version": SCHEMA,
        "source_scope": "owner_selected_existing_csv_and_xml_snapshot_only",
        "selected_process_name_category": name,
        "xml_mode_candidate": xml_report["mode_candidate"],
        "xml_use_client_settings_candidate":
            xml_report["use_client_settings_candidate"],
        "source_row_match_category": category,
        "selected_pid_exact_path_createfile_success_rows": exact_open,
        "selected_pid_exact_path_readfile_success_rows": exact_read,
        "selected_pid_exact_path_readfile_after_prior_open_rows": read_after_open,
        "selected_pid_exact_path_failed_open_or_read_rows": failed_exact,
        "selected_pid_other_config_path_successful_reads":
            same_pid_other_path_reads,
        "other_pid_selected_config_path_successful_reads":
            other_pid_exact_path_reads,
        "literal_selected_pid_and_normalized_path_found_in_csv":
            exact_read > 0 or exact_open > 0 or failed_exact > 0,
        "selected_pid_exact_path_successful_read_observed": exact_read > 0,
        "csv_complete_unfiltered_capture_verified": False,
        "csv_chronological_order_and_file_handle_verified": False,
        "selected_pid_authentic_original_vida_verified": False,
        "selected_pid_start_time_and_capture_window_verified": False,
        "selected_config_file_contents_at_capture_time_verified": False,
        "original_vida_selected_this_config_file_verified": False,
        "effective_diagnostic_connection_mode_verified": False,
        "same_process_loaded_virtual_j2534_module_verified": False,
        "original_vida_readvin_getscript_verified": False,
        "original_vida_j2534_tx_rx_verified": False,
        "original_vida_vin_accepted_verified": False,
        "ecu_identity_accepted_verified": False,
        "private_pid_path_xml_vin_exported": False,
        "next_gate": "independently_verify_original_process_identity_and_capture_window",
        "limitations": [
            "Matching a PID and normalized path in an exported CSV is a stronger row match, not OS file identity.",
            "Procmon may be filtered, reordered or from an earlier process with a recycled PID.",
            "The local XML contents may differ from the bytes read by the process at capture time.",
            "No J2534 module presence or effective VIDA diagnostic mode is inferred.",
            "ReadVin, J2534 TX/RX and accepted VIN/ECU are not tested.",
        ],
    }


def _read_owner_csv(path):
    if (not isinstance(path, Path) or path.suffix.casefold() != ".csv"
            or path.is_symlink() or not path.is_file()):
        raise SourceError("invalid_csv_file")
    try:
        before = path.stat()
        if not 0 < before.st_size <= procmon.MAX_BYTES:
            raise SourceError("csv_size")
        with path.open("rb") as stream:
            prefix = stream.read(4)
            stream.seek(0)
            data = stream.read(procmon.MAX_BYTES + 1)
        if len(data) > procmon.MAX_BYTES:
            raise SourceError("csv_size")
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (
                after.st_size, after.st_mtime_ns):
            raise SourceError("csv_changed")
        encoding = ("utf-16" if prefix.startswith((b"\xff\xfe", b"\xfe\xff"))
                    else "utf-8-sig")
        return data.decode(encoding, errors="strict")
    except SourceError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise SourceError("csv_unreadable") from None


def analyze_files(csv_path, xml_path, process_name, pid):
    if not isinstance(xml_path, Path) or os.name != "nt":
        # The real owner-only path identity check is Windows-specific:
        # accepting a Linux pathname as a Windows path would invent a match.
        raise SourceError("windows_owner_host_required")
    normalized = procmon._candidate_path(str(xml_path))
    if normalized is None:
        raise SourceError("not_absolute_windows_config_path")
    try:
        xml_report = xml_audit.classify_path(xml_path)
    except xml_audit.CandidateError:
        raise SourceError("invalid_xml_candidate") from None
    return analyze_text(_read_owner_csv(csv_path), process_name, pid,
                        str(xml_path), xml_report)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Offline exact-PID/path VIDA candidate config file read audit")
    parser.add_argument("--procmon-csv", type=Path, required=True)
    parser.add_argument("--xml-candidate", type=Path, required=True)
    parser.add_argument("--process-name", required=True,
                        choices=sorted(procmon.PROCESS_NAMES))
    parser.add_argument("--pid", required=True,
                        help="Private owner-selected numeric PID; never echoed in report")
    args = parser.parse_args(argv)
    try:
        report = analyze_files(args.procmon_csv, args.xml_candidate,
                               args.process_name, args.pid)
    except (SourceError, procmon.AuditError):
        print("ERROR: VIDA_EXACT_CANDIDATE_FILE_READ_NOT_VERIFIED", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
