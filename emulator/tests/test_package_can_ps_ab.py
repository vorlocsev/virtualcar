"""Offline tests for synthetic, read-only CAN_PS API-outcome A/B package."""
import configparser
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

MOD = Path(__file__).resolve().parents[1] / "tools" / "package_can_ps_ab.py"
spec = importlib.util.spec_from_file_location("package_can_ps_ab", MOD)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
SHA = "a" * 40
BASE = """[Vehicle]
VIN=YV1CZ0002A0000001
ECUCount=1
[ECU0]
RequestId=7E0
ResponseId=7E8
[P2]
StrictRouting=1
[D2_40]
B9FBFrameCount=0
[D2_50]
B9FBFrameCount=0
[D2_50_B9F0]
FrameCount=0
[PassiveCAN]
Enabled=0
[PassiveTrace]
Enabled=0
"""


def fake_pe(machine=0x14C, magic=0x10B):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", data, 0x84, machine)
    struct.pack_into("<H", data, 0x98, magic)
    return bytes(data)


class CanPsABPackageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.work = root / "emulator"
        self.work.mkdir()
        self.bin = root / "VirtualCarJ2534.dll"
        self.bin.write_bytes(fake_pe())
        tool_dir = self.work / "tools"
        tool_dir.mkdir()
        (tool_dir / "Set-VirtualCarAB.ps1").write_text(
            "#Requires -RunAsAdministrator\n# VirtualCar-CANPS-AB-v1\n", encoding="utf-8")
        (self.work / "virtualcar-p2.ini").write_text(BASE, encoding="utf-8")
        self.output = root / "artifacts"
        self.output.mkdir()

    def build(self):
        return tool.create(self.work, self.bin, self.output, SHA)

    def test_01_exact_four_mode_folders_and_allowlisted_files(self):
        with zipfile.ZipFile(self.build()) as z:
            expected = {"BUILDINFO.json", "SHA256SUMS.txt", "README_RUN_RU.txt", "Set-VirtualCarAB.ps1"}
            for mode, label in tool.MODES:
                expected.add(label + "/virtualcar.ini")
                expected.add(label + "/VirtualCarJ2534.dll")
            self.assertEqual(set(z.namelist()), expected)
            self.assertFalse(any("private" in n.lower() or "dump" in n.lower() for n in expected))

    def test_02_identical_dll_and_only_one_variable_between_modes(self):
        with zipfile.ZipFile(self.build()) as z:
            profiles = {}
            dlls = []
            for mode, label in tool.MODES:
                dlls.append(z.read(label + "/VirtualCarJ2534.dll"))
                cfg = configparser.ConfigParser(interpolation=None)
                cfg.read_string(z.read(label + "/virtualcar.ini").decode())
                self.assertEqual(cfg.get("Diagnostics", "CanPsApiOutcomeMode"), str(mode))
                self.assertEqual(cfg.get("Diagnostics", "EnableCanPsConfigProbe"), "1")
                self.assertEqual(cfg.get("Diagnostics", "BackendTelemetryEnabled"), "1")
                cfg.set("Diagnostics", "CanPsApiOutcomeMode", "0")
                profiles[label] = {section: dict(cfg.items(section)) for section in cfg.sections()}
            self.assertEqual(len(set(dlls)), 1)
            self.assertEqual(len(set(json.dumps(p, sort_keys=True) for p in profiles.values())), 1)

    def test_03_no_private_vin_fixtures_or_synthetic_passive_traffic(self):
        with zipfile.ZipFile(self.build()) as z:
            for mode, label in tool.MODES:
                cfg = configparser.ConfigParser(interpolation=None)
                cfg.read_string(z.read(label + "/virtualcar.ini").decode())
                self.assertEqual(cfg.get("Vehicle", "VIN"), tool.SYNTHETIC_VIN)
                self.assertEqual(cfg.getint("Vehicle", "ECUCount"), 1)
                self.assertEqual(cfg.getint("Vehicle", "EmitIsoRxStart"), 1)
                self.assertEqual(cfg.getint("P2", "StrictRouting"), 1)
                for section in cfg.sections():
                    if section.startswith("D2_"):
                        self.assertEqual(cfg.getint(section, "FrameCount",
                                                     fallback=cfg.getint(section, "B9FBFrameCount", fallback=0)), 0)
                self.assertEqual(cfg.getint("PassiveCAN", "Enabled"), 0)
                self.assertEqual(cfg.getint("PassiveTrace", "Enabled"), 0)

    def test_04_per_file_checksums_and_build_provenance(self):
        target = self.build()
        with zipfile.ZipFile(target) as z:
            sums = z.read("SHA256SUMS.txt").decode().splitlines()
            self.assertEqual(len(sums), len(z.namelist()) - 1)
            for line in sums:
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)
            info = json.loads(z.read("BUILDINFO.json"))
            self.assertEqual(info["source_commit"], SHA)
            self.assertEqual(info["dll_sha256"], hashlib.sha256(fake_pe()).hexdigest())
            for key in ("contains_private_data", "ecu_identity_verified",
                        "vdash_e2e_verified", "actual_bus_tx_enabled", "release_published"):
                self.assertFalse(info[key])
        outer = Path(str(target) + ".sha256").read_text()
        self.assertTrue(outer.startswith(hashlib.sha256(target.read_bytes()).hexdigest() + "  "))

    def test_05_reject_non_x86_and_invalid_binaries(self):
        for data in (fake_pe(machine=0x8664, magic=0x20B), b"broken", fake_pe(magic=0x20B)):
            self.bin.write_bytes(data)
            with self.assertRaises(ValueError):
                self.build()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_06_reject_personal_or_enabled_replay_profiles(self):
        source = self.work / "virtualcar-p2.ini"
        variants = [
            BASE.replace(tool.SYNTHETIC_VIN, "PERSONAL_VIN_VALUE"),
            BASE.replace("ECUCount=1", "ECUCount=2"),
            BASE.replace("StrictRouting=1", "StrictRouting=0"),
            BASE.replace("B9FBFrameCount=0", "B9FBFrameCount=1", 1),
            BASE.replace("[PassiveCAN]\nEnabled=0", "[PassiveCAN]\nEnabled=1"),
            BASE + "\n[Diagnostics]\nEnableCanPsConfigProbe=1\n",
            BASE + "\n[ECU1]\nRequestId=726\n",
        ]
        for content in variants:
            source.write_text(content)
            with self.assertRaises(ValueError, msg=content[:45]):
                self.build()
        self.assertEqual(list(self.output.iterdir()), [])

    def test_07_fails_closed_no_overwrite_or_source_mutation(self):
        original = (self.work / "virtualcar-p2.ini").read_bytes()
        self.build()
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual((self.work / "virtualcar-p2.ini").read_bytes(), original)
        with self.assertRaises(ValueError):
            tool.create(self.work, self.bin, self.output, "short")

    def test_08_disabled_modes_require_exact_allowlist(self):
        for mode in (-1, 4, 999):
            with self.assertRaises(ValueError):
                tool.canonical_profile(mode)
        self.assertIn("CanPsApiOutcomeMode=0", tool.canonical_profile(0).decode())
        self.assertIn("CanPsApiOutcomeMode=3", tool.canonical_profile(3).decode())
        self.assertNotIn("VIN=PERSONAL", tool.canonical_profile(0).decode())


if __name__ == "__main__":
    unittest.main()
