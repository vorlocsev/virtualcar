#!/usr/bin/env python3
"""Synthetic-only regression for B3A307 J2534 provider origin audit.

No registry access, no file reads/writes, no original VIDA or OEM data.
"""
from pathlib import Path
import runpy

script = Path(__file__).resolve().with_name(
    "B3A307-Audit-J2534-Registry-Origins.py"
)
mod = runpy.run_path(str(script), run_name="b3a307_synthetic_test_import")
snapshot = mod["snapshot_report"]
ini_dir = mod["canonical_dir_from_ini"]
dll_dir = mod["canonical_dir_from_dll"]

assert ini_dir(r"C:\LAB\A\virtualcar.ini") == r"c:\lab\a"
assert ini_dir(r"C:\LAB\A\other.ini") is None
assert dll_dir(r"C:\LAB\A\VirtualCar.dll") == r"c:\lab\a"
assert dll_dir(r"C:\LAB\A\VirtualCar.exe") is None
assert dll_dir("virtualcar.dll") is None

paths = {
    2: rb"C:\LAB\A\virtualcar.ini",
    3: rb"C:\LAB\B\virtualcar.ini",
}
registry = {
    "32": {
        "state": "READ_OK",
        "paths": [
            r"C:\lab\a\VirtualCar-J2534.dll",
            r"C:\lab\b\VirtualCar-J2534.dll",
            r"C:\lab\b\AnotherLabJ2534.dll",
            r"C:\lab\elsewhere\Unrelated.dll",
        ],
    },
    "64": {
        "state": "NOT_PRESENT",
        "paths": [],
    },
}
values = {
    (2, "Diagnostics", "EnableGGDCemLab"): "0",
    (3, "Diagnostics", "EnableGGDCemLab"): "1",
    (2, "ECU1", "RequestId"): "18DA50F1",
    (2, "ECU1", "ResponseId"): "18DAF150",
    (3, "ECU1", "RequestId"): "18DA50F1",
    (3, "ECU1", "ResponseId"): "18DAF150",
}

def current_getter(path: str):
    epoch = 2 if r"\lab\a" in path.lower() else 3
    return lambda sec, key, default: values.get((epoch, sec, key), default)

rows = snapshot(paths, registry, get_current=current_getter)
for expected in (
    "B3A307_NORMALIZED_INI_PATHS_DIFFER=TRUE",
    "B3A307_REG32_STATUS=READ_OK",
    "B3A307_REG32_FUNCTIONLIBRARY_ENTRIES=4",
    "B3A307_REG32_VALID_ABSOLUTE_DLL_PATH_ENTRIES=4",
    "B3A307_REG32_EPOCH2_SAME_DIRECTORY_ENTRIES=1",
    "B3A307_REG32_EPOCH3_SAME_DIRECTORY_ENTRIES=2",
    "B3A307_REG32_EPOCH2_DIR_MATCH=TRUE",
    "B3A307_REG32_EPOCH3_DIR_MATCH=TRUE",
    "B3A307_REG64_STATUS=NOT_PRESENT",
    "B3A307_REG64_EPOCH2_DIR_MATCH=NOT_ASSESSED",
    "B3A307_EPOCH2_CURRENT_READY=FALSE",
    "B3A307_EPOCH3_CURRENT_READY=TRUE",
    "B3A307_EXACT_DLL_IDENTITY=NOT_PROVEN",
    "B3A307_NO_REGISTRY_OR_INI_MUTATIONS=TRUE",
    "B3A307_RESULT=READ_ONLY_COMPLETE",
):
    assert expected in rows, (expected, rows)
assert not any("C:\\LAB" in x or "VirtualCar-J2534.dll" in x for x in rows)

# No provider association is not positive evidence of absent J2534 traffic:
# VIDA may load the DLL directly without using registry discovery.
other = {
    "32": {"state": "READ_OK", "paths": [r"C:\elsewhere\driver.dll"]},
    "64": {"state": "UNAVAILABLE", "paths": []},
}
out = snapshot(paths, other)
assert "B3A307_REG32_EPOCH2_DIR_MATCH=FALSE" in out
assert "B3A307_REG64_EPOCH3_DIR_MATCH=NOT_ASSESSED" in out
assert "B3A307_CURRENT_INI_INSPECTION=NOT_REQUESTED" in out

# Alias/path normalization only; same directory does not identify same file.
alias = {2: rb"C:\LAB\A\virtualcar.ini",
         3: rb"c:/lab/a/VIRTUALCAR.ini"}
same = snapshot(alias, registry)
assert "B3A307_NORMALIZED_INI_PATHS_DIFFER=FALSE" in same
print("B3A307_SYNTHETIC_REGISTRY_ORIGINS_REGRESSION=PASS")
