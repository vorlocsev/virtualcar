#!/usr/bin/env python3
"""Sanitize operator-entered VDASH G2 read-only observation metadata.

No memory access, execution, decryption, source-code extraction or changes to
VDASH occur here. Input is PRIVATE. Output is a small allowlisted summary.
Every assessment is an observation of a bounded byte window, not proof of
successful CLR method recovery, reachable CIL or ECU identification.
"""
import argparse
import json
from pathlib import Path
import re
import sys

FORMAT = "virtualcar.vdash.g2.observation.v1"
# Private v2 probe source-grounded sample limits. All tokens are build-local.
TARGETS = {
    "0x06000001": ("module_initializer", 64),
    "0x0600000d": ("loader_candidate", 64),
    "0x0600117a": ("result_helper_a", 20),
    "0x0600117b": ("result_helper_b", 20),
    "0x06001160": ("parse_data", 64),
    "0x0600132b": ("detect", 64),
    "0x06001359": ("shared_rva_predicate_candidate", 20),
}
MAX_INPUT = 256 * 1024
HEADERS = {"tiny", "fat", "other", "unknown"}
READ_STATES = {"ok", "read_failed", "not_attempted"}


def _int(value, low, high):
    return type(value) is int and low <= value <= high


def audit(document):
    if not isinstance(document, dict) or document.get("format") != FORMAT:
        raise ValueError("unsupported_format")
    attestation = document.get("attestation")
    if not isinstance(attestation, dict):
        raise ValueError("missing_attestation")
    for key in ("original_binary_hash_matched", "running_original_image"):
        if type(attestation.get(key)) is not bool:
            raise ValueError("invalid_attestation")
    probes = document.get("probes")
    if not isinstance(probes, list) or len(probes) != len(TARGETS):
        raise ValueError("seven_probes_required")
    by_token = {}
    for entry in probes:
        if not isinstance(entry, dict):
            raise ValueError("invalid_probe")
        token = entry.get("token")
        if not isinstance(token, str) or not re.fullmatch(r"0x[0-9a-fA-F]{8}", token):
            raise ValueError("invalid_token")
        token = token.lower()
        if token not in TARGETS or token in by_token:
            raise ValueError("unexpected_or_duplicate_probe")
        gap = entry.get("next_distinct_method_distance_bytes")
        aliases = entry.get("rva_alias_count")
        window = entry.get("window_bytes")
        if (not _int(gap, 1, 1_000_000) or
                not _int(aliases, 1, 100_000) or
                not _int(window, 1, 64)):
            raise ValueError("invalid_rva_window")
        # Reject historical v1 overlapping 64-byte samples at 20-byte gaps.
        if window != min(64, gap) or window != TARGETS[token][1]:
            raise ValueError("overlap_or_wrong_window")
        if token == "0x06001359" and aliases != 72:
            raise ValueError("expected_shared_rva_not_attested")
        state = entry.get("read_status")
        changed = entry.get("changed_vs_disk")
        header = entry.get("cil_header_class")
        if state not in READ_STATES or header not in HEADERS:
            raise ValueError("invalid_read_status")
        if state == "ok":
            if type(changed) is not bool:
                raise ValueError("missing_observation")
        elif changed is not None or header != "unknown":
            raise ValueError("unobserved_cannot_contain_observation")
        if state != "ok":
            assessment = "not_observed"
        elif not changed:
            assessment = "unchanged_at_sampled_window"
        elif aliases > 1:
            assessment = "changed_shared_rva_unattributed"
        elif header in ("tiny", "fat"):
            assessment = "changed_unique_rva_header_candidate"
        else:
            assessment = "changed_unique_rva_unclassified"
        by_token[token] = {
            "label": TARGETS[token][0],
            "window_bytes": window,
            "rva_ownership": "shared" if aliases > 1 else "unique_in_report",
            "assessment": assessment,
            "header_class": header if state == "ok" else "unknown",
        }
    # Emit in fixed order; never copy filenames, digests, bytes, PIDs or extras.
    ordered = [{"token": token, **by_token[token]} for token in TARGETS]
    counts = {a: sum(p["assessment"] == a for p in ordered) for a in (
        "not_observed", "unchanged_at_sampled_window",
        "changed_shared_rva_unattributed",
        "changed_unique_rva_header_candidate",
        "changed_unique_rva_unclassified")}
    return {
        "format": "virtualcar.vdash.g2.sanitized.v1",
        "contains_private_metadata": False,
        "operator_attestation": {
            "original_binary_hash_matched": attestation["original_binary_hash_matched"],
            "running_original_image": attestation["running_original_image"],
        },
        "evidence_level": "operator_attested_window_observation"
        if all(attestation[k] for k in (
            "original_binary_hash_matched", "running_original_image"))
        else "unattested_window_observation",
        "targets": ordered,
        "counts": counts,
        "runtime_method_recovery_verified": False,
        "vdash_ecu_identification_verified": False,
        "limitations": [
            "Source-grounded MethodDef tokens and RVA windows apply only to the examined build",
            "Self-reported binary attestation is not independently verified by this parser",
            "Changed bytes do not establish decoded CIL or executed control flow",
            "Shared RVA changes cannot be assigned to one MethodDef token",
            "Unchanged or unreadable windows cannot disprove runtime modification",
            "No VDASH client session or J2534 vehicle result is observed by this tool",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Private local metadata JSON")
    parser.add_argument("--output", required=True, type=Path,
                        help="New sanitized JSON path; no overwrite")
    args = parser.parse_args(argv)
    try:
        if args.source.resolve() == args.output.resolve():
            raise ValueError("same_file")
        if args.source.stat().st_size > MAX_INPUT:
            raise ValueError("input_limit")
        with args.source.open(encoding="utf-8-sig") as handle:
            report = audit(json.load(handle))
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2)
            handle.write("\n")
    except (OSError, ValueError, UnicodeError, json.JSONDecodeError):
        print("G2 observation audit failed (private details withheld)", file=sys.stderr)
        return 2
    print("PASS: sanitized bounded-window observation; method recovery and ECU acceptance unverified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
