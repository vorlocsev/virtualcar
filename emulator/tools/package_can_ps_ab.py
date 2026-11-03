#!/usr/bin/env python3
"""Create four isolated, synthetic CAN_PS API-only Windows x86 LAB folders.

No physical adapter, ECU traffic, private VIN or real vehicle configuration.
This artifact is for explicitly approved local VDASH A/B observation, not a release.
"""
import argparse
import configparser
import hashlib
import json
from pathlib import Path
import re
import stat
import struct
import zipfile

SYNTHETIC_VIN = "YV1CZ0002A0000001"
MODES = ((0, "CONTROL"), (1, "A_FILTER"), (2, "B_D8_WRITE"), (3, "C_D8_PERIODIC"))
PACKAGE_NAME = "VirtualCar-CANPS-AB-Windows-x86-LAB"
README = """VIRTUAL CAR CAN_PS API-ONLY A/B, SYNTHETIC XC90 P2 MY2005

This is an experimental Windows x86 J2534 DLL, NOT a CAN_PS transport.
All four directories contain byte-identical DLLs and the same synthetic
vehicle profile. Only CanPsApiOutcomeMode differs:
  CONTROL/      0: baseline, existing rejections
  A_FILTER/     1: PASS_FILTER-only API success
  B_D8_WRITE/   2: exact D8 WriteMsgs API success (no bus TX)
  C_D8_PERIODIC/3: exact D8 1000 ms registration (no firing)

Do not use with a physical adapter or actual ECU. No real VIN/CEM/flash data.
Do not call an API-only success a CAN TX, received ECU response, or successful
vehicle detection.

Local workflow:
1. Read BUILDINFO.json and verify SHA256SUMS.txt against extracted files.
2. Keep original Virtual Car installation/registered adapter untouched.
3. Close VDASH and its worker before *each* run. Register/select ONLY that
   run's virtual DLL in the 32-bit J2534 list, never a physical adapter.
4. Record DLL SHA-256 and actual loaded-module path/hash, client version and
   synthetic MY2005 profile. Re-run bounded automatic vehicle discovery.
5. Record GUI result, presence of CEM/ECM in list, warning text, and ordered
   J2534 metadata from a fresh log suffix. Keep raw logs and VIN locally.
6. Stop VDASH, confirm all workers exited, then change the registered LAB DLL
   to the next folder; avoid comparing cumulative counts across runs.
7. Remove only your LAB registration when finished; restore original
   client adapter selection. Do not overwrite the existing J2534 adapter.

For optional registration run PowerShell as Administrator with an explicit mode:
  .\Set-VirtualCarAB.ps1 -Mode CONTROL
  .\Set-VirtualCarAB.ps1 -Mode A_FILTER
  .\Set-VirtualCarAB.ps1 -Mode B_D8_WRITE
  .\Set-VirtualCarAB.ps1 -Mode C_D8_PERIODIC
  .\Set-VirtualCarAB.ps1 -Remove
This script touches ONLY a dedicated 32-bit J2534 LAB entry, checks ownership
and DLL digest, and refuses known active VDASH processes. It does not choose an
adapter in VDASH, run VDASH, or touch other registered adapters.
It never runs automatically. Registration requires explicit user action.
Windows x86 and host CI tests are not VDASH GUI acceptance tests.
"""
BASE_VEHICLE = """[Vehicle]
VIN=YV1CZ0002A0000001
BatteryMv=12500
EmitIsoRxStart=1
ECUCount=1

[ECU0]
RequestId=7E0
ResponseId=7E8
PartNumber=VIRTUAL-ECU
Software=SIM-1.0

[P2]
StrictRouting=1
ReplaySpacingMs=12

[D2_40]
ResponseId=00800003
B9FBFrameCount=0

[D2_50]
ResponseId=01200003
B9FBFrameCount=0

[D2_40_B9F0]
FrameCount=0

[D2_50_B9F0]
FrameCount=0

[D2_40_B9FC]
FrameCount=0

[D2_50_B9FC]
FrameCount=0

[PassiveCAN]
Enabled=0

[PassiveTrace]
Enabled=0
Count=0

"""


def check_pe32(data):
    if len(data) < 256 or data[:2] != b"MZ":
        raise ValueError("invalid_pe_binary")
    offset = struct.unpack_from("<I", data, 0x3C)[0]
    if offset > len(data) - 26 or data[offset:offset + 4] != b"PE\0\0":
        raise ValueError("invalid_pe_signature")
    if struct.unpack_from("<H", data, offset + 4)[0] != 0x014C:
        raise ValueError("binary_not_x86")
    if struct.unpack_from("<H", data, offset + 24)[0] != 0x010B:
        raise ValueError("binary_not_pe32")


def check_source_profile(raw):
    cfg = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        cfg.read_string(raw.decode("utf-8-sig"))
    except (UnicodeError, configparser.Error) as exc:
        raise ValueError("invalid_source_profile") from exc
    if cfg.get("Vehicle", "VIN", fallback=None) != SYNTHETIC_VIN:
        raise ValueError("non_synthetic_vin")
    if cfg.getint("Vehicle", "ECUCount", fallback=-1) != 1:
        raise ValueError("extra_ecu")
    if cfg.getint("P2", "StrictRouting", fallback=0) != 1:
        raise ValueError("non_strict_p2")
    if cfg.get("ECU0", "RequestId", fallback="").upper() != "7E0":
        raise ValueError("ecm_route_changed")
    if cfg.get("ECU0", "ResponseId", fallback="").upper() != "7E8":
        raise ValueError("ecm_route_changed")
    for section in cfg.sections():
        if section.startswith("D2_"):
            for name in ("FrameCount", "B9FBFrameCount"):
                if cfg.has_option(section, name) and cfg.getint(section, name) != 0:
                    raise ValueError("enabled_vehicle_fixture")
        if section.startswith("D2_Node") and cfg.getint(section, "Enabled", fallback=0):
            raise ValueError("enabled_d2_extra_node")
        if section.startswith("ECU") and section != "ECU0":
            raise ValueError("extra_ecu")
    for section in ("PassiveCAN", "PassiveTrace"):
        if cfg.getint(section, "Enabled", fallback=0) != 0:
            raise ValueError("passive_signal_enabled")
    if cfg.has_section("Diagnostics"):
        raise ValueError("unexpected_diag_opt_in_in_source")


def canonical_profile(mode):
    if mode not in dict(MODES):
        raise ValueError("unsupported_mode")
    return (BASE_VEHICLE + "[Diagnostics]\n"
            + "BackendTelemetryEnabled=1\n"
            + "EnableCanPsConfigProbe=1\n"
            + f"CanPsApiOutcomeMode={mode}\n").encode("ascii")


def create(root, dll_path, out_dir, source_sha):
    root, dll_path, out_dir = Path(root), Path(dll_path), Path(out_dir)
    if not re.fullmatch(r"[a-fA-F0-9]{40}", source_sha):
        raise ValueError("invalid_source_commit")
    if not out_dir.is_dir() or out_dir.is_symlink():
        raise ValueError("invalid_output_dir")
    src_profile = root / "virtualcar-p2.ini"
    if not src_profile.is_file() or src_profile.is_symlink():
        raise ValueError("source_profile_not_regular")
    if not dll_path.is_file() or dll_path.is_symlink():
        raise ValueError("dll_not_regular")
    check_source_profile(src_profile.read_bytes())
    dll = dll_path.read_bytes()
    check_pe32(dll)
    register_script = root / "tools" / "Set-VirtualCarAB.ps1"
    if not register_script.is_file() or register_script.is_symlink():
        raise ValueError("lab_selector_not_regular")
    script_data = register_script.read_bytes()
    if b"VirtualCar-CANPS-AB-v1" not in script_data:
        raise ValueError("invalid_lab_selector")
    files = {"Set-VirtualCarAB.ps1": script_data}
    for mode, label in MODES:
        prefix = f"{label}/"
        files[prefix + "VirtualCarJ2534.dll"] = dll
        files[prefix + "virtualcar.ini"] = canonical_profile(mode)
    info = {
        "format": "virtualcar-canps-api-only-ab-v1",
        "source_commit": source_sha.lower(),
        "dll_sha256": hashlib.sha256(dll).hexdigest(),
        "architecture": "windows-x86-pe32",
        "synthetic_profile": "P2_MY2005_one_ECM_no_CEM_fixtures",
        "mode_directories": {label: mode for mode, label in MODES},
        "release_published": False,
        "vdash_e2e_verified": False,
        "ecu_identity_verified": False,
        "contains_private_data": False,
        "actual_bus_tx_enabled": False,
    }
    files["README_RUN_RU.txt"] = (
        "Virtual Car: CAN_PS A/B. Синтетический автомобиль, без физических ECU.\n\n"
        "CONTROL = 0; A_FILTER = 1; B_D8_WRITE = 2; C_D8_PERIODIC = 3.\n"
        "Все четыре DLL идентичны. Перед сменой режима завершите VDASH.\n"
        "Выберите только виртуальную DLL соответствующего каталога.\n"
        "Журналы и VIN не публикуйте. Это имитация результата J2534 API,\n"
        "не доказательство CAN-обмена или успешного обнаружения блоков.\n\n"
        + README
    ).encode("utf-8")
    files["BUILDINFO.json"] = (json.dumps(info, indent=2, sort_keys=True) + "\n").encode("utf-8")
    files["SHA256SUMS.txt"] = "".join(
        hashlib.sha256(data).hexdigest() + "  " + name + "\n"
        for name, data in sorted(files.items())
    ).encode("ascii")
    filename = f"{PACKAGE_NAME}-{source_sha[:12].lower()}.zip"
    dest = out_dir / filename
    if dest.exists():
        raise ValueError("archive_already_exists")
    with zipfile.ZipFile(dest, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
    sidecar = out_dir / (filename + ".sha256")
    sidecar.write_text(hashlib.sha256(dest.read_bytes()).hexdigest()
                       + "  " + filename + "\n", encoding="ascii")
    return dest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--dll", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--source-sha", required=True)
    args = parser.parse_args(argv)
    print(create(args.root, args.dll, args.out_dir, args.source_sha).name)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
