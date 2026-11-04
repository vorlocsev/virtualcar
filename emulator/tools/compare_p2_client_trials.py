#!/usr/bin/env python3
"""Compare TWO/THREE redacted client trial reports, never raw J2534 logs.

Trials A=disabled CEM D2, B=published donor-era 13-frame B9FB,
C=explicitly enabled mixed public B9FB/B9F0. The tool does not authenticate
SectorV/VDASH, a donor CEM, a VIN, or XC90 V8 MY2009 compatibility.
"""
import argparse
import json
from pathlib import Path
import sys

FORMAT = "virtualcar-p2-client-trial-comparison-v1"
BOUNDARY_FORMAT = "virtualcar-p2-client-capture-boundary-v1"
MAX_BYTES = 256 * 1024
STAGES = ("native_records", "connected", "b9fb_transport",
          "b9f0_transport", "p3_transport", "operator_completed_ui_scan",
          "operator_reported_vin")


def _read(path):
    if not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise ValueError("missing_or_oversized_safe_report")
    item = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(item, dict) or item.get("format") != BOUNDARY_FORMAT:
        raise ValueError("not_a_client_boundary_report")
    for key in ("read_only", "contains_payload_data", "raw_log_exported",
                "client_run_executed_by_tool", "native_executable_identity_verified",
                "client_ecu_inventory_verified", "vehicle_identity_verified",
                "xc90_v8_my2009_verified"):
        expected = key == "read_only"
        if item.get(key) is not expected:
            raise ValueError("invalid_safe_report_verification_flags")
    for key in ("b9fb_positive_transport_count",
                "b9f0_positive_transport_count",
                "first_p3_positive_transport_count",
                "connect_succeeded"):
        value = item.get(key)
        if type(value) is not int or not 0 <= value <= 100000:
            raise ValueError("unbounded_or_missing_count")
    flags = {
        "native_records": item.get("new_native_records_observed") is True,
        "connected": item["connect_succeeded"] > 0,
        "b9fb_transport": item["b9fb_positive_transport_count"] > 0,
        "b9f0_transport": item["b9f0_positive_transport_count"] > 0,
        "p3_transport": item["first_p3_positive_transport_count"] > 0,
        "operator_completed_ui_scan": (
            item.get("operator_ecu_list_attributable_to_completed_scan") is True),
        "operator_reported_vin": (
            item.get("ui_vin_display_reported") == "visible"
            and item.get("same_run_operator_attested") is True),
    }
    observed = item.get("reported_client")
    # Preserve only a fixed public category, never original arbitrary text.
    client = (observed if observed in
              ("sectorv", "vdash_2_0", "vdash_2_5_115_79")
              else "not_verified")
    return {"stages": flags, "client_category": client}


def compare(report_a, report_b, report_c=None):
    trials = [
        ("A_no_d2", _read(report_a)),
        ("B_published_donor_b9fb", _read(report_b)),
    ]
    if report_c is not None:
        trials.append(("C_mixed_donor_b9fb_b9f0", _read(report_c)))
    categories = {
        record["client_category"] for _, record in trials
        if record["client_category"] != "not_verified"
    }
    warnings = []
    if len(categories) > 1:
        warnings.append("different_operator_reported_client_families")
    if any(record["client_category"] == "not_verified"
           for _, record in trials):
        warnings.append("one_or_more_client_labels_unverified")
    if not all(record["stages"]["native_records"] for _, record in trials):
        warnings.append("one_or_more_runs_have_no_new_native_j2534_records")
    stages = []
    prior = None
    for label, record in trials:
        value = record["stages"]
        row = {
            "trial": label,
            "stages": value,
            "changed_since_previous": (
                [name for name in STAGES if value[name] != prior[name]]
                if prior is not None else []),
        }
        stages.append(row)
        prior = value
    return {
        "format": FORMAT,
        "read_only": True,
        "contains_payload_data": False,
        "comparability_warning_codes": warnings,
        "trials": stages,
        "same_client_family_self_reported": (len(categories) == 1
                                              and not any(
                                                  r["client_category"] == "not_verified"
                                                  for _, r in trials)),
        "actual_client_executed_independently_verified": False,
        "sectorv_vdash_acceptance_verified": False,
        "genuine_xc90_v8_my2009_verified": False,
        "limitations": [
            "Differences are observed report fields, NOT proof that the client parsed the B9FB/B9F0 bytes.",
            "A missing request may indicate wrong DLL selection, no client launch, or no protocol path.",
            "Donor XC70-era fixture fields and mixed B9F0 are not genuine XC90 V8 MY2009 ECU identities.",
            "No process names, PIDs, timestamps, VIN, ECU identifiers, source paths or CAN payloads are exported.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--a", type=Path, required=True,
                   help="Trial A SAFE-JSON-REPORTS/client-boundary.json")
    p.add_argument("--b", type=Path, required=True,
                   help="Trial B SAFE-JSON-REPORTS/client-boundary.json")
    p.add_argument("--c", type=Path,
                   help="Optional Trial C SAFE-JSON-REPORTS/client-boundary.json")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        inputs = [args.a, args.b] + ([args.c] if args.c else [])
        if len({path.resolve() for path in inputs + [args.output]}) != (
                len(inputs) + 1):
            raise ValueError("input_output_paths_overlap")
        result = compare(args.a, args.b, args.c)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, UnicodeError, ValueError, TypeError, KeyError,
            json.JSONDecodeError):
        print("Trial comparison rejected: malformed or unsafe input",
              file=sys.stderr)
        return 2
    print("PASS: compared safe native transport stages; genuine client/ECU identity unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
