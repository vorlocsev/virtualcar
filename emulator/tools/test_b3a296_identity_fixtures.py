#!/usr/bin/env python3
"""Pure offline synthetic regression for B3A296; no private INI required."""
from pathlib import Path
import runpy

root = Path(__file__).resolve().parent
tool = runpy.run_path(str(root / "B3A296-Audit-CEM529-Identity-Fixtures.py"),
                      run_name="b3a296_import_only")
run = tool["run"]
source = (root.parent / "src" / "virtualcar.c").read_text(
    encoding="utf-8", errors="replace"
)
base = """[Diagnostics]
EnableGGDCemLab=1
[Vehicle]
ECUCount=2
[ECU1]
RequestId=18DA50F1
ResponseId=18DAF150
"""

empty = run(base, source)
assert "B3A296_C_SOURCE_EXPECTED_GUARDS=PASS" in empty
assert "B3A296_PRIVATE_29BIT_CEM_ROUTE=PASS" in empty
assert "B3A296_F110_EXPLICIT_VALID_FIXTURE=FALSE" in empty
assert "B3A296_F106_EXPLICIT_VALID_FIXTURE=FALSE" in empty
assert "B3A296_F114_29BIT_DIRECT_FIXTURE_BLOCKED_BY_SOURCE=TRUE" in empty

configured = run(base + """
DID0Code=F110
DID0Hex=01 02
DID1Code=F106
DID1Hex=AA:BB:CC
DID2Code=F114
DID2Hex=11 22
DID3Code=F110
DID3Hex=DD
""", source)
assert "B3A296_F110_EXPLICIT_VALID_FIXTURE=TRUE" in configured
assert "B3A296_F110_FIXTURE_BYTES_FIRST_SLOT=2" in configured
assert "B3A296_F110_DUPLICATE_VALID_SLOTS=1" in configured
assert "B3A296_F106_EXPLICIT_VALID_FIXTURE=TRUE" in configured
assert "B3A296_F106_FIXTURE_BYTES_FIRST_SLOT=3" in configured
assert "B3A296_F114_EXPLICIT_VALID_FIXTURE=FALSE" in configured
assert "B3A296_ECU1_INVALID_OR_IGNORED_DID_SLOTS=1" in configured

invalid = run(base + "DID0Code=F110\nDID0Hex=GARBAGE\n", source)
assert "B3A296_F110_EXPLICIT_VALID_FIXTURE=FALSE" in invalid
assert "B3A296_ECU1_INVALID_OR_IGNORED_DID_SLOTS=1" in invalid
print("B3A296_SYNTHETIC_OFFLINE_REGRESSION=PASS")
