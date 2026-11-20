#!/usr/bin/env python3
"""Stream a large native Virtual Car log for J2534 D2 B9F0 delivery evidence.

Only emitter-owned frame generation markers are examined; no VIN, ECU
identity, payload, PID, private path or original timestamp is exported.
"""
import argparse
import json
from pathlib import Path
from audit_j2534_discovery import PREFIX, _native_d2_delivery_tags
from audit_b9f0_tag_gap_attribution import TagGapAttribution

SCHEMA = "virtualcar-b9f0-emitter-rx-v1"
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_SOURCE_ROWS = 6000000
MAX_TAG_ROWS = 150000
MAX_LINE = 4096
TAG = "P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)"


def analyze_source(lines):
    scan = {"source_rows_scanned": 0, "tag_rows": 0,
            "oversized_rows_ignored": 0,
            "native_prefix_rows": 0,
            "non_native_prefix_rows": 0,
            "repeated_pid_marker_rows": 0,
            "non_crlf_rows": 0,
            "unterminated_rows": 0,
            "replacement_character_rows": 0}

    adjacency = TagGapAttribution()

    def bounded():
        for line in lines:
            scan["source_rows_scanned"] += 1
            if scan["source_rows_scanned"] > MAX_SOURCE_ROWS:
                raise ValueError("bounded_source_rows_exceeded")
            # Assess text integrity before any parser truncation. Count fixed
            # categories only: no original PID, bytes, paths, host or line.
            native = PREFIX.match(line) is not None
            scan["native_prefix_rows" if native else "non_native_prefix_rows"] += 1
            if line.count("[PID=") > 1:
                scan["repeated_pid_marker_rows"] += 1
            if not line.endswith("\r\n"):
                scan["non_crlf_rows"] += 1
            if not line.endswith(("\r", "\n")):
                scan["unterminated_rows"] += 1
            if "\ufffd" in line:
                scan["replacement_character_rows"] += 1
            if len(line) > MAX_LINE:
                scan["oversized_rows_ignored"] += 1
                # Preserve same-PID interruption of an adjacent RX/tag pair.
                m = PREFIX.match(line[:512])
                safe = (line[:m.end()] + "overlong record excluded\n"
                        if m else "\n")
                adjacency.observe(safe)
                yield safe
                continue
            # A text fragment mentioning the label is not an emitted tag.
            # Match the same native prefix and tag-start rule as both auditors.
            if native and PREFIX.match(line).group(2).startswith(TAG):
                scan["tag_rows"] += 1
                if scan["tag_rows"] > MAX_TAG_ROWS:
                    raise ValueError("bounded_native_tag_rows_exceeded")
            adjacency.observe(line)
            yield line

    report = _native_d2_delivery_tags(bounded(), include_b9f0=True)
    return {
        "schema_version": SCHEMA,
        "complete_source_scan": True,
        "source_scan_counts": scan,
        "native_d2_delivery_tags": report,
        "tag_adjacency_diagnostics": adjacency.summary(report),
        "real_ecu_response_verified": False,
        "sectorv_ecu_identity_accepted_verified": False,
        "limitations": [
            "Native RX evidence comes from the simulated J2534 DLL, not a physical ECU.",
            "A complete shape does not confirm a specific B9F0 stage or client decoding.",
            "B9F0 stages lack shared request IDs; source-level stage/delivery correlation is not verified.",
            "Non-CRLF, unprefixed, repeated PID-marker or replacement-character rows are structural observations, not proof of corruption or lost CAN packets.",
            "Only native-prefixed emitted D2 tag-start records contribute to tag_rows; oversized rows remain excluded.",
            "No VIN, PID, private path, timestamp, CAN payload or key is exported.",
        ],
    }


def main(argv=None):
    p = argparse.ArgumentParser(description="Bounded, read-only full-log B9F0 native RX audit")
    p.add_argument("--native", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        src = args.native
        if (not src.is_file() or src.is_symlink()
                or src.stat().st_size > MAX_SOURCE_BYTES):
            raise ValueError("invalid_or_excessive_source")
        # Preserve CRLF to distinguish native logline() from copied/altered
        # text. Python's default universal-newline mode hides this signal.
        with src.open("r", encoding="utf-8-sig", errors="replace",
                      newline="") as reader:
            report = analyze_source(reader)
    except (OSError, ValueError):
        p.exit(2, "ERROR: invalid_or_unreadable_bounded_input\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
