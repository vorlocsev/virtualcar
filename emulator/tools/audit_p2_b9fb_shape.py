#!/usr/bin/env python3
"""Privacy-safe, evidence-only audit of a P2 CEM D2 B9FB reply.

Does not modify the emulator, decode private identities, infer a model year,
or treat J2534 delivery as acceptance by SectorV/VDASH/VIDA.

The observed 88-byte CRLF layout is one documented example, not an OEM schema.
"""
import argparse
import json
from pathlib import Path
import re

from import_p2_trace import sessions, validate_response

VIN_SHAPE = re.compile(rb"^[A-HJ-NPR-Z0-9]{17}$")
FIELD_WIDTHS = (3, 17, 9, 3, 6, 2, 6, 20)


def vida_2014d_d2_response_id_candidate(can_id):
    """Classify a recorded ID against the *documented* VIDA 2014D D2 mask.

    spnda/volvo_vida_db scripts/d2.py describes a J2534 pass filter with
    mask/pattern 1 on an odd, extended CAN response ID. This is only an
    offline candidate check: the imported trace does not retain trustworthy
    J2534 CAN_29BIT_ID, filter installation or session attribution.
    """
    if not isinstance(can_id, int) or not 0 < can_id <= 0x1FFFFFFF:
        return "not_evaluated"
    if can_id <= 0x7FF:
        # Even an 11-bit-sized integer may be transmitted with 29-bit flags.
        return "width_unknown_without_j2534_flags"
    return ("odd_extended_id_candidate" if can_id & 1
            else "even_extended_id_mask_mismatch")


def _base_result(frames, target):
    return {
        "schema_version": "virtualcar-p2-b9fb-shape-v1",
        "target": f"0x{target:02X}",
        "rx_frames": len(frames),
        "transport": "unverified",
        "transport_reason": "not_yet_checked",
        "vida2014d_d2_rx_filter_candidate": "not_evaluated",
        "j2534_rx_29bit_flags_verified": False,
        "payload_byte_count": None,
        "embedded_nul": None,
        "observed_length_marker_relation": "unknown",
        "observed_crlf_count": None,
        "published_88_byte_shape": "unknown",
        "vin_shaped_field": False,
        "vin_field_offset": None,
        "six_digit_field_compared_with_vin_suffix": "unknown",
        "checksum_status": "unknown",
        "vehicle_identity_verified": False,
        "client_result": "client_result_unknown",
        "normal_mode_result": "unknown",
        "replay_approved": False,
        "notes": [
            "B9FB transport delivery does not prove identity or normal-mode acceptance.",
            "The 88-byte CRLF field layout is only one published example; field meanings are not generalized.",
            "No payload, VIN, vehicle numbers, raw CAN frames, input path, or identity hash is exported.",
        ],
    }


def audit_frames(frames, target=0x50):
    """Analyze preselected 8-byte D2 RX frames; never return raw bytes."""
    out = _base_result(frames, target)
    try:
        validate_response(frames, target, 0xFB)
    except ValueError:
        out["transport"] = "invalid"
        out["transport_reason"] = "d2_frame_sequence_or_response_route_invalid"
        return out

    # The D2 sequence is valid, but this is NOT evidence of actual VIDA
    # filter installation, 29-bit RxStatus or a client's acceptance.
    out["vida2014d_d2_rx_filter_candidate"] = vida_2014d_d2_response_id_candidate(frames[0][0])
    full = b"".join(data[1:] for _, data in frames)
    if not full.startswith(bytes((target, 0xF9, 0xFB))):
        # The existing importer accepts some single-frame negative replies.
        # An error reply must never be classified as a positive B9FB identity.
        out["transport"] = "negative_or_unknown"
        out["transport_reason"] = "no_positive_b9fb_echo"
        return out

    content = full[3:]
    out["transport"] = "complete"
    out["transport_reason"] = "d2_positive_echo_and_frame_sequence_only"
    out["payload_byte_count"] = len(content)
    out["embedded_nul"] = b"\x00" in content
    out["observed_crlf_count"] = content.count(b"\r\n")
    if len(content):
        # Only a mathematical relation. 0x57 is NOT asserted to be a length field.
        out["observed_length_marker_relation"] = (
            "first_byte_equals_remaining_byte_count"
            if content[0] == len(content) - 1 else "relation_not_observed"
        )

    # This layout reproduces the *structure* of one published B9FB example:
    # 6 binary prefix bytes and eight CRLF-delimited fields. It is NOT a
    # cross-model decoder, and matching its widths proves no vehicle identity.
    if len(content) != 88 or content[:2] != b"\x57\x00":
        return out
    sections = content[6:].split(b"\r\n")
    if len(sections) != 9 or sections[-1] != b"":
        return out
    fields = sections[:-1]
    if tuple(map(len, fields)) != FIELD_WIDTHS:
        return out
    if not all(all(0x20 <= byte <= 0x7E for byte in f) for f in fields):
        return out
    out["published_88_byte_shape"] = "matches_one_observed_example"
    candidate = fields[1]
    vin_like = (
        VIN_SHAPE.fullmatch(candidate) is not None
        and any(65 <= b <= 90 for b in candidate)
        and any(48 <= b <= 57 for b in candidate)
    )
    if not vin_like:
        return out

    out["vin_shaped_field"] = True
    out["vin_field_offset"] = 6 + len(fields[0]) + 2
    # The field at this position is six ASCII digits in the observed example.
    # Compare literal bytes, without calling it an OEM chassis field.
    if re.fullmatch(rb"[0-9]{6}", fields[4]) and re.fullmatch(rb"[0-9]{6}", candidate[-6:]):
        out["six_digit_field_compared_with_vin_suffix"] = (
            "equal" if fields[4] == candidate[-6:] else "different"
        )
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only B9FB frame/shape audit; no vehicle identity accepted"
    )
    parser.add_argument("log", type=Path, help="Local J2534 text log, never uploaded")
    parser.add_argument("--target", choices=("40", "50"), default="50")
    parser.add_argument("--session-index", type=int, default=None,
                        help="Zero-based response session if multiple sessions exist")
    parser.add_argument("--output", type=Path, required=True,
                        help="NEW privacy-safe JSON, exclusive creation")
    args = parser.parse_args(argv)
    if args.output.resolve() == args.log.resolve():
        parser.error("output and log must be different")
    target = int(args.target, 16)
    try:
        groups = sessions(args.log.read_text(encoding="utf-8-sig", errors="replace").splitlines(),
                          target, 0xFB)
    except OSError as exc:
        parser.error(f"cannot read source: {exc.__class__.__name__}")
    if not groups:
        parser.error("no B9FB response session found")
    if args.session_index is None:
        if len(groups) != 1:
            parser.error("multiple sessions found: select --session-index explicitly")
        selected = 0
    else:
        selected = args.session_index
        if selected < 0 or selected >= len(groups):
            parser.error("session-index is out of range")
    result = audit_frames(groups[selected], target=target)
    result["sessions_found"] = len(groups)
    result["selected_session_index"] = selected
    result["channel_and_baud_verified"] = False  # Importer has no reliable channel tuple.
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except OSError as exc:
        parser.error(f"cannot create exclusive output: {exc.__class__.__name__}")
    print("B9FB structural audit complete; client_result=unknown; replay_approved=NO")


if __name__ == "__main__":
    main()
