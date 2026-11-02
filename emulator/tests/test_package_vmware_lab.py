"""VMware distribution safety, architecture, fidelity and privacy gates."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

MODULE = Path(__file__).resolve().parents[1] / "tools" / "package_vmware_lab.py"
spec = importlib.util.spec_from_file_location("package_vmware_lab", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
COMMIT = "a" * 40
PROFILE = """[Vehicle]
VIN=YV1CZ0002A0000001
ECUCount=1
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


def fake_pe(machine=0x014C, magic=0x010B):
    data = bytearray(512)
    data[:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, 0x80)
    data[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", data, 0x84, machine)
    struct.pack_into("<H", data, 0x98, magic)
    return bytes(data)


class VMwarePackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "emulator"
        self.out = Path(self.temp.name) / "out"
        self.root.mkdir()
        self.out.mkdir()
        for rel in tool.FILES.values():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            content = fake_pe() if path.suffix in (".exe", ".dll") else b"BENCH ONLY\n"
            path.write_bytes(content)
        (self.root / "virtualcar-p2.ini").write_text(PROFILE, encoding="utf-8")

    def build(self):
        return tool.create_package(self.root, self.out, COMMIT, "vmware-lab-test")

    def test_01_whitelisted_contents_only(self):
        with zipfile.ZipFile(self.build()) as z:
            expected = set(tool.FILES) | {"virtualcar.ini", "BUILDINFO.json", "SHA256SUMS.txt"}
            self.assertEqual(set(z.namelist()), {tool.PREFIX + "/" + name for name in expected})
            # Read-only J2534 preflight must actually be usable from unpacked LAB.
            self.assertIn(tool.PREFIX + "/tools/audit_j2534_connect.py", z.namelist())
            self.assertIn(tool.PREFIX + "/README_P3TOOL_J2534_PREFLIGHT_RU.md", z.namelist())
            self.assertFalse(any("private" in path.lower() or "dump" in path.lower()
                                 for path in z.namelist()))

    def test_02_p2_strict_default_and_metadata_enabled(self):
        with zipfile.ZipFile(self.build()) as z:
            active = z.read(tool.PREFIX + "/virtualcar.ini").decode("utf-8")
            self.assertIn("[Diagnostics]\nBackendTelemetryEnabled=1", active)
            self.assertIn("StrictRouting=1", active)
            self.assertIn("ECUCount=1", active)
            self.assertIn("B9FBFrameCount=0", active)
            self.assertNotIn("DIDF1B0Hex=", active)

    def test_03_archive_checksums_match_all_entries(self):
        with zipfile.ZipFile(self.build()) as z:
            checks = z.read(tool.PREFIX + "/SHA256SUMS.txt").decode("ascii").splitlines()
            self.assertEqual(len(checks), len(z.namelist()) - 1)
            for line in checks:
                digest, name = line.split("  ", 1)
                self.assertEqual(hashlib.sha256(z.read(tool.PREFIX + "/" + name)).hexdigest(), digest)

    def test_04_outer_checksum_and_source_traceability(self):
        path = self.build()
        line = Path(str(path) + ".sha256").read_text(encoding="ascii")
        self.assertTrue(line.startswith(hashlib.sha256(path.read_bytes()).hexdigest() + "  "))
        with zipfile.ZipFile(path) as z:
            info = json.loads(z.read(tool.PREFIX + "/BUILDINFO.json"))
            self.assertEqual(info["source_commit"], COMMIT)
            self.assertFalse(info["vmware_e2e_verified"])
            self.assertFalse(info["ecu_identity_verified"])
            self.assertTrue(info["backend_telemetry_enabled"])

    def test_05_reject_x64_and_invalid_pe_without_output(self):
        for binary in ("VirtualCarJ2534.dll", "VirtualCarControl.exe"):
            for data in (fake_pe(machine=0x8664, magic=0x020B), b"bad"):
                (self.root / binary).write_bytes(data)
                with self.assertRaises(ValueError):
                    self.build()
                self.assertEqual(list(self.out.iterdir()), [])
                (self.root / binary).write_bytes(fake_pe())

    def test_06_reject_private_vehicle_and_active_d2_fixture(self):
        path = self.root / "virtualcar-p2.ini"
        for profile in (PROFILE.replace(tool.SYNTHETIC_VIN, "PRIVATE_IDENTIFIER"),
                        PROFILE.replace("B9FBFrameCount=0", "B9FBFrameCount=1", 1),
                        PROFILE.replace("StrictRouting=1", "StrictRouting=0"),
                        PROFILE.replace("[PassiveTrace]\nEnabled=0", "[PassiveTrace]\nEnabled=1")):
            path.write_text(profile, encoding="utf-8")
            with self.assertRaises(ValueError):
                self.build()
        self.assertEqual(list(self.out.iterdir()), [])

    def test_07_no_overwrite_and_no_source_mutation(self):
        source = self.root / "virtualcar-p2.ini"
        before = source.read_bytes()
        self.build()
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(source.read_bytes(), before)
        self.assertEqual(len(list(self.out.glob("*.zip"))), 1)

    def test_08_missing_input_invalid_sha_and_symlink_fail_closed(self):
        with self.assertRaises(ValueError):
            tool.create_package(self.root, self.out, "bad", "vmware-lab-test")
        required = self.root / "scripts" / "install.ps1"
        required.unlink()
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(list(self.out.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
