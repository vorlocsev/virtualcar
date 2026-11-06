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


def _kind(value):
    if value == "VehCommSpecification":
        return "veh_comm_specification"
    return "empty_type" if value == "" else "other_type"


def _time(parts):
    hour, minute, second, milli = map(int, parts)
    if hour > 23 or minute > 59 or second > 59:
        raise ValueError("invalid VIDA log timestamp")
    return (((hour * 60) + minute) * 60 + second) * 1000 + milli


def audit_lines(lines):
    counts = {
        "get_script_requests": 0,
        "requests_veh_comm_specification": 0,
        "requests_other_type": 0,
        "requests_empty_type": 0,
        "fetched_script_events": 0,
        "running_script_events": 0,
        "matched_get_fetch_run_triplets": 0,
        "matched_veh_comm_specification_triplets": 0,
        "orphan_fetched_script_events": 0,
        "unmatched_running_script_events": 0,
        "different_script_running_events": 0,
        "superseded_incomplete_get_script_requests": 0,
        "script_missing_exception_mentions": 0,
        "get_vehcomm_specification_error_mentions": 0,
        "run_identify_vehicle_method_mentions": 0,
    }
    pending = {}
    observed = 0
    for raw in lines:
        observed += 1
        if observed > MAX_LINES or len(raw) > 8192:
            raise ValueError("too many or oversized log lines")
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
                pending[thread] = {"time": time_ms, "kind": kind, "fetched": None}
                continue
            fetched = FETCHED.search(payload)
            if fetched:
                counts["fetched_script_events"] += 1
                if (current is None or current["fetched"] is not None
                        or time_ms - current["time"] < 0
                        or time_ms - current["time"] > MAX_WINDOW_MS):
                    counts["orphan_fetched_script_events"] += 1
                else:
                    current["fetched"] = fetched.group(1)
                continue
        if component == "Script":
            running = RUNNING.search(payload)
            if running:
                counts["running_script_events"] += 1
                if (current is None or current["fetched"] is None
                        or time_ms - current["time"] < 0
                        or time_ms - current["time"] > MAX_WINDOW_MS):
                    counts["unmatched_running_script_events"] += 1
                elif running.group(1) != current["fetched"]:
                    counts["different_script_running_events"] += 1
                else:
                    counts["matched_get_fetch_run_triplets"] += 1
                    if current["kind"] == "veh_comm_specification":
                        counts["matched_veh_comm_specification_triplets"] += 1
                pending.pop(thread, None)

    return {
        "schema_version": SCHEMA,
        "input_kind": "private_vida_trace_read_only",
        "parsed_line_count": observed,
        "events": counts,
        "matching_scope": "same_vida_component_thread_and_30_second_log_window",
        "external_source_examples_are_not_my2009_evidence": True,
        "get_script_type_is_not_runtime_call_site": True,
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
