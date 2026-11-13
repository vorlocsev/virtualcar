#!/usr/bin/env python3
"""B3A58: opt-in canonical synthetic CEM B9FB profile for isolated Virtual Car.

Reuses the committed synthetic 13-frame donor, replacing only its 17-byte
observed VIN-shaped field with an owner-private VIN. This is NOT an OEM dump,
a successful VIDA ReadVin, or permission to modify a vehicle.
"""
import argparse
import configparser
import io
import json
import os
from pathlib import Path
import sys

from audit_p2_b9fb_shape import audit_frames
from audit_vida_b3a54_private_b9fb_vin import (
    _get, _identity_json, _ini, _read_b9fb, _read_identity_file, VIN_SHAPE,
)

PUBLIC_TEMPLATE = Path(__file__).resolve().parents[1] / "virtualcar-p2-b9fb-lab-vin.ini"
CANONICAL_PROVENANCE = "synthetic_canonical_b9fb_v1_from_public_2005_donor"
MAX_TEMPLATE_BYTES = 512 * 1024


def build_profile(template_text, identity_json_text):
    """Produce a private INI without returning identity, frames or paths in reports."""
    cfg = _ini(template_text)
    state, new_vin, year, _location = _identity_json(identity_json_text)
    if (state != "valid_17_ascii_shape_not_oem_validated"
            or new_vin is None or year != "declares_my2009"):
        raise ValueError("private_vin_or_model_year_not_usable")
    original_vin = _get(cfg, "Vehicle", "VIN", "")
    if not VIN_SHAPE.fullmatch(original_vin):
        raise ValueError("not_a_known_synthetic_template")
    if _get(cfg, "D2_50", "FrameCount") is not None:
        raise ValueError("ambiguous_native_framecount_precedence")
    if _get(cfg, "D2_50", "B9FBFrameCount") != "13":
        raise ValueError("not_13_frame_template")
    if _get(cfg, "P2", "StrictRouting") != "1":
        raise ValueError("unexpected_routing")
    for section in ("D2_40",):
        if _get(cfg, section, "B9FBFrameCount", "0") != "0":
            raise ValueError("unverified_extra_cem_fixture")
    for section in ("D2_40_B9F0", "D2_50_B9F0", "D2_40_B9FC", "D2_50_B9FC"):
        if _get(cfg, section, "FrameCount", "0") != "0":
            raise ValueError("unverified_extra_cem_fixture")

    status, count, frames = _read_b9fb(cfg)
    if status != "declared_frame_values_loaded_locally" or count != 13 or frames is None:
        raise ValueError("invalid_b9fb_transport")
    audit = audit_frames(frames, target=0x50)
    if (audit["transport"] != "complete" or
            audit["published_88_byte_shape"] != "matches_one_observed_example" or
            not audit["vin_shaped_field"]):
        raise ValueError("unsupported_synthetic_b9fb_shape")

    original = b"".join(frame[1:] for _can_id, frame in frames)
    vin_begin, vin_end = 3 + 11, 3 + 28
    if (len(original) != 91 or original[:3] != bytes.fromhex("50 F9 FB") or
            original[vin_begin:vin_end] != original_vin.encode("ascii")):
        raise ValueError("template_vin_does_not_match_frames")

    patched = original[:vin_begin] + new_vin.encode("ascii") + original[vin_end:]
    assert len(patched) == 91
    for index, (_can_id, original_frame) in enumerate(frames):
        replacement = bytes((original_frame[0],)) + patched[index * 7:(index + 1) * 7]
        cfg.set("D2_50", f"B9FBFrame{index:X}", replacement.hex(" ").upper())

    cfg.set("Vehicle", "VIN", new_vin)
    cfg.set("Vehicle", "ModelYear", "2009")
    cfg.set("P2", "FixtureProvenance", CANONICAL_PROVENANCE)
    cfg.set("P2", "FixtureAuthority", "virtual_cem_reference_not_oem_capture")

    updated_status, updated_count, updated_frames = _read_b9fb(cfg)
    updated_audit = audit_frames(updated_frames, target=0x50) if updated_frames else {}
    if (updated_status != "declared_frame_values_loaded_locally" or
            updated_count != 13 or updated_audit.get("transport") != "complete" or
            updated_audit.get("published_88_byte_shape") !=
            "matches_one_observed_example" or
            b"".join(row[1][1:] for row in updated_frames)[vin_begin:vin_end] !=
            new_vin.encode("ascii")):
        raise ValueError("generated_profile_failed_validation")

    stream = io.StringIO()
    stream.write("; VIRTUAL CAR SYNTHETIC REFERENCE; NOT AN OEM CEM CAPTURE\n")
    stream.write("; Owner-private VIN. Do not upload to GitHub or share.\n\n")
    cfg.write(stream, space_around_delimiters=True)
    return stream.getvalue()


def write_exclusive(path, content):
    """Explicit local-only output; never silently replace an active INI."""
    if path.suffix.casefold() != ".ini" or not path.parent.is_dir():
        raise ValueError("explicit_existing_output_directory_required")
    descriptor = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
    except BaseException:
        try:
            path.unlink()
        except OSError:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-json", required=True, type=Path,
                        help="local owner-private vehicle-identity.json")
    parser.add_argument("--output", required=True, type=Path,
                        help="NEW output .ini; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        if (PUBLIC_TEMPLATE.is_symlink() or not PUBLIC_TEMPLATE.is_file() or
                PUBLIC_TEMPLATE.stat().st_size > MAX_TEMPLATE_BYTES):
            raise ValueError("invalid_public_template")
        template_text = PUBLIC_TEMPLATE.read_text(encoding="utf-8-sig")
        identity = _read_identity_file(args.identity_json)
        private_ini = build_profile(template_text, identity)
        write_exclusive(args.output, private_ini)
    except (OSError, ValueError, UnicodeError, configparser.Error, json.JSONDecodeError):
        print("B3A58: REJECTED; no private identity or frames disclosed", file=sys.stderr)
        return 2
    print("B3A58: CREATED_NEW_PRIVATE_SYNTHETIC_CEM_INI")
    print("D2_50 B9FB: 13 framed messages, structural validation passed")
    print("Original VIDA ReadVin and OEM provenance: NOT_VERIFIED")
    print("No active profile replaced, hardware or VIDA contacted, or identity printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
