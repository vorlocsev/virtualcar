#!/usr/bin/env python3
"""Synthetic-only B3A310 test; no Windows registry or private data access."""
from pathlib import Path
import runpy

tool = runpy.run_path(str(Path(__file__).resolve().with_name(
    "B3A310-Resolve-VIDA-J2534-Adapter-Label.py")),
    run_name="b3a310_test_import",
)
resolve = tool["resolve"]

paths = {
    2: rb"C:\synthetic\old\virtualcar.ini",
    3: rb"C:\synthetic\good\virtualcar.ini",
}
registered = [
    ("J2534 Diagnostic Interface", r"C:\synthetic\old\VirtualCarJ2534.dll"),
    ("J2534 Diagnostic Lab 277", r"C:\synthetic\good\VirtualCarJ2534.dll"),
    ("J2534 Diagnostic Lab 261", r"C:\synthetic\other\VirtualCarJ2534.dll"),
]

got = resolve(paths, registered, readiness=lambda unused: True)
for expected in (
    "B3A310_EPOCH3_PROVIDER_MATCH_COUNT=1",
    "B3A310_ADAPTER_LABEL=J2534 Diagnostic Lab 277",
    "B3A310_EPOCH3_CURRENT_GGD_READY=TRUE",
    "B3A310_HISTORICAL_PROVIDER_SELECTION=NOT_PROVEN",
    "B3A310_RESULT=READ_ONLY_COMPLETE",
):
    assert expected in got, (expected, got)
assert not any(r"C:\synthetic" in line for line in got)

not_ready = resolve(paths, registered, readiness=lambda unused: False)
assert "B3A310_EPOCH3_CURRENT_GGD_READY=FALSE" in not_ready

none = resolve(paths, registered[:1])
assert "B3A310_ADAPTER_LABEL=UNRESOLVED" in none
assert "B3A310_RESULT=AMBIGUOUS_OR_NO_MATCH" in none

ambiguous = resolve(paths, registered + [
    ("J2534 Diagnostic Lab Extra", r"C:\synthetic\good\second.dll")])
assert "B3A310_EPOCH3_PROVIDER_MATCH_COUNT=2" in ambiguous
assert "B3A310_ADAPTER_LABEL=UNRESOLVED" in ambiguous

unsafe = resolve(paths, [
    ("J2534 Diagnostic Lab C:\\private\\path",
     r"C:\synthetic\good\VirtualCarJ2534.dll")])
assert "B3A310_ADAPTER_LABEL=UNSAFE_LABEL_REDACTED" in unsafe

print("B3A310_SYNTHETIC_PROVIDER_LABEL_REGRESSION=PASS")
