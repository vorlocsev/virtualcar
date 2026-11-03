#!/usr/bin/env python3
"""Offline read-only profile consistency audit for synthetic Virtual Car research.

This is configuration provenance analysis, NOT VDASH client behavior and
not a real P2 ECU or vehicle authentication tool.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
import sys

FORMAT = "virtualcar-vdash-profile-contract-v1"
SERVICES = ("B9FB", "B9F0", "B9FC")
BUSES = ("40", "50")
MAX_BYTES = 65536


def _decimal(section, field, value, limit=1024):
    if value is None:
        return None
    if not re.fullmatch(r"[0-9]{1,5}", value.strip()):
        raise ValueError("invalid_decimal")
    number = int(value.strip(), 10)
    if not 0 <= number <= limit:
        raise ValueError("out_of_range")
    return number


def _can_id(text):
    if text is None:
        return None
    value = text.strip()
    if not re.fullmatch(r"(?:0[xX])?[0-9a-fA-F]{1,8}", value):
        raise ValueError("invalid_can_id")
    result = int(value, 16)
    if result > 0x1FFFFFFF:
        raise ValueError("invalid_can_range")
    return result


def audit(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("source_size")
    profile = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        profile.read_string(source)
    except configparser.Error as exc:
        raise ValueError("malformed_ini") from exc
    sections = profile.sections()
    if len(sections) > 128:
        raise ValueError("too_many_sections")

    def get(section, key):
        return profile.get(section, key, fallback=None) if profile.has_section(section) else None

    n = _decimal("Vehicle", "ECUCount", get("Vehicle", "ECUCount"), 32)
    indexed = sorted(int(s[3:]) for s in sections if re.fullmatch(r"ECU(?:0|[1-9][0-9]?)", s))
    if len(indexed) > 32:
        raise ValueError("too_many_ecus")
    strict = _decimal("P2", "StrictRouting", get("P2", "StrictRouting"), 1)
    has_p3_cem = False
    has_obd_ecm = False
    for index in indexed:
        req = _can_id(get("ECU" + str(index), "RequestId"))
        resp = _can_id(get("ECU" + str(index), "ResponseId"))
        has_p3_cem |= req == 0x726 and resp == 0x72E
        has_obd_ecm |= req == 0x7E0 and resp == 0x7E8

    d2 = []
    for bus in BUSES:
        for service in SERVICES:
            section = "D2_" + bus if service == "B9FB" else "D2_" + bus + "_" + service
            field = "B9FBFrameCount" if service == "B9FB" else "FrameCount"
            raw = get(section, field)
            frames = _decimal(section, field, raw, 256)
            state = "unreported" if frames is None else (
                "zero_declared" if frames == 0 else "nonzero_unverified")
            d2.append({"bus": bus, "service": service, "frame_count": frames,
                       "state": state})
            # A declared count of zero with nonempty FrameN is ambiguous.
            if frames == 0 and profile.has_section(section):
                for key in profile[section]:
                    if re.fullmatch(r"(?:b9fb)?frame[0-9]+", key.lower()):
                        raise ValueError("frame_count_conflict")

    count_consistent = (n is not None and indexed == list(range(n)))
    if n is not None and not count_consistent:
        focus = "ecu_count_mismatch"
    elif has_p3_cem and strict == 1:
        focus = "strict_p2_with_p3_route_unverified"
    elif has_p3_cem and any(x["state"] != "unreported" for x in d2):
        focus = "mixed_p2_p3_lab_configuration"
    elif any(x["state"] == "nonzero_unverified" for x in d2):
        focus = "declared_d2_frames_need_source_validation"
    elif strict == 1 and all(x["state"] != "nonzero_unverified" for x in d2):
        focus = "strict_p2_no_d2_read_fixtures"
    else:
        focus = "configuration_only_no_acceptance_evidence"

    return {
        "format": FORMAT, "read_only": True, "contains_payload_data": False,
        "ecu_count_declared": n,
        "indexed_ecu_sections": len(indexed),
        "ecu_section_count_consistent": count_consistent,
        "p2_strict_routing": None if strict is None else bool(strict),
        "has_726_72e_p3_route": has_p3_cem,
        "has_7e0_7e8_obd_route": has_obd_ecm,
        "d2_service_fixtures": d2,
        "profile_research_focus": focus,
        "ecu_identity_verified": False,
        "vdash_acceptance_verified": False,
        "xc90_v8_my2009_verified": False,
        "limitations": [
            "Configuration is not a CAN or J2534 runtime capture.",
            "A declared D2 frame count cannot prove frame bytes, provenance or correctness.",
            "Zero/missing D2 fixtures do not prove the client requests the service.",
            "Mixed P2/P3 configuration is a lab provenance warning, not a proven routing fault.",
            "OBD ECU rows and a VIN field do not prove real XC90 V8 MY2009 identity.",
            "No VIN, CAN frame, private field, raw value or filepath is emitted.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.input.resolve() == args.output.resolve():
            raise ValueError("overlap")
        if args.input.stat().st_size > MAX_BYTES:
            raise ValueError("large_file")
        report = audit(args.input.read_text(encoding="utf-8-sig"))
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (OSError, UnicodeError, ValueError):
        print("Profile contract audit refused invalid or private input", file=sys.stderr)
        return 2
    print("PASS: bounded configuration audit; VDASH ECU acceptance unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
