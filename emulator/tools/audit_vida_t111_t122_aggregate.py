#!/usr/bin/env python3
"""Owner-private bounded SQL Server T111 -> T122 reference coverage probe.

Only CarCom, only fixed columns, a TOP(1000) aggregate with no row values
returned to Python. Not proof of ReadVin execution or ECU/VIN acceptance.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

from vida_unified_analyzer import (
    AnalyzerError, DSN_RE, MAX_COLUMNS, MAX_TABLES, SQL_COLUMNS, SQL_TABLES,
    _insert_column, _insert_table, _rows,
)

SCHEMA = "virtualcar-vida-t111-t122-sampled-join-v1"
SAMPLE_LIMIT = 1000


class ProbeError(Exception):
    """Messages must never contain private identifiers or connection strings."""


def _quoted(value: str) -> str:
    """Quote an identifier returned from the SQL catalog, not user-provided SQL."""
    if not isinstance(value, str) or not value or len(value) > 128 or "\x00" in value:
        raise ProbeError("invalid catalog schema identity")
    return "[" + value.replace("]", "]]" ) + "]"


def _resolve(tables, name, required):
    matching = [(schema, cols) for (schema, table), cols in tables.items()
                if table == name.casefold()]
    if len(matching) != 1:
        raise ProbeError("missing or ambiguous reference table")
    schema, columns = matching[0]
    if not set(col.casefold() for col in required).issubset(columns):
        raise ProbeError("required reference columns are not visible")
    return schema


def _aggregate_sql(source_schema, target_schema):
    source = _quoted(source_schema) + ".[T111_Service]"
    target = _quoted(target_schema) + ".[T122_Protocol]"
    return f"""
WITH sample AS (
    SELECT TOP ({SAMPLE_LIMIT}) s.[fkT122_Protocol] AS [protocol_ref]
    FROM {source} AS s
    ORDER BY s.[id]
)
SELECT COUNT_BIG(*),
       SUM(CASE WHEN sample.[protocol_ref] IS NULL THEN 1 ELSE 0 END),
       SUM(CASE WHEN sample.[protocol_ref] IS NOT NULL AND EXISTS (
           SELECT 1 FROM {target} AS p
           WHERE p.[id] = sample.[protocol_ref]) THEN 1 ELSE 0 END),
       SUM(CASE WHEN sample.[protocol_ref] IS NOT NULL AND NOT EXISTS (
           SELECT 1 FROM {target} AS p
           WHERE p.[id] = sample.[protocol_ref]) THEN 1 ELSE 0 END)
FROM sample
"""


def _validate_counts(result):
    if len(result) != 1 or len(result[0]) != 4:
        raise ProbeError("unexpected aggregate result")
    n, nulls, matches, misses = result[0]
    if type(n) is not int or n < 0 or n > SAMPLE_LIMIT:
        raise ProbeError("invalid sampled row count")
    values = [0 if x is None and n == 0 else x
              for x in (nulls, matches, misses)]
    if (any(type(x) is not int or x < 0 or x > n for x in values)
            or sum(values) != n):
        raise ProbeError("inconsistent aggregate counts")
    return n, *values


def probe(dsn: str, connector=None):
    if not isinstance(dsn, str) or not DSN_RE.fullmatch(dsn):
        raise ProbeError("invalid DSN name")
    if connector is None:
        try:
            import pyodbc
        except ImportError:
            raise ProbeError("pyodbc unavailable") from None
        connector = pyodbc.connect
    conn_string = (f"DSN={dsn};DATABASE=CarCom;Trusted_Connection=Yes;"
                   "Encrypt=Yes;TrustServerCertificate=No;ApplicationIntent=ReadOnly;")
    try:
        db = connector(conn_string, autocommit=True, timeout=8)
        try:
            db.timeout = 8
            cursor = db.cursor()
            identity = _rows(cursor, "SELECT DB_NAME()", 1)
            if len(identity) != 1 or identity[0][0] != "CarCom":
                raise ProbeError("unexpected active database")
            table_rows = _rows(cursor, SQL_TABLES, MAX_TABLES)
            column_rows = _rows(cursor, SQL_COLUMNS, MAX_COLUMNS)
            tables = {}
            for schema, name in table_rows:
                _insert_table(tables, schema, name)
            for schema, name, column in column_rows:
                _insert_column(tables, schema, name, column)
            source = _resolve(tables, "T111_Service", ("id", "fkT122_Protocol"))
            target = _resolve(tables, "T122_Protocol", ("id",))
            rows = _rows(cursor, _aggregate_sql(source, target), 1)
        finally:
            db.close()
    except (ProbeError, AnalyzerError):
        raise ProbeError("catalog or aggregate preflight failed") from None
    except Exception:
        raise ProbeError("SQL Server aggregate read failed") from None
    sample, nulls, matches, misses = _validate_counts(rows)
    return {
        "schema_version": SCHEMA,
        "status": "sampled_reference_coverage_only",
        "source_database": "CarCom",
        "source_table": "T111_Service", "target_table": "T122_Protocol",
        "sample_bound": SAMPLE_LIMIT, "sampled_service_rows": sample,
        "null_reference_rows": nulls, "matching_reference_rows": matches,
        "unmatched_reference_rows": misses,
        "sample_nonempty": sample > 0,
        "catalog_visibility_complete_verified": False,
        "all_rows_verified": False, "selected_vehicle_profile_verified": False,
        "readvin_execution_verified": False, "d2_baud_verified": False,
        "client_vin_accepted": False, "ecu_identification_verified": False,
        "replay_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Owner-private T111/T122 bounded aggregate")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        root = Path(__file__).resolve().parents[2]
        dest = args.output.resolve()
        if root == dest or root in dest.parents or not args.output.parent.is_dir():
            raise ProbeError("unsafe output destination")
        result = probe(os.environ.get("VIDA_SQLSERVER_DSN", ""))
        with args.output.open("x", encoding="utf-8") as f:
            json.dump(result, f, sort_keys=True, indent=2)
            f.write("\n")
        print("Bounded CarCom aggregate generated; vehicle evidence unverified.")
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
