#!/usr/bin/env python3
"""Read-only VMware registry32 provenance check for the canonical lab J2534 provider.

Never loads a DLL, starts SectorV, changes the registry, contacts hardware,
prints a local path/hash/VIN, or equates a DLL hash with vehicle acceptance.
A self-hosted CI runner is not necessarily the GUI test VM.
"""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import struct
import sys

SCHEMA = "virtualcar-vmware-provider-provenance-v1"
KEY = r"SOFTWARE\PassThruSupport.04.04\SectorV Virtual Car"
MAX_DLL = 64 * 1024 * 1024


def _pe_machine(path):
    """Return x86, other_pe, invalid_pe, missing, or unreadable; no exceptions/paths."""
    try:
        if not path.is_file():
            return "missing"
        if not 96 <= path.stat().st_size <= MAX_DLL:
            return "invalid_pe"
        with path.open("rb") as source:
            header = source.read(64)
            if len(header) != 64 or header[:2] != b"MZ":
                return "invalid_pe"
            pe_offset = struct.unpack_from("<I", header, 0x3C)[0]
            if not 64 <= pe_offset <= 4096:
                return "invalid_pe"
            source.seek(pe_offset)
            coff = source.read(26)
            if len(coff) != 26 or coff[:4] != b"PE\x00\x00":
                return "invalid_pe"
            machine = struct.unpack_from("<H", coff, 4)[0]
            magic = struct.unpack_from("<H", coff, 24)[0]
            return "x86" if (machine, magic) == (0x14C, 0x10B) else "other_pe"
    except (OSError, ValueError, OverflowError, struct.error):
        return "unreadable"


def _file_digest(path):
    """Bounded snapshot to reject races and oversized installed binaries."""
    before = path.stat()
    if not 96 <= before.st_size <= MAX_DLL:
        raise ValueError("size")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError("changed")
    return digest.digest(), before.st_size



def _executable_section_digest(path):
    """Fingerprint only PE32 executable section bytes, never return the bytes.

    Equal code-section bytes can coexist with differing data/metadata, and
    unequal bytes do not establish the source version or semantic behavior.
    """
    try:
        before = path.stat()
        if not 256 <= before.st_size <= MAX_DLL:
            return None
        data = path.read_bytes()
        if len(data) != before.st_size or data[:2] != b"MZ" or len(data) < 64:
            return None
        pe = struct.unpack_from("<I", data, 0x3C)[0]
        if not 64 <= pe <= min(4096, len(data) - 24):
            return None
        if data[pe:pe + 4] != b"PE\x00\x00":
            return None
        machine, sections = struct.unpack_from("<HH", data, pe + 4)
        optional_size = struct.unpack_from("<H", data, pe + 20)[0]
        optional = pe + 24
        if (machine != 0x14C or not 1 <= sections <= 96
                or optional + optional_size + sections * 40 > len(data)):
            return None
        if struct.unpack_from("<H", data, optional)[0] != 0x10B:
            return None
        table = optional + optional_size
        code = []
        for index in range(sections):
            at = table + index * 40
            raw_size, raw_start = struct.unpack_from("<II", data, at + 16)
            flags = struct.unpack_from("<I", data, at + 36)[0]
            if flags & 0x20000000:  # IMAGE_SCN_MEM_EXECUTE
                if (raw_size == 0 or raw_start < table + sections * 40
                        or raw_start + raw_size > len(data)):
                    return None
                code.append(data[raw_start:raw_start + raw_size])
        if not code:
            return None
        after = path.stat()
        if (before.st_size, before.st_mtime_ns) != (
                after.st_size, after.st_mtime_ns):
            return None
        digest = hashlib.sha256()
        for part in code:
            digest.update(struct.pack("<I", len(part)))
            digest.update(part)
        return digest.digest()
    except (OSError, ValueError, OverflowError, IndexError, struct.error):
        return None


def _export_contract(path):
    """Reuse the existing exact-14-exports PE verifier without leaking output.

    This establishes a narrow static ABI shape only; additional exports may be
    legitimate for another J2534 provider and are not a confirmed failure.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                               "native-cpp" / "tests"))
        from verify_pe_exports import verify
        with contextlib.redirect_stdout(io.StringIO()):
            verify(path, "Win32")
        return "exact_14_named_j2534"
    except (ImportError, OSError, ValueError, UnicodeError,
            OverflowError, IndexError, struct.error):
        return "not_exact_or_unverifiable"


def assess(provider_present, function_library, built_path):
    """Return fixed-category, redacted evidence; never serialize input paths."""
    report = {
        "schema_version": SCHEMA,
        "evidence_scope": "local_runner_registry32_only",
        "provider_status": "not_assessed",
        "binary_comparison": "not_assessed",
        "executable_sections": "not_assessed",
        "installed_export_contract": "not_assessed",
        "sectorv_client_execution": "not_performed",
        "vin_or_ecu_accepted": "not_verified",
        "physical_adapter_presence": "not_inspected",
    }
    if not provider_present:
        report["provider_status"] = "canonical_provider_absent"
        return report
    if not isinstance(function_library, str) or not function_library.strip():
        report["provider_status"] = "library_value_missing"
        return report
    value = os.path.expandvars(function_library.strip().strip('"'))
    if not value or value.startswith("\\\\") or not Path(value).is_absolute():
        report["provider_status"] = "nonlocal_or_relative_path"
        return report
    candidate = Path(value)
    state = _pe_machine(candidate)
    if state == "missing":
        report["provider_status"] = "installed_library_missing"
        return report
    if state == "other_pe":
        report["provider_status"] = "installed_library_not_x86"
        return report
    if state != "x86":
        report["provider_status"] = "installed_library_unverifiable"
        return report
    report["provider_status"] = "installed_library_x86"
    report["installed_export_contract"] = _export_contract(candidate)
    tested = Path(built_path)
    if _pe_machine(tested) != "x86":
        report["binary_comparison"] = "tested_build_unverifiable"
        return report
    try:
        old_digest, old_len = _file_digest(candidate)
        new_digest, new_len = _file_digest(tested)
        report["binary_comparison"] = (
            "exact_bytes" if old_len == new_len and old_digest == new_digest
            else "different_bytes"
        )
        installed_code = _executable_section_digest(candidate)
        tested_code = _executable_section_digest(tested)
        report["executable_sections"] = (
            "same_bytes" if installed_code == tested_code else "different_bytes"
        ) if installed_code is not None and tested_code is not None else "unverifiable"
    except (OSError, ValueError):
        report["binary_comparison"] = "comparison_unverifiable"
    return report


def read_registry32():
    """Open exactly one HKLM canonical key with read rights, never enumerate keys."""
    if sys.platform != "win32":
        return None, None, "runner_not_windows"
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, KEY, 0,
                            winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as key:
            try:
                value, kind = winreg.QueryValueEx(key, "FunctionLibrary")
            except FileNotFoundError:
                value, kind = None, None
            if kind not in (winreg.REG_SZ, winreg.REG_EXPAND_SZ):
                value = None
            return True, value, None
    except FileNotFoundError:
        return False, None, None
    except (OSError, PermissionError):
        return None, None, "registry_read_unavailable"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--built-dll", required=True, type=Path)
    args = parser.parse_args(argv)
    present, candidate, error = read_registry32()
    if error:
        result = assess(False, None, args.built_dll)
        result["provider_status"] = error
    else:
        result = assess(present, candidate, args.built_dll)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    # A missing local provider is an observation, NOT a failed source build.
    return 0


if __name__ == "__main__":
    sys.exit(main())
