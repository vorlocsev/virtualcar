#!/usr/bin/env python3
"""B3A308 synthetic-only PE/provider matching test; no file or registry IO."""
from pathlib import Path
import runpy

tool = runpy.run_path(
    str(Path(__file__).resolve().with_name(
        "B3A308-Compare-J2534-Registered-DLL-Binaries.py")),
    run_name="b3a308_synthetic_import",
)
compare = tool["compare_current"]
classify = tool["classify_bytes"]


def synthetic_pe(machine: int, *, markers: bool) -> bytes:
    header = bytearray(256)
    header[:2] = b"MZ"
    header[0x3C:0x40] = (0x80).to_bytes(4, "little")
    header[0x80:0x84] = b"PE\x00\x00"
    header[0x84:0x86] = machine.to_bytes(2, "little")
    if markers:
        header.extend(tool["GGD_MARKERS"]["A45F"])
        header.extend(tool["GGD_MARKERS"]["DD02"])
    return bytes(header)


old = synthetic_pe(0x014C, markers=False)
new = synthetic_pe(0x014C, markers=True)
x64 = synthetic_pe(0x8664, markers=True)
assert classify(old)["machine"] == "X86"
assert classify(x64)["machine"] == "X64"
assert classify(b"invalid")["machine"] == "NOT_PE"
assert classify(old)["marker_a45f"] == "FALSE"
assert classify(new)["marker_a45f"] == "TRUE"
assert classify(old)["sha256_internal"] != classify(new)["sha256_internal"]

paths = {
    2: rb"C:\Synthetic\Old\virtualcar.ini",
    3: rb"C:\Synthetic\New\virtualcar.ini",
}
registry = {
    "32": {
        "state": "READ_OK",
        "paths": [
            r"C:\Synthetic\Old\VirtualCar.dll",
            r"C:\Synthetic\New\VirtualCar.dll",
            r"C:\Synthetic\Elsewhere\Unrelated.dll",
        ]
    }
}
files = {
    r"C:\Synthetic\Old\VirtualCar.dll": old,
    r"C:\Synthetic\New\VirtualCar.dll": new,
}
report = compare(paths, registry, read=lambda name: files[name])
for marker in (
    "B3A308_REG32_STATUS=READ_OK",
    "B3A308_EPOCH2_DIRECTORY_MATCH_COUNT=1",
    "B3A308_EPOCH3_DIRECTORY_MATCH_COUNT=1",
    "B3A308_EPOCH2_BINARY_STATUS=READ_ONLY_INSPECTED",
    "B3A308_EPOCH3_BINARY_STATUS=READ_ONLY_INSPECTED",
    "B3A308_EPOCH2_PE_MACHINE=X86",
    "B3A308_EPOCH3_PE_MACHINE=X86",
    "B3A308_EPOCH2_GGD_A45F_MARKER=FALSE",
    "B3A308_EPOCH3_GGD_A45F_MARKER=TRUE",
    "B3A308_EPOCH3_GGD_DD02_MARKER=TRUE",
    "B3A308_EPOCH2_VS_3_CURRENT_DLL_BYTES_EQUAL=FALSE",
    "B3A308_ORIGINAL_VIDA_PROVIDER_SELECTED=NOT_PROVEN",
    "B3A308_RESULT=READ_ONLY_COMPLETE",
):
    assert marker in report, (marker, report)
assert not any("C:\\Synthetic" in text or "sha256_internal" in text for text in report)

# Identical binaries in different directories cannot prove which was loaded.
same_files = dict(files)
same_files[r"C:\Synthetic\Old\VirtualCar.dll"] = new
same = compare(paths, registry, read=lambda name: same_files[name])
assert "B3A308_EPOCH2_VS_3_CURRENT_DLL_BYTES_EQUAL=TRUE" in same

# Multiple registered DLLs in one directory are not a unique attribution.
ambiguous = {"32": {"state": "READ_OK", "paths": registry["32"]["paths"] +
                            [r"C:\Synthetic\New\Another.dll"]}}
no_match = compare(paths, ambiguous, read=lambda name: files[name])
assert "B3A308_EPOCH3_DIRECTORY_MATCH_COUNT=2" in no_match
assert "B3A308_EPOCH3_BINARY_STATUS=AMBIGUOUS_OR_NO_MATCH" in no_match
assert "B3A308_EPOCH2_VS_3_CURRENT_DLL_BYTES_EQUAL=UNKNOWN" in no_match

# A missing 32-bit registry view is not evidence that VIDA could not use DLL.
not_present = compare(paths, {"32": {"state": "NOT_PRESENT", "paths": []}},
                      read=lambda name: files[name])
assert "B3A308_EPOCH2_BINARY_STATUS=REGISTRY_UNAVAILABLE" in not_present
assert "B3A308_EPOCH2_VS_3_CURRENT_DLL_BYTES_EQUAL=UNKNOWN" in not_present

print("B3A308_SYNTHETIC_DLL_BINARY_IDENTITY_REGRESSION=PASS")
