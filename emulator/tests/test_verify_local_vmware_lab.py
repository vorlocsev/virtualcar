"""Synthetic tampering tests for actual LAB ZIP integrity verifier."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"


def import_tool(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


package = import_tool("package_vmware_lab")
verify = import_tool("verify_local_vmware_lab")
SHA = "9" * 40
PROFILE = """[Vehicle]
VIN=YV1CZ0002A0000001
ECUCount=1
[P2]
StrictRouting=1
[D2_40]
B9FBFrameCount=0
[D2_50]
B9FBFrameCount=0
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


class LocalRealLabVerifierTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "input"
        self.out = Path(temp.name) / "private-output"
        self.root.mkdir()
        self.out.mkdir()
        for rel in package.FILES.values():
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(fake_pe() if path.suffix in (".dll", ".exe")
                             else b"synthetic local-only fixture\n")
        (self.root / "virtualcar-p2.ini").write_text(PROFILE, encoding="utf-8")
        self.zip = package.create_package(self.root, self.out, SHA, "test-bundle")

    def _rewrite_zip(self, change, *, resums=True, resha=True):
        with zipfile.ZipFile(self.zip) as archive:
            members = {
                item.filename.split(package.PREFIX + "/", 1)[1]:
                archive.read(item) for item in archive.infolist()
            }
        change(members)
        if resums:
            members["SHA256SUMS.txt"] = "".join(
                hashlib.sha256(data).hexdigest() + "  " + name + "\n"
                for name, data in sorted(members.items())
                if name != "SHA256SUMS.txt"
            ).encode("ascii")
        with zipfile.ZipFile(self.zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, data in sorted(members.items()):
                archive.writestr(package.PREFIX + "/" + name, data)
        if resha:
            sidecar = Path(str(self.zip) + ".sha256")
            sidecar.write_text(
                hashlib.sha256(self.zip.read_bytes()).hexdigest() + "  " +
                self.zip.name + "\n", encoding="ascii"
            )

    def test_01_package_from_synthetic_x86_fixture_is_verified(self):
        self.assertTrue(verify.verify_local_lab(self.zip, self.root, SHA))
        self.assertEqual(verify.main([
            "--archive", str(self.zip), "--source-root", str(self.root),
            "--source-sha", SHA]), 0)

    def test_02_refuse_wrong_git_commit_even_with_valid_zip(self):
        with self.assertRaises(ValueError):
            verify.verify_local_lab(self.zip, self.root, "a" * 40)
        with self.assertRaises(ValueError):
            verify.verify_local_lab(self.zip, self.root, "not-a-commit")

    def test_03_refuse_corrupted_outer_zip_and_sidecar(self):
        sidecar = Path(str(self.zip) + ".sha256")
        sidecar.write_text("0" * 64 + "  " + self.zip.name, encoding="ascii")
        with self.assertRaises(ValueError):
            verify.verify_local_lab(self.zip, self.root, SHA)
        sidecar.unlink()
        with self.assertRaises(ValueError):
            verify.verify_local_lab(self.zip, self.root, SHA)

    def test_04_reject_modified_j2534_dll_even_when_checksums_repaired(self):
        def modify(members):
            members["VirtualCarJ2534.dll"] += b"untrusted addendum"
        self._rewrite_zip(modify)
        with self.assertRaisesRegex(ValueError, "differs from source"):
            verify.verify_local_lab(self.zip, self.root, SHA)

    def test_05_reject_claimed_vmware_or_vin_acceptance_in_buildinfo(self):
        def modify(members):
            info = json.loads(members["BUILDINFO.json"])
            info["vmware_e2e_verified"] = True
            info["operator_gui_acceptance_verified"] = True
            members["BUILDINFO.json"] = json.dumps(info).encode("utf-8")
        self._rewrite_zip(modify)
        with self.assertRaisesRegex(ValueError, "manifest"):
            verify.verify_local_lab(self.zip, self.root, SHA)

    def test_06_reject_private_or_non_synthetic_vehicle_profile(self):
        def modify(members):
            members["virtualcar.ini"] = members["virtualcar.ini"].replace(
                b"YV1CZ0002A0000001", b"PRIVATE-UNKNOWN-VIN"
            )
        self._rewrite_zip(modify)
        with self.assertRaisesRegex(ValueError, "profile"):
            verify.verify_local_lab(self.zip, self.root, SHA)

    def test_07_reject_unknown_or_missing_zip_files(self):
        def extra(members):
            members["private-donor.ini"] = b"SECRET"
        self._rewrite_zip(extra)
        with self.assertRaisesRegex(ValueError, "unknown paths"):
            verify.verify_local_lab(self.zip, self.root, SHA)

    def test_08_reject_changed_pe_architecture_even_if_rebuilt_checksums_and_sources(self):
        new_exe = fake_pe(machine=0x8664, magic=0x020B)
        (self.root / "VirtualCarControl.exe").write_bytes(new_exe)
        def modify(members):
            members["VirtualCarControl.exe"] = new_exe
        self._rewrite_zip(modify)
        with self.assertRaisesRegex(ValueError, "not_windows_x86_pe32"):
            verify.verify_local_lab(self.zip, self.root, SHA)


if __name__ == "__main__":
    unittest.main()
