"""Eight offline gates for native B9FB -> first A3 source-local timing."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_audit_d2_followup_window import A3, D2FB, marker, response, tx

spec = importlib.util.spec_from_file_location(
    "verify_native_d2_followup", ROOT / "tools" / "verify_native_d2_followup.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def case(gap_ms=490):
    # Last synthetic RX is at 1,032,000 microseconds.
    # Native runner later sends an unconfigured LS125 B9FB request. The
    # auditor must count that as one *unanswered* attempt, not as a second
    # completed response or an error in the first HS500 B9FB.
    a3_us = 1_032_000 + gap_ms * 1000
    return (tx() + response() + tx(A3, at=a3_us)
            + tx(bytes.fromhex("CB 40 B9 FB 00 00 00 00"),
                 channel=2, baud=125000, at=a3_us + 50_000))


def run(lines):
    return tool.verify("\n".join(lines))


class NativeD2FollowupGateTests(unittest.TestCase):
    def test_01_native_490ms_gap_passes_without_client_acceptance(self):
        result = run(case())
        self.assertTrue(result["native_d2_followup_verified"])
        self.assertEqual(result["last_rx_to_first_next_tx_ms"], 490)
        self.assertEqual(result["b9fb_rx_frames"], 13)
        self.assertEqual(result["other_unanswered_b9fb_attempts"], 1)
        self.assertEqual(result["b9fb_target"], "0x50")
        self.assertEqual(result["first_next_tx_target"], "0x50")
        self.assertTrue(result["first_next_tx_same_target"])
        self.assertTrue(result["first_next_tx_same_channel"])
        self.assertEqual(result["within_500_ms"], "first_tx_within_window")
        self.assertFalse(result["client_acceptance_verified"])
        self.assertFalse(result["same_run_with_sectorv_client_verified"])

    def test_02_window_is_measured_not_assumed_before_500_or_1000(self):
        for gap, within500, within1000 in (
            (0, True, True), (500, True, True),
            (501, False, True), (1000, False, True),
            (1001, False, False), (1200, False, False),
        ):
            with self.subTest(gap_ms=gap):
                result = run(case(gap))
                self.assertEqual(result["last_rx_to_first_next_tx_ms"], gap)
                self.assertEqual(result["within_500_ms"] == "first_tx_within_window", within500)
                self.assertEqual(result["within_1000_ms"] == "first_tx_within_window", within1000)

    def test_03_a3_to_wrong_target_does_not_match_original_b9fb(self):
        lines = tx() + response()
        lines += tx(bytes.fromhex("CF 40 A3 02 03 A5 A5 00"),
                    at=1_132_000)
        parsed = tool.audit("\n".join(lines))["observations"][0]
        self.assertEqual(parsed["first_next_tx_target"], "0x40")
        self.assertFalse(parsed["first_next_tx_same_target"])
        with self.assertRaises(ValueError):
            run(lines)

    def test_04_other_app_tx_first_or_missing_a3_is_not_accepted(self):
        other = tx() + response() + tx(bytes.fromhex("02 09 02 00 00 00 00 00"),
                                       at=1_132_000, can=0x7DF)
        for lines in (tx() + response(), other, other + tx(A3, at=1_232_000)):
            with self.subTest(lines=len(lines)), self.assertRaises(ValueError):
                run(lines)

    def test_05_incomplete_b9fb_and_wrong_can_rx_route_refused(self):
        for lines in (
            tx() + response(include_final=False) + tx(A3, at=1_232_000),
            tx() + response(can=0x01200004) + tx(A3, at=1_232_000),
            tx() + response()[:-2] + tx(A3, at=1_232_000),
        ):
            with self.subTest(lines=len(lines)), self.assertRaises(ValueError):
                run(lines)

    def test_06_cross_pid_channel_or_clock_unknown_fail_closed(self):
        pid = tx() + response() + tx(A3, pid="FEEDBEEF", at=1_132_000)
        channel = tx() + response() + tx(A3, channel=2, at=1_132_000)
        missing_ctx = tx() + response() + [marker("TX (app request)",
                                                   (0xFFFFE).to_bytes(4, "big")+A3)]
        for lines in (pid, channel, missing_ctx):
            with self.subTest(lines=len(lines)), self.assertRaises(ValueError):
                run(lines)

    def test_07_native_log_accepted_fields_only_private_text_redacted(self):
        secret = "MY_PRIVATE_VIN_12345678901234567"
        raw = "\n".join(case() + [secret])
        result = tool.verify(raw)
        self.assertNotIn(secret, json.dumps(result))
        self.assertNotIn("ABCDEF12", json.dumps(result))
        self.assertNotIn("PRIVATE_CLIENT", json.dumps(result))
        self.assertNotIn("CB 50 B9", json.dumps(result))
        self.assertNotIn("source_path", json.dumps(result))
        self.assertEqual(result["evidence_scope"], "synthetic_native_x86_dll_only")

    def test_08_cli_exclusive_write_invalid_input_and_source_protection(self):
        with tempfile.TemporaryDirectory() as d:
            source, output = Path(d) / "private-native.log", Path(d) / "redacted.json"
            raw = "\n".join(case())
            source.write_text(raw, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(output)]), 0)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["last_rx_to_first_next_tx_ms"], 490)
            data = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(output)]), 2)
                self.assertEqual(tool.main([str(source), "--output", str(source)]), 2)
            self.assertEqual(output.read_bytes(), data)
            self.assertEqual(source.read_text(encoding="utf-8"), raw)
            bad = Path(d) / "do-not-create.json"
            source.write_text("malformed log", encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(bad)]), 2)
            self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main()
