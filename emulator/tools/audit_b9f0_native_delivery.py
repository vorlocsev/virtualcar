#!/usr/bin/env python3
"""Stream a large native Virtual Car log for J2534 D2 B9F0 delivery evidence.

Only emitter-owned frame generation markers are examined; no VIN, ECU
identity, payload, PID, private path or original timestamp is exported.
"""
import argparse
import json
from pathlib import Path
from audit_j2534_discovery import PREFIX, _native_d2_delivery_tags

SCHEMA = "virtualcar-b9f0-emitter-rx-v1"
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_SOURCE_ROWS = 6000000
MAX_TAG_ROWS = 150000
MAX_LINE = 4096
TAG = "P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)"


def analyze_source(lines):
    scan = {"source_rows_scanned": 0, "tag_rows": 0,
            "oversized_rows_ignored": 0}

    def bounded():
        for line in lines:
            scan["source_rows_scanned"] += 1
            if scan["source_rows_scanned"] > MAX_SOURCE_ROWS:
                raise ValueError("bounded_source_rows_exceeded")
            if len(line) > MAX_LINE:
                scan["oversized_rows_ignored"] += 1
                # Preserve same-PID interruption of an adjacent RX/tag pair.
                m = PREFIX.match(line[:512])
                yield (line[:m.end()] + "overlong record excluded\n"
                       if m else "\n")
                continue
            if TAG in line:
                scan["tag_rows"] += 1
                if scan["tag_rows"] > MAX_TAG_ROWS:
                    raise ValueError("bounded_native_tag_rows_exceeded")
            yield line

    report = _native_d2_delivery_tags(bounded())
    return {
        "schema_version": SCHEMA,
        "complete_source_scan": True,
        "source_scan_counts": scan,
        "native_d2_delivery_tags": report,
        "real_ecu_response_verified": False,
        "sectorv_ecu_identity_accepted_verified": False,
        "limitations": [
            "Native RX evidence comes from the simulated J2534 DLL, not a physical ECU.",
            "A complete shape does not confirm a specific B9F0 stage or client decoding.",
            "B9F0 stages lack shared request IDs; source-level stage/delivery correlation is not verified.",
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
        with src.open("r", encoding="utf-8-sig", errors="replace") as reader:
            report = analyze_source(reader)
    except (OSError, ValueError):
        p.exit(2, "ERROR: invalid_or_unreadable_bounded_input\n")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
