"""VC095E synthetic checks of the local catalog serialization contract."""
import copy
import json
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "tools"))
import prepare_vc094b_local_profile as package


class LocalPackageChecks(unittest.TestCase):
    def setUp(self):
        block = bytearray(142)
        block[0] = 0x8c
        block[8] = 2
        block[33] = 1
        block[1] = sum(block[2:]) % 256
        self.ini = (b"[Vehicle]\r\n[VC054_F106Lab]\r\nBlockHex=" +
                    block.hex().encode() + b"\r\nLayout=donor-142\r\nEnabled=1\r\n")
        self.rows = [dict(offset=i, name="Parameter", value="Original",
                          locked=i in package.LOCKED) for i in sorted(package.FIELDS)]
        self.options = [dict(offset=i, baseline_code=f"{block[i]:02X}", choices=[])
                        for i in sorted(package.FIELDS)]
        self.row = next(x for x in self.options if x["offset"] == 60)
        self.row["choices"].append(dict(code="01", text="Option"))
        changed = bytearray(block)
        changed[60] = 1
        changed[1] = sum(changed[2:]) % 256
        candidate = self.ini.replace(block.hex().encode(), changed.hex().encode())
        self.cases = [dict(offset=60, code="01", ini_sha256=package.digest(candidate))]

    def validate(self):
        package.validate_catalog(self.ini, self.rows, self.options, self.cases)

    def test_01_valid_catalog_and_reference(self):
        self.validate()

    def test_02_incomplete_or_reordered_catalog(self):
        self.rows.reverse()
        with self.assertRaises(ValueError):
            self.validate()
        self.rows.reverse()
        self.options.pop()
        with self.assertRaises(ValueError):
            self.validate()

    def test_03_wrong_lock_and_baseline(self):
        self.rows[0]["locked"] = False
        with self.assertRaises(ValueError):
            self.validate()
        self.rows[0]["locked"] = True
        self.row["baseline_code"] = "FF"
        with self.assertRaises(ValueError):
            self.validate()

    def test_04_utf16_length_and_invalid_labels(self):
        self.rows[0]["name"] = "🚗" * 257
        with self.assertRaises(ValueError):
            self.validate()
        self.rows[0]["name"] = "🚗" * 256
        self.validate()
        for label in ("", "Faulty value", "Undefined value", "🚗" * 513):
            self.row["choices"][0]["text"] = label
            with self.assertRaises(ValueError):
                self.validate()

    def test_05_locked_and_duplicate_choices(self):
        self.options[0]["choices"] = [dict(code="01", text="Option")]
        with self.assertRaises(ValueError):
            self.validate()
        self.options[0]["choices"] = []
        self.row["choices"].append(copy.deepcopy(self.row["choices"][0]))
        with self.assertRaises(ValueError):
            self.validate()

    def test_06_reference_digest_and_duplicate(self):
        old = self.cases[0]["ini_sha256"]
        self.cases[0]["ini_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.validate()
        self.cases[0]["ini_sha256"] = old
        self.cases.append(copy.deepcopy(self.cases[0]))
        with self.assertRaises(ValueError):
            self.validate()

    def test_07_unlisted_and_topology_references(self):
        self.cases[0]["code"] = "02"
        with self.assertRaises(ValueError):
            self.validate()
        self.cases[0].update(offset=13, code="01")
        next(x for x in self.options if x["offset"] == 13)["choices"] = [
            dict(code="01", text="Equipment")]
        with self.assertRaises(ValueError):
            self.validate()

    def test_08_overlapping_input_package_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            private = pathlib.Path(temp) / "private"
            target = private / "package"
            (target / "vehicle-data").mkdir(parents=True)
            (target / "VirtualCar.exe").write_bytes(b"synthetic")
            with patch.object(package, "checked_inputs") as checked:
                with self.assertRaisesRegex(ValueError, "overlapping_private_and_package_paths"):
                    package.prepare(private, target)
                checked.assert_not_called()
            private = target / "nested"
            private.mkdir()
            with patch.object(package, "checked_inputs") as checked:
                with self.assertRaisesRegex(ValueError, "overlapping_private_and_package_paths"):
                    package.prepare(private, target)
                checked.assert_not_called()


    def test_09_noninteger_offsets(self):
        for row in (self.rows[0], self.options[0], self.cases[0]):
            original = row["offset"]
            for invalid in (float(original), str(original), True):
                with self.subTest(invalid=invalid, original=original):
                    row["offset"] = invalid
                    with self.assertRaisesRegex(ValueError, "catalog_offset_type"):
                        self.validate()
            row["offset"] = original
        self.validate()

    def test_10_unexpected_record_keys(self):
        for row in (self.rows[0], self.options[0], self.row["choices"][0], self.cases[0]):
            row["extra"] = 1
            with self.assertRaisesRegex(ValueError, "catalog_shape"):
                self.validate()
            del row["extra"]
        self.validate()

    def test_11_missing_record_keys(self):
        for row, key in ((self.rows[0], "name"), (self.options[0], "choices"),
                         (self.row["choices"][0], "text"), (self.cases[0], "ini_sha256")):
            old = row.pop(key)
            with self.assertRaisesRegex(ValueError, "catalog_shape"):
                self.validate()
            row[key] = old
        self.validate()

    def test_12_invalid_array_types(self):
        for i, items in enumerate((self.rows, self.options, self.cases)):
            args = [self.rows, self.options, self.cases]
            args[i] = tuple(items)
            with self.assertRaisesRegex(ValueError, "catalog_shape"):
                package.validate_catalog(self.ini, *args)
        self.row["choices"] = tuple(self.row["choices"])
        with self.assertRaisesRegex(ValueError, "catalog_shape"):
            self.validate()

    def test_13_invalid_reference_scalar_types(self):
        case = self.cases[0]
        for key, invalid in (("code", []), ("code", 1), ("code", "0a"),
                             ("ini_sha256", None), ("ini_sha256", 123),
                             ("ini_sha256", "A" * 64)):
            old = case[key]
            case[key] = invalid
            with self.assertRaises(ValueError):
                self.validate()
            case[key] = old
        self.validate()

    def test_14_manifest_complete_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            marker = {"schema": "synthetic", "profile_sha256": "0" * 64}
            package.publish_manifest(root, marker)
            self.assertEqual(json.loads((root / "local-profile.json").read_bytes()), marker)
            self.assertFalse((root / ".local-profile.json.pending").exists())

    def test_15_manifest_no_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            final = root / "local-profile.json"
            final.write_bytes(b"existing")
            with self.assertRaises(FileExistsError):
                package.publish_manifest(root, {"schema": "synthetic"})
            self.assertEqual(final.read_bytes(), b"existing")
            self.assertFalse((root / ".local-profile.json.pending").exists())

    def test_16_manifest_failed_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp)
            for method in ("fsync", "link"):
                with patch.object(package.os, method, side_effect=OSError("synthetic failure")):
                    with self.assertRaises(OSError):
                        package.publish_manifest(root, {"schema": "synthetic"})
                self.assertFalse((root / "local-profile.json").exists())
                self.assertFalse((root / ".local-profile.json.pending").exists())


    def with_resume_target(self, check):
        with tempfile.TemporaryDirectory() as temp:
            root = pathlib.Path(temp) / "profile"
            root.mkdir()
            files = {"virtualcar.ini": b"synthetic ini",
                     "configuration.json": b"synthetic catalog"}
            check(root, files)

    def test_17_resume_missing_files(self):
        def check(root, files):
            first = root / "virtualcar.ini"
            first.write_bytes(files[first.name])
            before = first.stat().st_mtime_ns
            package.write_profile_files(root, files, resume=True)
            self.assertEqual(first.stat().st_mtime_ns, before)
            self.assertEqual((root / "configuration.json").read_bytes(), files["configuration.json"])
        self.with_resume_target(check)

    def test_18_resume_empty_directory(self):
        def check(root, files):
            package.write_profile_files(root, files, resume=True)
            self.assertEqual({p.name for p in root.iterdir()}, set(files))
        self.with_resume_target(check)

    def test_19_resume_complete_unpublished_directory(self):
        def check(root, files):
            for name, raw in files.items():
                (root / name).write_bytes(raw)
            with patch.object(package.os, "fsync", side_effect=AssertionError("unexpected write")):
                package.write_profile_files(root, files, resume=True)
        self.with_resume_target(check)

    def test_20_resume_rejects_published_or_pending_marker(self):
        def check(root, files):
            for name in ("local-profile.json", ".local-profile.json.pending"):
                marker = root / name
                marker.write_bytes(b"synthetic")
                with self.assertRaisesRegex(ValueError, "unexpected_resume_entry"):
                    package.write_profile_files(root, files, resume=True)
                self.assertEqual(list(root.iterdir()), [marker])
                marker.unlink()
        self.with_resume_target(check)

    def test_21_resume_rejects_changed_bytes(self):
        def check(root, files):
            first = root / "virtualcar.ini"
            for raw in (b"truncated", b"x" * len(files[first.name])):
                first.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, "resume_content_mismatch"):
                    package.write_profile_files(root, files, resume=True)
                self.assertEqual(first.read_bytes(), raw)
                self.assertFalse((root / "configuration.json").exists())
        self.with_resume_target(check)

    def test_22_resume_rejects_unknown_entry(self):
        def check(root, files):
            unknown = root / "unknown.txt"
            unknown.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "unexpected_resume_entry"):
                package.write_profile_files(root, files, resume=True)
            self.assertEqual(unknown.read_bytes(), b"keep")
            self.assertEqual(list(root.iterdir()), [unknown])
        self.with_resume_target(check)

    def test_23_resume_requires_existing_directory(self):
        def check(root, files):
            with self.assertRaises(FileNotFoundError):
                package.write_profile_files(root / "missing", files, resume=True)
            with self.assertRaises(FileExistsError):
                package.write_profile_files(root, files)
            first = root / "file"
            first.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "invalid_resume_target"):
                package.write_profile_files(first, files, resume=True)
        self.with_resume_target(check)

    def test_24_resume_rejects_nested_directory(self):
        def check(root, files):
            nested = root / "virtualcar.ini"
            nested.mkdir()
            with self.assertRaises(ValueError):
                package.write_profile_files(root, files, resume=True)
            self.assertTrue(nested.is_dir())
            self.assertFalse((root / "configuration.json").exists())
        self.with_resume_target(check)


if __name__ == "__main__":
    unittest.main()
