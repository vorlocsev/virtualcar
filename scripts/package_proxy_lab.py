"""Package only freshly built proxy tools and static lab instructions. No release."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

BINARY_INPUTS = (
    "SectorV-Trace-OneClick-v0.3.6.7-dev26.exe",
    "cmd/oneclick/assets/VirtualCarTrace32.dll",
    "cmd/oneclick/assets/VirtualCarTraceAttribution-x86.exe",
    "cmd/oneclick/assets/VirtualCarTraceSummary-x86.exe",
    "cmd/oneclick/assets/VirtualCarIgnition-x86.exe",
)
DOC_INPUTS = ("docs/DEV46_PROXY_RU.md", "docs/DEV46_LAB_START_RU.txt")


def require_pe32(data, name):
    if len(data) < 128 or data[:2] != b"MZ":
        raise ValueError(f"{name}: missing Windows PE header")
    off = struct.unpack_from("<I", data, 0x3C)[0]
    if off < 64 or off > len(data) - 26:
        raise ValueError(f"{name}: invalid PE header offset")
    if (data[off:off + 4] != b"PE\0\0"
            or struct.unpack_from("<H", data, off + 4)[0] != 0x14C
            or struct.unpack_from("<H", data, off + 24)[0] != 0x10B):
        raise ValueError(f"{name}: expected Windows x86 PE32")


def package(root, output, commit):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Expected the exact 40-character Git commit SHA")
    # Read and validate the entire allowlist before creating the output.
    # Never glob a workspace, logs, emulator profiles or synthetic test DLLs.
    entries = {}
    for relative in BINARY_INPUTS + DOC_INPUTS:
        data = (root / relative).read_bytes()
        if relative in BINARY_INPUTS:
            require_pe32(data, relative)
        entries[Path(relative).name] = data
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "schema": 1,
        "build_commit": commit,
        "scope": "dev46 laboratory tracing proxy; no release",
        "original_dll_included": False,
        "vehicle_validation": "not_performed",
        "files": {},
    }
    for name, data in entries.items():
        (output / name).write_bytes(data)
        manifest["files"][name] = {
            "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    result = package(repo, repo / "_build" / "dev46-lab", args.commit)
    print(f"dev46 lab: {len(result['files'])} allowlisted files; commit {args.commit}")
