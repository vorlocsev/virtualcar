#!/usr/bin/env python3
"""Synthetic B3A309 regression: candidate paths and mock process modules.

Neither real process enumeration nor registry, DLL, VIDA or file I/O occurs.
"""
from pathlib import Path
import runpy

mod = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A309-Check-Live-VIDA-J2534-Modules.py")),
    run_name="b3a309_synthetic_import")
candidates = mod["candidates"]
report = mod["report"]
canonical = mod["canonical_file"]

paths = {
    2: rb"C:\Lab\Epoch2\virtualcar.ini",
    3: rb"C:\Lab\Epoch3\virtualcar.ini",
}
registry = {
    "32": {"state": "READ_OK", "paths": [
        r"C:\Lab\Epoch2\virtualcar_j2534.dll",
        r"C:\Lab\Epoch3\virtualcar_j2534.dll",
        r"C:\Lab\Other\unused.dll",
    ]}
}
assert canonical(r"C:\Lab\Epoch2\virtualcar_j2534.dll") == (
    r"c:\lab\epoch2\virtualcar_j2534.dll")
assert candidates(paths, registry["32"]) == {
    2: r"c:\lab\epoch2\virtualcar_j2534.dll",
    3: r"c:\lab\epoch3\virtualcar_j2534.dll",
}

modules = {r"c:\lab\epoch3\virtualcar_j2534.dll", r"c:\windows\syswow64\iexplore.exe"}
rows = report(paths, registry, "READ_OK", modules)
for required in (
    "B3A309_LOADED_MODULE_ENUM_STATUS=READ_OK",
    "B3A309_EPOCH2_UNIQUE_REG32_DLL_ORIGIN=TRUE",
    "B3A309_EPOCH3_UNIQUE_REG32_DLL_ORIGIN=TRUE",
    "B3A309_EPOCH2_REGISTERED_DLL_LOADED_NOW=FALSE",
    "B3A309_EPOCH3_REGISTERED_DLL_LOADED_NOW=TRUE",
    "B3A309_RESULT=READ_ONLY_COMPLETE",
):
    assert required in rows, (required, rows)
assert not any(r"C:\Lab" in item or "virtualcar_j2534" in item for item in rows)

wrong_process = report(paths, registry, "PID_NOT_IEXPLORE", set())
assert "B3A309_LOADED_MODULE_ENUM_STATUS=PID_NOT_IEXPLORE" in wrong_process
assert "B3A309_EPOCH2_REGISTERED_DLL_LOADED_NOW=NOT_ASSESSED" in wrong_process
assert "B3A309_EPOCH3_REGISTERED_DLL_LOADED_NOW=NOT_ASSESSED" in wrong_process

ambiguous = {"32": {"state": "READ_OK", "paths":
                         registry["32"]["paths"] +
                         [r"C:\Lab\Epoch3\another_j2534.dll"]}}
out = report(paths, ambiguous, "READ_OK", modules)
assert "B3A309_EPOCH3_UNIQUE_REG32_DLL_ORIGIN=FALSE" in out
assert "B3A309_EPOCH3_REGISTERED_DLL_LOADED_NOW=NOT_ASSESSED" in out

missing = report(paths, {"32": {"state": "NOT_PRESENT", "paths": []}},
                 "READ_OK", modules)
assert "B3A309_EPOCH3_REGISTERED_DLL_LOADED_NOW=NOT_ASSESSED" in missing
print("B3A309_SYNTHETIC_LIVE_MODULE_PROVENANCE_REGRESSION=PASS")
