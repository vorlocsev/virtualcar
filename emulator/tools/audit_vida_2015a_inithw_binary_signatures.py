#!/usr/bin/env python3
"""Owner-only VIDA .NET component string-signature census, not IL analysis.

Search installed .DLL/.EXE files for a fixed list of GetInitHwSettings and
CarCom-related ASCII/UTF-16LE metadata tokens. Never loads/executes an
assembly, invokes VIDA, connects to SQL or writes source files.
Only matching module basenames, SHA256 and Boolean fixed-token signatures
are emitted; contents, arbitrary strings, local directory paths and
original car/profile/VIN data are not disclosed.
A token match is NOT proof of method existence, IL callsite, precedence,
VIDA 2015A runtime execution or effective D2 baud.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

SOURCE_TOKENS = (
    "GetInitHwSettings",
    "vadis_GetHwSettings",
    "GetHwSettings",
    "CarComRepository",
    "HwSettings",
    "folderLevel",
    "T136_InitHw_Profile",
)
ENCODED = {
    label: (label.encode("ascii"), label.encode("utf-16le"))
    for label in SOURCE_TOKENS
}
MAX_TOKEN_LEN = max(len(b) for values in ENCODED.values() for b in values)
MAX_SOURCE_BINARY_BYTES = 128 * 1024 * 1024
MAX_SCAN_BYTES = 8 * 1024 * 1024 * 1024
MAX_BINARIES = 30000
MAX_SECONDS = 180
CHUNK = 1024 * 1024
SAFE_BASENAME = re.compile(r"[A-Za-z0-9_.-]{1,160}\Z")


class EvidenceError(ValueError):
    pass


def _scan(path: Path, *, max_binary_size: int = MAX_SOURCE_BINARY_BYTES) -> tuple[dict, str, int] | None:
    if path.is_symlink() or not path.is_file():
        return None
    size = path.stat().st_size
    if size < 1 or size > max_binary_size:
        return None
    flags = {name: False for name in SOURCE_TOKENS}
    digest = hashlib.sha256()
    carry = b""
    consumed = 0
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK):
            consumed += len(chunk)
            digest.update(chunk)
            buf = carry + chunk
            for name, encodings in ENCODED.items():
                if not flags[name] and any(token in buf for token in encodings):
                    flags[name] = True
            carry = buf[-(MAX_TOKEN_LEN - 1):]
    if consumed != size:
        raise EvidenceError("binary changed during read")
    return flags, digest.hexdigest(), consumed


def audit(root: Path) -> dict:
    if not root.is_dir() or root.is_symlink():
        raise EvidenceError("invalid immutable scan root")
    files_scanned = 0
    binaries_skipped_size = 0
    total_bytes = 0
    hits = []
    start = time.monotonic()

    def _walking_error(error):
        raise EvidenceError("unreadable source directory") from error

    for directory, subdirs, files in os.walk(root, topdown=True, followlinks=False, onerror=_walking_error):
        if time.monotonic() - start > MAX_SECONDS:
            raise EvidenceError("bounded original binary scan timed out")
        subdirs[:] = sorted(name for name in subdirs if not (Path(directory) / name).is_symlink())
        for filename in sorted(files):
            if time.monotonic() - start > MAX_SECONDS:
                raise EvidenceError("bounded original binary scan timed out")
            path = Path(directory) / filename
            if path.suffix.casefold() not in (".dll", ".exe") or path.is_symlink():
                continue
            # Real VIDA installs can have spaces or localized filenames.
            # Scan them too; suppress only untrusted basename presentation.
            safe_filename = filename if SAFE_BASENAME.fullmatch(filename) else "special_filename_suppressed"
            size = path.stat().st_size
            if size < 1 or size > MAX_SOURCE_BINARY_BYTES:
                binaries_skipped_size += 1
                continue
            if files_scanned >= MAX_BINARIES or total_bytes + size > MAX_SCAN_BYTES:
                raise EvidenceError("bounded binary scan scope exceeded")
            result = _scan(path)
            if result is None:
                binaries_skipped_size += 1
                continue
            flags, digest, size_read = result
            total_bytes += size_read
            files_scanned += 1
            if any(flags.values()):
                hits.append({
                    "module_basename": safe_filename,
                    "sha256": digest,
                    "fixed_token_present": flags,
                })
    hits.sort(key=lambda v: (v["module_basename"].casefold(), v["sha256"]))
    if len(hits) > 500:
        raise EvidenceError("unbounded matched source assemblies")
    return {
        "schema_version": "virtualcar-vida-original-carcom-string-census-v1",
        "status": "installed_binary_fixed_token_presence_only",
        "source": "owner_local_original_binaries_read_only",
        "binary_files_scanned": files_scanned,
        "binary_files_skipped_size_or_empty": binaries_skipped_size,
        "matching_binaries": len(hits),
        "matches": hits,
        "original_binary_contents_or_install_paths_emitted": False,
        "source_writes_performed": False,
        "assemblies_loaded_or_executed": False,
        "sql_or_vida_routines_called": False,
        "token_match_proves_methoddef_or_il": False,
        "vida_2015a_procedure_callers_verified": False,
        "runtime_selected_profile_set_verified": False,
        "inherited_hardware_settings_verified": False,
        "d2_baudrate_verified": False,
        "original_vida_readvin_accepted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only local VIDA binaries: fixed GetInitHwSettings token census"
    )
    parser.add_argument("--folder", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        print(json.dumps(audit(args.folder), indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"status": "failed", "error_class": type(exc).__name__}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
