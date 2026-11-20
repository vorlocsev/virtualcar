#!/usr/bin/env python3
"""Offline, privacy-bounded Procmon CSV evidence for candidate VIDA config reads.

Only an explicit owner-selected CSV and an explicit candidate process name are
inspected. Successful CreateFile/ReadFile for diagnostic.config.xml is file I/O,
NOT proof of original VIDA identity, parsed XML, effective mode or ReadVin.
Never launches Procmon, VIDA, J2534 or any executable; never saves raw events.
"""
import argparse
import csv
import io
import json
import ntpath
from pathlib import Path
import sys

SCHEMA = "virtualcar-vida-procmon-config-read-v1"
MAX_BYTES = 32 * 1024 * 1024
MAX_ROWS = 300_000
MAX_FIELD = 8192
REQUIRED = frozenset(("Process Name", "PID", "Operation", "Path", "Result"))
PROCESS_NAMES = frozenset((
    "iexplore.exe", "java.exe", "vidamonitor.exe", "w3wp.exe",
))
TARGET = "diagnostic.config.xml"


class AuditError(Exception):
    """Static error marker; no private CSV value or path is ever copied."""


def _bucket(size):
    return "zero" if size == 0 else "one" if size == 1 else "multiple"


def _candidate_path(raw):
    if (not isinstance(raw, str) or not 1 <= len(raw) <= 2048
            or "\0" in raw or not ntpath.isabs(raw)):
        return None
    # Procmon normally shows drive-qualified or UNC paths. Root-relative
    # strings alone must not be promoted to an observed concrete file.
    drive, tail = ntpath.splitdrive(raw)
    qualified_drive = (len(drive) == 2 and drive[1] == ":"
                       and tail.startswith(("\\", "/")))
    qualified_unc = raw.startswith("\\\\") and len(drive) > 2
    if not qualified_drive and not qualified_unc:
        return None
    if ntpath.basename(raw).casefold() != TARGET:
        return None
    return ntpath.normcase(ntpath.normpath(raw))


def _process_name(value):
    if not isinstance(value, str) or value.casefold() not in PROCESS_NAMES:
        raise AuditError("unsupported_process_name")
    return value.casefold()


def analyze_reader(reader, selected_process):
    """Read rows in original CSV order; never infer handle IDs or runtime mode."""
    selected = _process_name(selected_process)
    columns = reader.fieldnames
    if (not columns or len(columns) != len(set(columns))
            or not REQUIRED.issubset(columns)):
        raise AuditError("missing_or_duplicate_csv_columns")

    # The exported trace can be filtered, reordered or truncated. No evidence
    # here authenticates Procmon, process image, source path or capture order.
    open_paths = set()
    successful_open = 0
    successful_read = 0
    read_after_open = 0
    read_without_open = 0
    failed_candidate_io = 0
    affected_pids = set()
    read_pids = set()
    read_paths = set()
    open_paths_all = set()
    rows = 0
    try:
        for row in reader:
            rows += 1
            if rows > MAX_ROWS or not isinstance(row, dict) or None in row:
                raise AuditError("invalid_or_oversized_csv")
            if not all(isinstance(row.get(key), str) for key in REQUIRED):
                raise AuditError("invalid_or_oversized_csv")
            if row["Process Name"].casefold() != selected:
                continue
            op = row["Operation"]
            if op not in ("CreateFile", "ReadFile", "CloseFile"):
                continue
            path = _candidate_path(row["Path"])
            if path is None:
                continue
            pid = row["PID"]
            if not pid.isascii() or not pid.isdecimal() or not 0 < int(pid) <= 0xFFFFFFFF:
                raise AuditError("invalid_selected_process_pid")
            if len(row["Path"]) > 2048:
                raise AuditError("invalid_selected_candidate_path")
            key = (pid, path)
            affected_pids.add(pid)
            if row["Result"] != "SUCCESS":
                if op in ("CreateFile", "ReadFile"):
                    failed_candidate_io += 1
                continue
            if op == "CreateFile":
                successful_open += 1
                open_paths.add(key)
                open_paths_all.add(path)
            elif op == "ReadFile":
                successful_read += 1
                read_pids.add(pid)
                read_paths.add(path)
                if key in open_paths:
                    read_after_open += 1
                else:
                    read_without_open += 1
            else:
                # Without handle IDs, even a same-process close does not prove
                # which handle closed. A later read is treated conservatively.
                open_paths.discard(key)
    except (csv.Error, UnicodeError, ValueError, OverflowError):
        raise AuditError("invalid_or_oversized_csv") from None

    if len(read_paths) > 1:
        category = "multiple_candidate_paths_read"
    elif len(read_pids) > 1:
        category = "multiple_name_matched_processes_read"
    elif read_after_open:
        category = "read_after_same_pid_path_open"
    elif successful_read:
        category = "read_without_prior_matching_open_in_export"
    elif successful_open:
        category = "open_only_no_read_in_export"
    elif failed_candidate_io:
        category = "failed_candidate_io_only"
    else:
        category = "no_matching_candidate_file_io"

    return {
        "schema_version": SCHEMA,
        "source_scope": "one_owner_selected_existing_procmon_csv",
        "selected_process_name_category": selected,
        "file_io_category": category,
        "candidate_createfile_success_events": successful_open,
        "candidate_readfile_success_events": successful_read,
        "candidate_readfile_after_prior_same_pid_path_open_events": read_after_open,
        "candidate_readfile_without_prior_matching_open_events": read_without_open,
        "candidate_file_io_failed_events": failed_candidate_io,
        "distinct_opened_candidate_paths_bucket": _bucket(len(open_paths_all)),
        "distinct_read_candidate_paths_bucket": _bucket(len(read_paths)),
        "distinct_name_matched_processes_with_candidate_io_bucket":
            _bucket(len(affected_pids)),
        "distinct_name_matched_processes_with_successful_reads_bucket":
            _bucket(len(read_pids)),
        "candidate_csv_structure_parsed": True,
        "csv_complete_unfiltered_capture_verified": False,
        "csv_chronological_order_verified": False,
        "original_vida_process_authenticity_verified": False,
        "original_vida_effective_config_path_verified": False,
        "diagnostic_xml_parsed_by_client_verified": False,
        "effective_diagnostic_connection_mode_verified": False,
        "paired_with_live_module_snapshot_verified": False,
        "original_vida_getscript_readvin_verified": False,
        "original_vida_j2534_tx_rx_verified": False,
        "original_vida_vin_accepted_verified": False,
        "ecu_identity_accepted_verified": False,
        "raw_csv_path_pid_xml_content_or_vin_exported": False,
        "next_gate": "independently_attribute_original_process_and_effective_runtime_config",
        "limitations": [
            "CSV rows may be filtered, out of order or incomplete.",
            "Same-PID and same-path events are not tied to one Windows file handle.",
            "Process name alone cannot authenticate an original VIDA service.",
            "Successful ReadFile is file I/O, not proof that VIDA parsed or selected its XML.",
            "Static config candidate and module snapshot cannot automatically be paired with this CSV.",
            "No diagnostic communication or original GUI acceptance was attempted.",
        ],
    }


def analyze_text(text, selected_process):
    if not isinstance(text, str) or not text or len(text) > MAX_BYTES:
        raise AuditError("invalid_input_size")
    csv.field_size_limit(MAX_FIELD)
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        return analyze_reader(reader, selected_process)
    except (csv.Error, UnicodeError):
        raise AuditError("invalid_or_oversized_csv") from None


def analyze_path(path, selected_process):
    if (not isinstance(path, Path) or path.suffix.casefold() != ".csv"
            or path.is_symlink() or not path.is_file()):
        raise AuditError("unsupported_input_file")
    try:
        before = path.stat()
        if not 0 < before.st_size <= MAX_BYTES:
            raise AuditError("invalid_input_size")
        with path.open("rb") as stream:
            prefix = stream.read(4)
            stream.seek(0)
            # Procmon CSV can be exported as UTF-8 (optionally BOM) or
            # converted into UTF-16 with BOM for a private local review.
            encoding = "utf-16" if prefix.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig"
            text = stream.read(MAX_BYTES + 1).decode(encoding, errors="strict")
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (
                after.st_size, after.st_mtime_ns):
            raise AuditError("source_changed_during_read")
        return analyze_text(text, selected_process)
    except AuditError:
        raise
    except (OSError, UnicodeError, ValueError):
        raise AuditError("invalid_or_unreadable_input") from None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only Procmon CSV candidate config file I/O classifier")
    parser.add_argument("--csv", type=Path, required=True,
                        help="Existing owner-local Procmon CSV; never upload the raw source")
    parser.add_argument("--process-name", required=True, choices=sorted(PROCESS_NAMES),
                        help="Explicit name category only; not executable authenticity")
    args = parser.parse_args(argv)
    try:
        report = analyze_path(args.csv, args.process_name)
    except AuditError:
        print("ERROR: VIDA_PROCMON_CANDIDATE_IO_NOT_VERIFIED", file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
