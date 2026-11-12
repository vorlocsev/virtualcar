#!/usr/bin/env python3
"""B3A51: read-only source-backed VIN vs D2 B9FB readiness audit.

Reads an explicitly supplied local virtualcar.ini. Prints categorical, non-
identifying results only. This is a snapshot of the file at audit time, NOT
proof this was the configuration loaded by original VIDA or the native DLL.
No VIN, frame, path, process identity, or private hash is exported.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
import sys

SCHEMA = "virtualcar-b3a51-vin-d2-readiness-v1"
MAX_INI_BYTES = 512 * 1024
MAX_D2_FRAMES = 64
INT = re.compile(r"(?:0[xX][0-9A-Fa-f]+|[0-9]+)\Z")
TARGETS = {"CEM_40": ("D2_40", 125000), "CEM_50": ("D2_50", 500000)}


def _native_num(value, fallback):
    """Mirror native parse_num decimal or 0x hexadecimal, with invalid fallback."""
    if not isinstance(value, str) or not INT.fullmatch(value):
        return fallback
    n = int(value[2:], 16) if value.lower().startswith("0x") else int(value, 10)
    return n & 0xFFFFFFFF


def _get(ini, section, key, fallback=None):
    return ini.get(section, key, fallback=fallback) if ini.has_section(section) else fallback


def inspect_ini(text):
    """Inspect one INI text without returning or printing any private data."""
    if not isinstance(text, str) or len(text) > MAX_INI_BYTES:
        raise ValueError("invalid bounded text")
    ini = configparser.ConfigParser(interpolation=None, strict=True)
    ini.read_string(text)
    vin = _get(ini, "Vehicle", "VIN")
    # The C code has a baked-in 17-character fallback and copies a configured
    # value only when strlen(value) == 17. This is not OEM VIN validation.
    origin = "native_fallback" if vin is None else "explicit_ini"
    vin_shape = ("native_fallback_not_identity_proof" if vin is None else
                 "ascii_17_character_only" if vin.isascii() and len(vin) == 17 else
                 "not_ascii_17")
    strict_setting = _get(ini, "P2", "StrictRouting", "0")
    strict = _native_num(strict_setting, 0) != 0
    out = {
        "schema_version": SCHEMA,
        "source_scope": "current_explicit_ini_snapshot_not_runtime_attribution",
        "vin_origin": origin,
        "vin_shape": vin_shape,
        "d2_b9fb": {},
        "strict_routing": "enabled" if strict else "disabled",
        "readvin_via_d2_verified": False,
        "genuine_ecu_fixture_origin_verified": False,
        "original_vida_vin_acceptance_verified": False,
    }
    for label, (section, baud) in TARGETS.items():
        raw_count = _get(ini, section, "FrameCount")
        if raw_count is None or raw_count == "":
            raw_count = _get(ini, section, "B9FBFrameCount", "0")
        count = _native_num(raw_count, 0)
        count = count if 0 <= count <= MAX_D2_FRAMES else 0
        missing = 0
        for index in range(count):
            key = f"{index:X}"
            first = _get(ini, section, f"B9FBFrame{key}")
            second = _get(ini, section, f"Frame{key}")
            if not first and not second:
                missing += 1
        status = ("none_declared" if not count else
                  "missing_frame_entries" if missing else
                  "declared_frames_not_validated")
        out["d2_b9fb"][label] = {
            "base_fixture_baud_bps": baud,
            "declared_frame_count": count,
            "missing_declared_frame_entries": missing,
            "static_fixture_status": status,
            "frames_usable_by_native_verified": False,
            "oem_origin_verified": False,
        }
    out["limitations"] = [
        "A configured 17-character VIN is not a Volvo D2 B9FB reply.",
        "Declared frame keys are not validated D2 transport, checksum or OEM provenance.",
        "Native config may have been changed after the previously saved VIDA run.",
        "StrictRouting disabled still cannot create missing response frames.",
        "Base CEM_40 125k and CEM_50 500k are emulator fixture expectations, not MY2009 truth.",
    ]
    return out


def evaluate_requests(audit, requested_modes):
    """Classify B3A50 categorical request modes under CURRENT INI assumptions."""
    if audit.get("schema_version") != SCHEMA:
        raise ValueError("unknown B3A51 report")
    if type(requested_modes) is not list or len(requested_modes) > 32:
        raise ValueError("invalid mode list")
    results = []
    for row in requested_modes:
        if (type(row) is not dict or set(row) !=
                {"target", "command", "baud_bps", "count"}
                or row["target"] not in TARGETS
                or row["command"] != "B9FB"
                or type(row["count"]) is not int or not 1 <= row["count"] <= 1000
                or row["baud_bps"] not in {"125000", "250000", "500000", "other"}):
            raise ValueError("invalid request mode")
        fixture = audit["d2_b9fb"][row["target"]]
        mismatch = (row["baud_bps"] != str(fixture["base_fixture_baud_bps"]))
        if audit["strict_routing"] == "enabled" and mismatch:
            label = "strict_route_mismatch_under_current_ini"
        elif fixture["static_fixture_status"] == "none_declared":
            label = "no_declared_b9fb_fixture"
        elif fixture["static_fixture_status"] == "missing_frame_entries":
            label = "declared_b9fb_incomplete"
        else:
            label = "candidate_unverified_not_oem_rx"
        results.append({
            "target": row["target"], "command": "B9FB",
            "baud_bps": row["baud_bps"], "requests": row["count"],
            "static_classification": label,
            "genuine_vida_rx_verified": False,
        })
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ini", required=True, type=Path,
                   help="explicit local virtualcar.ini, never uploaded")
    args = p.parse_args(argv)
    try:
        if (args.ini.is_symlink() or args.ini.name.lower() != "virtualcar.ini" or
                not args.ini.is_file() or args.ini.stat().st_size > MAX_INI_BYTES):
            raise ValueError("invalid local INI")
        data = inspect_ini(args.ini.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError, configparser.Error):
        # Never print secret-bearing parse errors or private file paths.
        print("B3A51: PRIVATE_INI_INVALID_OR_UNREADABLE", file=sys.stderr)
        return 2
    print("B3A51: STATIC_VIN_AND_D2_READINESS_AUDITED")
    print("VIN shape:", data["vin_shape"])
    print("VIN origin:", data["vin_origin"])
    print("StrictRouting:", data["strict_routing"])
    print("B9FB fixture declaration:", json.dumps(data["d2_b9fb"], sort_keys=True))
    print("Original VIDA VIN acceptance / authentic OEM CEM B9FB: NOT_VERIFIED")
    print("INI read-only; source contents and private path not printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
