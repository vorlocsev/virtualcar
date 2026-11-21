"""Eight offline regression gates for separately staged CEM50 J2534 adapter.

All VINs and binaries are fabricated. No Windows registry, VIDA or hardware.
"""
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import prepare_j2534_cem50_adapter as prepare
from audit_vida_b3a54_private_b9fb_vin import _get, _ini, _read_b9fb
sys.path.pop(0)

SYNTHETIC_VIN = "YV1CZ0003A0000002"


def fake_pe32(machine=0x014C, magic=0x010B):
    blob = bytearray(1024)
    blob[0:2] = b"MZ"
    struct.pack_into("<I", blob, 0x3C, 0x80)
    blob[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<H", blob, 0x84, machine)
    struct.pack_into("<H", blob, 0x98, magic)
    return bytes(blob)


class Cem50AdapterStagingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dll = self.root / "test-x86.dll"
        self.dll.write_bytes(fake_pe32())
        self.sha = hashlib.sha256(self.dll.read_bytes()).hexdigest()
        self.identity = self.root / "vehicle-identity.json"
        self.identity.write_text(
            json.dumps({"Vehicle": {"VIN": SYNTHETIC_VIN, "ModelYear": 2009}}),
            encoding="utf-8")
        self.destination = self.root / "isolated"

    def invoke(self):
        return prepare.stage(self.dll, self.identity, self.destination, self.sha)

    def test_01_stage_creates_independent_dll_ini_and_installer(self):
        manifest = self.invoke()
        self.assertEqual(manifest["adapter_display_name"], "J2534 CEM50 B9FB")
        self.assertTrue((self.destination / prepare.DLL_NAME).is_file())
        self.assertTrue((self.destination / "virtualcar.ini").is_file())
        self.assertTrue((self.destination / "install_j2534_cem50_adapter.ps1").is_file())
        self.assertEqual((self.destination / prepare.DLL_NAME).read_bytes(), self.dll.read_bytes())
        self.assertEqual(manifest["dll_sha256"], self.sha)

    def test_02_exact_17_byte_vin_in_all_thirteen_cem50_frames(self):
        self.invoke()
        cfg = _ini((self.destination / "virtualcar.ini").read_text(encoding="utf-8"))
        self.assertEqual(_get(cfg, "Vehicle", "VIN"), SYNTHETIC_VIN)
        self.assertEqual(_get(cfg, "Vehicle", "ModelYear"), "2009")
        status, count, frames = _read_b9fb(cfg)
        self.assertEqual((status, count),
                         ("declared_frame_values_loaded_locally", 13))
        stream = b"".join(data[1:] for _, data in frames)
        self.assertEqual(stream[:3], bytes.fromhex("50 F9 FB"))
        self.assertEqual(stream[14:31], SYNTHETIC_VIN.encode("ascii"))

    def test_03_no_extra_cem40_or_identification_fixture(self):
        self.invoke()
        cfg = _ini((self.destination / "virtualcar.ini").read_text(encoding="utf-8"))
        self.assertEqual(_get(cfg, "P2", "StrictRouting"), "1")
        self.assertEqual(_get(cfg, "D2_40", "B9FBFrameCount"), "0")
        for key in ("D2_40_B9F0", "D2_50_B9F0", "D2_40_B9FC", "D2_50_B9FC"):
            self.assertEqual(_get(cfg, key, "FrameCount"), "0")

    def test_04_manifest_private_vin_not_committed_or_logged(self):
        self.invoke()
        manifest = (self.destination / "adapter_manifest.json").read_text(encoding="utf-8")
        installer = (self.destination / "install_j2534_cem50_adapter.ps1").read_text()
        self.assertNotIn(SYNTHETIC_VIN, manifest)
        self.assertNotIn(SYNTHETIC_VIN, installer)
        self.assertFalse(json.loads(manifest)["registration_applied"])
        self.assertNotIn("Virtual", json.loads(manifest)["adapter_display_name"])

    def test_05_wrong_sha_or_bad_digest_rejected_without_output(self):
        for digest in ("x" * 64, "deadbeef"):
            with self.subTest(digest=digest):
                with self.assertRaises(ValueError):
                    prepare.stage(self.dll, self.identity, self.destination, digest)
                self.assertFalse(self.destination.exists())

    def test_06_x64_or_non_pe_binary_rejected(self):
        for blob in (fake_pe32(machine=0x8664, magic=0x020B), b"not a dll"):
            with self.subTest(size=len(blob)):
                self.dll.write_bytes(blob)
                digest = hashlib.sha256(blob).hexdigest()
                with self.assertRaises(ValueError):
                    prepare.stage(self.dll, self.identity, self.destination, digest)
                self.assertFalse(self.destination.exists())

    def test_07_existing_target_never_overwritten(self):
        self.destination.mkdir()
        sentinel = self.destination / "keep.txt"
        sentinel.write_text("do not overwrite")
        with self.assertRaises(ValueError):
            self.invoke()
        self.assertEqual(sentinel.read_text(), "do not overwrite")

    def test_08_invalid_identity_or_wrong_year_rejected_without_files(self):
        for value in (
            {"VIN": SYNTHETIC_VIN, "ModelYear": 2010},
            {"VIN": "BAD", "ModelYear": 2009},
            {"Vehicle": {"VIN": SYNTHETIC_VIN, "ModelYear": 2009},
             "Identity": {"VIN": SYNTHETIC_VIN, "ModelYear": 2009}},
        ):
            with self.subTest(value=list(value)):
                self.identity.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.invoke()
                self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
