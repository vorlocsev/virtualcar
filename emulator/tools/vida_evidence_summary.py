#!/usr/bin/env python3
"""Combine already-redacted VIDA research reports into evidence-limited gates.

This tool never opens original VIDA XML, SQL databases, VIN or J2534 traces.
It cannot establish provenance or runtime causality between input reports.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCHEMA = "virtualcar-vida-evidence-summary-v1"
MAX_REPORT_BYTES = 1024 * 1024
DATABASES = frozenset(("CarCom", "DiagSwdlRepository", "BaseData"))
CATALOG_NEGATIVE = (
    "source_rows_read", "original_xml_sql_read", "cross_database_snapshot_verified",
    "record_joins_verified", "catalog_visibility_complete_verified",
    "selected_vehicle_profile_verified", "d2_baud_verified",
    "readvin_execution_verified", "client_vin_accepted", "replay_approved",
)
COMPARE_NEGATIVE = (
    "catalog_visibility_complete_verified", "cross_database_snapshot_verified",
    "record_joins_verified", "selected_vehicle_profile_verified", "d2_baud_verified",
    "readvin_execution_verified", "client_vin_accepted",
)
READVIN_NEGATIVE = (
    "original_xml_included", "runtime_readvin_selected", "vin_accepted_by_client",
    "xc90_v8_my2009_verified", "replay_approved",
)
STAGES = (
    "catalog_metadata", "catalog_shape_comparison", "readvin_static_graph",
    "profile_to_readvin_join", "getscript_runtime_selection",
    "j2534_correlated_exchange", "client_vin_acceptance",
)


class EvidenceError(ValueError):
    """Use fixed error categories; do not expose private source data."""


def _object_unique(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise EvidenceError("duplicate JSON key")
        obj[key] = value
    return obj


def _reject_nonfinite(_):
    raise EvidenceError("nonfinite JSON number")


def read_report(path: Path):
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > MAX_REPORT_BYTES):
        raise EvidenceError("unsafe report source")
    try:
        return json.loads(path.read_bytes().decode("utf-8"),
                          object_pairs_hook=_object_unique,
                          parse_constant=_reject_nonfinite)
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise EvidenceError("invalid redacted report") from None


def _uint(value, limit=100000):
    if type(value) is not int or not 0 <= value <= limit:
        raise EvidenceError("invalid redacted count")
    return value


def _negative(obj, names):
    if any(obj.get(name) is not False for name in names):
        raise EvidenceError("runtime or private evidence claim unsupported")


def _catalog(report):
    if (type(report) is not dict or
            report.get("schema_version") != "virtualcar-vida-unified-catalog-v1" or
            report.get("status") != "metadata_only" or
            report.get("backend") not in ("sqlite-export", "sqlserver")):
        raise EvidenceError("unexpected catalog schema")
    _negative(report, CATALOG_NEGATIVE)
    dbs = report.get("databases")
    if type(dbs) is not dict or set(dbs) != DATABASES:
        raise EvidenceError("incomplete catalog scope")
    for entry in dbs.values():
        if type(entry) is not dict or type(entry.get("known_tables")) is not dict:
            raise EvidenceError("invalid catalog metadata")
        for name in ("table_count", "column_count", "declared_fk_column_count"):
            _uint(entry.get(name))
    if type(report.get("edges")) is not list or len(report["edges"]) > 1000:
        raise EvidenceError("invalid catalog edge summary")
    return {"backend": report["backend"], "report_shape_accepted": True}


def _comparison(report):
    if (type(report) is not dict or
            report.get("schema_version") != "virtualcar-vida-catalog-compare-v1" or
            report.get("status") != "metadata_shape_comparison_only"):
        raise EvidenceError("unexpected comparison schema")
    _negative(report, COMPARE_NEGATIVE)
    counts = {}
    for name in ("table_disagreements", "column_disagreements", "candidate_edge_disagreements"):
        items = report.get(name)
        if type(items) is not list or len(items) > 1000 or any(type(x) is not dict for x in items):
            raise EvidenceError("invalid comparison counts")
        counts[name] = len(items)
    return counts


def _readvin(report):
    if (type(report) is not dict or
            report.get("schema_version") != "virtualcar-vida-redacted-readvin-crosscheck-v1" or
            report.get("input_kind") != "two_redacted_static_vida_reports" or
            report.get("structural_counters_consistent") is not True):
        raise EvidenceError("unexpected ReadVin schema")
    _negative(report, READVIN_NEGATIVE)
    if _uint(report.get("crosschecked_fields")) != 7:
        raise EvidenceError("incomplete ReadVin crosscheck")
    nodes = _uint(report.get("nodes"), 20000)
    readers = _uint(report.get("readvin_nodes"), 20000)
    outputs = _uint(report.get("identity_output_nodes"), 20000)
    methods = report.get("identity_methods")
    if type(methods) is not dict or set(methods) != {"add_vin_declarations", "x40_declarations"}:
        raise EvidenceError("invalid identity declarations")
    declared = sum(_uint(v, 20000) for v in methods.values())
    if not (0 < readers <= nodes and 0 < outputs <= nodes and declared > 0):
        raise EvidenceError("empty or inconsistent ReadVin graph")
    return {"crosschecked_fields": 7, "readvin_reader_nodes": readers,
            "identity_output_nodes": outputs, "identity_call_declarations": declared}


def assemble(catalog=None, comparison=None, readvin=None):
    if catalog is None and comparison is None and readvin is None:
        raise EvidenceError("no evidence reports supplied")
    accepted_catalog = _catalog(catalog) if catalog is not None else None
    accepted_comparison = _comparison(comparison) if comparison is not None else None
    accepted_readvin = _readvin(readvin) if readvin is not None else None
    if accepted_comparison is not None:
        matched = all(n == 0 for n in accepted_comparison.values())
        comparison_status = "passed" if matched else "failed"
    else:
        comparison_status = "not_tested"
    statuses = {
        "catalog_metadata": "passed" if accepted_catalog else "not_tested",
        "catalog_shape_comparison": comparison_status,
        "readvin_static_graph": "passed" if accepted_readvin else "not_tested",
        "profile_to_readvin_join": "not_tested",
        "getscript_runtime_selection": "not_tested",
        "j2534_correlated_exchange": "not_tested",
        "client_vin_acceptance": "not_tested",
    }
    # 'Passed' applies only to the structural validation of supplied reports,
    # never to provenance, original VIDA execution, transport or vehicle identity.
    return {
        "schema_version": SCHEMA, "status": "redacted_static_evidence_summary_only",
        "gate_semantics": "report_structure_not_runtime_acceptance",
        "stages": [{"id": name, "status": statuses[name]} for name in STAGES],
        "catalog": accepted_catalog,
        "comparison_disagreement_counts": accepted_comparison,
        "readvin_graph": accepted_readvin,
        "open_blockers": [name for name in STAGES if statuses[name] != "passed"],
        "same_installation_provenance_verified": False,
        "original_vida_data_verified": False,
        "profile_script_link_verified": False,
        "actual_getscript_selected": False,
        "physical_j2534_verified": False,
        "client_vin_accepted": False,
        "replay_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline VIDA redacted evidence summary")
    parser.add_argument("--catalog-report", type=Path)
    parser.add_argument("--compare-report", type=Path)
    parser.add_argument("--readvin-report", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        sources = [p for p in (args.catalog_report, args.compare_report, args.readvin_report)
                   if p is not None]
        checkout = Path(__file__).resolve().parents[2]
        target = args.output.resolve()
        if (not sources or not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or target == checkout or checkout in target.parents
                or target in {source.resolve() for source in sources}):
            raise EvidenceError("unsafe output or empty inputs")
        result = assemble(
            catalog=read_report(args.catalog_report) if args.catalog_report else None,
            comparison=read_report(args.compare_report) if args.compare_report else None,
            readvin=read_report(args.readvin_report) if args.readvin_report else None,
        )
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        print("VIDA redacted summary written; runtime VIN/ECU not verified.")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
