#!/usr/bin/env python3
"""Build/preflight an isolated, private CEM_40 synthetic laboratory contract.

Revises PR #348's B3A146 experiment: no historical B9FB payload bytes are
transplanted. The 88-byte/CRLF envelope is a test convention, not a Volvo
schema. Unknown OEM fields are explicit laboratory markers. Nothing here
activates a profile, registers a DLL, contacts VIDA or communicates with a car.
"""
import argparse
import configparser
import io
import os
from pathlib import Path
import sys

from audit_vida_b3a54_private_b9fb_vin import _identity_json, _read_identity_file


CONTRACT = "cem40-synthetic-envelope-v2"
OUTPUT_NAME = "b3a146-cem40-lab.ini"
MAX_BYTES = 512 * 1024
RESPONSE_ID = "00800003"


def _identity(raw):
    state, vin, year, _ = _identity_json(raw)
    if (state != "valid_17_ascii_shape_not_oem_validated" or
            year != "declares_my2009" or vin is None or
            vin[9] != "9" or not vin[-6:].isascii() or not vin[-6:].isdigit()):
        raise ValueError("identity_shape_year_or_serial_inconsistent")
    return vin


def encode_d2(payload):
    """Encode meaningful bytes using the D2 0x08-series, with zero padding."""
    if not 1 <= len(payload) <= 64 * 7:
        raise ValueError("unsupported_payload_length")
    if len(payload) <= 7:
        return [bytes((0xC8 + len(payload),)) + payload.ljust(7, b"\0")]
    chunks = [payload[pos:pos + 7] for pos in range(0, len(payload), 7)]
    frames = []
    for index, chunk in enumerate(chunks):
        header = (0x8F if index == 0 else 0x48 + len(chunk)
                  if index == len(chunks) - 1 else 0x08 | (index & 7))
        frames.append(bytes((header,)) + chunk.ljust(7, b"\0"))
    return frames


def decode_d2(frames, *, service, selector):
    """Strict transport preflight, including significant terminal byte count."""
    if not frames or len(frames) > 64 or any(len(f) != 8 for f in frames):
        raise ValueError("invalid_frame_count_or_size")
    if len(frames) == 1:
        count = frames[0][0] - 0xC8
        if not 3 <= count <= 7 or any(frames[0][1 + count:]):
            raise ValueError("invalid_single_frame_length_or_padding")
        payload = frames[0][1:1 + count]
    else:
        if frames[0][0] != 0x8F:
            raise ValueError("invalid_first_frame")
        if any(frame[0] != 0x08 | (index & 7)
               for index, frame in enumerate(frames[1:-1], 1)):
            raise ValueError("invalid_continuation_sequence")
        count = frames[-1][0] - 0x48
        if not 1 <= count <= 7 or any(frames[-1][1 + count:]):
            raise ValueError("invalid_last_frame_length_or_padding")
        payload = b"".join(frame[1:] for frame in frames[:-1]) + frames[-1][1:1 + count]
    if payload[:3] != bytes((0x40, service, selector)):
        raise ValueError("invalid_address_or_positive_echo")
    return payload


def _b9fb(vin):
    # ONLY the widths and VIN offset of one historical example are reused.
    # These are lab-owned field meanings, not inferred Volvo field meanings.
    fields = (b"LAB", vin.encode("ascii"), b"000000000", b"000",
              vin[-6:].encode("ascii"), b"00", b"000000",
              b"SYNTHETIC-NOT-OEM!!!")
    body = b"\x57\x00LAB!" + b"\r\n".join(fields) + b"\r\n"
    if tuple(map(len, fields)) != (3, 17, 9, 3, 6, 2, 6, 20) or len(body) != 88:
        raise ValueError("internal_contract_length")
    return b"\x40\xf9\xfb" + body


def _fixture(cfg, section, frames, *, b9fb=False):
    prefix = "B9FBFrame" if b9fb else "Frame"
    cfg[section] = {"ResponseId": RESPONSE_ID, prefix + "Count": str(len(frames))}
    for index, frame in enumerate(frames):
        cfg[section][f"{prefix}{index:X}"] = frame.hex(" ").upper()


def _contract(vin, enable_synthetic_b9f0):
    cfg = configparser.ConfigParser(interpolation=None, strict=True)
    cfg.optionxform = str
    cfg["Vehicle"] = {"VIN": vin, "ModelYear": "2009", "BatteryMv": "12500",
                      "EmitIsoRxStart": "0", "ECUCount": "1"}
    cfg["ECU0"] = {"RequestId": "7E0", "ResponseId": "7E8",
                   "PartNumber": "VIRTUAL-ECU", "Software": "SIM-1.0"}
    cfg["Diagnostics"] = {"StrictJ2534Filters": "1", "BackendTelemetryEnabled": "1"}
    cfg["P2"] = {"StrictRouting": "1", "ReplaySpacingMs": "12",
                 "FixtureProvenance": CONTRACT,
                 "FixtureAuthority": "synthetic_laboratory_not_oem"}
    _fixture(cfg, "D2_40", encode_d2(_b9fb(vin)), b9fb=True)
    _fixture(cfg, "D2_50", [], b9fb=True)
    cfg["D2_50"]["ResponseId"] = "01200003"
    _fixture(cfg, "D2_40_B9F0", encode_d2(b"\x40\xf9\xf0" + bytes(15))
             if enable_synthetic_b9f0 else [])
    _fixture(cfg, "D2_50_B9F0", [])
    cfg["D2_50_B9F0"]["ResponseId"] = "01000003"
    _fixture(cfg, "D2_40_B9FC", [])
    _fixture(cfg, "D2_50_B9FC", [])
    cfg["D2_50_B9FC"]["ResponseId"] = "01200003"
    cfg["PassiveCAN"] = {"Enabled": "0"}
    cfg["PassiveTrace"] = {"Enabled": "0"}
    cfg["LabContract"] = {
        "Schema": CONTRACT, "Synthetic": "1", "OEMVerified": "0",
        "VIDAAcceptance": "not_verified", "Route": "CEM_40_CAN_125000",
        "ModelTarget": "XC90", "EngineTarget": "B8444S", "ModelYearTarget": "2009",
        "TransmissionVariant": "unknown_not_encoded",
        "CEMHardwareSoftware": "unknown_not_encoded",
        "IdentityAuthority": "owner_private_json_not_oem_attestation",
        "Timing": "12ms_configuration_only_measure_actual_delivery",
    }
    cfg["Provenance_CEM40_B9FB"] = {
        "Origin": "entire_payload_synthetic_except_owner_vin",
        "Envelope": "one_observed_88byte_CRLF_example_not_oem_schema",
        "BinaryPrefix": "synthetic_57_00_LAB_marker_not_oem_checksum",
        "Field0": "LAB_marker_unknown_oem_meaning",
        "Field1": "owner_private_json_VIN",
        "Field2": "synthetic_zero_FYON_not_engine",
        "Field3": "synthetic_zero_TypePNR3_not_validated_type",
        "Field4": "VIN_suffix_lab_convention_not_proven_chassis_schema",
        "Field5": "synthetic_zero_factory_not_validated",
        "Field6": "synthetic_zero_structure_week_not_model_year",
        "Field7": "SYNTHETIC_NOT_OEM_marker",
    }
    cfg["Provenance_CEM40_B9F0"] = {
        "Origin": "explicit_synthetic_15_zero_bytes_not_part_numbers",
        "Enabled": "1" if enable_synthetic_b9f0 else "0",
        "ParserAcceptance": "not_verified",
    }
    return cfg


def _parse(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_BYTES:
        raise ValueError("bounded_profile_required")
    cfg = configparser.ConfigParser(interpolation=None, strict=True)
    cfg.read_string(text)
    if cfg.defaults() or len({s.casefold() for s in cfg.sections()}) != len(cfg.sections()):
        raise ValueError("defaults_or_ambiguous_sections")
    return cfg


def _normalized(cfg):
    return {section.casefold(): {key.casefold(): value for key, value in cfg.items(section)}
            for section in cfg.sections()}


def validate_profile(text, identity_json):
    """Reject any change to routing, identity, provenance or enabled fixtures.

    Returns only categorical public-safe information. Exact values are checked
    against a fresh reconstruction so extra/legacy INI keys cannot escape the
    preflight through native loader precedence or silently enable other replies.
    """
    vin = _identity(identity_json)
    cfg = _parse(text)
    normalized = _normalized(cfg)
    enabled = normalized.get("d2_40_b9f0", {}).get("framecount") == "3"
    if normalized != _normalized(_contract(vin, enabled)):
        raise ValueError("profile_differs_from_explicit_synthetic_contract")
    for section, prefix, selector in (("d2_40", "b9fbframe", 0xFB),
                                      ("d2_40_b9f0", "frame", 0xF0)):
        values = normalized[section]
        frames = [bytes.fromhex(values[f"{prefix}{i:x}"])
                  for i in range(int(values[prefix + "count"]))]
        if frames:
            decode_d2(frames, service=0xF9, selector=selector)
    return {"contract": CONTRACT, "preflight": "PASS", "synthetic": True,
            "b9fb_frames": 13, "b9f0_frames": 3 if enabled else 0,
            "identity_consistency": "PASS", "vida_acceptance": "NOT_VERIFIED",
            "oem_semantics": "NOT_VERIFIED", "activated": False}


def build_profile(identity_json, *, enable_synthetic_b9f0=False):
    cfg = _contract(_identity(identity_json), enable_synthetic_b9f0)
    stream = io.StringIO()
    stream.write("; PRIVATE SYNTHETIC CEM LAB CONTRACT; NOT OEM XC90 DATA\n")
    stream.write("; Do not publish. Generation does not activate this profile.\n\n")
    cfg.write(stream)
    result = stream.getvalue()
    validate_profile(result, identity_json)
    return result


def write_new(path, text):
    """Create outside a checkout/active install in a dedicated existing lab dir."""
    path = Path(os.path.abspath(path))
    if (path.name.casefold() != OUTPUT_NAME or not path.parent.is_dir() or
            "lab" not in path.parent.name.casefold() or path.is_symlink()):
        raise ValueError("new_dedicated_lab_output_required")
    if any(parent.is_symlink() or (parent / ".git").exists()
           for parent in (path.parent, *path.parent.parents)):
        raise ValueError("output_must_be_outside_checkout_without_redirects")
    if any((path.parent / name).exists()
           for name in ("virtualcar.ini", "VirtualCar.dll", "VirtualCar32.dll", "VirtualCarJ2534.dll")):
        raise ValueError("output_directory_contains_active_profile_or_dll")
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--identity-json", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--enable-synthetic-b9f0", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--profile", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.identity_json.name.casefold() != "vehicle-identity.json":
            raise ValueError("explicit_identity_json_required")
        identity = _read_identity_file(args.identity_json)
        if args.validate_only:
            if args.output or args.enable_synthetic_b9f0 or not args.profile:
                raise ValueError("invalid_validation_arguments")
            if (args.profile.is_symlink() or not args.profile.is_file() or
                    args.profile.stat().st_size > MAX_BYTES):
                raise ValueError("invalid_profile_source")
            validate_profile(args.profile.read_text(encoding="utf-8-sig"), identity)
            print("B3A146_V2: PRIVATE_SYNTHETIC_PREFLIGHT_PASS")
        else:
            if not args.output or args.profile:
                raise ValueError("new_output_required")
            content = build_profile(identity, enable_synthetic_b9f0=args.enable_synthetic_b9f0)
            write_new(args.output, content)
            print("B3A146_V2: PRIVATE_LAB_PROFILE_CREATED_NOT_ACTIVATED")
        print("OEM semantics, original VIDA ReadVin and ECU identification: NOT_VERIFIED")
        return 0
    except (OSError, ValueError, UnicodeError, configparser.Error):
        print("B3A146_V2: REJECTED; private values not printed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
