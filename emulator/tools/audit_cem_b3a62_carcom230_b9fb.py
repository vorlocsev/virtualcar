#!/usr/bin/env python3
"""Read-only CarCom 230 vs published synthetic D2_50 B9FB frame comparison.

The source is an explicitly chosen INI. No ECU, VIN, J2534, VIDA, registry,
or installed-profile mutation. Never export INI paths, VIN or raw frames.
"""
import argparse
import configparser
import json
from pathlib import Path
import re

SCHEMA = "virtualcar-b3a62-carcom230-published-b9fb-v1"
CARCOM230_LENGTH = 86
VIN_OFFSET, VIN_LENGTH = 11, 17
COMMON_FIELDS = ((0, 1), (1, 5), (6, 3), (11, 17), (30, 9),
                 (41, 3), (46, 6), (54, 2), (58, 6), (66, 20))
GAPS = ((9, 2), (28, 2), (39, 2), (44, 2),
        (52, 2), (56, 2), (64, 2))
VIN_SHAPE = re.compile(rb"[A-HJ-NPR-Z0-9]{17}\Z")
HEX_FRAME = re.compile(r"(?:[0-9a-fA-F]{2}[ \t]+){7}[0-9a-fA-F]{2}\Z")


def _base():
    return {
        "schema_version": SCHEMA,
        "status": "NOT_ASSESSED",
        "source_section": "D2_50",
        "source_kind": "provided_local_ini_not_authenticated_as_active",
        "frame_count": None,
        "d2_framing_valid": False,
        "synthetic_application_bytes": None,
        "carcom230_root_bytes": CARCOM230_LENGTH,
        "common_fields": len(COMMON_FIELDS),
        "common_field_bytes": sum(width for _, width in COMMON_FIELDS),
        "carcom_unmapped_bytes": sum(width for _, width in GAPS),
        "carcom_vin_offset": VIN_OFFSET,
        "carcom_vin_length": VIN_LENGTH,
        "source_vin_shape": "not_assessed",
        "source_vin_vs_ini": "not_assessed",
        "first_byte_equals_remaining_count": False,
        "post_root_bytes": None,
        "post_root_is_crlf": False,
        "carcom230_prefix_structurally_consistent": False,
        "first_byte_semantics_verified": False,
        "crlf_oem_semantics_verified": False,
        "original_vida_readvin_verified": False,
        "j2534_rx_delivered_verified": False,
        "ecu_identification_verified": False,
        "physical_ecu_or_oem_origin_verified": False,
        "contains_raw_identity_path_or_frames": False,
    }


def compare(ini_text):
    """Return categorical evidence only. A structure match is NOT OEM proof."""
    out = _base()
    try:
        if not isinstance(ini_text, str) or len(ini_text.encode("utf-8")) > 262144:
            raise ValueError("bounded text required")
        cfg = configparser.ConfigParser(interpolation=None, strict=True)
        cfg.read_string(ini_text)
        if len({s.casefold() for s in cfg.sections()}) != len(cfg.sections()):
            raise ValueError("ambiguous sections")
        if not cfg.has_section("D2_50"):
            out["status"] = "NO_D2_50_SECTION"
            return out
        section = cfg["D2_50"]
        raw = section.get("FrameCount", section.get("B9FBFrameCount", "0")).strip()
        if not re.fullmatch(r"(?:0[xX][0-9a-fA-F]+|[0-9]+)", raw):
            raise ValueError("invalid frame count")
        count = int(raw, 0) if raw.lower().startswith("0x") else int(raw, 10)
        out["frame_count"] = count
        if count == 0:
            out["status"] = "NO_D2_50_B9FB_FIXTURE"
            return out
        if count != 13:
            out["status"] = "NOT_THE_PUBLISHED_13_FRAME_SHAPE"
            return out
        frames = []
        for index in range(13):
            frame = section.get(f"B9FBFrame{index:X}", section.get(f"Frame{index:X}", "")).strip()
            if not HEX_FRAME.fullmatch(frame):
                raise ValueError("malformed frame")
            frames.append(bytes.fromhex(frame))
    except (ValueError, UnicodeError, configparser.Error):
        out["status"] = "MALFORMED_SOURCE_INI_OR_FRAME"
        return out

    if (frames[0][:4] != bytes.fromhex("8f 50 f9 fb") or
            [frame[0] for frame in frames[1:]] !=
            [0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
             0x08, 0x09, 0x0A, 0x0B, 0x4F]):
        out["status"] = "INVALID_D2_FRAME_SEQUENCE"
        return out
    out["d2_framing_valid"] = True
    # Each D2 frame has one control byte and seven content bytes. The first
    # frame's initial 3 data bytes are target + positive B9 FB service echo.
    d2_content = b"".join(frame[1:] for frame in frames)
    assert len(d2_content) == 91 and d2_content[:3] == b"\x50\xF9\xFB"
    payload = d2_content[3:]
    out["synthetic_application_bytes"] = len(payload)
    out["first_byte_equals_remaining_count"] = payload[0] == len(payload) - 1
    out["post_root_bytes"] = len(payload) - CARCOM230_LENGTH
    out["post_root_is_crlf"] = payload[CARCOM230_LENGTH:] == b"\x0d\x0a"
    candidate = payload[VIN_OFFSET:VIN_OFFSET + VIN_LENGTH]
    shape = VIN_SHAPE.fullmatch(candidate) is not None
    out["source_vin_shape"] = "17_ascii_vin_shape" if shape else "invalid_vin_shape"
    declared = cfg.get("Vehicle", "VIN", fallback="")
    out["source_vin_vs_ini"] = (
        "equal" if shape and declared.encode("utf-8") == candidate else
        "different" if shape and declared else "not_assessable"
    )
    # A declared CarCom field covers offsets 66..85. Its metadata does NOT
    # say the following CRLF belongs to the ECU reply or is transport padding.
    structure = (len(payload) == 88 and out["post_root_is_crlf"] and
                 out["first_byte_equals_remaining_count"] and shape)
    out["carcom230_prefix_structurally_consistent"] = structure
    if not structure:
        out["status"] = "NOT_THE_PUBLISHED_CARCOM230_PREFIX_SHAPE"
    elif out["source_vin_vs_ini"] != "equal":
        out["status"] = "SYNTHETIC_VIN_DECLARATION_MISMATCH"
    else:
        out["status"] = "SYNTHETIC_86_BYTE_PREFIX_PLUS_CRLF"
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ini", type=Path, required=True,
                        help="explicit local source, never modified")
    args = parser.parse_args(argv)
    try:
        if args.ini.is_symlink() or not args.ini.is_file() or args.ini.stat().st_size > 262144:
            raise ValueError("unavailable source")
        source = args.ini.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError):
        print(json.dumps(dict(_base(), status="SOURCE_UNAVAILABLE"), sort_keys=True))
        return 2
    print(json.dumps(compare(source), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
