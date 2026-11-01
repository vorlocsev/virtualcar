"""Synthetic PE header fixtures only; no proprietary binaries or vehicle data."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "package_proxy_lab", Path(__file__).resolve().parents[1] / "scripts/package_proxy_lab.py")
lab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lab)
COMMIT = "1234567890abcdef1234567890abcdef12345678"


class PackageLabTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(__file__).resolve().parents[1] / "_build" / "package-tests"
        self.base.mkdir(parents=True, exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=self.base)
        self.root = Path(self.tmp.name)
        self.addCleanup(self.cleanup_tmp)
        self.output = self.root / "out"
        data = bytearray(160)
        data[:2] = b"MZ"
        struct.pack_into("<I", data, 0x3C, 64)
        data[64:68] = b"PE\0\0"
        struct.pack_into("<H", data, 68, 0x14C)
        struct.pack_into("<H", data, 88, 0x10B)
        for relative in lab.BINARY_INPUTS + lab.DOC_INPUTS:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data if relative in lab.BINARY_INPUTS else b"Synthetic lab instructions\n")

    def cleanup_tmp(self):
        # TemporaryDirectory recursively removes its tree: first verify that
        # the resolved target stays in this test's workspace output directory.
        self.assertTrue(self.root.resolve().is_relative_to(self.base.resolve()))
        self.tmp.cleanup()

    def test_exact_allowlist_and_hash_manifest(self):
        result = lab.package(self.root, self.output, COMMIT)
        expected = {Path(p).name for p in lab.BINARY_INPUTS + lab.DOC_INPUTS}
        self.assertEqual({p.name for p in self.output.iterdir()}, expected | {"manifest.json"})
        self.assertEqual(result["build_commit"], COMMIT)
        self.assertFalse(result["original_dll_included"])
        self.assertEqual(result["vehicle_validation"], "not_performed")
        for name, metadata in result["files"].items():
            data = (self.output / name).read_bytes()
            self.assertEqual(metadata, {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    def test_missing_input_fails_before_output(self):
        (self.root / lab.BINARY_INPUTS[0]).unlink()
        with self.assertRaises(FileNotFoundError):
            lab.package(self.root, self.output, COMMIT)
        self.assertFalse(self.output.exists())

    def test_x64_binary_rejected(self):
        path = self.root / lab.BINARY_INPUTS[1]
        data = bytearray(path.read_bytes())
        struct.pack_into("<H", data, 68, 0x8664)
        struct.pack_into("<H", data, 88, 0x20B)
        path.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "x86 PE32"):
            lab.package(self.root, self.output, COMMIT)
        self.assertFalse(self.output.exists())

    def test_truncated_and_invalid_offsets_rejected(self):
        path = self.root / lab.BINARY_INPUTS[0]
        original = path.read_bytes()
        for off in (0, 159, 0xFFFFFFFF):
            with self.subTest(offset=off):
                data = bytearray(original)
                struct.pack_into("<I", data, 0x3C, off)
                path.write_bytes(data)
                with self.assertRaises(ValueError):
                    lab.package(self.root, self.output, COMMIT)
        path.write_bytes(b"MZ")
        with self.assertRaises(ValueError):
            lab.package(self.root, self.output, COMMIT)
        self.assertFalse(self.output.exists())

    def test_requires_exact_revision(self):
        for commit in ("main", "development", "abc123", COMMIT + "0", "../" + COMMIT):
            with self.subTest(commit=commit), self.assertRaises(ValueError):
                lab.package(self.root, self.output, commit)
        self.assertFalse(self.output.exists())

    def test_existing_output_not_overwritten_or_reused(self):
        self.output.mkdir()
        sentinel = self.output / "existing.txt"
        sentinel.write_text("preserve", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            lab.package(self.root, self.output, COMMIT)
        self.assertEqual([p.name for p in self.output.iterdir()], ["existing.txt"])
        self.assertEqual(sentinel.read_text(encoding="utf-8"), "preserve")

    def test_unlisted_logs_profiles_original_and_fixture_dll_excluded(self):
        for name in ("private.ini", "trace.jsonl", "VirtualCarJ2534.dll", "SyntheticJ2534.dll"):
            (self.root / name).write_text("SYNTHETIC_EXCLUSION_MARKER", encoding="utf-8")
        lab.package(self.root, self.output, COMMIT)
        for path in self.output.iterdir():
            self.assertNotIn(b"SYNTHETIC_EXCLUSION_MARKER", path.read_bytes())
        self.assertFalse((self.output / "VirtualCarJ2534.dll").exists())
        self.assertFalse((self.output / "SyntheticJ2534.dll").exists())

    def test_portable_manifest_and_source_bytes_preserved(self):
        before = {p: (self.root / p).read_bytes() for p in lab.BINARY_INPUTS + lab.DOC_INPUTS}
        result = lab.package(self.root, self.output, COMMIT)
        self.assertEqual(result, json.loads((self.output / "manifest.json").read_text(encoding="utf-8")))
        self.assertNotIn(str(self.root), json.dumps(result))
        self.assertEqual(before, {p: (self.root / p).read_bytes() for p in before})


if __name__ == "__main__":
    unittest.main(verbosity=2)
