#!/usr/bin/env python3
"""Read-only, privacy-safe gate audit for an explicitly curated SectorV event summary.

This is NOT a SectorV binary disassembler, log parser, or genuine vehicle capture.
No client behavior is inferred from J2534 delivery, CAN payload or an A3 echo.
Never outputs VIN, protected A3 operands, file names, hashes or raw log lines.
"""
import argparse
import json
from pathlib import Path
import re

SCHEMA = "virtualcar-sectorv-gate-evidence-v1"
EVENTS = {"b9fb_matcher", "hardware_a3", "normal_mode_warning", "ecu_reachable"}
SOURCES = {"client_log", "client_ui"}
SHAPE = {
    "b9fb_matcher": {"event", "source", "observed", "matched", "ignored"},
    "hardware_a3": {"event", "source", "target", "outcome", "elapsed_ms"},
    "normal_mode_warning": {"event", "source"},
    "ecu_reachable": {"event", "source", "count"},
}


def _integer(value, low=0, high=100000):
    return type(value) is int and low <= value <= high


def audit(raw):
    """Allowlisted input only. Reject arbitrary/identifying strings fail-closed."""
    if type(raw) is not dict or set(raw) != {
        "schema_version", "client", "version", "scenario", "run_scope", "observations"
    }:
        raise ValueError("expected only the six allowlisted input fields")
    if raw["schema_version"] != SCHEMA or raw["client"] != "SectorV":
        raise ValueError("wrong schema or client")
    if type(raw["version"]) is not str or not re.fullmatch(r"\d+\.\d+\.\d+(?:\.\d+)?", raw["version"]):
        raise ValueError("version must be a public numeric release number")
    if raw["scenario"] not in ("P2_MY2005_lab", "P2_MY2009_lab", "unknown_lab"):
        raise ValueError("scenario must be a safe laboratory category")
    if raw["run_scope"] != "same_client_run":
        raise ValueError("independent runs cannot be merged into one gate result")
    events = raw["observations"]
    if type(events) is not list or len(events) > 32 or not events:
        raise ValueError("expected 1 to 32 observations from one client run")

    matcher = None
    hardware = {}
    warning = False
    reachable = None
    phases = []
    for ev in events:
        if type(ev) is not dict or ev.get("event") not in EVENTS:
            raise ValueError("unknown or unstructured event")
        kind = ev["event"]
        if set(ev) != SHAPE[kind] or ev["source"] not in SOURCES:
            raise ValueError("event contains unsupported or private fields")
        # Client API-log and UI observations have different provenance.
        if kind in ("b9fb_matcher", "hardware_a3") and ev["source"] != "client_log":
            raise ValueError("matcher and hardware result require client log evidence")
        if kind == "ecu_reachable" and ev["source"] not in SOURCES:
            raise ValueError("invalid ECU list source")

        if kind == "b9fb_matcher":
            if matcher is not None:
                raise ValueError("ambiguous multiple B9FB matchers")
            nums = (ev["observed"], ev["matched"], ev["ignored"])
            if not all(_integer(n, 0, 64) for n in nums) or nums[1] + nums[2] > nums[0]:
                raise ValueError("invalid B9FB matcher counts")
            matcher = {
                "observed": nums[0], "matched": nums[1], "ignored": nums[2],
                "frame_matcher_complete": nums[0] > 0 and nums[0] == nums[1] and nums[2] == 0,
            }
            phases.append("b9fb_matcher")
        elif kind == "hardware_a3":
            target = ev["target"]
            if target not in ("40", "50") or target in hardware:
                raise ValueError("unknown or duplicate CEM target")
            if ev["outcome"] not in ("timeout", "rx_seen", "unknown"):
                raise ValueError("unknown hardware outcome")
            if not _integer(ev["elapsed_ms"], 0, 60000):
                raise ValueError("invalid client-reported interval")
            hardware[target] = {
                "outcome": ev["outcome"],
                "elapsed_ms": ev["elapsed_ms"],
            }
            phases.append("hardware_a3_" + target)
        elif kind == "normal_mode_warning":
            if warning:
                raise ValueError("duplicate warning")
            warning = True
            phases.append("normal_mode_warning")
        else:
            if reachable is not None or not _integer(ev["count"], 0, 100):
                raise ValueError("duplicate or invalid ECU reachability")
            reachable = ev["count"]
            phases.append("ecu_reachable")

    # Source-list ordering is retained only within this single client source.
    # Do not compute durations or causal relationships across client/J2534 clocks.
    return {
        "schema_version": "virtualcar-sectorv-gate-report-v1",
        "client": "SectorV",
        "client_version": raw["version"],
        "scenario": raw["scenario"],
        "same_client_run": True,
        "observation_order": phases,
        "b9fb_client_matcher": matcher if matcher else "not_observed",
        "hardware_a3": hardware,
        "normal_mode_warning_observed": warning,
        "ecu_reachable_observed": reachable,
        "normal_mode_predicate": "unknown",
        "expected_e3_response_bytes": "unknown",
        "a3_security_access_authorized": "unknown",
        "b9fb_vehicle_identity_accepted": "unknown",
        "client_ecu_identification_accepted": "unknown",
        "replay_approved": False,
        "findings": [
            "A complete B9FB frame matcher only proves the client matched frames, not VIN or ECU identity.",
            "Hardware A3 result is a distinct client stage; timeout alone cannot define a valid E3 reply.",
            "A normal-mode warning records a client symptom but does not identify its exact acceptance predicate.",
            "No clocks from different processes are aligned; durations are only client-reported observations.",
            "Synthetic lab scenarios and older model years cannot establish XC90 V8 MY2009 behavior.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Read-only SectorV gate evidence summary, not client acceptance")
    p.add_argument("input", type=Path, help="Curated event JSON, never private raw client logs")
    p.add_argument("--output", type=Path, required=True, help="New, privacy-safe JSON file only")
    a = p.parse_args(argv)
    if a.input.resolve() == a.output.resolve():
        p.error("input and output must differ")
    try:
        data = json.loads(a.input.read_text(encoding="utf-8"))
        result = audit(data)
    except (OSError, ValueError, TypeError) as exc:
        p.error(f"invalid evidence: {type(exc).__name__}")
    try:
        with a.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            f.write("\n")
    except OSError as exc:
        p.error(f"cannot create exclusive output: {type(exc).__name__}")
    print("SectorV gate audit complete; exact normal-mode predicate: UNKNOWN; replay: NO")


if __name__ == "__main__":
    main()
