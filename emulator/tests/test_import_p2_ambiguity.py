"""P0: selecting a D2 response from mixed or simulated sources needs provenance gates."""
from contextlib import redirect_stderr, redirect_stdout
import configparser
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "p0_explicit_trace_import", ROOT / "tools" / "import_p2_trace.py")
importer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(importer)

PUBLIC = (ROOT / "samples" / "p2_b9fb_public_redacted.txt").read_text(
    encoding="utf-8")
NEGATIVE = (
    "TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n"
    "RX (simulated) 01 20 00 03 CB 50 7F B9 11 00 00 00\n")
POSITIVE = (
    "TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00\n"
    "RX (simulated) 01 20 00 03 CC 50 F9 FB 00 00 00 00\n")


class ExplicitImportSessionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.folder = Path(temp.name)
        self.log = self.folder / "private-source.log"
        self.profile = self.folder / "synthetic-base.ini"
        self.output = self.folder / "new.ini"
        self.profile.write_text(
            "; synthetic fixture, NOT a physical vehicle\n"
            "[Vehicle]\nVIN=XXXXXXXXXXXXXXXXX\n",
            encoding="utf-8")

    def invoke(self, source, *flags, output=None):
        self.log.write_text(source, encoding="utf-8")
        dest = output or self.output
        argv = [
            "import_p2_trace.py", str(self.log),
            "--target", "50", "--opcode", "FB",
            "--profile", str(self.profile), "--output", str(dest),
            *flags]
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", argv), redirect_stdout(out), redirect_stderr(err):
            try:
                importer.main()
                code = 0
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), err.getvalue()

    def test_01_single_public_example_stays_unverified(self):
        code, stdout, stderr = self.invoke(PUBLIC)
        self.assertEqual((code, stderr), (0, ""))
        ini = self.output.read_text(encoding="utf-8")
        self.assertIn("Source classification: unverified_trace_origin", ini)
        self.assertIn("replay_approved=false", ini)
        self.assertIn("Selected session index: 0 of 1", ini)
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.output, encoding="utf-8")
        self.assertEqual(cfg.getint("D2_50", "B9FBFrameCount"), 13)
        self.assertIn("NOT independent OEM evidence", stdout)
        self.assertNotIn("YV1CZ0002A0000001", ini)

    def test_02_two_public_sessions_require_explicit_selection(self):
        source = PUBLIC + PUBLIC
        code, _, stderr = self.invoke(source)
        self.assertEqual(code, 2)
        self.assertIn("select --session-index explicitly", stderr)
        self.assertFalse(self.output.exists())
        self.assertEqual(len(importer.sessions(source.splitlines(), 0x50, 0xFB)), 2)

    def test_03_explicit_selection_of_shorter_negative_not_longest(self):
        source = PUBLIC + NEGATIVE
        self.assertEqual(self.invoke(source)[0], 2)
        self.assertEqual(self.invoke(source, "--session-index", "1")[0], 0)
        ini = self.output.read_text(encoding="utf-8")
        self.assertIn("Source classification: emulator_tagged_rx", ini)
        self.assertIn("Selected session index: 1 of 2", ini)
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.output, encoding="utf-8")
        self.assertEqual(cfg.getint("D2_50", "B9FBFrameCount"), 1)
        self.assertIn("CB 50 7F B9", cfg.get("D2_50", "B9FBFrame0"))

    def test_04_explicit_selection_first_public_session_in_mixed_source(self):
        code, _, _ = self.invoke(PUBLIC + NEGATIVE, "--session-index", "0")
        self.assertEqual(code, 0)
        ini = self.output.read_text(encoding="utf-8")
        self.assertIn("unverified_trace_origin", ini)
        self.assertIn("Selected session index: 0 of 2", ini)
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.output, encoding="utf-8")
        self.assertEqual(cfg.getint("D2_50", "B9FBFrameCount"), 13)

    def test_05_negative_and_out_of_range_indices_fail_closed(self):
        for value in ("-1", "2", "99"):
            with self.subTest(index=value):
                code, _, err = self.invoke(PUBLIC + NEGATIVE, "--session-index", value)
                self.assertEqual(code, 2)
                self.assertIn("session-index is out of range", err)
                self.assertFalse(self.output.exists())
        self.assertEqual(self.invoke(PUBLIC, "--session-index", "1")[0], 2)
        self.assertFalse(self.output.exists())

    def test_06_simulated_positive_is_tagged_not_promoted(self):
        code, stdout, _ = self.invoke(POSITIVE)
        self.assertEqual(code, 0)
        self.assertIn("emulator_tagged_rx", self.output.read_text(encoding="utf-8"))
        self.assertIn("NOT independent OEM evidence", stdout)
        cfg = configparser.ConfigParser(interpolation=None)
        cfg.read(self.output, encoding="utf-8")
        self.assertEqual(cfg.getint("D2_50", "B9FBFrameCount"), 1)
        self.assertEqual(cfg.get("D2_50", "B9FBFrame0").split()[:4],
                         ["CC", "50", "F9", "FB"])

    def test_07_emulator_delivery_marker_and_mixed_sources_are_tagged(self):
        source = PUBLIC.replace(
            "PassThruReadMsgs() msg",
            "PassThruReadMsgs -> delivered", 1)
        classified = importer.sessions_with_origin(source.splitlines(), 0x50, 0xFB)
        self.assertEqual((len(classified), len(classified[0][0])), (1, 13))
        self.assertEqual(classified[0][1], "emulator_tagged_rx")
        self.assertEqual(self.invoke(source)[0], 0)
        self.assertIn("emulator_tagged_rx", self.output.read_text(encoding="utf-8"))

    def test_08_ambiguous_input_never_overwrites_existing_output(self):
        original = b"EXISTING_PRIVATE_FILE_MUST_STAY"
        self.output.write_bytes(original)
        code, _, _ = self.invoke(PUBLIC + NEGATIVE)
        self.assertEqual(code, 2)
        self.assertEqual(self.output.read_bytes(), original)
        code, _, _ = self.invoke(PUBLIC, "--session-index", "0")
        self.assertEqual(code, 2)
        self.assertEqual(self.output.read_bytes(), original)

    def test_09_unrelated_tx_does_not_merge_simulator_and_capture(self):
        unrelated = "TX (app request) 00 0F FF FE CB 40 B9 FB 00 00 00 00\n"
        source = POSITIVE + unrelated + PUBLIC
        groups = importer.sessions_with_origin(source.splitlines(), 0x50, 0xFB)
        self.assertEqual([len(frames) for frames, _ in groups], [1, 13])
        self.assertEqual([origin for _, origin in groups],
                         ["emulator_tagged_rx", "unverified_trace_origin"])
        self.assertEqual(self.invoke(source)[0], 2)


if __name__ == "__main__":
    unittest.main()
