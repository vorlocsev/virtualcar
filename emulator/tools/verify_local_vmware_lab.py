#!/usr/bin/env python3
"""Verify a locally built, *unpublished* VMware LAB ZIP against CI source outputs.

This verifies bytes, packaging, profile, and static PE architecture only.
It never loads a DLL, runs the GUI, changes the registry, or certifies VIN/ECU.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import zipfile

from package_vmware_lab import FILES, PREFIX, check_pe32, diagnostic_profile

MAX_ARCHIVE_BYTES = 128 * 1024 * 1024
MAX_ENTRY_BYTES = 64 * 1024 * 1024
MAX_METADATA_BYTES = 64 * 1024


def _digest_stream(handle):
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _sha_file(path):
    with path.open("rb") as stream:
        return _digest_stream(stream)


def verify_local_lab(archive_path, source_root, source_sha):
    """Fail closed on any incorrect file, claim, ZIP member or sidecar."""
    if not re.fullmatch(r"[0-9a-fA-F]{40}", source_sha):
        raise ValueError("invalid source commit")
    archive_path, source_root = Path(archive_path), Path(source_root)
    if (not archive_path.is_file() or archive_path.is_symlink()
            or archive_path.stat().st_size > MAX_ARCHIVE_BYTES):
        raise ValueError("invalid local ZIP")
    sidecar = Path(str(archive_path) + ".sha256")
    if (not sidecar.is_file() or sidecar.is_symlink()
            or sidecar.stat().st_size > 256):
        raise ValueError("invalid checksum sidecar")
    digest = _sha_file(archive_path)
    if sidecar.read_text(encoding="ascii").strip() != (
            digest + "  " + archive_path.name):
        raise ValueError("ZIP checksum mismatch")

    expected_files = set(FILES) | {
        "virtualcar.ini", "BUILDINFO.json", "SHA256SUMS.txt"
    }
    expected_paths = {PREFIX + "/" + name for name in expected_files}
    with zipfile.ZipFile(archive_path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(expected_paths) or set(names) != expected_paths:
            raise ValueError("ZIP contains missing, duplicate or unknown paths")
        entries = archive.infolist()
        if (any(e.file_size > MAX_ENTRY_BYTES or e.file_size < 0
                or e.is_dir() for e in entries)
                or sum(e.file_size for e in entries) > MAX_ARCHIVE_BYTES):
            raise ValueError("ZIP entry size limit exceeded")

        info = archive.getinfo(PREFIX + "/BUILDINFO.json")
        sums_info = archive.getinfo(PREFIX + "/SHA256SUMS.txt")
        if (info.file_size > MAX_METADATA_BYTES
                or sums_info.file_size > MAX_METADATA_BYTES):
            raise ValueError("metadata size exceeded")
        manifest = json.loads(archive.read(info).decode("utf-8"))
        required = {
            "format": "virtualcar-vmware-lab-v1",
            "source_commit": source_sha.lower(),
            "architecture": "windows-x86-pe32",
            "profile": "synthetic_p2_read_only",
            "backend_telemetry_enabled": True,
            "vmware_e2e_verified": False,
            "ecu_identity_verified": False,
            "contains_private_vehicle_data": False,
            "two_phase_operator_collector_included": True,
            "operator_gui_acceptance_verified": False,
        }
        if type(manifest) is not dict or any(
            type(manifest.get(k)) is not type(v) or manifest.get(k) != v
            for k, v in required.items()
        ):
            raise ValueError("unverified or contradictory LAB build manifest")

        checksum_text = archive.read(sums_info).decode("ascii")
        checksums = {}
        for row in checksum_text.splitlines():
            if "  " not in row:
                raise ValueError("invalid checksum row")
            hexdigest, name = row.split("  ", 1)
            if (not re.fullmatch(r"[a-f0-9]{64}", hexdigest)
                    or name in checksums or name not in expected_files
                    or name == "SHA256SUMS.txt"):
                raise ValueError("unexpected checksum entry")
            checksums[name] = hexdigest
        if set(checksums) != expected_files - {"SHA256SUMS.txt"}:
            raise ValueError("incomplete checksums")

        for name in sorted(expected_files - {"SHA256SUMS.txt"}):
            with archive.open(PREFIX + "/" + name) as reader:
                actual = _digest_stream(reader)
            if actual != checksums[name]:
                raise ValueError("LAB member checksum mismatch")
            if name in FILES:
                source_file = source_root / FILES[name]
                if not source_file.is_file() or source_file.is_symlink():
                    raise ValueError("LAB source file unavailable")
                if actual != _sha_file(source_file):
                    raise ValueError("LAB member differs from source build")

        original_profile = (source_root / "virtualcar-p2.ini").read_bytes()
        if archive.read(PREFIX + "/virtualcar.ini") != diagnostic_profile(
                original_profile):
            raise ValueError("LAB profile does not match synthetic safe source")
        # Parse the actual PE bytes in the packaged archive, not just fake
        # fixture paths or its manifest's architecture claim.
        for name in ("VirtualCarJ2534.dll", "VirtualCarControl.exe"):
            check_pe32(archive.read(PREFIX + "/" + name))
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args(argv)
    try:
        verify_local_lab(args.archive, args.source_root, args.source_sha)
    except (OSError, UnicodeError, ValueError, KeyError,
            IndexError, zipfile.BadZipFile, json.JSONDecodeError):
        # Do not echo private local paths or exception strings to CI logs.
        print("Local LAB ZIP verification failed", file=sys.stderr)
        return 2
    print("PASS: local VMware LAB ZIP sources, PE32, integrity and synthetic profile; no GUI test or publishing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
