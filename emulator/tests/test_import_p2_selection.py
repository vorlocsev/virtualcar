"""Eight read-only regressions for choosing one D2 response from repeated attempts.

All frames originate from the checked-in redacted public donor or are synthetic.
A complete D2 transport frame is not authenticated XC90 CEM identity.
"""
import configparser
from contextlib import redirect_stderr, redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "import_p2_trace_selection", ROOT / "tools" / "import_p2_trace.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

TX = "TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00"
CAN_ID = 0x01200003


def donor():
    source = (ROOT / "samples" / "p2_b9fb_public_redacted.txt").read_text(
        encoding="utf-8").splitlines()
    captures = tool.sessions(source, 0x50, 0xFB)
    assert len(captures) == 1 and len(captures[0]) == 13
    return captures[0]


def two_frame(can_id=CAN_ID):
    return [
        (can_id, bytes.fromhex("8F 50 F9 FB 57 00 31 82")),
        (can_id, bytes.fromhex("4F 00 00 00 00 00 00 00")),
    ]


def contaminated(frames):
    # A post-terminal RX must make this source attempt invalid,
    # even though its raw frame count exceeds the clean attempt.
    return frames + [(CAN_ID, bytes.fromhex("09 00 00 00 00 00 00 00"))]


def trace_run(frames):
    def line(can_id, data):
        payload = can_id.to_bytes(4, "big") + data
        return "RX (simulated) " + " ".join(f"{value:02X}" for value in payload)
    return [TX] + [line(can_id, data) for can_id, data in frames]


def import_cli(source, profile, output):
    with patch.object(sys, "argv", [
        "import_p2_trace.py", str(source), "--profile", str(profile),
        "--output", str(output)
    ]), redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
        try:
            tool.main()
        except SystemExit as exc:
            return exc.code
    return 0


class SelectionRegressions(unittest.TestCase):
    def test_01_longer_invalid_attempt_does_not_mask_complete_donor(self):
        valid = donor()
        for attempts in ([contaminated(valid), valid],
                         [valid, contaminated(valid)]):
            with self.subTest(order=attempts[0] is valid):
                self.assertIs(tool.select_complete_response(attempts, 0x50, 0xFB),
                              valid)

    def test_02_truncated_donor_does_not_mask_complete_donor(self):
        complete = donor()
        selected = tool.select_complete_response(
            [complete[:-1], complete], 0x50, 0xFB)
        self.assertIs(selected, complete)

    def test_03_longest_individually_valid_run_wins(self):
        complete = donor()
        short = two_frame()
        tool.validate_response(short, 0x50, 0xFB)
        self.assertIs(tool.select_complete_response(
            [short, complete], 0x50, 0xFB), complete)
        self.assertIs(tool.select_complete_response(
            [complete, short], 0x50, 0xFB), complete)

    def test_04_equal_length_tie_preserves_first_valid_attempt(self):
        first, second = two_frame(), two_frame(0x00400003)
        self.assertIs(tool.select_complete_response(
            [first, second], 0x50, 0xFB), first)
        self.assertIs(tool.select_complete_response(
            [second, first], 0x50, 0xFB), second)

    def test_05_only_invalid_attempts_fail_closed(self):
        complete = donor()
        bad_service = [
            (CAN_ID, bytes.fromhex("8F 50 F9 F0 00 00 00 00")),
            (CAN_ID, bytes.fromhex("4F 00 00 00 00 00 00 00")),
        ]
        for attempts in ([], [complete[:-1]],
                         [contaminated(complete)], [bad_service]):
            with self.subTest(count=len(attempts)):
                with self.assertRaisesRegex(
                    ValueError, "No complete D2 response"
                ):
                    tool.select_complete_response(attempts, 0x50, 0xFB)

    def test_06_no_assembly_across_distinct_request_windows(self):
        complete = donor()
        source = trace_run(complete[:-1]) + trace_run(complete[-1:])
        groups = tool.sessions(source, 0x50, 0xFB)
        self.assertEqual([len(g) for g in groups], [12, 1])
        with self.assertRaises(ValueError):
            tool.select_complete_response(groups, 0x50, 0xFB)

    def test_07_target_opcode_and_mixed_can_id_are_still_enforced(self):
        foreign = two_frame()
        foreign[0] = (CAN_ID, bytes.fromhex("8F 40 F9 FB 00 00 00 00"))
        mixed = two_frame()
        mixed[1] = (0x00400003, mixed[1][1])
        valid = two_frame()
        self.assertIs(tool.select_complete_response(
            [foreign, mixed, valid], 0x50, 0xFB), valid)
        with self.assertRaises(ValueError):
            tool.select_complete_response([valid], 0x50, 0xF0)

    def test_08_cli_recovers_complete_capture_and_preserves_private_inputs(self):
        complete = donor()
        raw = "\n".join(
            trace_run(contaminated(complete)) + trace_run(complete)
            + ["PRIVATE_NOTE_NEVER_EXPORT"]
        ) + "\n"
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            source = directory / "private.log"
            profile = directory / "p2.ini"
            output = directory / "selected.ini"
            source.write_text(raw, encoding="utf-8")
            profile.write_text("[Vehicle]\nVIN=XXXXXXXXXXXXXXXXX\n", encoding="utf-8")
            original_source = source.read_bytes()
            original_profile = profile.read_bytes()
            self.assertEqual(import_cli(source, profile, output), 0)
            cfg = configparser.ConfigParser(interpolation=None)
            cfg.read(output, encoding="utf-8")
            self.assertEqual(cfg.getint("D2_50", "B9FBFrameCount"), 13)
            result = output.read_text(encoding="utf-8")
            self.assertNotIn("PRIVATE_NOTE_NEVER_EXPORT", result)
            self.assertNotIn(str(source), result)
            self.assertEqual(source.read_bytes(), original_source)
            self.assertEqual(profile.read_bytes(), original_profile)
            self.assertEqual(import_cli(source, profile, output), 2)
            self.assertEqual(source.read_bytes(), original_source)


if __name__ == "__main__":
    unittest.main()
