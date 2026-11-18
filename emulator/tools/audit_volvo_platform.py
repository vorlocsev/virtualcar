#!/usr/bin/env python3
"""Read-only Volvo P2 / P2 Restyling / P3 model-year classification.

The P2 facelift is a generation/appearance phase on the same P2 platform.
Model year is a catalog hint, not an ECU communication contract.
This tool never selects J2534 routes, D2/GGD, CEM H/L or ECU fixtures.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

UNKNOWN = "Unknown"
P2 = "P2"
P2_RESTYLING = "P2-Restyling"
P3 = "P3"
LABELS = frozenset({UNKNOWN, P2, P2_RESTYLING, P3})

# Approximate model-year catalog boundaries for supported Volvo model families.
# Source notes: docs/B3A310-VOLVO-PLATFORM-GENERATIONS-RU.md
# Years differ by regional market and actual production/changeover.
# Intentionally OMIT modern SPA/CMA/P1/P80 vehicles and uncertain years.
RANGES: dict[str, tuple[tuple[int, int, str], ...]] = {
    "XC90": ((2003, 2006, P2), (2007, 2014, P2_RESTYLING)),
    "S80": ((1999, 2003, P2), (2004, 2006, P2_RESTYLING),
            (2007, 2016, P3)),
    "S60": ((2001, 2004, P2), (2005, 2009, P2_RESTYLING),
            (2011, 2018, P3)),
    "V70": ((2001, 2004, P2), (2005, 2007, P2_RESTYLING),
            (2008, 2016, P3)),
    "XC70": ((2001, 2004, P2), (2005, 2007, P2_RESTYLING),
             (2008, 2016, P3)),
    "XC60": ((2009, 2017, P3),),
    "V60": ((2011, 2018, P3),),
}


def normalize_model(model: str) -> str:
    if not isinstance(model, str):
        raise ValueError("model must be text")
    name = model.strip().upper().replace(" ", "").replace("-", "")
    if name not in RANGES:
        raise ValueError("unsupported or ambiguous model; cannot infer platform")
    return name


def parse_generation(label: str | None) -> str:
    text = (label or "").strip()
    if not text or text.upper() == "UNKNOWN":
        return UNKNOWN
    normalized = text.upper().replace("_", "-").replace(" ", "-")
    if normalized == "P2":
        return P2
    if normalized in {"P2-RESTYLING", "P2-FACELIFT"}:
        return P2_RESTYLING
    if normalized == "P3":
        return P3
    raise ValueError("generation must be P2, P2-Restyling, P3 or Unknown")


def suggest_generation(model: str, model_year: int) -> str:
    name = normalize_model(model)
    if type(model_year) is not int or model_year < 1900 or model_year > 2100:
        raise ValueError("model_year must be an integer from 1900 to 2100")
    matches = [g for lo, hi, g in RANGES[name] if lo <= model_year <= hi]
    if len(matches) > 1:
        raise ValueError("internal overlapping model-year ranges")
    return matches[0] if matches else UNKNOWN


def audit_platform(
    model: str,
    model_year: int,
    declared_generation: str | None = None,
    engine: str | None = None,
    cem_hardware: str | None = None,
    diagnostic_protocol: str | None = None,
) -> dict[str, Any]:
    name = normalize_model(model)
    suggestion = suggest_generation(name, model_year)
    declared = parse_generation(declared_generation)
    hardware = (cem_hardware or UNKNOWN).strip().upper()
    if hardware not in {"H", "L", "UNKNOWN"}:
        raise ValueError("CEM hardware must be H, L or Unknown")
    diagnostic = (diagnostic_protocol or UNKNOWN).strip().upper()
    if diagnostic not in {"D2", "GGD", "UNKNOWN"}:
        raise ValueError("diagnostic protocol must be D2, GGD or Unknown")
    motor = (engine or "").strip().upper()
    if motor and (len(motor) > 24 or not motor.replace("-", "").isalnum()):
        raise ValueError("invalid engine identifier")

    warnings: list[str] = []
    if suggestion == UNKNOWN:
        warnings.append("NO_SUPPORTED_MODEL_YEAR_RULE: check VIN, market and vehicle generation")
    if declared != UNKNOWN and suggestion != UNKNOWN and declared != suggestion:
        warnings.append("DECLARED_GENERATION_CONFLICT: do not select a platform automatically")
        generation = UNKNOWN
        evidence = "conflict"
    elif declared != UNKNOWN:
        generation = declared
        evidence = "declared_metadata"
    else:
        generation = suggestion
        evidence = "model_year_range_only" if suggestion != UNKNOWN else "unknown"

    family = "P2" if generation in {P2, P2_RESTYLING} else "P3" if generation == P3 else UNKNOWN
    facelift = True if generation == P2_RESTYLING else False if generation == P2 else None
    if motor and name == "XC90" and model_year == 2009 and motor == "B8444S":
        # Note explicitly rather than allowing an assumption that MY2009 is P3.
        warnings.append("XC90_2009_V8_REMAINS_P2: restyling does not mean P3")
    return {
        "schema_version": "virtualcar-volvo-platform-generation-v1",
        "model": name,
        "model_year": model_year,
        "engine": motor or None,
        "generation": generation,
        "suggested_generation": suggestion,
        "declared_generation": declared,
        "platform_family": family,
        "p2_restyling": facelift,
        "evidence_level": evidence,
        "cem_hardware": hardware,
        "diagnostic_protocol": diagnostic,
        "protocol_inferred_from_generation": False,
        "cem_hardware_inferred_from_generation": False,
        "approved_for_ecu_response_selection": False,
        "original_vida_runtime_verified": False,
        "warnings": warnings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", required=True)
    ap.add_argument("--model-year", required=True, type=int)
    ap.add_argument("--engine", default="")
    ap.add_argument("--generation", default="Unknown")
    ap.add_argument("--cem-hardware", default="Unknown")
    ap.add_argument("--protocol", default="Unknown")
    a = ap.parse_args()
    try:
        value = audit_platform(a.model, a.model_year, a.generation, a.engine,
                               a.cem_hardware, a.protocol)
    except ValueError as exc:
        ap.error(str(exc))
    print(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
