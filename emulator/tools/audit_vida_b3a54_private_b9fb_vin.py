#!/usr/bin/env python3
"""B3A54: privacy-safe, offline VIN/B9FB consistency in an existing private INI.

Only validates the one documented 88-byte D2 B9FB example. No VIN/frame
substitution, no replay, no J2534/VIDA connection, no file writes.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
import sys

from audit_p2_b9fb_shape import audit_frames

SCHEMA = "virtualcar-b3a54-private-b9fb-consistency-v1"
MAX_FILE = 512 * 1024
MAX_IDENTITY_JSON = 128 * 1024
VIN_SHAPE = re.compile(r"[A-HJ-NPR-Z0-9]{17}\Z")
COUNT_SHAPE = re.compile(r"(?:0[xX][0-9a-fA-F]+|[0-9]+)\Z")
HEX_BYTE = set("0123456789abcdefABCDEF")
LAB_SOURCE_HINT = "historical_public_2005_fixture_with_replaced_VIN"


def _ini(text):
    if not isinstance(text, str) or len(text.encode("utf-8")) > MAX_FILE:
        raise ValueError("bounded_ini_required")
    cfg = configparser.ConfigParser(interpolation=None, strict=True)
    cfg.read_string(text)
    if len({s.casefold() for s in cfg.sections()}) != len(cfg.sections()):
        raise ValueError("ambiguous_section_names")
    return cfg


def _section(cfg, name):
    return next((s for s in cfg.sections() if s.casefold() == name.casefold()), None)


def _get(cfg, section, key, fallback=None):
    actual = _section(cfg, section)
    return cfg.get(actual, key, fallback=fallback) if actual else fallback


def _num(raw, default=0, *, hex_number=False):
    if raw is None or not raw:
        return default
    raw = raw.strip()
    if hex_number:
        valid = re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]+", raw)
        base = 16
    else:
        valid = COUNT_SHAPE.fullmatch(raw)
        base = 16 if raw.lower().startswith("0x") else 10
    if not valid:
        return default
    return int(raw[2:] if raw.lower().startswith("0x") else raw, base) & 0xFFFFFFFF


def _frame8(value):
    if not value or len(value) > 510:
        return None
    parts, i = [], 0
    while i < len(value):
        while i < len(value) and value[i] in " \t:-":
            i += 1
        if i == len(value):
            break
        if i + 1 >= len(value) or value[i] not in HEX_BYTE or value[i+1] not in HEX_BYTE:
            return None
        parts.append(int(value[i:i+2], 16))
        i += 2
        if len(parts) > 8:
            return None
    return bytes(parts) if len(parts) == 8 else None


def _read_b9fb(cfg, target=0x50):
    section = f"D2_{target:02X}"
    count = _get(cfg, section, "FrameCount")
    if count is None or not count:
        count = _get(cfg, section, "B9FBFrameCount", "0")
    if not COUNT_SHAPE.fullmatch(count.strip()):
        return "invalid_declared_count", 0, None
    n = _num(count, 0)
    if n == 0:
        return "no_declared_frames", 0, None
    if n > 64:
        return "excessive_declared_count", 0, None
    rid_default = 0x00800003 if target == 0x40 else 0x01200003
    rid = _num(_get(cfg, section, "ResponseId"), rid_default, hex_number=True)
    if rid > 0x1FFFFFFF:
        return "invalid_response_id", n, None
    frames = []
    for i in range(n):
        key = f"{i:X}"
        entry = _get(cfg, section, f"B9FBFrame{key}")
        if not entry:
            entry = _get(cfg, section, f"Frame{key}")
        data = _frame8(entry)
        if data is None:
            return "missing_or_invalid_frame", n, None
        frames.append((rid, data))
    return "declared_frame_values_loaded_locally", n, frames


def _unique_json_object(pairs):
    """Reject duplicate/case-colliding JSON keys; never echo their values."""
    out, folded = {}, set()
    for key, value in pairs:
        if key.casefold() in folded:
            raise ValueError("ambiguous_identity_json")
        folded.add(key.casefold())
        out[key] = value
    return out


def _identity_json(text):
    """Recognize bounded private JSON layouts without showing their contents.

    B3A12's exact local JSON layout is not attested by repository code.
    Accept only explicit root / Vehicle / Identity / VehicleIdentity
    layouts; multiple candidate locations fail closed.
    """
    if type(text) is not str or len(text.encode("utf-8")) > MAX_IDENTITY_JSON:
        raise ValueError("bounded_identity_json_required")
    root = json.loads(text, object_pairs_hook=_unique_json_object,
                      parse_constant=lambda _x: (_ for _ in ()).throw(
                          ValueError("nonfinite_identity_json")))
    if type(root) is not dict:
        return "unsupported_schema", None, "unknown", "unrecognized"

    def normalized(key):
        return key.casefold().replace("_", "").replace("-", "")

    def field(obj, wanted):
        matches = [key for key in obj if normalized(key) == wanted]
        if len(matches) > 1:
            raise ValueError("ambiguous_identity_json_alias")
        return obj[matches[0]] if matches else None

    candidates = []
    if field(root, "vin") is not None:
        candidates.append(("root_vin", root))
    for key in ("vehicle", "identity", "vehicleidentity"):
        child = field(root, key)
        if type(child) is dict and field(child, "vin") is not None:
            candidates.append(("nested_" + key, child))
    if len(candidates) > 1:
        raise ValueError("ambiguous_identity_json_locations")
    if not candidates:
        return "unsupported_schema", None, "unknown", "unrecognized"

    origin, obj = candidates[0]
    vin = field(obj, "vin")
    year = field(obj, "modelyear")
    year_class = ("declares_my2009" if type(year) in (int, str)
                  and str(year) == "2009" else "other_or_unknown")
    if type(vin) is not str or not VIN_SHAPE.fullmatch(vin):
        return "missing_or_invalid_17_ascii_vin", None, year_class, origin
    return "valid_17_ascii_shape_not_oem_validated", vin, year_class, origin

def inspect_profiles(private_ini_text, active_ini_text=None, identity_json_text=None):
    private = _ini(private_ini_text)
    active = _ini(active_ini_text) if active_ini_text is not None else None
    identity_state, identity_vin, identity_year, identity_origin = (
        _identity_json(identity_json_text) if identity_json_text is not None
        else ("not_supplied", None, "unknown", "not_supplied"))
    vin = _get(private, "Vehicle", "VIN", "")
    vin_state = ("valid_17_ascii_shape_not_oem_validated" if VIN_SHAPE.fullmatch(vin)
                 else "missing_or_invalid_17_ascii_shape")
    raw_state, count, frames = _read_b9fb(private)
    report = {
        "schema_version": SCHEMA,
        "scope": "current_private_profile_read_only_not_historical_loaded_ini",
        "private_vin_state": vin_state,
        "identity_json_state": identity_state,
        "identity_json_schema_location": identity_origin,
        "identity_json_model_year": identity_year,
        "identity_json_vs_private_ini_vin": "not_assessable",
        "b9fb_field_vs_identity_json_vin": "not_assessable",
        "private_b9fb_target": "CEM_50",
        "private_b9fb_declared_count": count,
        "private_b9fb_loader_state": raw_state,
        "d2_transport": "not_checked",
        "published_88_byte_shape": "not_checked",
        "vin_field_vs_private_vin": "not_assessable",
        "observed_six_digit_field_vs_vin_suffix": "unknown",
        "profile_provenance": "not_authenticated",
        "active_ini_b9fb": "not_supplied",
        "active_candidate_exact_frame_match": "not_assessable",
        "replay_approved": False,
        "oem_my2009_origin_verified": False,
        "original_vida_vin_accepted": False,
        "contains_vin_can_payload_paths_pids_or_hashes": False,
    }
    hint = _get(private, "P2", "FixtureProvenance", "")
    if hint == LAB_SOURCE_HINT:
        report["profile_provenance"] = "known_published_donor_with_replaced_vin_not_oem_my2009"
    if identity_vin is not None and vin_state.startswith("valid_17"):
        report["identity_json_vs_private_ini_vin"] = (
            "equal" if identity_vin == vin else "different")
    if frames is not None:
        shape = audit_frames(frames, target=0x50)
        report["d2_transport"] = shape["transport"]
        report["published_88_byte_shape"] = shape["published_88_byte_shape"]
        report["observed_six_digit_field_vs_vin_suffix"] = (
            shape["six_digit_field_compared_with_vin_suffix"])
        if (shape["transport"] == "complete"
                and shape["published_88_byte_shape"] == "matches_one_observed_example"
                and shape["vin_shaped_field"]):
            data = b"".join(frame[1:] for _can_id, frame in frames)
            observed = data[3+11:3+28]
            report["vin_field_vs_private_vin"] = (
                "equal" if vin_state.startswith("valid_17") and
                observed == vin.encode("ascii") else "different")
            if identity_vin is not None:
                report["b9fb_field_vs_identity_json_vin"] = (
                    "equal" if observed == identity_vin.encode("ascii") else "different")
    if active is not None:
        state, n, active_frames = _read_b9fb(active)
        report["active_ini_b9fb"] = ("zero_frames_declared" if n == 0
                                     else "nonzero_candidate_unverified")
        if state not in ("no_declared_frames", "declared_frame_values_loaded_locally"):
            report["active_ini_b9fb"] = "invalid_or_unreadable_declaration"
        if frames is not None and active_frames is not None:
            report["active_candidate_exact_frame_match"] = (
                "equal_current_files_only" if frames == active_frames else
                "different_current_files_only")
        elif n == 0 and count > 0:
            report["active_candidate_exact_frame_match"] = "candidate_not_in_active_ini"
    return report


def _read_local(path):
    if (path.is_symlink() or not path.is_file() or
            path.suffix.lower() != ".ini" or path.stat().st_size > MAX_FILE):
        raise ValueError("invalid_local_ini")
    return path.read_text(encoding="utf-8-sig")


def _read_identity_file(path):
    if (path.is_symlink() or not path.is_file() or
            path.name.casefold() != "vehicle-identity.json" or
            path.stat().st_size > MAX_IDENTITY_JSON):
        raise ValueError("invalid_identity_json_path")
    return path.read_text(encoding="utf-8-sig")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--private-profile", required=True, type=Path,
                   help="explicit path to OWNER-PRIVATE lab INI; never uploaded")
    p.add_argument("--active-ini", type=Path,
                   help="optional current J2534 virtualcar.ini; never edited")
    p.add_argument("--identity-json", type=Path,
                   help="optional owner-private vehicle-identity.json; never printed")
    args = p.parse_args(argv)
    try:
        if (args.active_ini and args.active_ini.resolve() ==
                args.private_profile.resolve()):
            raise ValueError("source_alias")
        result = inspect_profiles(
            _read_local(args.private_profile),
            _read_local(args.active_ini) if args.active_ini else None,
            _read_identity_file(args.identity_json) if args.identity_json else None)
    except (OSError, ValueError, UnicodeError, configparser.Error):
        print("B3A54: INVALID_OR_UNREADABLE_PRIVATE_INI", file=sys.stderr)
        return 2
    print("B3A54: PRIVATE_B9FB_VIN_CONSISTENCY")
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    print("Historical VIDA DLL load, original ECU RX and VIN acceptance: NOT_VERIFIED")
    print("Inputs unchanged; raw VIN/frame/path/PID not printed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
