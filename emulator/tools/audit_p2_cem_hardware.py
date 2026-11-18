#!/usr/bin/env python3
"""Conservative, read-only P2 CEM-H/L identification aid.

A diagnostic number (CarCom D2/GGD) is NOT a hardware part number.
CEM-H/L is not CAN HS/LS. Community part lists are hints, never proof.
No ECU access, PIN operation, database access, or J2534 activity.
"""
from __future__ import annotations

import argparse
import json
import re
from typing import Any

# Community list, not OEM-authoritative:
# https://github.com/vtl/volvo-cem-cracker/blob/master/volvo-cem-cracker.ino
# Important: 30682982 appears in BOTH original author sections.
CEM_L_COMMUNITY_PARTS = frozenset({
    "30682981", "30682982", "30728356", "30728542",
    "30765149", "30765646", "30786475", "30786889",
    "31282457", "31314468", "31394158",
})
CEM_H_COMMUNITY_PARTS = frozenset({
    "30786476", "30728539", "30682982", "30728357",
    "30765148", "30765643", "30786890", "30795115",
    "31282455", "31394157", "30786579",
})


def normalize_marking(raw: str | None) -> str:
    if raw is None or not raw.strip() or raw.strip().upper() == "UNKNOWN":
        return "UNKNOWN"
    text = raw.strip().upper().replace(" ", "-")
    if text in {"H", "CEM-H"}:
        return "H"
    if text in {"L", "CEM-L"}:
        return "L"
    raise ValueError("hardware marking must be H, L, CEM-H, CEM-L or UNKNOWN")


def normalize_diagnostic_protocol(raw: str | None) -> str:
    if raw is None or not raw.strip() or raw.strip().upper() == "UNKNOWN":
        return "UNKNOWN"
    text = raw.strip().upper()
    if text in {"D2", "GGD"}:
        return text
    raise ValueError("diagnostic protocol must be D2, GGD or UNKNOWN")


def audit_cem(
    hardware_marking: str | None = None,
    hardware_part_number: str | None = None,
    diagnostic_number: str | None = None,
    diagnostic_protocol: str | None = None,
) -> dict[str, Any]:
    label = normalize_marking(hardware_marking)
    protocol = normalize_diagnostic_protocol(diagnostic_protocol)
    pn = (hardware_part_number or "").strip()
    if pn and re.fullmatch(r"[0-9]{7,8}", pn) is None:
        raise ValueError("hardware part number must be 7 or 8 decimal digits")
    diag = (diagnostic_number or "").strip()
    if diag and re.fullmatch(r"[0-9]{7,8}(?:\s+[A-Z]{1,2})?", diag) is None:
        raise ValueError("diagnostic number must contain 7-8 digits and optional suffix")

    candidates: list[str] = []
    if pn in CEM_L_COMMUNITY_PARTS:
        candidates.append("L")
    if pn in CEM_H_COMMUNITY_PARTS:
        candidates.append("H")

    warnings: list[str] = []
    classification = label
    if len(candidates) > 1:
        warnings.append("PART_LIST_CONFLICT: same hardware part number appears as H and L")
    if label != "UNKNOWN" and candidates and label not in candidates:
        warnings.append("LABEL_PART_CONFLICT: recheck physical CEM label and part number")
        classification = "UNKNOWN"
    if label == "UNKNOWN" and len(candidates) == 1:
        warnings.append("PART_ONLY_IS_CANDIDATE: verify the physical H/L marking")
    if label == "UNKNOWN" and not candidates:
        warnings.append("NO_HARDWARE_CLASS_EVIDENCE")
    if protocol != "UNKNOWN":
        warnings.append("DIAGNOSTIC_PROTOCOL_IS_INDEPENDENT_OF_HARDWARE_CLASS")
    return {
        "schema_version": "virtualcar-cem-hardware-audit-v1",
        "hardware_class": classification,
        "hardware_class_evidence": "declared_physical_marking" if label != "UNKNOWN" and classification == label else "unverified",
        "declared_hardware_marking": label,
        "hardware_part_number": pn or None,
        "community_part_candidates": candidates,
        "diagnostic_number": diag or None,
        "diagnostic_protocol": protocol,
        "hardware_class_accepted_for_fixture_selection": False,
        "original_vida_verified": False,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--marking", default="UNKNOWN", help="Physical case marking: CEM-H / CEM-L")
    parser.add_argument("--hardware-part", default="", help="Hardware number from the physical label")
    parser.add_argument("--diagnostic-number", default="", help="Separate VIDA diagnostic number, not HW number")
    parser.add_argument("--protocol", default="UNKNOWN", choices=["UNKNOWN", "D2", "GGD"])
    args = parser.parse_args()
    try:
        record = audit_cem(args.marking, args.hardware_part, args.diagnostic_number, args.protocol)
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(record, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
