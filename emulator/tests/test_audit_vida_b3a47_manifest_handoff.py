"""Eight synthetic B3A46 -> B3A45 private manifest integration gates."""
import contextlib
import io
import json
import tempfile
from pathlib import Path
import sys
from unittest import mock
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_j2534_session_window as tool
sys.path.pop(0)

NATIVE_LINE = "[PID=1234ABCD iexplore.exe] PassThruOpen -> device 1\n"


class B3A47PrivateHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vida = self.root / "VIDA.log"
        self.native = self.root / "SectorVVirtualCar.log"
        self.vida.write_text("old original log\n", encoding="utf-8")
        self.native.write_text("old native log\n", encoding="utf-8")
        self.manifest = self.root / "owner-private" / "source-manifest.json"
        self.manifest.parent.mkdir()
        self.baseline = self.root / "owner-private" / "baseline.private.json"
        self.out = self.root / "owner-private" / "report.json"
        self.write_manifest()

    def write_manifest(self, records=None):
        if records is None:
            records = [self.candidate(self.native)]
        self.manifest.write_text(json.dumps({
            "schema_version": "virtualcar-b3a46-source-inventory-v1",
            "private_do_not_upload": True,
            "paths_are_not_process_attribution": True,
            "candidates": records,
        }), encoding="utf-8")

    @staticmethod
    def candidate(path, status="native_marker_in_tail", count=1):
        return {"path": str(path), "status": status,
                "bytes": 99, "markers_in_tail": count}

    def invoke(self, mode, *, selection=None, args=None):
        if selection is None:
            selection = ["--candidate-manifest", str(self.manifest),
                         "--candidate-index", "1"]
        fields = [mode, "--vida-log", str(self.vida),
                  *selection, "--private-baseline", str(self.baseline)]
        if mode == "delta":
            fields.extend(("--output", str(self.out)))
        if args:
            fields.extend(args)
        with contextlib.redirect_stdout(io.StringIO()):
            tool.main(fields)

    def test_01_manifest_selected_baseline_and_delta(self):
        self.invoke("baseline")
        with self.native.open("a", encoding="utf-8") as stream:
            stream.write(NATIVE_LINE)
        with self.vida.open("a", encoding="utf-8") as stream:
            stream.write("ReadVin\n")
        self.invoke("delta")
        report = json.loads(self.out.read_text())
        self.assertEqual(report["virtual_marker_counts"]["open_success"], 1)
        self.assertEqual(report["vida_literal_counts"]["read_vin_literal"], 1)
        self.assertFalse(report["vin_accepted_verified"])
        self.assertNotIn(str(self.native), json.dumps(report))
        self.assertNotIn("1234ABCD", json.dumps(report))

    def test_02_manual_candidate_index_two(self):
        second = self.root / "second" / "SectorVVirtualCar.log"
        second.parent.mkdir()
        second.write_text("old secondary\n", encoding="utf-8")
        self.write_manifest([self.candidate(self.native), self.candidate(second)])
        self.invoke("baseline", selection=["--candidate-manifest", str(self.manifest),
                                            "--candidate-index", "2"])
        with second.open("a", encoding="utf-8") as stream:
            stream.write(NATIVE_LINE)
        self.invoke("delta", selection=["--candidate-manifest", str(self.manifest),
                                         "--candidate-index", "2"])
        report = json.loads(self.out.read_text())
        self.assertEqual(report["virtual_marker_counts"]["open_success"], 1)
        self.assertEqual(report["appended_bytes"]["original_vida"], 0)

    def test_03_explicit_native_log_path_is_backward_compatible(self):
        direct = ["--virtual-log", str(self.native)]
        self.invoke("baseline", selection=direct)
        with self.native.open("a", encoding="utf-8") as stream:
            stream.write(NATIVE_LINE)
        self.invoke("delta", selection=direct)
        report = json.loads(self.out.read_text())
        self.assertEqual(report["virtual_marker_counts"]["open_success"], 1)

    def test_04_missing_or_out_of_range_index_rejected(self):
        for option in (
            ["--candidate-manifest", str(self.manifest)],
            ["--candidate-manifest", str(self.manifest), "--candidate-index", "0"],
            ["--candidate-manifest", str(self.manifest), "--candidate-index", "2"],
            ["--candidate-index", "1"],
        ):
            with self.subTest(option=option):
                with contextlib.redirect_stderr(io.StringIO()):
                    with self.assertRaises((ValueError, SystemExit)):
                        self.invoke("baseline", selection=option)
        self.assertFalse(self.baseline.exists())

    def test_05_bad_manifest_schema_fails_closed(self):
        for field, value in (
            ("schema_version", "forged"),
            ("private_do_not_upload", False),
            ("paths_are_not_process_attribution", False),
            ("candidates", []),
        ):
            with self.subTest(field=field):
                current = json.loads(self.manifest.read_text())
                current[field] = value
                self.manifest.write_text(json.dumps(current))
                with self.assertRaises(ValueError):
                    self.invoke("baseline")
                self.write_manifest()
        self.assertFalse(self.baseline.exists())

    def test_06_unapproved_status_value_and_filename_rejected(self):
        for record in (
            self.candidate(self.native, status="missing"),
            self.candidate(self.native, count=0),
            self.candidate(self.root / "PRIVATE_VIN.log"),
        ):
            with self.subTest(record=record["status"]):
                self.write_manifest([record])
                with self.assertRaises(ValueError):
                    self.invoke("baseline")
        self.assertFalse(self.baseline.exists())

    def test_07_symlink_source_and_spoofed_pairs_rejected(self):
        with mock.patch.object(Path, "is_symlink", autospec=True, return_value=True):
            with self.assertRaisesRegex(ValueError, "candidate native log path"):
                tool._candidate_log(self.manifest, 1)
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                self.invoke("baseline", args=["--virtual-log", str(self.native)])
        self.assertFalse(self.baseline.exists())

    def test_08_private_manifest_not_overwritten_and_portable_root(self):
        self.invoke("baseline")
        with self.assertRaises(FileExistsError):
            self.invoke("baseline")
        self.assertTrue(self.manifest.is_file())
        with mock.patch.object(tool, "ROOT", None):
            path = self.root / "owner-private" / "new-safe.private.json"
            tool._external(path, (self.vida, self.native, self.manifest))
        if tool.ROOT is not None:
            with self.assertRaises(ValueError):
                tool._external(tool.ROOT / "README.md", (self.vida, self.native))


if __name__ == "__main__":
    unittest.main()
