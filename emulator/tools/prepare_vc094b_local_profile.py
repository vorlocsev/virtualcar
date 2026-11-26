"""Owner-local XC90 V8 package preparation. Never publish or register it."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "cem529_config"))
from vc059 import FILES, outside_checkout
from vc0591 import PINS
from vc0592 import Editor, strict_json
from vc0594 import IdentityGate, TOPOLOGY_SHA
from audit_vc090d_readvin_evidence import read_frozen

MAX_INPUT = 32 * 1024 * 1024
PROFILE_ID = "xc90-v8-2009"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def checked_inputs(folder):
    outside_checkout(folder)
    raw = {k: read_frozen(folder / name, MAX_INPUT) for k, name in FILES.items()}
    for key, expected in PINS.items():
        if digest(raw[key]) != expected:
            raise ValueError("pinned_input_mismatch")
    if digest(raw["topology"]) != TOPOLOGY_SHA:
        raise ValueError("topology_mismatch")
    gate = IdentityGate(Editor(strict_json(raw["store"]), [raw[k] for k in PINS]), raw["topology"])
    audit = gate.audit(gate.editor.draft([]))
    if audit["status"] != "pass" or audit["configured_routes"] != 8 or audit["locked_fields"] != 12:
        raise ValueError("baseline_gate")
    rows = []
    options = []
    for offset, base in sorted(gate.editor.rows.items()):
        info = gate.editor.options(offset)
        rows.append({"offset": offset, "name": info["name"], "value": base["as_text"], "locked": info["locked"]})
        options.append({"offset": offset, "baseline_code": info["baseline_code"],
                        "choices": [{"code": item["code"], "text": item["as_text"]}
                                    for item in info["options"] if item["selectable"]
                                    and item["code"] != info["baseline_code"]]})
    if len(rows) != 127 or sum(r["locked"] for r in rows) != 12:
        raise ValueError("baseline_row_count")
    return raw, rows, options


def prepare(private_dir, package):
    private_dir, package = Path(private_dir), Path(package)
    if not private_dir.is_absolute() or not package.is_absolute():
        raise ValueError("absolute_paths_required")
    outside_checkout(package)
    if not (package / "VirtualCar.exe").is_file():
        raise ValueError("missing_package")
    for path in (private_dir, package, package / "vehicle-data", *package.parents, *private_dir.parents):
        info = path.lstat()
        if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("reparse_path")
    if private_dir.resolve() == package.resolve() or package.resolve() in private_dir.resolve().parents:
        raise ValueError("original_inputs_inside_package")
    raw, rows, options = checked_inputs(private_dir)
    if len(raw["ini"]) > 1024 * 1024:
        raise ValueError("profile_size")
    base = package / "vehicle-data" / "p2"
    dll = read_frozen(base / "VirtualCarJ2534.dll", 64 * 1024 * 1024)
    declared = read_frozen(base / "candidate.sha256", 128).decode("ascii").strip()
    if digest(dll) != declared.lower():
        raise ValueError("candidate_mismatch")
    # Copy only the reviewed read-only simulator baseline and the display catalog.
    # Do not duplicate original research reports, raw dictionaries or VIDA files.
    catalog = json.dumps({"schema": "vc094b-cem-baseline-v1", "rows": rows},
                         ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    editor = json.dumps({"schema": "vc094d-cem-options-v1", "rows": options},
                        ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(catalog) > 1024 * 1024 or len(editor) > 4 * 1024 * 1024:
        raise ValueError("catalog_size")
    for key, name in FILES.items():
        if read_frozen(private_dir / name, MAX_INPUT) != raw[key]:
            raise ValueError("source_changed")
    target = package / "vehicle-data" / PROFILE_ID
    target.mkdir(exist_ok=False)
    files = {"virtualcar.ini": raw["ini"], "VirtualCarJ2534.dll": dll,
             "candidate.sha256": declared.lower().encode("ascii"), "configuration.json": catalog,
             "configuration-options.json": editor}
    # Manifest last: partial writes never qualify as a usable installed profile.
    for name, data in files.items():
        with (target / name).open("xb") as stream:
            stream.write(data)
    manifest = {"schema": "vc094d-local-profile-v2", "profile_sha256": digest(raw["ini"]),
                "native_sha256": digest(dll), "catalog_sha256": digest(catalog),
                "options_sha256": digest(editor)}
    with (target / "local-profile.json").open("xb") as stream:
        stream.write(json.dumps(manifest, sort_keys=True).encode("ascii"))
    return manifest


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-dir", type=Path, required=True)
    p.add_argument("--package", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        prepare(a.private_dir, a.package)
    except (OSError, ValueError, KeyError, TypeError, OverflowError, RecursionError):
        p.exit(2, "VC094B_LOCAL_PROFILE=REJECTED\n")
    print("VC094B_LOCAL_PROFILE=PREPARED_127_ROWS_12_LOCKED_8_ROUTES")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
