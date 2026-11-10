#!/usr/bin/env python3
"""Combine already-redacted VIDA research reports into evidence-limited gates.

This tool never opens original VIDA XML, SQL databases, VIN or J2534 traces.
It cannot establish provenance or runtime causality between input reports.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
from pathlib import Path
import sys

SCHEMA = "virtualcar-vida-evidence-summary-v1"
BUNDLE_SCHEMA = "virtualcar-vida-redacted-report-bundle-v1"
MAX_REPORT_BYTES = 1024 * 1024
MAX_MANIFEST_BYTES = 8192
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
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
DICETIMING_NEGATIVE = (
    "source_rows_read", "sql_definitions_read", "original_timing_values_read",
    "timing_profile_link_verified", "cross_database_snapshot_verified",
    "d2_baud_verified", "readvin_execution_verified", "client_vin_accepted",
    "physical_j2534_verified", "replay_approved",
)
READVIN_NEGATIVE = (
    "original_xml_included", "runtime_readvin_selected", "vin_accepted_by_client",
    "xc90_v8_my2009_verified", "replay_approved",
)
STAGES = (
    "report_bytes_binding", "catalog_metadata", "dice_timing_metadata",
    "catalog_shape_comparison", "dice_timing_count_comparison",
    "readvin_static_graph",
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


def read_report_with_digest(path: Path, max_bytes=MAX_REPORT_BYTES):
    """Hash precisely the bytes that are parsed, so there is no read/hash race."""
    if (path.is_symlink() or not path.is_file()
            or path.stat().st_size > max_bytes):
        raise EvidenceError("unsafe report source")
    try:
        data = path.read_bytes()
        if len(data) > max_bytes:
            raise EvidenceError("oversized report source")
        obj = json.loads(data.decode("utf-8"),
                         object_pairs_hook=_object_unique,
                         parse_constant=_reject_nonfinite)
        return obj, hashlib.sha256(data).hexdigest()
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise EvidenceError("invalid redacted report") from None


def read_report(path: Path):
    return read_report_with_digest(path)[0]


def verify_bundle_manifest(manifest, report_digests):
    """Verify report-byte equality only, never common origin or authenticity."""
    if (type(manifest) is not dict or
            set(manifest) != {"schema_version", "scope", "reports",
                              "same_installation_provenance_verified",
                              "runtime_evidence_verified"} or
            manifest["schema_version"] != BUNDLE_SCHEMA or
            manifest["scope"] != "redacted_report_bytes_only" or
            manifest["same_installation_provenance_verified"] is not False or
            manifest["runtime_evidence_verified"] is not False):
        raise EvidenceError("unsupported bundle manifest")
    listed = manifest["reports"]
    if (type(listed) is not dict or not listed or
            set(listed) != set(report_digests)):
        raise EvidenceError("manifest report set mismatch")
    for kind, wanted in listed.items():
        if (type(wanted) is not str or not _SHA256.fullmatch(wanted) or
                not hmac.compare_digest(wanted, report_digests[kind])):
            raise EvidenceError("redacted report digest mismatch")
    return True


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


def _dice_timing(report):
    if (type(report) is not dict or
            report.get("schema_version") != "virtualcar-vida-dicetiming-metadata-v1" or
            report.get("status") != "metadata_only" or
            report.get("database") != "DiceTiming" or
            report.get("backend") not in ("sqlite-export", "sqlserver")):
        raise EvidenceError("unexpected DiceTiming schema")
    _negative(report, DICETIMING_NEGATIVE)
    tables = _uint(report.get("table_count"), 2000)
    columns = _uint(report.get("column_count"), 30000)
    keys = _uint(report.get("declared_fk_column_count"), 30000)
    if (tables < 1 or columns < tables or
            (report["backend"] == "sqlite-export" and keys != 0)):
        raise EvidenceError("incomplete DiceTiming metadata")
    return {"backend": report["backend"], "table_count": tables,
            "column_count": columns, "declared_fk_column_count": keys,
            "timing_values_verified": False}


def _dice_timing_count_comparison(report):
    if (type(report) is not dict or
            report.get("schema_version") != "virtualcar-vida-dicetiming-count-compare-v1" or
            report.get("status") != "aggregate_count_comparison_only" or
            report.get("database") != "DiceTiming"):
        raise EvidenceError("unexpected DiceTiming comparison schema")
    for name in ("sqlite_fk_metadata_available", "schema_equivalence_verified",
                 "same_installation_provenance_verified", "referential_rows_verified",
                 "timing_profile_link_verified", "original_timing_values_read",
                 "d2_baud_verified", "readvin_execution_verified",
                 "client_vin_accepted", "replay_approved"):
        if report.get(name) is not False:
            raise EvidenceError("unexpected DiceTiming comparison evidence claim")
    st = _uint(report.get("sqlite_table_count"), 2000)
    ss = _uint(report.get("sqlserver_table_count"), 2000)
    ct = _uint(report.get("sqlite_column_count"), 30000)
    cs = _uint(report.get("sqlserver_column_count"), 30000)
    _uint(report.get("sqlserver_declared_fk_column_count"), 30000)
    if not (st > 0 and ss > 0 and ct >= st and cs >= ss):
        raise EvidenceError("incomplete DiceTiming comparison totals")
    matches_tables, matches_columns = st == ss, ct == cs
    for name, expected in (("table_counts_equal", matches_tables),
                           ("column_counts_equal", matches_columns),
                           ("aggregate_counts_equal", matches_tables and matches_columns)):
        if report.get(name) is not expected:
            raise EvidenceError("inconsistent DiceTiming count comparison")
    return {"table_counts_equal": matches_tables,
            "column_counts_equal": matches_columns,
            "aggregate_counts_equal": matches_tables and matches_columns,
            "schema_equivalence_verified": False}


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


def assemble(catalog=None, comparison=None, readvin=None, dice_timing=None,
             report_bytes_bound=False, dice_timing_comparison=None):
    if type(report_bytes_bound) is not bool:
        raise EvidenceError("invalid byte-binding status")
    if all(item is None for item in (catalog, comparison, readvin, dice_timing,
                                    dice_timing_comparison)):
        raise EvidenceError("no evidence reports supplied")
    accepted_catalog = _catalog(catalog) if catalog is not None else None
    accepted_dice_timing = _dice_timing(dice_timing) if dice_timing is not None else None
    accepted_dice_comparison = (_dice_timing_count_comparison(dice_timing_comparison)
                                if dice_timing_comparison is not None else None)
    accepted_comparison = _comparison(comparison) if comparison is not None else None
    accepted_readvin = _readvin(readvin) if readvin is not None else None
    if accepted_comparison is not None:
        matched = all(n == 0 for n in accepted_comparison.values())
        comparison_status = "passed" if matched else "failed"
    else:
        comparison_status = "not_tested"
    dice_comparison_status = ("not_tested" if accepted_dice_comparison is None else
                              "passed" if accepted_dice_comparison["aggregate_counts_equal"]
                              else "failed")
    statuses = {
        "report_bytes_binding": "passed" if report_bytes_bound else "not_tested",
        "catalog_metadata": "passed" if accepted_catalog else "not_tested",
        "dice_timing_metadata": "passed" if accepted_dice_timing else "not_tested",
        "catalog_shape_comparison": comparison_status,
        "dice_timing_count_comparison": dice_comparison_status,
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
        "dice_timing_catalog": accepted_dice_timing,
        "dice_timing_count_comparison": accepted_dice_comparison,
        "comparison_disagreement_counts": accepted_comparison,
        "readvin_graph": accepted_readvin,
        "open_blockers": [name for name in STAGES if statuses[name] != "passed"],
        "redacted_report_bytes_bound": report_bytes_bound,
        "same_installation_provenance_verified": False,
        "original_vida_data_verified": False,
        "dice_timing_profile_mapping_verified": False,
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
    parser.add_argument("--dicetiming-report", type=Path)
    parser.add_argument("--dicetiming-compare-report", type=Path)
    parser.add_argument("--bundle-manifest", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        paths = {"catalog": args.catalog_report, "comparison": args.compare_report,
                 "readvin": args.readvin_report, "dicetiming": args.dicetiming_report,
                 "dicetiming_compare": args.dicetiming_compare_report}
        sources = [p for p in paths.values() if p is not None]
        if args.bundle_manifest is not None:
            sources.append(args.bundle_manifest)
        checkout = Path(__file__).resolve().parents[2]
        target = args.output.resolve()
        resolved = [p.resolve() for p in sources]
        if (not any(p is not None for p in paths.values())
                or not args.output.parent.is_dir() or args.output.parent.is_symlink()
                or target == checkout or checkout in target.parents
                or target in resolved or len(set(resolved)) != len(resolved)):
            raise EvidenceError("unsafe output or empty inputs")
        loaded = {key: read_report_with_digest(path) for key, path in paths.items()
                  if path is not None}
        if args.bundle_manifest is not None:
            manifest, _ = read_report_with_digest(args.bundle_manifest, MAX_MANIFEST_BYTES)
            verify_bundle_manifest(manifest, {key: pair[1] for key, pair in loaded.items()})
        result = assemble(
            catalog=loaded["catalog"][0] if "catalog" in loaded else None,
            comparison=loaded["comparison"][0] if "comparison" in loaded else None,
            readvin=loaded["readvin"][0] if "readvin" in loaded else None,
            dice_timing=loaded["dicetiming"][0] if "dicetiming" in loaded else None,
            dice_timing_comparison=(loaded["dicetiming_compare"][0]
                                    if "dicetiming_compare" in loaded else None),
            report_bytes_bound=args.bundle_manifest is not None,
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
