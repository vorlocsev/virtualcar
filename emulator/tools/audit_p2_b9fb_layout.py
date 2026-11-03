#!/usr/bin/env python3
"""Audit binary-safe structure of a *recorded* Volvo P2 D2 B9FB read.

Strictly source observations. The known public fixture is redacted and belongs
to an unspecified donor, not a verified XC90 V8 MY2009 CEM. This tool cannot
validate a VIN, checksum, hardware identity, ECU acceptance or service order.
"""
import argparse
import json
from pathlib import Path
import sys

from import_p2_trace import sessions, validate_response

FORMAT = "virtualcar-p2-b9fb-layout-evidence-v1"
MAX_SOURCE_BYTES = 1024 * 1024
MAX_LINES = 5000
CONTROL_EXAMPLE = (0x8F, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E,
                   0x0F, 0x08, 0x09, 0x0A, 0x0B, 0x4F)


def audit(source, target=0x50):
    if not isinstance(source, str) or len(source.encode("utf-8")) > MAX_SOURCE_BYTES:
        raise ValueError("invalid_source")
    if target not in (0x40, 0x50):
        raise ValueError("unsupported_target")
    lines = source.splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError("too_many_lines")
    groups = sessions(lines, target, 0xFB)
    if len(groups) != 1:
        raise ValueError("requires_exactly_one_recorded_b9fb_response")
    frames = groups[0]
    validate_response(frames, target, 0xFB)
    control = tuple(data[0] for _can, data in frames)
    wire_body = b"".join(data[1:] for _can, data in frames)
    expected_echo = bytes((target, 0xF9, 0xFB))
    if not wire_body.startswith(expected_echo):
        raise ValueError("b9fb_echo_not_observed")
    payload = wire_body[len(expected_echo):]
    breaks = [index for index in range(len(payload) - 1)
              if payload[index:index + 2] == b"\r\n"]
    mask = b"X" * 17
    positions = [index for index in range(len(payload) - len(mask) + 1)
                 if payload[index:index + len(mask)] == mask]
    # The initial 0x57 in this sample equals the number of bytes *following*
    # it. This is an observed arithmetic coincidence, not an asserted schema.
    length_coincidence = bool(payload and payload[0] == len(payload) - 1)
    recorded_shape = (
        target == 0x50 and len(frames) == 13 and
        frames[0][0] == 0x01200003 and control == CONTROL_EXAMPLE and
        len(payload) == 88 and
        breaks == [9, 28, 39, 44, 52, 56, 64, 86] and
        positions == [11] and payload[:2] == b"\x57\x00"
    )
    return {
        "format": FORMAT,
        "read_only": True,
        "contains_payload_data": False,
        "transport_framing_checked": True,
        "target_group": "40" if target == 0x40 else "50",
        "captured_response_count": len(groups),
        "frames": len(frames),
        "d2_payload_bytes_with_echo": len(wire_body),
        "positive_echo_bytes": len(expected_echo),
        "post_echo_body_bytes": len(payload),
        "has_embedded_nul": b"\x00" in payload,
        "crlf_separator_offsets": breaks,
        "redaction_mask_span_count": len(positions),
        "redaction_mask_span_offset": positions[0] if len(positions) == 1 else None,
        "first_byte_equals_following_byte_count": length_coincidence,
        "matches_known_redacted_donor_footprint": recorded_shape,
        "vin_value_verified": False,
        "schema_semantics_verified": False,
        "checksum_verified": False,
        "xc90_v8_my2009_identity_verified": False,
        "vdash_ecu_acceptance_verified": False,
        "limitations": [
            "Only D2 envelope/framing and bounded byte-layout properties are checked.",
            "The redacted 13-frame donor example is not a real XC90 V8 MY2009 fixture.",
            "0x57 matching the remaining byte count is observed, not a decoded length rule.",
            "CRLF positions are evidence from the supplied bytes, not a universal B9FB format.",
            "A sequence of seventeen X characters is a sample redaction mask, not a VIN.",
            "No field values, VIN, raw CAN frames or input paths are copied into this report.",
            "No requirement that B9F0 precede B9FB is inferred from separate source excerpts.",
            "Successful transport does not prove VDASH or SectorV accepted the block.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("capture", type=Path)
    p.add_argument("--target", choices=("40", "50"), default="50")
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args(argv)
    try:
        if args.capture.resolve() == args.output.resolve():
            raise ValueError("same_file")
        if args.capture.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError("large_file")
        report = audit(args.capture.read_text(encoding="utf-8-sig"),
                       int(args.target, 16))
        with args.output.open("x", encoding="utf-8") as dest:
            json.dump(report, dest, indent=2, sort_keys=True)
            dest.write("\n")
    except (OSError, UnicodeError, ValueError):
        print("Unable to audit the B9FB capture (private details withheld)",
              file=sys.stderr)
        return 2
    print("PASS: B9FB framing/layout observations; identity and client acceptance unknown")
    return 0


if __name__ == "__main__":
    sys.exit(main())
