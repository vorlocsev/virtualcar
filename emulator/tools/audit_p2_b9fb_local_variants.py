#!/usr/bin/env python3
"""Private, read-only comparison of P2 B9FB candidate responses.

The report contains only counts, positional indexes, categories and conclusions.
In particular, it contains no input path, VIN, frame bytes, hashes, CAN IDs or
other stable fingerprints. Equality of two sequences after masking one observed
17-character text field is NOT evidence that either sequence came from an ECU.

This tool does not modify emulator profiles or authorize diagnostic replay.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

from audit_p2_b9fb_shape import audit_frames
from import_p2_trace import sessions_with_origin

SCHEMA = "virtualcar-p2-b9fb-local-variants-v1"
MAX_SOURCES = 64
MAX_BYTES_PER_SOURCE = 32 * 1024 * 1024
MAX_TOTAL_SESSIONS = 2048
MASKED_FIELD_OFFSET = 3 + 11  # Positive B9FB echo, then field at content offset 11.
MASKED_FIELD_LENGTH = 17


def _comparable(frames, shape):
    """Return in-memory-only equality key and 17-byte field for known shape.

    The structure is one published 88-byte *example*, not an OEM decoder.
    All sequence/CAN-ID bytes and every byte outside the second text field must
    agree for a comparison group. The key and field never leave this function.
    """
    if (shape["transport"] != "complete"
            or shape["published_88_byte_shape"] != "matches_one_observed_example"
            or len(frames) != 13):
        return None
    flattened = b"".join(data[1:] for _, data in frames)
    if len(flattened) != 91 or MASKED_FIELD_OFFSET + MASKED_FIELD_LENGTH > len(flattened):
        return None
    start = MASKED_FIELD_OFFSET
    end = start + MASKED_FIELD_LENGTH
    key = (
        tuple((can_id, data[0]) for can_id, data in frames),
        flattened[:start] + b"\x00" * MASKED_FIELD_LENGTH + flattened[end:],
    )
    return key, flattened[start:end]


def audit_local_logs(sources, target=0x50):
    """Compare already-loaded local log line collections, excluding raw values.

    Source indexes refer only to the caller's local input ordering. A simulator
    marker is evidence of simulator logging. Lack of such marker does not prove
    physical hardware, source independence, model year or original provenance.
    """
    if target not in (0x40, 0x50) or len(sources) > MAX_SOURCES:
        raise ValueError("invalid input target or source count")
    rows, groups, lookup = [], [], {}
    total = 0
    for source_index, lines in enumerate(sources):
        found = sessions_with_origin(lines, target, 0xFB)
        total += len(found)
        if total > MAX_TOTAL_SESSIONS:
            raise ValueError("too many candidate response sessions")
        for session_index, (frames, origin) in enumerate(found):
            shape = audit_frames(frames, target=target)
            comparable = _comparable(frames, shape)
            group_index = None
            if comparable is not None:
                key, field = comparable
                if key not in lookup:
                    lookup[key] = len(groups)
                    groups.append({"origin_counts": Counter(), "fields": set(), "members": []})
                group_index = lookup[key]
                group = groups[group_index]
                group["fields"].add(field)
                group["origin_counts"][origin] += 1
                group["members"].append((source_index, session_index))
            rows.append({
                "source_index": source_index,
                "session_index": session_index,
                "rx_frames": len(frames),
                "transport": shape["transport"],
                "published_88_byte_shape": shape["published_88_byte_shape"],
                "origin_marker": origin,
                "comparison_group": group_index,
                "replay_approved": False,
            })
    published_groups = []
    for index, group in enumerate(groups):
        counts = group["origin_counts"]
        published_groups.append({
            "comparison_group": index,
            "candidate_count": len(group["members"]),
            "distinct_observed_17byte_field_values": len(group["fields"]),
            "emulator_tagged_count": counts["emulator_tagged_rx"],
            "unverified_origin_count": counts["unverified_trace_origin"],
            "member_indexes": [
                {"source_index": s, "session_index": t}
                for s, t in group["members"]
            ],
            "comparison_scope": "same_can_id_framing_and_all_bytes_except_observed_17byte_field",
            "oem_origin_verified": False,
        })
    return {
        "schema_version": SCHEMA,
        "read_only": True,
        "contains_raw_can_vin_paths_or_hashes": False,
        "sources_checked": len(sources),
        "target_category": f"0x{target:02X}",
        "candidate_count": len(rows),
        "transport_categories": dict(sorted(Counter(
            row["transport"] for row in rows).items())),
        "origin_marker_categories": dict(sorted(Counter(
            row["origin_marker"] for row in rows).items())),
        "candidates": rows,
        "comparison_groups": published_groups,
        "authentic_vehicle_provenance": "not_verified",
        "cross_process_transaction_correlation": "not_established",
        "client_vin_and_ecu_acceptance": "not_verified",
        "replay_approved": False,
        "notes": [
            "Grouping uses a published 88-byte example, not a universal CEM or OEM schema.",
            "A group compares exact CAN IDs, frame controls and every byte outside one observed 17-byte text field.",
            "Different values in that field do NOT prove vehicle model, year, VIN validity or an original capture.",
            "Emulator-tagged delivery is not a new independent ECU capture.",
            "An unverified source marker is not proof that a trace came from a real ECU.",
            "No original trace, VIN, raw CAN data, source path, identifying hash or reference bytes are emitted.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Compare private local B9FB response candidates without exporting payloads")
    parser.add_argument("logs", nargs="+", type=Path, help="One or more PRIVATE local J2534 logs")
    parser.add_argument("--target", choices=("40", "50"), default="50")
    parser.add_argument("--output", type=Path, required=True, help="NEW redacted report")
    args = parser.parse_args(argv)
    if len(args.logs) > MAX_SOURCES:
        parser.error("too many inputs")
    if len({path.resolve() for path in args.logs}) != len(args.logs):
        parser.error("duplicate source inputs")
    if args.output.resolve() in {path.resolve() for path in args.logs}:
        parser.error("output must not alias any source")
    try:
        sources = []
        for path in args.logs:
            if not path.is_file() or path.stat().st_size > MAX_BYTES_PER_SOURCE:
                raise ValueError("source absent or too large")
            sources.append(path.read_text(
                encoding="utf-8-sig", errors="replace").splitlines())
        result = audit_local_logs(sources, target=int(args.target, 16))
    except (OSError, ValueError, TypeError):
        parser.error("invalid local input or bounded response list")
    try:
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
    except OSError:
        parser.error("cannot create exclusive redacted output")
    print("B9FB candidate comparison complete. OEM origin and replay NOT verified.")


if __name__ == "__main__":
    main()
