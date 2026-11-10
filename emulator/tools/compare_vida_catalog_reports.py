#!/usr/bin/env python3
"""Compare only redacted VIDA schema reports; never open source databases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from audit_vida_carcom_schema_links import CANDIDATE_EDGES, HARDWARE_CANDIDATE_EDGES, TABLES
from vida_unified_analyzer import (SCHEMA as INPUT_SCHEMA, MAX_TABLES,
                                   MAX_COLUMNS, MAX_KEYS)

MAX_INPUT_BYTES = 1024 * 1024
OUTPUT_SCHEMA = "virtualcar-vida-catalog-compare-v1"
UNVERIFIED = (
    "source_rows_read", "original_xml_sql_read", "cross_database_snapshot_verified",
    "record_joins_verified", "catalog_visibility_complete_verified",
    "selected_vehicle_profile_verified", "d2_baud_verified",
    "readvin_execution_verified", "client_vin_accepted", "replay_approved",
)
HINTS = tuple((kind, db, src, sc, dst, dc)
              for kind, edges in (("service_shape", CANDIDATE_EDGES),
                                  ("hardware_shape", HARDWARE_CANDIDATE_EDGES))
              for db, src, sc, dst, dc in edges)


class CompareError(Exception):
    """Generic failures: never echo report paths, content or VIN."""


def _no_duplicates(pairs):
    result = {}
    for key, val in pairs:
        if key in result:
            raise CompareError("duplicate JSON key")
        result[key] = val
    return result


def read_redacted_report(path: Path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_INPUT_BYTES:
        raise CompareError("invalid redacted report file")
    try:
        with path.open("r", encoding="utf-8") as fh:
            return json.load(fh, object_pairs_hook=_no_duplicates)
    except (OSError, UnicodeError, ValueError, RecursionError):
        raise CompareError("invalid JSON report") from None


def _check(report, backend):
    if not isinstance(report, dict) or report.get("schema_version") != INPUT_SCHEMA:
        raise CompareError("unexpected report schema")
    if report.get("backend") != backend or report.get("status") != "metadata_only":
        raise CompareError("unexpected backend or evidence status")
    if any(report.get(flag) is not False for flag in UNVERIFIED):
        raise CompareError("unsupported verified claim")
    databases = report.get("databases")
    if not isinstance(databases, dict) or set(databases) != set(TABLES):
        raise CompareError("incomplete report databases")
    for db, hints in TABLES.items():
        entry = databases[db]
        if not isinstance(entry, dict) or not isinstance(entry.get("known_tables"), dict):
            raise CompareError("invalid known-table inventory")
        fixed = entry["known_tables"]
        if set(fixed) != set(hints):
            raise CompareError("unexpected table inventory")
        for label, maximum in (("table_count", MAX_TABLES),
                               ("column_count", MAX_COLUMNS),
                               ("declared_fk_column_count", MAX_KEYS)):
            value = entry.get(label)
            if type(value) is not int or not 0 <= value <= maximum:
                raise CompareError("invalid catalog count")
        if backend == "sqlite-export" and entry["declared_fk_column_count"] != 0:
            raise CompareError("unexpected SQLite declared FK count")
        present_count = 0
        known_column_count = 0
        for table, columns in hints.items():
            item = fixed[table]
            if not isinstance(item, dict) or type(item.get("present")) is not bool:
                raise CompareError("invalid table presence")
            yes, no = item.get("known_columns_present"), item.get("known_columns_missing")
            if not isinstance(yes, list) or not isinstance(no, list):
                raise CompareError("invalid column shapes")
            if (any(type(x) is not str for x in yes + no) or len(yes + no) != len(set(yes + no))
                    or set(yes + no) != set(columns) or (not item["present"] and yes)):
                raise CompareError("ambiguous column shapes")
            count = item.get("column_count")
            if (type(count) is not int or count < len(yes)
                    or (item["present"] and count == 0)
                    or (not item["present"] and count != 0)):
                raise CompareError("inconsistent known-table column count")
            present_count += int(item["present"])
            known_column_count += count
        if (present_count > entry["table_count"]
                or known_column_count > entry["column_count"]):
            raise CompareError("inconsistent aggregate catalog count")
    edges = report.get("edges")
    if not isinstance(edges, list) or len(edges) > 256:
        raise CompareError("invalid report edges")
    shapes = {}
    for edge in edges:
        if not isinstance(edge, dict):
            raise CompareError("invalid report edge")
        kind = edge.get("evidence")
        if kind == "sqlserver_declared_fk":
            if backend != "sqlserver" or edge.get("referential_rows_verified") is not False:
                raise CompareError("unexpected declared FK")
            continue  # No SQL Server declared FK can prove a row join.
        key = (kind, edge.get("database"), edge.get("source"),
               edge.get("source_column"), edge.get("target"), edge.get("target_column"))
        if any(type(value) is not str for value in key):
            raise CompareError("invalid report edge identity")
        if key not in HINTS or key in shapes or type(edge.get("column_shape_present")) is not bool:
            raise CompareError("unexpected or duplicate shape edge")
        if edge.get("referential_rows_verified") is not False:
            raise CompareError("unverified referential claim")
        _, db, src, source_column, dst, target_column = key
        left = databases[db]["known_tables"][src]
        right = databases[db]["known_tables"][dst]
        expected = (left["present"] and right["present"]
                    and source_column in left["known_columns_present"]
                    and target_column in right["known_columns_present"])
        if edge["column_shape_present"] != expected:
            raise CompareError("inconsistent candidate edge shape")
        shapes[key] = edge["column_shape_present"]
    if set(shapes) != set(HINTS):
        raise CompareError("missing known shape edges")
    return databases, shapes


def compare(sqlite_report, sqlserver_report):
    left, lshapes = _check(sqlite_report, "sqlite-export")
    right, rshapes = _check(sqlserver_report, "sqlserver")
    tables = []
    columns = []
    for db, hints in TABLES.items():
        for table, expected in hints.items():
            ltab = left[db]["known_tables"][table]
            rtab = right[db]["known_tables"][table]
            if ltab["present"] != rtab["present"]:
                tables.append({"database": db, "table": table,
                               "sqlite_present": ltab["present"],
                               "sqlserver_present": rtab["present"]})
            for col in expected:
                l = col in ltab["known_columns_present"]
                r = col in rtab["known_columns_present"]
                if l != r:
                    columns.append({"database": db, "table": table, "column": col,
                                    "sqlite_present": l, "sqlserver_present": r})
    edges = []
    for kind, db, src, sc, dst, dc in HINTS:
        key = (kind, db, src, sc, dst, dc)
        if lshapes[key] != rshapes[key]:
            edges.append({"kind": kind, "database": db, "source": src,
                          "target": dst, "sqlite_shape": lshapes[key],
                          "sqlserver_shape": rshapes[key]})
    return {"schema_version": OUTPUT_SCHEMA, "status": "metadata_shape_comparison_only",
            "catalog_visibility_complete_verified": False,
            "cross_database_snapshot_verified": False, "record_joins_verified": False,
            "selected_vehicle_profile_verified": False, "d2_baud_verified": False,
            "readvin_execution_verified": False, "client_vin_accepted": False,
            "table_disagreements": tables, "column_disagreements": columns,
            "candidate_edge_disagreements": edges}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare redacted VIDA catalog shape reports")
    parser.add_argument("--sqlite-report", required=True, type=Path)
    parser.add_argument("--sqlserver-report", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        checkout = Path(__file__).resolve().parents[2]
        output = args.output.resolve()
        if output == checkout or checkout in output.parents or not args.output.parent.is_dir():
            raise CompareError("unsafe output destination")
        sources = [args.sqlite_report, args.sqlserver_report]
        if output in {path.resolve() for path in sources}:
            raise CompareError("output aliases source")
        result = compare(*(read_redacted_report(path) for path in sources))
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, sort_keys=True, indent=2)
            handle.write("\n")
        print("Redacted catalog shapes compared; original VIDA evidence unverified.")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
