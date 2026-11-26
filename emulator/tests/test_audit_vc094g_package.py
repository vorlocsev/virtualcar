"""Synthetic distribution integrity checks; no real private data or executable use."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vc094g_package as audit

HEAD = "a" * 40


def pe(machine=0x8664, magic=0x20b):
    data = bytearray(128)
    data[:2] = b"MZ"
    data[60:64] = (64).to_bytes(4, "little")
    data[64:68] = b"PE\0\0"
    data[68:70] = machine.to_bytes(2, "little")
    data[88:90] = magic.to_bytes(2, "little")
    return bytes(data)


class PackageChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "VirtualCar"
        self.root.mkdir()
        self.emulator = Path(self.temp.name) / "source"
        self.emulator.mkdir()
        self.native = pe(0x14c, 0x10b)
        self.native_sha = audit.digest(self.native)
        self.base = []
        self.files = []
        for name in sorted(audit.RUNTIME):
            raw = pe() if name.endswith((".exe", ".dll")) else b"synthetic runtime"
            self.put(name, raw)
            self.base.append(self.row("VirtualCar.WinUI.exe" if name == "VirtualCar.exe" else name, raw))
        profiles = []
        for ident, source in audit.PROFILES.items():
            raw = ("synthetic profile " + ident).encode()
            (self.emulator / source).write_bytes(raw)
            self.add_profile(ident, raw)
            profiles.append(dict(id=ident, profile_sha256=audit.digest(raw), native_sha256=self.native_sha,
                                 scope="synthetic_or_historical_demo"))
        self.build = dict(schema="vc075-winui-build-v1", source_sha=HEAD, publish="pass",
                          platform="win-x64", files=self.base)
        self.manifest = dict(schema="vc094a-package-v1", source_sha=HEAD, native_sha256=self.native_sha,
                             profiles=profiles, files=self.files, private_profile_included=False,
                             artwork="skipped", original_vida="not_tested", physical_j2534="not_tested",
                             registration="not_tested", package_ui="not_tested")

    @staticmethod
    def row(name, raw):
        return dict(path=name, bytes=len(raw), sha256=audit.digest(raw))

    def put(self, name, raw):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        self.files.append(self.row(name, raw))

    def add_profile(self, ident, raw):
        prefix = "vehicle-data/" + ident + "/"
        self.put(prefix+"virtualcar.ini", raw)
        self.put(prefix+"VirtualCarJ2534.dll", self.native)
        self.put(prefix+"candidate.sha256", self.native_sha.encode())

    def verify(self):
        return audit.verify(self.root, self.manifest, self.build, HEAD, self.emulator)

    def test_01_full_demo_and_zip_roundtrip(self):
        expected, private = self.verify()
        self.assertFalse(private)
        output = self.root.parent / "demo.zip"
        self.assertEqual(audit.archive(self.root, expected, private, output), audit.digest_file(output))
        with zipfile.ZipFile(output) as z:
            self.assertEqual(set(z.namelist()), {"VirtualCar/"+n for n in expected})
        with self.assertRaises(FileExistsError):
            audit.archive(self.root, expected, private, output)

    def test_02_exact_head_and_publish_bytes(self):
        self.build["source_sha"] = "b"*40
        with self.assertRaises(ValueError):
            self.verify()
        self.build["source_sha"] = HEAD
        row = next(r for r in self.base if r["path"] == "VirtualCar.WinUI.exe")
        row["sha256"] = "0"*64
        with self.assertRaises(ValueError):
            self.verify()

    def test_03_missing_extra_and_changed_files(self):
        path = self.root / "VirtualCar.exe"
        original = path.read_bytes()
        path.unlink()
        with self.assertRaises(ValueError):
            self.verify()
        path.write_bytes(original)
        (self.root / "unexpected.txt").write_text("unexpected")
        with self.assertRaises(ValueError):
            self.verify()
        (self.root / "unexpected.txt").unlink()
        path.write_bytes(original + b"modified")
        with self.assertRaises(ValueError):
            self.verify()

    def test_04_reject_path_and_case_aliases(self):
        for name in ("../evil", "/root", "a//b", "C:ads", "a\\b", "AUX.dll", "a."):
            with self.assertRaises(ValueError):
                audit.safe_name(name)
        with self.assertRaises(ValueError):
            audit.inventory([self.row("A.dll", b"x"), self.row("a.DLL", b"x")])
        with self.assertRaises(ValueError):
            audit.parse(b'{"a":1,"a":2}')

    def test_05_native_and_tracked_profile_integrity(self):
        report = dict(schema="vc090-native-preflight-v1", status="pass", failed_stage="",
                      source_sha=HEAD, native_dll_sha256=self.native_sha, native_dll_bytes=len(self.native),
                      gates=dict.fromkeys(("source_and_managed_inventory", "fresh_native_build",
                          "x86_export_contract", "native_silence_and_evidence", "synthetic_identity_replay",
                          "can_ms_lifecycle", "registry32_preflight", "final_integrity"), "pass"),
                      **dict.fromkeys(("registration_install_remove", "vida_provider_selection",
                          "vida_loaded_module_identity", "vida_readvin", "vida_t111", "vida_t122",
                          "physical_j2534"), "not_tested"))
        audit.verify_preflight(report, self.manifest, HEAD)
        report["gates"]["final_integrity"] = "fail"
        with self.assertRaises(ValueError):
            audit.verify_preflight(report, self.manifest, HEAD)
        report["gates"]["final_integrity"] = "pass"
        report["native_dll_bytes"] += 1
        with self.assertRaises(ValueError):
            audit.verify_preflight(report, self.manifest, HEAD)
        with self.assertRaises(ValueError):
            audit.pe(pe(), 0x14c, 0x10b)
        path = self.emulator / audit.PROFILES["p2"]
        original = path.read_bytes()
        path.write_bytes(b"wrong tracked profile")
        with self.assertRaises(ValueError):
            self.verify()
        path.write_bytes(original)
        self.manifest["profiles"][0]["native_sha256"] = "0"*64
        with self.assertRaises(ValueError):
            self.verify()

    def test_06_artwork_scope_and_sidecars(self):
        self.manifest["artwork"] = "two_reference_photos"
        with self.assertRaises(ValueError):
            self.verify()
        for name in ("xc90-v8", "p2-reference"):
            raw = b"synthetic artwork bytes"
            self.put("artwork/"+name+".jpg", raw)
            self.put("artwork/"+name+".sha256", audit.digest(raw).encode())
        self.put("artwork/credits.txt", b"synthetic attribution")
        self.verify()
        (self.root / "artwork/xc90-v8.sha256").write_bytes(b"0"*64)
        with self.assertRaises(ValueError):
            self.verify()

    def test_07_private_scope_no_public_zip(self):
        ident = audit.PRIVATE
        raw = b"synthetic private fixture"
        self.add_profile(ident, raw)
        prefix = "vehicle-data/" + ident + "/"
        local = dict(schema="vc094d2-local-profile-v3", native_sha256=self.native_sha,
                     profile_sha256=audit.digest(raw))
        for key, file in (("catalog_sha256", "configuration.json"), ("options_sha256", "configuration-options.json"),
                          ("references_sha256", "configuration-references.json")):
            payload = file.encode()
            self.put(prefix+file, payload)
            local[key] = audit.digest(payload)
        self.put(prefix+"local-profile.json", json.dumps(local).encode())
        self.manifest["private_profile_included"] = True
        self.manifest["profiles"].append(dict(id=ident, profile_sha256=audit.digest(raw),
                                             native_sha256=self.native_sha, scope="owner_local_private"))
        expected, private = self.verify()
        self.assertTrue(private)
        output = self.root.parent / "private.zip"
        with self.assertRaises(ValueError):
            audit.archive(self.root, expected, private, output)
        self.assertFalse(output.exists())
        self.manifest["private_profile_included"] = False
        with self.assertRaises(ValueError):
            self.verify()

    def test_08_no_runtime_claim_and_archive_source_change(self):
        self.manifest["original_vida"] = "pass"
        with self.assertRaises(ValueError):
            self.verify()
        self.manifest["original_vida"] = "not_tested"
        expected, private = self.verify()
        (self.root / "VirtualCar.exe").write_bytes(b"changed")
        output = self.root.parent / "demo.zip"
        with self.assertRaises(ValueError):
            audit.archive(self.root, expected, private, output)
        self.assertFalse(output.exists())
        self.assertFalse(list(output.parent.glob(".vc094g-*")))
        (self.root / "VirtualCar.exe").write_bytes(pe())
        (self.root / "unexpected.txt").write_bytes(b"unexpected")
        with self.assertRaises(ValueError):
            audit.archive(self.root, expected, private, output)
        self.assertFalse(output.exists())
        (self.root / "unexpected.txt").unlink()
        output.write_bytes(b"existing")
        with self.assertRaises(FileExistsError):
            audit.archive(self.root, expected, private, output)
        self.assertEqual(output.read_bytes(), b"existing")


if __name__ == "__main__":
    unittest.main()
