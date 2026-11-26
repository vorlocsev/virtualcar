"""VC095E synthetic checks of the local catalog serialization contract."""
import copy
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


if __name__ == "__main__":
    unittest.main()
