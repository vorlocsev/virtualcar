#!/usr/bin/env python3
"""Privacy-safe read-only audit of VIDA ScriptProvider trace event sequencing.

Evidence supported: script lookup -> fetched -> running, in a single trace thread.
NOT established: dynamic call target, VIN recognition, ECU support, or client acceptance.
No original identifiers, raw lines or source paths are returned.
"""

import argparse
import json
from pathlib import Path
import re

SCHEMA = "virtualcar-vida-script-selection-trace-v1"
MAX_BYTES = 4 * 1024 * 1024
MAX_LINES = 100_000
MAX_WINDOW_MS = 30_000
DAY_MS = 24 * 60 * 60 * 1000
# Limit parsing to explicit VIDA-style components and thread IDs.
HEADER = re.compile(
    r"^\s*(\d\d):(\d\d):(\d\d)[,.](\d{3})\s+"
    r"\[\s*(ScriptProvider|Script|RunScriptService)\s*\]"
    r"\[(\d{3})\]\[\s*([A-Za-z]+)\s*\]\s*(.*)$"
)
GET_SCRIPT = re.compile(
    r"\bDatabase:\s*DiagSwdlRepository\s*,\s*SP:\s*GetScript\s*,?\s*"
    r"Type:\s*'([^'\r\n]{0,80})'", re.IGNORECASE
)
FETCHED = re.compile(r"\bFetched script:\s*'([^'\r\n]{1,128})'", re.IGNORECASE)
RUNNING = re.compile(r"\bRunning script:\s*'([^'\r\n]{1,128})'", re.IGNORECASE)
# Exact explicit diagnostic Profile label only. It is NOT a model/VIN mapping.
EMPTY_PROFILE = re.compile(r"\bProfile:\s*'EMPTYPROFILE,'", re.IGNORECASE)
# The first ReadVin lookup can be unbound: distinguish a literal bootstrap
# request shape from a generic EmptyProfile mention. Neither proves VIN.
EMPTY_SCRIPT_ID = re.compile(r"\bScriptId:\s*''", re.IGNORECASE)
UNBOUND_ECU_TYPE = re.compile(r"\bEcuType:\s*'-1'", re.IGNORECASE)
# Log source declarations, not a guess based on the calendar date.
SESSION_START = re.compile(r"^Starting new logsession:\s+\d{4}-\d\d-\d\d\b")
RELEASE = re.compile(r"^VIDA release:\s*(VIDA2014D|VIDA2015A)\s*$")
IMAGE_REPO_LOGIN_FAILURE = 'Cannot open database "ImageRepository" requested by the login.'


def _kind(value):
    if value == "VehCommSpecification":
        return "veh_comm_specification"
    if value == "ReadVin":
        return "read_vin"
    return "empty_type" if value == "" else "other_type"


def _time(parts):
    hour, minute, second, milli = map(int, parts)
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("invalid VIDA log timestamp")
    return (((hour * 60) + minute) * 60 + second) * 1000 + milli


def _elapsed_ms(start_ms, end_ms):
    """Elapsed within a short same-day window or one bounded midnight turn.

    Clock-only VIDA logs carry no event date. Never assume an arbitrary
    negative delta means midnight: only a request in the final 30 s of a
    day and an event in the first 30 s may wrap. A successful correlation
    is still log-shape evidence, not a verified ReadVin invocation.
    """
    if end_ms >= start_ms:
        return end_ms - start_ms
    if start_ms >= DAY_MS - MAX_WINDOW_MS and end_ms < MAX_WINDOW_MS:
        return DAY_MS - start_ms + end_ms
    return -1


def audit_lines(lines):
    counts = {
        "get_script_requests": 0,
        "requests_veh_comm_specification": 0,
        "requests_read_vin": 0,
        "requests_read_vin_explicit_empty_profile": 0,
        "requests_read_vin_unbound_bootstrap_shape": 0,
        "requests_other_type": 0,
        "requests_empty_type": 0,
        "fetched_script_events": 0,
        "running_script_events": 0,
        "matched_get_fetch_run_triplets": 0,
        "matched_veh_comm_specification_triplets": 0,
        "matched_read_vin_triplets": 0,
        "matched_midnight_rollover_triplets": 0,
        "matched_read_vin_midnight_rollover_triplets": 0,
        "matched_read_vin_explicit_empty_profile_triplets": 0,
        "matched_read_vin_unbound_bootstrap_shape_triplets": 0,
        "orphan_fetched_script_events": 0,
        "unmatched_running_script_events": 0,
        "out_of_order_running_script_events": 0,
        "different_script_running_events": 0,
        "superseded_incomplete_get_script_requests": 0,
        "script_missing_exception_mentions": 0,
        "get_vehcomm_specification_error_mentions": 0,
        "run_identify_vehicle_method_mentions": 0,
        "declared_vida2014d_release_lines": 0,
        "declared_vida2015a_release_lines": 0,
        "session_boundary_lines": 0,
        "readvin_triplets_declared_vida2014d": 0,
        "readvin_triplets_declared_vida2015a": 0,
        "readvin_triplets_version_unreported": 0,
        "image_repository_login_failure_mentions": 0,
        "diagswdl_repository_sp_mentions": 0,
        "j2534_driver_load_attempts": 0,
    }
    pending = {}
    release = "unreported"
    observed = 0
    for raw in lines:
        observed += 1
        if observed > MAX_LINES or len(raw) > 8192:
            raise ValueError("too many or oversized log lines")
        # Session boundary is stronger than a matching thread ID/time window.
        # A subsequent release declaration also invalidates pending matches.
        if SESSION_START.match(raw):
            counts["session_boundary_lines"] += 1
            pending.clear()
            release = "unreported"
            continue
        declared = RELEASE.fullmatch(raw.strip())
        if declared:
            release = declared.group(1)
            pending.clear()
            if release == "VIDA2014D":
                counts["declared_vida2014d_release_lines"] += 1
            else:
                counts["declared_vida2015a_release_lines"] += 1
            continue
        if IMAGE_REPO_LOGIN_FAILURE in raw:
            counts["image_repository_login_failure_mentions"] += 1
        if "Database: DiagSwdlRepository, SP:" in raw:
            counts["diagswdl_repository_sp_mentions"] += 1
        if "Loading J2534 driver:" in raw:
            counts["j2534_driver_load_attempts"] += 1
        # Exception text/stack traces are intentionally not associated with a
        # specific fetch: a naked exception line contains no verified thread.
        if "ScriptMissingException" in raw:
            counts["script_missing_exception_mentions"] += 1
        if "GetVehCommSpecification" in raw and "exception" in raw.lower():
            counts["get_vehcomm_specification_error_mentions"] += 1
        if "RunIdentifyVehicleScript" in raw:
            counts["run_identify_vehicle_method_mentions"] += 1
        match = HEADER.match(raw)
        if not match:
            continue
        time_ms = _time(match.groups()[:4])
        component, thread, level, payload = match.groups()[4:]
        current = pending.get(thread)
        if component == "ScriptProvider":
            request = GET_SCRIPT.search(payload)
            if request:
                if current is not None:
                    counts["superseded_incomplete_get_script_requests"] += 1
                kind = _kind(request.group(1))
                counts["get_script_requests"] += 1
                counts["requests_" + kind] += 1
                explicit_empty = kind == "read_vin" and EMPTY_PROFILE.search(payload) is not None
                if explicit_empty:
                    counts["requests_read_vin_explicit_empty_profile"] += 1
                bootstrap = (explicit_empty
                             and EMPTY_SCRIPT_ID.search(payload) is not None
                             and UNBOUND_ECU_TYPE.search(payload) is not None)
                if bootstrap:
                    counts["requests_read_vin_unbound_bootstrap_shape"] += 1
                pending[thread] = {"time": time_ms, "kind": kind, "fetched": None,
                                   "fetched_time": None,
                                   "explicit_empty_profile": explicit_empty,
                                   "unbound_bootstrap_shape": bootstrap,
                                   "release": release}
                continue
            fetched = FETCHED.search(payload)
            if fetched:
                counts["fetched_script_events"] += 1
                if (current is None or current["fetched"] is not None
                        or not 0 <= _elapsed_ms(current["time"], time_ms) <= MAX_WINDOW_MS):
                    counts["orphan_fetched_script_events"] += 1
                else:
                    current["fetched"] = fetched.group(1)
                    current["fetched_time"] = time_ms
                continue
        if component == "Script":
            running = RUNNING.search(payload)
            if running:
                counts["running_script_events"] += 1
                if (current is None or current["fetched"] is None
                        or not 0 <= _elapsed_ms(current["time"], time_ms) <= MAX_WINDOW_MS):
                    counts["unmatched_running_script_events"] += 1
                elif (_elapsed_ms(current["time"], time_ms)
                      < _elapsed_ms(current["time"], current["fetched_time"])):
                    # Preserve request-relative ordering across a legitimate
                    # midnight turn; reject reversed fetch/run timestamps.
                    # Both elapsed values are bounded by the request window.
                    counts["unmatched_running_script_events"] += 1
                    counts["out_of_order_running_script_events"] += 1
                elif running.group(1) != current["fetched"]:
                    counts["different_script_running_events"] += 1
                else:
                    counts["matched_get_fetch_run_triplets"] += 1
                    crossed_midnight = (current["fetched_time"] < current["time"]
                                        or time_ms < current["time"])
                    if crossed_midnight:
                        counts["matched_midnight_rollover_triplets"] += 1
                        if current["kind"] == "read_vin":
                            counts["matched_read_vin_midnight_rollover_triplets"] += 1
                    if current["kind"] == "veh_comm_specification":
                        counts["matched_veh_comm_specification_triplets"] += 1
                    elif current["kind"] == "read_vin":
                        counts["matched_read_vin_triplets"] += 1
                        suffix = ("declared_vida2014d" if current["release"] == "VIDA2014D"
                                  else "declared_vida2015a" if current["release"] == "VIDA2015A"
                                  else "version_unreported")
                        counts["readvin_triplets_" + suffix] += 1
                        if current["explicit_empty_profile"]:
                            counts["matched_read_vin_explicit_empty_profile_triplets"] += 1
                        if current["unbound_bootstrap_shape"]:
                            counts["matched_read_vin_unbound_bootstrap_shape_triplets"] += 1
                pending.pop(thread, None)

    return {
        "schema_version": SCHEMA,
        "input_kind": "private_vida_trace_read_only",
        "parsed_line_count": observed,
        "events": counts,
        "matching_scope": "same_thread_30_second_window_and_same_declared_log_session",
        "midnight_rollover_is_clock_only_inference": True,
        "release_declarations_are_per_supplied_log_not_original_dll_version": True,
        "literal_release_marker_does_not_prove_incompatible_diagnostic_engine": True,
        "image_repository_login_failure_is_not_getscript_failure": True,
        "j2534_driver_load_attempt_is_not_connection_success": True,
        "cross_file_or_cross_date_correlation_established": False,
        "actual_j2534_connection_success_verified": False,
        "external_source_examples_are_not_my2009_evidence": True,
        "get_script_type_is_not_runtime_call_site": True,
        "read_vin_get_fetch_run_is_log_chronology_not_identity": True,
        "empty_profile_token_is_not_verified_vehicle_profile": True,
        "empty_profile_unbound_ecu_type_is_only_request_shape": True,
        "script_content_provenance_verified": False,
        "script_selected_for_identify_vehicle_verified": False,
        "b9fb_to_vin_mapping_verified": False,
        "actual_vida_client_identity_verified": False,
        "xc90_v8_my2009_verified": False,
        "sectorv_ecu_inventory_verified": False,
        "replay_approved": False,
    }


def audit_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("invalid private log")
    with path.open("r", encoding="utf-8-sig", errors="strict", newline=None) as source:
        return audit_lines(source)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Safe VIDA ScriptProvider event audit")
    parser.add_argument("private_trace", type=Path, help="Local private VIDA text log")
    parser.add_argument("--output", type=Path, required=True, help="New categorical JSON only")
    args = parser.parse_args(argv)
    if args.private_trace.resolve() == args.output.resolve():
        parser.error("input and output must differ")
    try:
        result = audit_file(args.private_trace)
    except (OSError, UnicodeError, ValueError) as exc:
        parser.error("invalid local VIDA trace: " + type(exc).__name__)
    try:
        with args.output.open("x", encoding="utf-8") as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
            target.write("\n")
    except OSError as exc:
        parser.error("cannot create exclusive report: " + type(exc).__name__)
    print("VIDA script trace audited; identity script selection NOT VERIFIED")


if __name__ == "__main__":
    main()
