#!/usr/bin/env python3
"""Read-only categorical classifier of BaseData.VehicleModel descriptions.

Read owner-private original description strings *only in memory*; output
bounded counts of fixed lexical XC90 shapes, never descriptions or model IDs.
Classification is not a selected VIDA vehicle or a cross-DB profile join.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3
import sys
import time

from audit_vida_profile_fk_counts import MAX_RUN_SECONDS, SchemaError, _catalog, _physical

MAX_MODEL_ROWS = 10000
MAX_DESCRIPTION_CHARS = 512
PREFIX_XC90 = re.compile(r"^XC90(?![A-Z0-9])")
TOKEN_XC90 = re.compile(r"(?<![A-Z0-9])XC90(?![A-Z0-9])")
SPACED_XC90 = re.compile(r"(?<![A-Z0-9])XC\s+90(?![A-Z0-9])")
HYPHEN_XC90 = re.compile(r"(?<![A-Z0-9])XC-90(?![A-Z0-9])")

REQUIRED = {
    "VehicleProfile": ("Id", "fkVehicleModel", "fkModelYear", "fkEngine"),
    "VehicleModel": ("Id", "Description"),
    "ModelYear": ("Id",),
    "Engine": ("Id",),
}


def _summarize_descriptions(descriptions: list) -> dict:
    if len(descriptions) > MAX_MODEL_ROWS:
        raise SchemaError("unbounded model catalog row count")
    counts = {
        "exact_xc90": 0,
        "prefix_xc90_token": 0,
        "anywhere_xc90_token": 0,
        "anywhere_xc90_substring": 0,
        "anywhere_xc_space_90_token": 0,
        "anywhere_xc_hyphen_90_token": 0,
        "null_or_empty_description_rows": 0,
    }
    for (original,) in descriptions:
        if original is None:
            counts["null_or_empty_description_rows"] += 1
            continue
        if not isinstance(original, str) or len(original) > MAX_DESCRIPTION_CHARS:
            raise SchemaError("invalid or oversized model description")
        s = original.strip().upper()
        if not s:
            counts["null_or_empty_description_rows"] += 1
            continue
        counts["exact_xc90"] += int(s == "XC90")
        counts["prefix_xc90_token"] += int(bool(PREFIX_XC90.search(s)))
        counts["anywhere_xc90_token"] += int(bool(TOKEN_XC90.search(s)))
        counts["anywhere_xc90_substring"] += int("XC90" in s)
        counts["anywhere_xc_space_90_token"] += int(bool(SPACED_XC90.search(s)))
        counts["anywhere_xc_hyphen_90_token"] += int(bool(HYPHEN_XC90.search(s)))
    if not (counts["exact_xc90"] <= counts["prefix_xc90_token"]
            <= counts["anywhere_xc90_token"]
            <= counts["anywhere_xc90_substring"] <= len(descriptions)):
        raise SchemaError("inconsistent XC90 shape categories")
    return counts


def audit(folder: Path) -> dict:
    if not folder.is_dir() or folder.is_symlink():
        raise SchemaError("unsafe owner-private offline directory")
    path = folder / "BaseData.sqlite"
    if path.is_symlink() or not path.is_file():
        raise SchemaError("missing original SQLite copy")
    if any(Path(str(path) + ext).exists() for ext in ("-wal", "-shm", "-journal")):
        raise SchemaError("uncheckpointed offline export")
    uri = path.resolve().as_uri() + "?mode=ro&immutable=1"
    with closing(sqlite3.connect(uri, uri=True, timeout=5)) as db:
        db.execute("PRAGMA query_only=ON")
        started = time.monotonic()
        db.set_progress_handler(
            lambda: int(time.monotonic() - started >= MAX_RUN_SECONDS),
            20000,
        )
        catalog = _catalog(db, "BaseData")
        if "description" not in catalog["VehicleModel"]["cols"]:
            raise SchemaError("missing exporter description inventory")
        if catalog["VehicleModel"]["rows"] > MAX_MODEL_ROWS:
            raise SchemaError("unbounded original model lookup table")
        tables = _physical(db, catalog, REQUIRED)
        rows = db.execute(
            "SELECT \"Description\" FROM " + tables["VehicleModel"] +
            " LIMIT " + str(MAX_MODEL_ROWS + 1)
        ).fetchall()
        if len(rows) != catalog["VehicleModel"]["rows"]:
            raise SchemaError("source and catalog row count differs")
        counts = _summarize_descriptions(rows)
        return {
            "schema_version": "virtualcar-vida-basedata-model-label-classes-v1",
            "status": "original_model_description_categories_only",
            "source": "owner_private_immutable_basedata_export",
            "source_rows_read": True,
            "source_writes_performed": False,
            "vehicle_model_table_rows_checked": len(rows),
            "description_counts": counts,
            "categories_can_overlap": True,
            "original_model_labels_or_ids_exported": False,
            "model_identity_resolved": False,
            "cross_database_profile_mapping_verified": False,
            "original_selection_of_43_reconstructed": False,
            "original_vida_readvin_accepted": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Owner-only VIDA model labels category preflight")
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), sort_keys=True, indent=2))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
