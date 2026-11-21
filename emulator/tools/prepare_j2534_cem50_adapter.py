#!/usr/bin/env python3
"""Stage an isolated J2534 CEM50/B9FB laboratory adapter from development.

The real owner VIN stays in a local vehicle-identity.json and new virtualcar.ini.
No ECU code, J2534 registry, installed VIDA or vehicle is changed here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import sys
import tempfile

from build_synthetic_cem_b9fb_profile import PUBLIC_TEMPLATE, build_profile
from audit_vida_b3a54_private_b9fb_vin import (
    _get, _ini, _read_b9fb, _read_identity_file,
)

ADAPTER_NAME = "J2534 CEM50 B9FB"
DLL_NAME = "VirtualCarJ2534.dll"  # Internal file name; never the adapter display name.
SCHEMA = "j2534-cem50-isolated-lab-v1"
SOURCE_BASIS = "9553d87d400f9baf80fa16fb4a30d163551a6bbb"
MAX_DLL = 20 * 1024 * 1024


def verify_pe32(blob: bytes) -> None:
    """Check PE32/x86 identity, not code authenticity or operational compatibility."""
    if len(blob) < 512 or blob[:2] != b"MZ":
        raise ValueError("not_pe")
    offset = struct.unpack_from("<I", blob, 0x3C)[0]
    if offset < 0x40 or offset + 26 > len(blob):
        raise ValueError("invalid_pe_offset")
    if blob[offset:offset + 4] != b"PE\x00\x00":
        raise ValueError("missing_pe_signature")
    machine = struct.unpack_from("<H", blob, offset + 4)[0]
    magic = struct.unpack_from("<H", blob, offset + 24)[0]
    if machine != 0x014C or magic != 0x010B:
        raise ValueError("not_x86_pe32")


def stage(dll: Path, identity: Path, output: Path, expected_sha256: str) -> dict:
    """Create a new, non-overwriting directory containing DLL/INI/installer."""
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256):
        raise ValueError("full_dll_sha256_required")
    root = Path(__file__).resolve().parents[2]
    output = output.absolute()
    if (output.exists() or output.is_symlink() or output == root
            or root in output.parents or not output.parent.is_dir()
            or output.parent.is_symlink()):
        raise ValueError("unsafe_output_directory")
    if (dll.is_symlink() or not dll.is_file() or dll.suffix.casefold() != ".dll"
            or dll.stat().st_size > MAX_DLL):
        raise ValueError("invalid_source_dll")
    dll_bytes = dll.read_bytes()
    verify_pe32(dll_bytes)
    digest = hashlib.sha256(dll_bytes).hexdigest()
    if digest != expected_sha256.lower():
        raise ValueError("dll_sha256_mismatch")
    identity_json = _read_identity_file(identity)
    template = PUBLIC_TEMPLATE.read_text(encoding="utf-8-sig")
    profile = build_profile(template, identity_json)
    config = _ini(profile)
    status, count, frames = _read_b9fb(config)
    if (status != "declared_frame_values_loaded_locally" or count != 13
            or frames is None or
            _get(config, "Vehicle", "ModelYear") != "2009" or
            _get(config, "P2", "StrictRouting") != "1" or
            _get(config, "D2_50", "ResponseId") != "01200003" or
            _get(config, "D2_40", "B9FBFrameCount") != "0"):
        raise ValueError("invalid_generated_cem50_profile")
    # Explicitly compare VIN in the 13 CAN D2 frames against Vehicle.VIN.
    stream = b"".join(frame[1:] for _, frame in frames)
    if stream[:3] != bytes.fromhex("50 F9 FB") or (
            stream[14:31] != _get(config, "Vehicle", "VIN").encode("ascii")):
        raise ValueError("cem50_vin_mismatch")
    installer = root / "emulator" / "scripts" / "install_j2534_cem50_adapter.ps1"
    if not installer.is_file():
        raise ValueError("missing_registration_script")
    tmp = Path(tempfile.mkdtemp(prefix=".cem50-stage-", dir=output.parent))
    try:
        (tmp / DLL_NAME).write_bytes(dll_bytes)
        (tmp / "virtualcar.ini").write_text(profile, encoding="utf-8", newline="\n")
        shutil.copyfile(installer, tmp / installer.name)
        manifest = {
            "schema_version": SCHEMA,
            "adapter_display_name": ADAPTER_NAME,
            "dll_file": DLL_NAME,
            "dll_sha256": digest,
            "source_basis_development_sha": SOURCE_BASIS,
            "binary_built_from_source_basis_verified": False,
            "cem_target": "0x50",
            "d2_b9fb_frame_count": 13,
            "vehicle_vin_equals_b9fb_vin": True,
            "vin_value_in_manifest": False,
            "replay_provenance": "synthetic_2005_donor_shape_not_oem_my2009",
            "original_vida_readvin_verified": False,
            "ecu_identification_verified": False,
            "registration_applied": False,
        }
        (tmp / "adapter_manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8")
        tmp.rename(output)
        return manifest
    finally:
        if tmp.exists():
            shutil.rmtree(tmp)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dll", type=Path, required=True,
                        help="Explicit trusted x86 J2534 DLL (never an installed physical driver)")
    parser.add_argument("--expected-dll-sha256", required=True,
                        help="Complete SHA256 of that DLL, obtained independently")
    parser.add_argument("--identity-json", type=Path, required=True,
                        help="Existing private vehicle-identity.json containing VIN + ModelYear=2009")
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="New directory outside repository; must not exist")
    args = parser.parse_args(argv)
    try:
        stage(args.dll, args.identity_json, args.output_dir,
              args.expected_dll_sha256)
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError) as exc:
        print("CEM50_ADAPTER: REJECTED (" + type(exc).__name__ + ")", file=sys.stderr)
        return 2
    print("CEM50_ADAPTER: STAGED_NOT_REGISTERED")
    print("CEM50/B9FB: 13 synthetic D2 frames, owner VIN matches Vehicle.VIN")
    print("VIDA ReadVin / ECU identification: NOT_VERIFIED")
    print("No registry, installed VIDA, active J2534 provider or vehicle changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
