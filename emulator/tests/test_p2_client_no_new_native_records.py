"""Eight negative-evidence gates for Begin/Finish with zero new J2534 bytes.

No client process, real hardware, VIN or proprietary application is run.
All cases are offline and use a private byte-prefix snapshot.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import prepare_p2_client_run as capture
from test_prepare_p2_client_run import session, ui


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class NoNewNativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.raw = self.root / "private-j2534.log"
        self.output = self.root / "SAFE-JSON-REPORTS"

    def run_tool(self, *, offset=0, digest=None, optional=True, ui_path=None):
        args = [str(self.raw), "--output-dir", str(self.output)]
        if offset is not None:
            args += ["--offset-bytes", str(offset)]
        if digest is not None:
            args += ["--prefix-sha256", digest]
        if optional:
            args.append("--allow-empty-append")
        if ui_path is not None:
            args += ["--ui", str(ui_path)]
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            return capture.main(args)

    def read_note(self):
        return json.loads((self.output / "client-boundary.json").read_text(
            encoding="utf-8"))

    def test_01_absent_new_log_with_empty_begin_snapshot_is_not_error(self):
        self.assertFalse(self.raw.exists())
        self.assertEqual(self.run_tool(digest=sha(b"")), 0)
        self.assertEqual(sorted(p.name for p in self.output.iterdir()),
                         sorted(capture.OUTPUTS))
        note = self.read_note()
        self.assertEqual(note["diagnostic_focus"],
                         "no_new_native_j2534_records_observed")
        self.assertEqual(note["native_p2_report_status"],
                         "unavailable_no_new_native_records")
        self.assertFalse(note["new_native_records_observed"])
        self.assertFalse(note["client_ecu_inventory_verified"])
        self.assertFalse(note["same_run_independently_verified"])
        self.assertFalse(note["native_executable_identity_verified"])

    def test_02_existing_empty_file_with_empty_snapshot_is_same_negative(self):
        self.raw.write_bytes(b"")
        self.assertEqual(self.run_tool(digest=sha(b"")), 0)
        note = self.read_note()
        self.assertEqual(note["diagnostic_focus"],
                         "no_new_native_j2534_records_observed")
        self.assertEqual(note["connect_attempts"], 0)

    def test_03_unchanged_historical_log_may_be_large_and_private(self):
        old = b"PRIVATE_HISTORICAL_OLD_VIN_1" * 170000
        self.raw.write_bytes(old)
        self.assertEqual(self.run_tool(offset=len(old), digest=sha(old)), 0)
        note = self.read_note()
        self.assertEqual(note["diagnostic_focus"],
                         "no_new_native_j2534_records_observed")
        self.assertFalse(note["new_native_records_observed"])
        export = "".join(p.read_text(encoding="utf-8")
                         for p in self.output.iterdir())
        self.assertNotIn("PRIVATE_HISTORICAL", export)
        self.assertNotIn(str(self.raw), export)
        self.assertEqual(self.raw.read_bytes(), old)

    def test_04_mutated_existing_prefix_same_length_is_rejected(self):
        original = b"PRIVATE_BEFORE\n"
        self.raw.write_bytes(b"PRIVATE_AFTER!\n")
        self.assertEqual(self.run_tool(offset=len(original),
                                       digest=sha(original)), 2)
        self.assertFalse(self.output.exists())

    def test_05_missing_old_log_with_nonzero_offset_is_not_no_evidence(self):
        self.assertEqual(self.run_tool(offset=40, digest=sha(b"A"*40)), 2)
        self.assertFalse(self.output.exists())

    def test_06_no_new_bytes_still_error_by_default_or_without_snapshot(self):
        self.raw.write_bytes(b"")
        self.assertEqual(self.run_tool(digest=sha(b""), optional=False), 2)
        self.assertEqual(self.run_tool(offset=None, digest=None), 2)
        self.assertFalse(self.output.exists())

    def test_07_real_appended_synthetic_log_stays_normal_evidence_report(self):
        data = (session() + "\n").encode("utf-8")
        self.raw.write_bytes(data)
        self.assertEqual(self.run_tool(digest=sha(b"")), 0)
        note = self.read_note()
        self.assertTrue(note["new_native_records_observed"])
        self.assertEqual(note["b9fb_positive_transport_count"], 1)
        self.assertEqual(note["b9f0_positive_transport_count"], 1)
        self.assertEqual(note["first_p3_positive_transport_count"], 1)
        self.assertNotEqual(note["diagnostic_focus"],
                            "no_new_native_j2534_records_observed")

    def test_08_untrusted_ui_and_exclusive_output_cannot_claim_ecu(self):
        observation = self.root / "ui.json"
        observation.write_text(json.dumps(ui(
            client="sectorv", ecu_list="nonempty",
            vin_display="visible",
            same_run_operator_attested=True)), encoding="utf-8")
        self.assertEqual(self.run_tool(digest=sha(b""),
                                       ui_path=observation), 0)
        note = self.read_note()
        self.assertEqual(note["ui_ecu_list_reported"], "nonempty")
        self.assertEqual(note["diagnostic_focus"],
                         "no_new_native_j2534_records_observed")
        self.assertFalse(note["same_run_independently_verified"])
        self.assertFalse(note["client_ecu_inventory_verified"])
        self.assertFalse(note["native_executable_identity_verified"])
        # No second Finish can overwrite a reviewable report.
        self.assertEqual(self.run_tool(digest=sha(b""),
                                       ui_path=observation), 2)
        self.assertTrue((self.output / "client-boundary.json").exists())


if __name__ == "__main__":
    unittest.main()
