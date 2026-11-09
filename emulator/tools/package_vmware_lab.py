#!/usr/bin/env python3
"""Build a closed-allowlist, read-only VMware lab ZIP from tested Windows x86 outputs."""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

PREFIX = "VirtualCar-VMware-LAB"
FILES = {
    "VirtualCarJ2534.dll": "VirtualCarJ2534.dll",
    "VirtualCarControl.exe": "VirtualCarControl.exe",
    "virtualcar-default.ini": "virtualcar-default.ini",
    "virtualcar-p2.ini": "virtualcar-p2.ini",
    "scripts/install.ps1": "scripts/install.ps1",
    "scripts/uninstall.ps1": "scripts/uninstall.ps1",
    "tools/audit_backend_evidence.py": "tools/audit_backend_evidence.py",
    "tools/audit_j2534_discovery.py": "tools/audit_j2534_discovery.py",
    "tools/audit_j2534_connect.py": "tools/audit_j2534_connect.py",
    # Real GUI-guest P0 collection tools. Preserve the exact reviewed
    # two-phase Python import closure inside the self-contained local LAB.
    # None of these tools starts SectorV, sends CAN or authenticates a VIN.
    "tools/audit_sectorv_operator_session.py": "tools/audit_sectorv_operator_session.py",
    "tools/audit_sectorv_fresh_window.py": "tools/audit_sectorv_fresh_window.py",
    "tools/audit_sectorv_ui_window_triage.py": "tools/audit_sectorv_ui_window_triage.py",
    "tools/audit_sectorv_ui_observation.py": "tools/audit_sectorv_ui_observation.py",
    "tools/audit_vmware_provider_provenance.py": "tools/audit_vmware_provider_provenance.py",
    "tools/audit_vmware_sectorv_process.ps1": "tools/audit_vmware_sectorv_process.ps1",
    # The provenance audit resolves this parser from the package-relative
    # native-cpp/tests directory. Static PE inspection only, no DLL load.
    "native-cpp/tests/verify_pe_exports.py": "native-cpp/tests/verify_pe_exports.py",
    "README_SECTORV_FRESH_WINDOW_RU.md": "README_SECTORV_FRESH_WINDOW_RU.md",
    "README_VMWARE_LAB_RU.md": "README_VMWARE_LAB_RU.md",
    "README_BACKEND_JSONL_RU.md": "README_BACKEND_JSONL_RU.md",
    "README_P3TOOL_J2534_PREFLIGHT_RU.md": "README_P3TOOL_J2534_PREFLIGHT_RU.md",
}
SYNTHETIC_VIN = "YV1CZ0002A0000001"


def check_pe32(data):
    """Reject PE32+ and foreign targets without loading executable code."""
    if len(data) < 256 or data[:2] != b"MZ":
        raise ValueError("invalid_windows_binary")
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if offset > len(data) - 26 or data[offset:offset + 4] != b"PE\x00\x00":
        raise ValueError("invalid_windows_binary")
    machine = struct.unpack_from("<H", data, offset + 4)[0]
    magic = struct.unpack_from("<H", data, offset + 24)[0]
    if machine != 0x014C or magic != 0x010B:
        raise ValueError("not_windows_x86_pe32")


def diagnostic_profile(data):
    """Enable metadata-only evidence on a safe, synthetic, no-CEM-fixture P2 base."""
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read_string(data.decode("utf-8-sig"))
    if cfg.get("Vehicle", "VIN", fallback="") != SYNTHETIC_VIN:
        raise ValueError("non_synthetic_vin")
    if cfg.getint("Vehicle", "ECUCount", fallback=-1) != 1:
        raise ValueError("unexpected_ecu_profile")
    if cfg.getint("P2", "StrictRouting", fallback=0) != 1:
        raise ValueError("unsafe_p2_routing")
    for section in cfg.sections():
        if section.startswith("D2_"):
            for key in ("FrameCount", "B9FBFrameCount"):
                if cfg.has_option(section, key) and cfg.getint(section, key) != 0:
                    raise ValueError("vehicle_fixture_is_enabled")
        if section.startswith("D2_Node") and cfg.getint(section, "Enabled", fallback=0) != 0:
            raise ValueError("extra_ecu_is_enabled")
    for section in ("PassiveCAN", "PassiveTrace"):
        if cfg.getint(section, "Enabled", fallback=0) != 0:
            raise ValueError("passive_replay_is_enabled")
    if cfg.has_section("Diagnostics"):
        raise ValueError("unexpected_diagnostics_section")
    return (
        "; VMware CEM discovery LAB, synthetic VIN. Not XC90 MY2009 identity.\n"
        + data.decode("utf-8-sig").rstrip()
        + "\n\n[Diagnostics]\nBackendTelemetryEnabled=1\n"
    ).encode("utf-8")


def create_package(root, output_dir, source_sha, version):
    if not re.fullmatch(r"[a-fA-F0-9]{40}", source_sha):
        raise ValueError("invalid_source_sha")
    if not re.fullmatch(r"[a-zA-Z0-9._-]{1,64}", version):
        raise ValueError("invalid_version")
    root, output_dir = Path(root), Path(output_dir)
    if not output_dir.is_dir():
        raise ValueError("output_directory_missing")
    files = {}
    for target, rel in FILES.items():
        path = root / rel
        if not path.is_file() or path.is_symlink():
            raise ValueError("missing_or_linked_input: " + rel)
        files[target] = path.read_bytes()
    for name in ("VirtualCarJ2534.dll", "VirtualCarControl.exe"):
        check_pe32(files[name])
    files["virtualcar.ini"] = diagnostic_profile(files["virtualcar-p2.ini"])
    buildinfo = {
        "format": "virtualcar-vmware-lab-v1",
        "source_commit": source_sha.lower(),
        "version": version,
        "architecture": "windows-x86-pe32",
        "profile": "synthetic_p2_read_only",
        "backend_telemetry_enabled": True,
        "vmware_e2e_verified": False,
        "ecu_identity_verified": False,
        "contains_private_vehicle_data": False,
        "two_phase_operator_collector_included": True,
        "operator_gui_acceptance_verified": False,
    }
    files["BUILDINFO.json"] = (json.dumps(buildinfo, indent=2, sort_keys=True) + "\n").encode()
    checksums = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())
    )
    files["SHA256SUMS.txt"] = checksums.encode("ascii")
    filename = "VirtualCar-VMware-LAB-" + version + "-Windows-x86.zip"
    target = output_dir / filename
    if target.exists():
        raise ValueError("release_zip_already_exists")
    with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            archive.writestr(PREFIX + "/" + name, data)
    sidecar = output_dir / (filename + ".sha256")
    sidecar.write_text(hashlib.sha256(target.read_bytes()).hexdigest()
                       + "  " + filename + "\n", encoding="ascii")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--version", required=True)
    args = parser.parse_args(argv)
    output = create_package(args.root, args.output_dir, args.source_sha, args.version)
    print(output.name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
