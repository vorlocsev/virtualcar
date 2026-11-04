#!/usr/bin/env python3
"""Prepare a private, read-only client-session diagnostic bundle.

Run AFTER closing an authorized SectorV/VDASH read-only client session.
This tool does not run a client, execute a DLL or infer ECU acceptance.
The native J2534 log is kept private; only allowlisted JSON is exported.
"""
import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import sys

from audit_j2534_connect import audit as audit_connect
from audit_j2534_discovery import audit as audit_discovery, PREFIX
from audit_native_j2534_lifecycle import audit as audit_lifecycle
from prepare_p2_capture import prepare as prepare_p2

FORMAT = "virtualcar-p2-client-capture-boundary-v1"
UI_FORMAT = "virtualcar-p2-client-ui-observation-v1"
MAX_BYTES = 4 * 1024 * 1024
OUTPUTS = ("connect-summary.json", "client-boundary.json")
CLIENTS = frozenset(("sectorv", "vdash_2_0", "vdash_2_5_115_79", "other"))
# The DLL logs the host executable's basename, not its signed identity.
# Deliberately recognize only observed/explicitly supported names.
NATIVE_LABEL = re.compile(r"^\[PID=[0-9A-Fa-f]{8} ([^\]\r\n]{1,96})\] ")
KNOWN_NATIVE_HOSTS = {
    "sectorv.exe": "sectorv",
    "vdash.exe": "vdash",
    "vdash2.exe": "vdash",
}
ECU_LIST = frozenset(("unknown", "empty", "nonempty"))
VIN_STATE = frozenset(("unknown", "visible", "not_visible"))
ALLOWED_UI_KEYS = frozenset((
    "format", "client", "virtual_adapter_selected",
    "scan_finished", "vin_display", "ecu_list",
    "same_run_operator_attested",
))


def _ui(document):
    """Reject unknown fields rather than accidentally exporting secrets."""
    if not isinstance(document, dict) or set(document) != ALLOWED_UI_KEYS:
        raise ValueError("invalid_ui_fields")
    if (document["format"] != UI_FORMAT
            or document["client"] not in CLIENTS
            or document["ecu_list"] not in ECU_LIST
            or document["vin_display"] not in VIN_STATE):
        raise ValueError("invalid_ui_enums")
    for key in ("virtual_adapter_selected", "scan_finished"):
        if document[key] is not None and type(document[key]) is not bool:
            raise ValueError("invalid_ui_milestone")
    if type(document["same_run_operator_attested"]) is not bool:
        raise ValueError("invalid_ui_attestation")
    return document


def _native_client_family(lines):
    """Classify only allowlisted host *labels* without exporting filenames.

    A filename printed by the virtual DLL is not a cryptographic or OS-level
    process attestation. Unknown VDASH build names stay unclassified.
    """
    labels = set()
    for line in lines:
        match = NATIVE_LABEL.match(line)
        if match is not None:
            labels.add(match.group(1).casefold())
            if len(labels) > 1:
                return "multiple_untrusted_executable_labels"
    if not labels:
        return "no_native_executable_label"
    return KNOWN_NATIVE_HOSTS.get(next(iter(labels)), "unclassified_executable")


def _client_label_comparison(ui, native_family):
    if ui is None:
        return "no_operator_client_reported"
    if ui["client"] == "other":
        return "operator_client_unspecified"
    if native_family == "multiple_untrusted_executable_labels":
        return "native_executable_labels_conflict"
    if native_family in ("unclassified_executable", "no_native_executable_label"):
        return "native_executable_unclassified"
    requested = "sectorv" if ui["client"] == "sectorv" else "vdash"
    if requested != native_family:
        return "operator_client_conflicts_with_native_label"
    return "operator_client_matches_untrusted_native_label"


def _category(tx):
    # Do not export UDS DIDs, RX identifiers, timestamps or process labels.
    route, service = tx.get("route"), tx.get("service")
    if route == "OBD":
        return "obd_vin_request" if service == "0902" else "other_obd"
    if route == "D2":
        return ("d2_b9fb" if service == "B9FB" else
                "d2_b9f0" if service == "B9F0" else
                "d2_other")
    if route == "P3":
        return "p3_did_read" if isinstance(service, str) and service.startswith("22") else "p3_other"
    return "unclassified"


def _counts(records):
    counts = Counter()
    for row in records:
        if not isinstance(row, dict):
            raise ValueError("invalid_discovery_row")
        family = _category(row)
        status = row.get("status")
        if status not in ("delivered", "unverified", "unsupported", "no_fixture",
                          "partial_rx", "negative_response", "timeout"):
            status = "other"
        counts[(family, status)] += 1
    # A fixed allowlist of category labels, no raw CAN value or private DID.
    return [
        {"family": family, "transport_status": status, "count": count}
        for (family, status), count in sorted(counts.items())
    ]


def prepare(source, ui=None):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("invalid_native_source_size")
    if ui is not None:
        ui = _ui(ui)
    lines = source.splitlines()
    # Native source and operator UI have no trusted common session token.
    # Multiple PID labels in a single source file must NOT be treated as
    # evidence of one connected client's complete J2534 exchange.
    native_processes = {
        m.group(1) for line in lines
        if (m := PREFIX.fullmatch(line.rstrip("\r\n"))) is not None
    }
    single_process_source = len(native_processes) == 1
    native_family = _native_client_family(lines)
    label_comparison = _client_label_comparison(ui, native_family)
    lifecycle = audit_lifecycle(source)
    connect = audit_connect(lines)
    discovery = audit_discovery(lines, include_obd=True)
    rows = discovery["transactions"]
    obd = discovery["obd_observation"]
    p2 = None
    p2_problem = None
    # A missing B9FB is a meaningful failure boundary and MUST still yield
    # a connection/discovery report, rather than rejecting all diagnostics.
    try:
        p2 = prepare_p2(source)
    except ValueError:
        p2_problem = "native_p2_evidence_not_comparable"

    p2_summary = p2["capture-summary.json"] if p2 is not None else None
    f0 = (p2_summary["b9f0_native_transport_audit"]
          if p2_summary is not None else None)
    direct_b9fb_b9f0 = (
        p2_summary["b9fb_to_b9f0_same_epoch_positive_binding"]
        if p2_summary is not None else None)
    direct_positive_b9f0 = bool(
        direct_b9fb_b9f0 is not None
        and direct_b9fb_b9f0[
            "positive_b9f0_transport_bound_to_direct_first_read"] is True)
    native_clean = bool(
        single_process_source and lifecycle["single_closed_device_cycle_verified"]
        and p2_summary is not None
        and p2_summary["native_epochs"] == 1
        and p2_summary["all_native_epochs_closed"] is True
        and p2_summary["native_tx_rx_context_complete"] is True
        and not p2_summary["native_chronology_parse_errors"]
        and not p2_summary["native_followup_parse_errors"]
        and not f0["parser_error_counts"])
    requested = [row for row in rows if row.get("route") in ("D2", "P3")]
    has_d2_b9fb = any(row.get("route") == "D2"
                      and row.get("service") == "B9FB" for row in requested)
    has_d2_b9f0 = any(row.get("route") == "D2"
                      and row.get("service") == "B9F0" for row in requested)
    b9fb_done = (p2_summary["b9fb_transport_completions_observed"]
                  if p2_summary is not None else 0)
    b9f0_positive = (f0["status_counts"].get("positive_transport_complete", 0)
                      if f0 is not None else 0)
    p3_after_f0 = (f0["post_positive_first_next_tx_service_counts"].get(
        "p3_read_data_by_identifier", 0) if f0 is not None else 0)
    p3_positive = (f0["post_positive_first_p3_positive_transport_count"]
                   if f0 is not None else 0)
    connect_attempts = connect["connect"]["attempts"]
    connect_ok = connect["connect"]["statuses"].get("ok", 0)
    any_errors = (bool(discovery["parse_errors"])
                  or connect["connect"]["invalid_events"] > 0)
    if any_errors:
        focus = "invalid_native_source_or_connect_metadata"
    elif not single_process_source:
        focus = "multiple_or_missing_native_process_scopes"
    elif lifecycle["status"] == "multiple_closed_device_cycles":
        focus = "multiple_native_j2534_device_cycles"
    elif not lifecycle["single_closed_device_cycle_verified"]:
        focus = "incomplete_or_invalid_native_j2534_device_cycle"
    elif (ui is not None and ui["same_run_operator_attested"]
          and label_comparison == "operator_client_conflicts_with_native_label"):
        focus = "operator_client_native_executable_label_mismatch"
    elif (ui is not None and ui["same_run_operator_attested"]
          and label_comparison in (
              "native_executable_unclassified",
              "native_executable_labels_conflict")):
        focus = "native_client_executable_label_unverified"
    elif connect_attempts == 0:
        focus = "no_virtual_adapter_connect_attempt_observed"
    elif connect_ok == 0:
        focus = "virtual_adapter_connect_failed"
    elif not has_d2_b9fb:
        focus = "no_native_b9fb_request_observed"
    elif not native_clean:
        focus = "native_p2_source_incomplete_or_unverifiable"
    elif not b9fb_done:
        focus = "b9fb_no_completed_positive_transport"
    elif not has_d2_b9f0:
        focus = "no_b9f0_request_after_b9fb"
    elif not b9f0_positive:
        focus = "no_positive_b9f0_transport"
    elif not direct_positive_b9f0:
        focus = "b9fb_b9f0_positive_transport_not_directly_bound"
    elif not p3_after_f0:
        focus = "no_first_p3_read_after_positive_b9f0"
    elif not p3_positive:
        focus = "first_p3_did_read_has_no_positive_transport"
    elif ui is not None and ui["same_run_operator_attested"] and ui["ecu_list"] == "empty":
        focus = "transport_positive_but_operator_reports_empty_ecu_list"
    elif ui is not None and ui["same_run_operator_attested"] and ui["ecu_list"] == "nonempty":
        focus = "operator_reports_nonempty_ecu_list_identity_unverified"
    else:
        focus = "native_transport_positive_client_ui_result_unknown"

    note = {
        "format": FORMAT, "read_only": True, "contains_payload_data": False,
        "raw_log_exported": False, "client_run_executed_by_tool": False,
        "native_log_diagnostic_scope": "one_supplied_local_file",
        "new_native_records_observed": bool(source),
        "single_native_process_label_observed": single_process_source,
        "native_executable_label_family": native_family,
        "operator_client_native_label_comparison": label_comparison,
        "native_executable_identity_verified": False,
        "native_device_lifecycle": lifecycle,
        "connect_attempts": connect_attempts,
        "connect_succeeded": connect_ok,
        "obd_vin_requests": obd["vin_requests"],
        "obd_vin_transport_deliveries": obd["vin_delivered"],
        "transport_family_counts": _counts(rows),
        "native_p2_report_status": (
            "available" if p2 is not None else p2_problem),
        "native_p2_single_closed_epoch": native_clean,
        "b9fb_positive_transport_count": b9fb_done,
        "b9f0_positive_transport_count": b9f0_positive,
        "direct_b9fb_b9f0_positive_transport_bound": direct_positive_b9f0,
        "direct_b9fb_b9f0_binding_status": (
            direct_b9fb_b9f0["status"] if direct_b9fb_b9f0 is not None
            else "not_comparable"),
        "first_p3_after_b9f0_observed_count": p3_after_f0,
        "first_p3_positive_transport_count": p3_positive,
        "reported_client": ui["client"] if ui is not None else "unreported",
        "ui_vin_display_reported": ui["vin_display"] if ui is not None else "unknown",
        "ui_ecu_list_reported": ui["ecu_list"] if ui is not None else "unknown",
        "ui_scan_finished_reported": ui["scan_finished"] if ui is not None else None,
        "ui_adapter_selected_reported": ui["virtual_adapter_selected"] if ui is not None else None,
        "same_run_operator_attested": (ui["same_run_operator_attested"]
                                       if ui is not None else False),
        "same_run_independently_verified": False,
        "client_ecu_inventory_verified": False,
        "vehicle_identity_verified": False,
        "xc90_v8_my2009_verified": False,
        "diagnostic_focus": focus,
        "limitations": [
            "J2534 native log and operator UI observation have no independently shared authenticated run ID.",
            "A native host executable basename is untrusted and never proves which signed application called J2534.",
            "Unrecognized native executable names are not guessed as SectorV or a particular VDASH build.",
            "A positive native B9FB, B9F0 or P3 transport does not establish diagnostic-client acceptance.",
            "One source PID can contain multiple PassThruOpen/PassThruClose cycles; their traffic is not one device session.",
            "UI list state is an operator report, not independently verified ECU identity.",
            "No VIN, DID, hardware identifiers, process ID, client account, raw CAN bytes or source path is exported.",
            "The source may stop before B9FB, in which case the P2 report is not invented.",
        ],
    }
    reports = {
        "connect-summary.json": connect,
        "client-boundary.json": note,
    }
    if p2 is not None:
        # Reuse the unchanged strict three native, private source-local
        # reports instead of recreating/softening the cross-audit evidence.
        reports.update(p2)
    return reports


def _no_new_native_reports(ui):
    """Publish absence of newly observed records, never a client verdict.

    Even when Begin/Finish successfully checked an unchanged native log,
    absence cannot distinguish a client not started, adapter not selected,
    DLL not loaded, a different TEMP directory, or a logging failure.
    """
    reports = prepare("", ui=ui)
    limited = {name: reports[name] for name in OUTPUTS}
    note = limited["client-boundary.json"]
    note["diagnostic_focus"] = "no_new_native_j2534_records_observed"
    note["native_log_diagnostic_scope"] = "verified_begin_finish_no_new_bytes"
    note["native_p2_report_status"] = "unavailable_no_new_native_records"
    note["native_p2_single_closed_epoch"] = False
    note["new_native_records_observed"] = False
    note["limitations"].append(
        "No appended J2534 bytes: client execution, adapter selection, DLL load, "
        "log path and logging operation cannot be independently inferred.")
    return limited


def _read_private_suffix(path, offset, expected_prefix, allow_empty=False):
    """Read only newly appended native bytes; reject rotation or truncation.

    The historical prefix digest never leaves the private caller state.
    SHA256 is a continuity check, NOT proof of diagnostic-client identity.
    """
    if type(offset) is not int or offset < 0 or offset > (1 << 40):
        raise ValueError("invalid_start_offset")
    if (not isinstance(expected_prefix, str) or
            re.fullmatch(r"[0-9a-fA-F]{64}", expected_prefix) is None):
        raise ValueError("invalid_original_digest")
    if not path.is_file():
        if (allow_empty and offset == 0
                and expected_prefix.lower() == hashlib.sha256(b"").hexdigest()
                and not path.exists()):
            return None
        raise ValueError("native_log_unavailable_or_not_file")
    stat = path.stat()
    if stat.st_size < offset or stat.st_size - offset > MAX_BYTES:
        raise ValueError("no_bounded_appended_session")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        unread = offset
        while unread:
            block = stream.read(min(unread, 64 * 1024))
            if not block:
                raise ValueError("native_log_truncated")
            digest.update(block)
            unread -= len(block)
        if digest.hexdigest() != expected_prefix.lower():
            raise ValueError("old_log_prefix_changed")
        if stat.st_size == offset:
            if allow_empty:
                return None
            raise ValueError("no_appended_native_records")
        # This DLL writes complete CRLF-terminated native log lines. If
        # the prior file ended mid-line, appending creates a synthetic
        # merged entry and cannot be source-attributed safely.
        if offset:
            stream.seek(offset - 1)
            if stream.read(1) != b"\n":
                raise ValueError("historical_prefix_ends_midline")
            stream.seek(offset)
        suffix = stream.read(MAX_BYTES + 1)
    if not suffix or len(suffix) > MAX_BYTES:
        raise ValueError("invalid_appended_session")
    if not suffix.endswith(b"\n"):
        raise ValueError("appended_session_ends_midline")
    # The native logger writes ASCII metadata; never replace malformed
    # bytes silently or convert a corrupt client capture into evidence.
    decoded = suffix.decode("utf-8-sig", errors="strict")
    if not decoded.startswith("[PID="):
        raise ValueError("appended_native_epoch_has_no_first_metadata")
    return decoded


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("native_log", type=Path)
    p.add_argument("--ui", type=Path, default=None,
                   help="Optional operator-only enum observation file")
    p.add_argument("--offset-bytes", type=int, default=None,
                   help="Private pre-client file length; checks only appended bytes")
    p.add_argument("--prefix-sha256", default=None,
                   help="Private SHA256 of the exact pre-client byte prefix")
    p.add_argument("--allow-empty-append", action="store_true",
                   help="For a verified Begin/Finish snapshot only: export a "
                        "negative-evidence report if no new J2534 bytes exist")
    p.add_argument("--output-dir", type=Path, required=True,
                   help="New directory; existing output is never overwritten")
    args = p.parse_args(argv)
    created = []
    made = False
    try:
        sources = [args.native_log.resolve()]
        if args.ui is not None:
            sources.append(args.ui.resolve())
        target = args.output_dir.resolve()
        if len(set(sources)) != len(sources) or target in sources:
            raise ValueError("overlapping_paths")
        if (args.offset_bytes is None) != (args.prefix_sha256 is None):
            raise ValueError("offset_and_digest_required_together")
        if args.allow_empty_append and args.offset_bytes is None:
            raise ValueError("empty_append_requires_private_begin_snapshot")
        if args.offset_bytes is None and args.native_log.stat().st_size > MAX_BYTES:
            raise ValueError("input_too_large")
        if args.ui is not None and args.ui.stat().st_size > 4096:
            raise ValueError("ui_too_large")
        ui = (json.loads(args.ui.read_text(encoding="utf-8-sig"))
              if args.ui is not None else None)
        # A historical log may be large. Only a SHA256-verified appended
        # suffix may bypass the whole-file size limit. The caller must
        # have recorded byte offset + digest before launching the client.
        source = (_read_private_suffix(args.native_log, args.offset_bytes,
                                      args.prefix_sha256,
                                      allow_empty=args.allow_empty_append)
                  if args.offset_bytes is not None
                  else args.native_log.read_text(encoding="utf-8-sig",
                                                errors="replace"))
        reports = (_no_new_native_reports(ui) if source is None
                   else prepare(source, ui=ui))
        output = {name: json.dumps(value, indent=2, sort_keys=True,
                                   ensure_ascii=False) + "\n"
                  for name, value in reports.items()}
        args.output_dir.mkdir(mode=0o700, parents=False, exist_ok=False)
        made = True
        for name in sorted(output):
            path = args.output_dir / name
            with path.open("x", encoding="utf-8") as f:
                created.append(path)
                f.write(output[name])
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        for path in created:
            try:
                path.unlink()
            except OSError:
                pass
        if made:
            try:
                args.output_dir.rmdir()
            except OSError:
                pass
        print("Private client capture rejected; details withheld", file=sys.stderr)
        return 2
    print("PASS: sanitized client-session boundary or explicit no-new-J2534-evidence report; ECU acceptance unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
