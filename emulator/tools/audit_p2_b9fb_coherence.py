#!/usr/bin/env python3
"""Audit INTERNAL consistency of the *known donor* P2 CEM B9FB layout.

The source profile must be a local synthetic/lab INI. This tool checks
transport and fixed offsets observed in one published 13-frame example;
it does NOT declare those offsets universal for XC90 V8 MY2009.

It does not output VIN, chassis digits, CAN bytes, hardware identifiers,
profile paths or arbitrary source strings. No source file is modified.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
import sys

from import_p2_trace import validate_response

FORMAT = "virtualcar-p2-b9fb-identity-coherence-v1"
MAX_BYTES = 65536
CONTROL = (0x8F, 9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F)
BREAKS = (9, 28, 39, 44, 52, 56, 64, 86)
YEAR_CODES = "123456789ABCDEFGHJKLMNPRSTVWXY"
VIN_RE = re.compile(rb"[A-HJ-NPR-Z0-9]{17}\Z")
HEX_BYTE = re.compile(r"[0-9A-Fa-f]{2}")
FRAME_KEY = re.compile(r"b9fbframe(?:[0-9a-f]+)\Z")
PROVENANCE_PREFIX = "historical_public_"


def _year_code(year):
    if type(year) is not int or not 2001 <= year <= 2030:
        raise ValueError("year_outside_audited_range")
    return YEAR_CODES[year - 2001]


def _check_code(value):
    if value is None:
        return None
    if type(value) is not str or not re.fullmatch(r"[0-9]{3}", value):
        raise ValueError("invalid_expected_type_code")
    return value.encode("ascii")


def _optional_vin_text(value):
    if value is None:
        return None
    if type(value) is not str or len(value) != 17:
        return None
    try:
        return value.encode("ascii")
    except UnicodeEncodeError:
        return None


def audit(source, expected_year=None, expected_type_code=None):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("profile_source_too_large")
    if expected_year is not None:
        _year_code(expected_year)
    expected_type = _check_code(expected_type_code)

    profile = configparser.ConfigParser(strict=True, interpolation=None)
    try:
        profile.read_string(source)
    except configparser.Error as exc:
        raise ValueError("invalid_profile_ini") from exc
    if len(profile.sections()) > 128:
        raise ValueError("too_many_profile_sections")
    if not profile.has_section("D2_50"):
        raise ValueError("missing_d2_50_fixture")
    section = profile["D2_50"]
    text_count = section.get("B9FBFrameCount")
    if text_count is None or not re.fullmatch(r"[0-9]{1,2}", text_count):
        raise ValueError("invalid_b9fb_count")
    count = int(text_count)
    if not 1 <= count <= 64:
        raise ValueError("unsupported_b9fb_count")
    can_raw = section.get("ResponseId")
    if can_raw is None or not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]{1,8}", can_raw):
        raise ValueError("invalid_d2_response_id")
    can_id = int(can_raw, 16)
    if not 0 < can_id <= 0x1FFFFFFF:
        raise ValueError("nonextended_can_response_id")
    keys = {key for key in section if FRAME_KEY.fullmatch(key)}
    want = {"b9fbframe" + format(i, "x") for i in range(count)}
    if keys != want:
        raise ValueError("missing_or_extra_b9fb_frame")

    frames = []
    for i in range(count):
        raw = section["B9FBFrame" + format(i, "X")].strip()
        parts = raw.split()
        if len(parts) != 8 or any(HEX_BYTE.fullmatch(p) is None for p in parts):
            raise ValueError("invalid_b9fb_frame_bytes")
        frames.append((can_id, bytes(int(v, 16) for v in parts)))
    validate_response(frames, 0x50, 0xFB)
    full = b"".join(payload[1:] for _, payload in frames)
    if not full.startswith(b"\x50\xF9\xFB"):
        raise ValueError("nonpositive_b9fb_echo")
    body = full[3:]
    breaks = tuple(i for i in range(len(body) - 1)
                   if body[i:i + 2] == b"\r\n")
    donor_footprint = (
        len(frames) == 13
        and can_id == 0x01200003
        and tuple(f[1][0] for f in frames) == CONTROL
        and len(body) == 88
        and body[:2] == b"\x57\x00"
        and breaks == BREAKS
    )
    result = {
        "format": FORMAT,
        "read_only": True,
        "contains_payload_data": False,
        "transport_framing_valid": True,
        "positive_b9fb_echo": True,
        "response_frames": len(frames),
        "post_echo_bytes": len(body),
        "known_donor_13frame_layout_matched": donor_footprint,
        "fixture_declares_historical_public_provenance": (
            profile.get("P2", "FixtureProvenance", fallback="")
            .startswith(PROVENANCE_PREFIX)),
        "embedded_vin_shape": "not_interpreted",
        "configured_vin_matches_embedded": None,
        "candidate_chassis_suffix_matches_embedded_vin": None,
        "declared_model_year_matches_vin_code": None,
        "expected_model_year_matches_vin_code": None,
        "candidate_type_code_matches_supplied_expectation": None,
        "possible_profile_inconsistencies": [],
        "schema_semantics_verified": False,
        "app_integrity_or_checksum_verified": False,
        "sectorv_vin_acceptance_verified": False,
        "xc90_v8_my2009_identity_verified": False,
        "limitations": [
            "Fixed offsets apply only to the recognized historical 13-frame donor footprint.",
            "The six-digit chassis and three-digit type positions are candidate fields, not an OEM schema.",
            "A matching VIN or expected type code does not authenticate any ECU or vehicle.",
            "The tenth VIN character is interpreted only for supplied years 2001-2030; other cycles are not inferred.",
            "No application-level checksum or client parse decision is available.",
            "No VIN, chassis, part number, raw CAN payload or private path is exported.",
        ],
    }
    if not donor_footprint:
        return result
    mask = body[11:28]
    if mask == b"X" * 17:
        result["embedded_vin_shape"] = "redacted_mask"
        return result
    if not VIN_RE.fullmatch(mask):
        result["embedded_vin_shape"] = "not_valid_vin_characters"
        result["possible_profile_inconsistencies"].append("donor_offset_11_vin_syntax")
        return result
    result["embedded_vin_shape"] = "17_ascii_vin_characters"
    configured = _optional_vin_text(profile.get("Vehicle", "VIN", fallback=None))
    if configured is not None:
        matches = configured == mask
        result["configured_vin_matches_embedded"] = matches
        if not matches:
            result["possible_profile_inconsistencies"].append("configured_vin_differs_from_b9fb")
    suffix = body[46:52]
    if re.fullmatch(rb"[0-9]{6}\Z", suffix):
        matches = mask[-6:] == suffix
        result["candidate_chassis_suffix_matches_embedded_vin"] = matches
        if not matches:
            result["possible_profile_inconsistencies"].append("donor_chassis_candidate_differs_from_vin")
    raw_year = profile.get("Vehicle", "ModelYear", fallback=None)
    if raw_year is not None and re.fullmatch(r"[0-9]{4}", raw_year):
        model_year = int(raw_year)
        if 2001 <= model_year <= 2030:
            matches = mask[9:10] == _year_code(model_year).encode("ascii")
            result["declared_model_year_matches_vin_code"] = matches
            if not matches:
                result["possible_profile_inconsistencies"].append("declared_model_year_differs_from_vin_code")
    if expected_year is not None:
        matches = mask[9:10] == _year_code(expected_year).encode("ascii")
        result["expected_model_year_matches_vin_code"] = matches
        if not matches:
            result["possible_profile_inconsistencies"].append("supplied_expected_year_differs_from_vin_code")
    if expected_type is not None and re.fullmatch(rb"[0-9]{3}\Z", body[41:44]):
        matches = body[41:44] == expected_type
        result["candidate_type_code_matches_supplied_expectation"] = matches
        if not matches:
            result["possible_profile_inconsistencies"].append("donor_type_candidate_differs_from_expectation")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile", type=Path, help="Private/local P2 laboratory INI")
    p.add_argument("--expected-year", type=int)
    p.add_argument("--expected-type-code")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if args.profile.resolve() == args.output.resolve():
            raise ValueError("same_source_and_output")
        if args.profile.stat().st_size > MAX_BYTES:
            raise ValueError("too_many_source_bytes")
        report = audit(
            args.profile.read_text(encoding="utf-8-sig"),
            expected_year=args.expected_year,
            expected_type_code=args.expected_type_code)
        with args.output.open("x", encoding="utf-8") as fp:
            json.dump(report, fp, indent=2, ensure_ascii=False, sort_keys=True)
            fp.write("\n")
    except (OSError, UnicodeError, ValueError, TypeError):
        print("B9FB identity coherence audit rejected source/output; private data withheld",
              file=sys.stderr)
        return 2
    print("PASS: donor-layout internal consistency audited; ECU/client identity unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
