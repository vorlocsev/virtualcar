#!/usr/bin/env python3
"""Audit P2 D2 CEM read-only fixture provenance and framing without identifiers.

Each active B9FB/B9F0/B9FC reply is independently validated and
source-labeled. Global INI provenance strings are operator-supplied claims,
NOT signed evidence. This tool never authenticates an ECU or a client.
"""
import argparse
import configparser
import json
from pathlib import Path
import re
import sys

from import_p2_trace import validate_response
from audit_p2_b9fb_coherence import audit as audit_b9fb

FORMAT = "virtualcar-p2-d2-fixture-source-audit-v1"
MAX_BYTES = 65536
HEX_ID = re.compile(r"(?:0[xX])?[0-9a-fA-F]{1,8}\Z")
HEX_BYTE = re.compile(r"[0-9a-fA-F]{2}\Z")
COUNTER = re.compile(r"(?:0|[1-9][0-9]?)\Z")
KNOWN_LOCAL_CLASSES = {
    "local_private_raw_unverified",
    "local_synthetic_vin_unverified",
    "local_redaction_attempt_unverified",
}
SECTIONS = (
    ("D2_40", 0x40, 0xFB),
    ("D2_50", 0x50, 0xFB),
    ("D2_40_B9F0", 0x40, 0xF0),
    ("D2_50_B9F0", 0x50, 0xF0),
    ("D2_40_B9FC", 0x40, 0xFC),
    ("D2_50_B9FC", 0x50, 0xFC),
)


def _origin(section):
    """Allowlist categories; never expose arbitrary local provenance text."""
    if section is None:
        return "section_undeclared"
    text = section.get("FixtureSourceClass", fallback="")
    if not text:
        return "section_undeclared"
    if text in KNOWN_LOCAL_CLASSES:
        return text
    return "section_unknown_claim"


def _record(profile, name, target, opcode):
    section = profile[name] if profile.has_section(name) else None
    result = {
        "target": "0x%02X" % target,
        "service": "B9%02X" % opcode,
        "expected_network": "ls_125k" if target == 0x40 else "hs_500k",
        "status": "disabled_no_fixture",
        "response_frames": 0,
        "source_class": _origin(section),
        "transport_framing_verified": False,
        "positive_transport_observed": False,
        "published_example_shape_matched": False,
        "ecu_identity_verified": False,
        "client_acceptance_verified": False,
        "application_checksum_verified": False,
        "source_authenticated": False,
    }
    if section is None:
        return result
    raw_count = section.get(
        "B9FBFrameCount" if opcode == 0xFB else "FrameCount",
        fallback=section.get("FrameCount", fallback="0") if opcode == 0xFB else "0")
    if COUNTER.fullmatch(raw_count.strip()) is None:
        raise ValueError("invalid_fixture_frame_count")
    count = int(raw_count)
    if count > 64:
        raise ValueError("fixture_frame_limit")
    if count == 0:
        return result
    raw_id = section.get("ResponseId", fallback="")
    if HEX_ID.fullmatch(raw_id.strip()) is None:
        raise ValueError("invalid_fixture_response_id")
    can_id = int(raw_id, 16)
    if not 0 < can_id <= 0x1FFFFFFF:
        raise ValueError("invalid_extended_can_response_id")
    prefix = "B9FBFrame" if opcode == 0xFB and section.get("B9FBFrameCount", fallback=None) is not None else "Frame"
    # Mirror the DLL's B9FBFrameN -> FrameN compatibility, without mixing
    # both series into a single completed response.
    if opcode == 0xFB and not any(k.lower().startswith("b9fbframe") for k in section):
        prefix = "Frame"
    expected_keys = {prefix.lower() + format(i, "x") for i in range(count)}
    declared = {
        key.lower() for key in section
        if re.fullmatch(r"(?:B9FBFrame|Frame)[0-9A-Fa-f]{1,2}", key, re.I)
    }
    if declared != expected_keys:
        raise ValueError("missing_or_mixed_fixture_frames")
    frames = []
    for i in range(count):
        raw = section[prefix + format(i, "X")].strip().split()
        if len(raw) != 8 or any(HEX_BYTE.fullmatch(x) is None for x in raw):
            raise ValueError("malformed_fixture_frame")
        frames.append((can_id, bytes(int(x, 16) for x in raw)))
    validate_response(frames, target, opcode)
    first = frames[0][1]
    positive = first[2:4] == bytes((0xF9, opcode))
    result.update({
        "status": "positive_transport" if positive else "negative_transport",
        "response_frames": count,
        "transport_framing_verified": True,
        "positive_transport_observed": positive,
    })
    # These are merely *shapes*, NEVER a decoded ECU hardware identity.
    if positive and target == 0x50 and opcode == 0xF0:
        result["published_example_shape_matched"] = (
            count == 3 and can_id == 0x01000003
            and [data[0] for _, data in frames] == [0x8F, 0x09, 0x4C])
    elif positive and target == 0x50 and opcode == 0xFB:
        # The existing B9FB specialist checks the known donor's complete
        # 13-frame footprint and internal fields. Other valid D2 layouts
        # remain unclassified, not "wrong car".
        result["published_example_shape_matched"] = (
            count == 13 and can_id == 0x01200003
            and [data[0] for _, data in frames] ==
            [0x8F, 9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F])
    return result


def audit(source):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_BYTES:
        raise ValueError("oversized_or_invalid_profile")
    profile = configparser.ConfigParser(strict=True, interpolation=None)
    try:
        profile.read_string(source)
    except configparser.Error as exc:
        raise ValueError("malformed_profile_ini") from exc
    if len(profile.sections()) > 128:
        raise ValueError("too_many_profile_sections")
    rows = [_record(profile, *item) for item in SECTIONS]
    active = [r for r in rows if r["transport_framing_verified"]]
    raw_global = profile.get("P2", "FixtureProvenance", fallback="")
    if raw_global == "local_composite_unverified_trace_import":
        global_claim = "local_composite_unverified"
    elif raw_global.startswith("historical_public_"):
        global_claim = "historical_public_label_only"
    elif raw_global:
        global_claim = "unrecognized_global_claim"
    else:
        global_claim = "none"
    categories = {r["source_class"] for r in active}
    warnings = []
    if active and global_claim == "historical_public_label_only":
        warnings.append("historical_label_is_not_authenticated_provenance")
    if any(r["source_class"] == "section_undeclared" for r in active):
        warnings.append("active_fixture_lacks_per_section_origin")
    if any(r["source_class"] == "section_unknown_claim" for r in active):
        warnings.append("unrecognized_fixture_origin_claim")
    if len(categories) > 1 or (len(active) > 1 and global_claim == "local_composite_unverified"):
        warnings.append("multi_section_sources_not_proven_same_donor")
    b9fb_coherence = None
    if any(row["target"] == "0x50" and row["service"] == "B9FB"
           and row["status"] == "positive_transport" and
           row["published_example_shape_matched"] for row in active):
        # Run the single known donor-layout audit, but expose only its
        # fixed vocabulary. It does not decode a verified part number.
        donor = audit_b9fb(source)
        b9fb_coherence = {
            "donor_88_byte_footprint": donor["known_donor_13frame_layout_matched"],
            "embedded_vin_shape": donor["embedded_vin_shape"],
            "configured_vin_matches_embedded": donor["configured_vin_matches_embedded"],
            "candidate_chassis_suffix_matches_embedded_vin":
                donor["candidate_chassis_suffix_matches_embedded_vin"],
            "possible_profile_inconsistencies": donor["possible_profile_inconsistencies"],
            "schema_semantics_verified": False,
            "checksum_verified": False,
        }
    return {
        "format": FORMAT,
        "read_only": True,
        "contains_payload_data": False,
        "profile_source_kind": "untrusted_local_ini",
        "global_provenance_claim": global_claim,
        "active_fixture_count": len(active),
        "fixture_source_consistency_verified": False,
        "application_checksum_verified": False,
        "xc90_v8_my2009_identity_verified": False,
        "sectorv_vdash_client_acceptance_verified": False,
        "fixtures": rows,
        "b9fb_donor_shape_coherence": b9fb_coherence,
        "source_warnings": warnings,
        "limitations": [
            "FixtureProvenance and FixtureSourceClass are plain INI labels, not trusted attestation.",
            "A donor-style B9FB or B9F0 shape does not establish an XC90 V8 MY2009 identity.",
            "No interpretation of B9F0 hardware/software part numbers is authenticated.",
            "B9FC application-level checksum and unknown fields are not inferred.",
            "No VIN, ECU hardware ID, CAN bytes, process labels, source filenames or paths exported.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("profile", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.profile.resolve() == args.output.resolve():
            raise ValueError("source_and_output_overlap")
        if args.profile.stat().st_size > MAX_BYTES:
            raise ValueError("too_many_source_bytes")
        summary = audit(args.profile.read_text(encoding="utf-8-sig"))
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(summary, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except (OSError, UnicodeError, ValueError, TypeError, KeyError):
        print("Local D2 fixture source audit rejected; private data withheld",
              file=sys.stderr)
        return 2
    print("PASS: D2 fixture source labels and transport audited; ECU identity unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
