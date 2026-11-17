#!/usr/bin/env python3
"""Synthetic B3A314 tests; no real registry, INI, VIDA, DLL or ECU calls."""
from pathlib import Path
import runpy

mod = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A314-Audit-CEM-F1xx-Profile-Gates.py")),
    run_name="b3a314_test_import",
)
evaluate = mod["evaluate"]
length = mod["parse_fixture_length"]

assert length("53 49 4D") == 3
assert length("53:49-4D") == 3
assert length("53,49\t4D") == 3
assert length("") == 0
assert length("0x53") == 0
assert length("5") == 0
assert length("53 ZZ") == 0
assert length("00" * 193) == 0
assert length("00" * 192) == 192


def fixture_get(values):
    return lambda section, key, default: values.get((section, key), default)


values = {
    ("Diagnostics", "EnableGGDCemLab"): "1",
    ("Vehicle", "ECUCount"): "2",
    ("ECU1", "RequestId"): "18DA50F1",
    ("ECU1", "ResponseId"): "18DAF150",
    ("ECU1", "DID0Code"): "F110",
    ("ECU1", "DID0Hex"): "53 49 4D",
    ("ECU1", "DID1Code"): "F106",
    ("ECU1", "DID1Hex"): "AA:BB",
    ("ECU1", "DID2Code"): "F114",
    ("ECU1", "DID2Hex"): "11 22",
    ("ECU1", "DID3Code"): "F110",
    ("ECU1", "DID3Hex"): "01",
}
result = evaluate(fixture_get(values))
for label in (
    "B3A314_CEM29_ROUTE_COUNT=1",
    "B3A314_CURRENT_GGD_ENABLED=TRUE",
    "B3A314_F110_VALID_CONFIGURED_SLOTS=2",
    "B3A314_F110_DUPLICATE_SLOTS=1",
    "B3A314_F110_POSITIVE_POSSIBLE_FROM_CURRENT_INI=TRUE",
    "B3A314_F106_VALID_CONFIGURED_SLOTS=1",
    "B3A314_F106_POSITIVE_POSSIBLE_FROM_CURRENT_INI=TRUE",
    "B3A314_F114_CONFIGURED_SLOTS_ALLOWED=FALSE",
    "B3A314_F114_29BIT_CEM_SYNTHETIC_VIN_HANDLER_REACHABLE=FALSE",
    "B3A314_RESULT=READ_ONLY_COMPLETE",
):
    assert label in result, (label, result)
assert not any("53 49 4D" in x or "18DA50F1" in x for x in result)

invalid = dict(values)
invalid[("ECU1", "DID0Hex")] = "GG 11"
invalid[("ECU1", "DID3Hex")] = ""
invalid[("ECU1", "DID1Hex")] = "A"  # odd nibble
x = evaluate(fixture_get(invalid))
assert "B3A314_F110_VALID_CONFIGURED_SLOTS=0" in x
assert "B3A314_F110_INVALID_PAYLOAD_SLOTS=2" in x
assert "B3A314_F106_VALID_CONFIGURED_SLOTS=0" in x
assert "B3A314_F110_POSITIVE_POSSIBLE_FROM_CURRENT_INI=FALSE" in x

wrong_route = dict(values)
wrong_route[("ECU1", "RequestId")] = "726"
x = evaluate(fixture_get(wrong_route))
assert "B3A314_CEM29_ROUTE_COUNT=0" in x
assert "B3A314_F110_VALID_CONFIGURED_SLOTS=0" in x
assert "B3A314_F106_POSITIVE_POSSIBLE_FROM_CURRENT_INI=FALSE" in x

print("B3A314_SYNTHETIC_CEM_F1XX_PROFILE_REGRESSION=PASS")
