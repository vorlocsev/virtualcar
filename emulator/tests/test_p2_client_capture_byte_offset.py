"""Eight fail-closed private-offset checks for one native client run.

The old log content is never copied to a public report. An appended suffix
is accepted only after its preceding byte prefix matches the original SHA256.
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
from test_prepare_p2_client_run import session


def sha(data):
    return hashlib.sha256(data).hexdigest()


class ByteOffsetCaptureTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)
        self.root = Path(self.dir.name)
        self.source = self.root / "private-native.log"
        self.safe = self.root / "safe"
        self.previous = b"PRIVATE_PREVIOUS_VIN_AND_CAN_PAYLOAD\n"

    def run_capture(self, *, old=None, appended=None, offset=None,
                    digest=None, opts=None):
        old = self.previous if old is None else old
        appended = session().encode("utf-8") if appended is None else appended
        self.source.write_bytes(old + appended)
        args = [str(self.source), "--output-dir", str(self.safe)]
        if offset is not None:
            args += ["--offset-bytes", str(offset)]
        if digest is not None:
            args += ["--prefix-sha256", str(digest)]
        args += opts or []
        with contextlib.redirect_stderr(io.StringIO()), \
                contextlib.redirect_stdout(io.StringIO()):
            result = capture.main(args)
        return result

    def test_01_exact_original_digest_allows_only_new_complete_run(self):
        self.assertEqual(self.run_capture(offset=len(self.previous),
                                          digest=sha(self.previous)), 0)
        note = json.loads((self.safe / "client-boundary.json").read_text())
        self.assertEqual(note["b9fb_positive_transport_count"], 1)
        self.assertEqual(note["b9f0_positive_transport_count"], 1)
        self.assertEqual(note["first_p3_positive_transport_count"], 1)
        self.assertFalse(note["client_ecu_inventory_verified"])
        exported = "".join(p.read_text(encoding="utf-8")
                           for p in self.safe.iterdir())
        for private in ("PRIVATE_PREVIOUS", "ABCDEF12",
                        "VCARLAB0000000000", str(self.source)):
            self.assertNotIn(private, exported)

    def test_02_changed_historical_prefix_is_rejected(self):
        self.assertEqual(self.run_capture(old=b"PRIVATE_CHANGED_HISTORICAL_BYTES\n",
                                          offset=len(self.previous),
                                          digest=sha(self.previous)), 2)
        self.assertFalse(self.safe.exists())

    def test_03_log_rotation_or_truncation_is_rejected(self):
        self.assertEqual(self.run_capture(old=b"", appended=b"short",
                                          offset=len(self.previous),
                                          digest=sha(self.previous)), 2)
        self.assertFalse(self.safe.exists())

    def test_04_no_appended_bytes_is_not_a_client_run(self):
        self.assertEqual(self.run_capture(appended=b"",
                                          offset=len(self.previous),
                                          digest=sha(self.previous)), 2)
        self.assertFalse(self.safe.exists())

    def test_05_missing_half_of_source_attestation_is_rejected(self):
        self.assertEqual(self.run_capture(offset=len(self.previous)), 2)
        self.assertFalse(self.safe.exists())
        self.assertEqual(self.run_capture(digest=sha(self.previous)), 2)
        self.assertFalse(self.safe.exists())

    def test_06_invalid_digest_negative_offset_and_same_output_path_fail(self):
        for offset, digest in ((-1, sha(self.previous)),
                               (len(self.previous), "BAD"),
                               (len(self.previous), "a"*65)):
            with self.subTest(offset=offset, digest=digest):
                self.assertEqual(self.run_capture(offset=offset,
                                                  digest=digest), 2)
                self.assertFalse(self.safe.exists())
        with contextlib.redirect_stderr(io.StringIO()):
            result = capture.main([str(self.source), "--output-dir",
                                   str(self.source)])
        self.assertEqual(result, 2)

    def test_07_old_log_over_four_megabytes_can_be_safely_skipped(self):
        # The old log is large but only the bounded new suffix is analyzed.
        old = b"P" * (capture.MAX_BYTES + 1)
        self.assertEqual(self.run_capture(old=old, offset=len(old),
                                          digest=sha(old)), 0)
        note = json.loads((self.safe / "client-boundary.json").read_text())
        self.assertTrue(note["native_p2_single_closed_epoch"])
        self.assertFalse(note["same_run_independently_verified"])
        self.assertEqual(self.source.read_bytes()[:8], b"P" * 8)

    def test_08_oversized_suffix_and_existing_output_are_rejected(self):
        suffix = b"X" * (capture.MAX_BYTES + 1)
        self.assertEqual(self.run_capture(offset=len(self.previous),
                                          digest=sha(self.previous),
                                          appended=suffix), 2)
        self.assertFalse(self.safe.exists())
        self.assertEqual(self.run_capture(offset=len(self.previous),
                                          digest=sha(self.previous)), 0)
        # Exclusive output: repeated Finish cannot overwrite the safe report.
        self.assertEqual(self.run_capture(offset=len(self.previous),
                                          digest=sha(self.previous)), 2)
        self.assertTrue((self.safe / "client-boundary.json").exists())


if __name__ == "__main__":
    unittest.main()
