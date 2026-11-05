#!/usr/bin/env python3
"""Correlate sanitized Virtual Car J2534 reports with reported VDASH UI milestones.

Observation only: not a VDASH executor, CEM fixture, protocol bypass, or identity proof.
"""
import argparse
import json
from pathlib import Path
import sys

FORMAT = "virtualcar-vdash-boundary-v1"
UI_FORMAT = "virtualcar-vdash-ui-milestones-v1"
CONNECT_FORMAT = "virtualcar-j2534-connect-audit-v1"
DISC_FORMAT = "virtualcar-j2534-evidence-v1"


def _count(x):
    if type(x) is not int or not 0 <= x <= 20000:
        raise ValueError("invalid_count")
    return x


def audit(ui, connect, discovery):
    if (not isinstance(ui, dict) or ui.get("format") != UI_FORMAT or
            ui.get("client_build") not in ("vdash_2_0", "vdash_2_5_115_79", "other") or
            ui.get("ecu_list") not in ("empty", "nonempty", "unknown")):
        raise ValueError("ui_format")
    for key in ("one_client_run_attested", "same_run_sources_attested"):
        if type(ui.get(key)) is not bool:
            raise ValueError("attestation")
    for key in ("predetect_vehicle_shown", "connect_pressed", "connect_ui_finished"):
        if ui.get(key) is not None and type(ui[key]) is not bool:
            raise ValueError("milestone")
    if (not isinstance(connect, dict) or connect.get("format") != CONNECT_FORMAT
            or connect.get("contains_payload_data") is not False):
        raise ValueError("connect_format")
    c = connect.get("connect")
    if not isinstance(c, dict) or not isinstance(c.get("statuses"), dict):
        raise ValueError("connect_shape")
    attempts, ok = _count(c.get("attempts")), _count(c["statuses"].get("ok", 0))
    invalid_connect = _count(c.get("invalid_events"))
    if len(c["statuses"]) > 20 or any(not isinstance(k, str) or len(k) > 40
             or _count(v) < 0 for k, v in c["statuses"].items()):
        raise ValueError("connect_status")
    if sum(c["statuses"].values()) != attempts:
        raise ValueError("connect_total")
    if (not isinstance(discovery, dict) or discovery.get("format") != DISC_FORMAT
            or discovery.get("read_only") is not True
            or discovery.get("contains_payload_data") is not False
            or discovery.get("replay_approved") is not False):
        raise ValueError("discovery_format")
    tx, obd, errors = (discovery.get("transactions"),
                       discovery.get("obd_observation"), discovery.get("parse_errors"))
    if not isinstance(tx, list) or not isinstance(obd, dict) or not isinstance(errors, dict):
        raise ValueError("discovery_shape")
    if len(tx) > 20000 or len(errors) > 30:
        raise ValueError("discovery_limit")
    if any(not isinstance(k, str) or len(k) > 80 or _count(v) < 0
           for k, v in errors.items()):
        raise ValueError("discovery_error")
    sessions = set()
    vin_req = vin_rx = targeted = target_rx = 0
    for event in tx:
        if not isinstance(event, dict):
            raise ValueError("event")
        session, route, service, status = [event.get(k) for k in (
            "session", "route", "service", "status")]
        if (type(session) is not int or not 0 < session <= 20000
                or route not in ("D2", "P3", "OBD") or not isinstance(service, str)
                or len(service) > 16 or not isinstance(status, str) or len(status) > 50):
            raise ValueError("event_shape")
        sessions.add(session)
        if route == "OBD" and service == "0902":
            vin_req += 1
            vin_rx += status == "delivered"
        elif route in ("D2", "P3"):
            targeted += 1
            target_rx += status == "delivered"
    if (_count(obd.get("vin_requests")) != vin_req
            or _count(obd.get("vin_delivered")) != vin_rx
            or _count(obd.get("recognized_d2_p3_probes")) != targeted):
        raise ValueError("discovery_totals")
    comparable = (ui["one_client_run_attested"] and ui["same_run_sources_attested"]
                  and len(sessions) <= 1 and sum(errors.values()) == 0
                  and invalid_connect == 0)
    if not comparable:
        focus = "no_cross_source_conclusion"
    elif ui["ecu_list"] == "nonempty":
        focus = "ui_list_observed_identity_unverified"
    elif ui.get("connect_pressed") is False:
        focus = "explicit_connect_not_observed"
    elif ui.get("connect_pressed") is not True:
        focus = "unknown_connect_ui_action"
    elif ui.get("connect_ui_finished") is False:
        focus = "ui_connect_not_complete"
    elif ui.get("connect_ui_finished") is None:
        focus = "ui_connect_completion_unknown"
    elif attempts == 0:
        focus = "inspect_driver_or_missing_connect_log"
    elif ok == 0:
        focus = "inspect_j2534_connect_failure"
    elif ui["ecu_list"] == "empty" and vin_rx and not targeted:
        focus = "vin_delivered_no_oem_request_observed"
    elif ui["ecu_list"] == "empty" and target_rx:
        focus = "inspect_command_result_and_ui_projection"
    else:
        focus = "more_client_transport_evidence_needed"
    # Explicit allowlist: no VIN, raw CAN, private source strings or paths.
    return {
        "format": FORMAT, "contains_payload_data": False, "read_only": True,
        "client_build_reported": ui["client_build"],
        "ui_ecu_list_reported": ui["ecu_list"],
        "ui_predetect_shown_reported": ui.get("predetect_vehicle_shown"),
        "ui_connect_pressed_reported": ui.get("connect_pressed"),
        "ui_connect_finished_reported": ui.get("connect_ui_finished"),
        "one_run_attested": ui["one_client_run_attested"],
        "source_alignment_attested": ui["same_run_sources_attested"],
        "cross_source_correlatable_by_attestation_only": comparable,
        "same_run_independently_verified": False,
        "j2534_connect_attempts": attempts, "j2534_connect_ok": ok,
        "j2534_invalid_connect_records": invalid_connect,
        "discovery_session_count": len(sessions),
        "vin_transport_requests": vin_req, "vin_transport_deliveries": vin_rx,
        "recognized_oem_requests": targeted, "recognized_oem_deliveries": target_rx,
        "source_parse_errors": sum(errors.values()),
        "research_focus": focus,
        "vdash_command_completion_verified": False,
        "initialize_units_execution_verified": False,
        "ecu_identity_verified": False, "xc90_v8_my2009_verified": False,
        "limitations": [
            "Manual run matching is not independently verified by source reports.",
            "J2534 Connect indicates local channel creation, not VDASH acceptance.",
            "VIN transport delivery is header/length evidence, not authentic vehicle identity.",
            "OEM delivery does not prove ResultData or InitializeUnits executed.",
            "Missing observed OEM request does not prove no other transport or client path.",
            "The saved method excerpts lack InitializeUnits and RefreshAvailability bodies.",
            "Incomplete UI Connect cannot prove that a completed ECU scan failed.",
            "Malformed J2534 Connect metadata prevents reliable connection classification.",
        ],
    }


def _load(path, limit):
    if path.stat().st_size > limit:
        raise ValueError("source_size")
    with path.open(encoding="utf-8-sig") as f:
        return json.load(f)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for option in ("ui", "connect", "discovery", "output"):
        p.add_argument("--" + option, required=True, type=Path)
    a = p.parse_args(argv)
    try:
        files = [a.ui.resolve(), a.connect.resolve(), a.discovery.resolve()]
        if len(set(files)) != 3 or a.output.resolve() in files:
            raise ValueError("source_overlap")
        result = audit(_load(a.ui, 4096), _load(a.connect, 131072),
                       _load(a.discovery, 2097152))
        with a.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, indent=2, sort_keys=True)
            f.write("\n")
    except (ValueError, OSError, UnicodeError, json.JSONDecodeError):
        print("VDASH audit failed; private details withheld", file=sys.stderr)
        return 2
    print("PASS: source-constrained observations; ECU acceptance not verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
