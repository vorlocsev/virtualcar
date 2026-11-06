#!/usr/bin/env python3
"""Read-only structural audit of minimal VIDA Script/ProfileMap/ScriptContent CSV.

Only counts and booleans leave the process; no profile ID, script ID, VIN,
SQL contents, user names, paths, or source row values are reported.
This does not establish which script VIDA actually ran.
"""
import argparse
import csv
import json
from pathlib import Path
import re

SCHEMA = "virtualcar-vida-script-profile-links-v1"
MAX_FILE = 4 * 1024 * 1024
MAX_ROWS = 100000
FIELDS = {
    "Script.csv": ("id",),
    "ScriptProfileMap.csv": ("fkProfile", "fkScript"),
    "ScriptContent.csv": ("fkScript", "fkLanguage"),
}
IDENTIFIER = re.compile(r"[A-Za-z0-9_\-]{1,80}\Z")


def _read_table(directory, basename):
    path = directory / basename
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_FILE:
        raise ValueError("invalid table source")
    with path.open("r", encoding="utf-8-sig", errors="strict", newline="") as stream:
        reader = csv.DictReader(stream)
        expected = FIELDS[basename]
        if reader.fieldnames != list(expected):
            raise ValueError("unexpected metadata headers")
        output = []
        for row in reader:
            if len(output) >= MAX_ROWS or None in row:
                raise ValueError("excessive or malformed metadata rows")
            entry = tuple(row[key] for key in expected)
            if not all(isinstance(val, str) and IDENTIFIER.fullmatch(val) for val in entry):
                raise ValueError("invalid metadata value")
            output.append(entry)
    return output


def audit(directory, profile_key=None):
    directory = Path(directory)
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("expected existing metadata directory")
    if profile_key is not None and not IDENTIFIER.fullmatch(profile_key):
        raise ValueError("invalid local profile selector")
    tables = {name: _read_table(directory, name) for name in FIELDS}
    script_rows = tables["Script.csv"]
    mappings = tables["ScriptProfileMap.csv"]
    contents = tables["ScriptContent.csv"]
    script_ids = {row[0] for row in script_rows}
    map_unique = set(mappings)
    content_unique = set(contents)
    profiles = {row[0] for row in mappings}
    orphan_map = sum(script not in script_ids for profile, script in mappings)
    orphan_content = sum(script not in script_ids for script, language in contents)
    chosen_mappings = {(p, s) for p, s in map_unique if p == profile_key} if profile_key is not None else set()
    chosen_ids = {s for _, s in chosen_mappings}
    content_script_ids = {s for s, lang in content_unique}
    selected = None
    if profile_key is not None:
        selected = {
            "selector_has_profile_mapping": profile_key in profiles,
            "mapped_script_count": len(chosen_ids),
            "mapped_script_rows_missing_from_script_table": len(chosen_ids - script_ids),
            "mapped_scripts_with_any_content": len(chosen_ids & content_script_ids),
            "mapped_scripts_without_content": len(chosen_ids - content_script_ids),
            "mapped_content_language_variants": sum(s in chosen_ids for s, lang in content_unique),
            "distinct_content_languages": len({lang for s, lang in content_unique if s in chosen_ids}),
        }
    return {
        "schema_version": SCHEMA,
        "evidence_kind": "offline_schema_linkage_only",
        "metadata_rows": {
            "scripts": len(script_rows),
            "profile_map": len(mappings),
            "script_content_languages": len(contents),
        },
        "profile_count_from_mappings": len(profiles),
        "duplicate_rows": {
            "script_primary_key": len(script_rows) - len(script_ids),
            "profile_map_pairs": len(mappings) - len(map_unique),
            "script_content_language_pairs": len(contents) - len(content_unique),
        },
        "orphan_foreign_key_rows": {
            "profile_map_script_missing": orphan_map,
            "script_content_script_missing": orphan_content,
        },
        "selected_profile": selected,
        "language_values_are_not_decoded": True,
        "source_sql_schema_verified_for_vida_2015a": False,
        "runtime_selected_identity_script_verified": False,
        "b9fb_to_vin_mapping_verified": False,
        "xc90_v8_my2009_verified": False,
        "sectorv_vida_acceptance_verified": False,
        "replay_approved": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private VIDA exported metadata links audit")
    parser.add_argument("input_dir", type=Path, help="Directory containing exactly named minimal CSV exports")
    parser.add_argument("--profile-key", help="Optional private profile identifier used only for local filtering")
    parser.add_argument("--output", type=Path, required=True, help="New safe JSON report; never overwrite")
    args = parser.parse_args(argv)
    if args.output.resolve() == args.input_dir.resolve():
        parser.error("output must be separate")
    try:
        output = audit(args.input_dir, args.profile_key)
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        parser.error("invalid local metadata: " + type(exc).__name__)
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(output, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
    except OSError as exc:
        parser.error("cannot create exclusive output: " + type(exc).__name__)
    print("VIDA script links counted; script selection and VIN unverified")


if __name__ == "__main__":
    main()
