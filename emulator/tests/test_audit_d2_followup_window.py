"""Eight synthetic source-local native D2 B9FB -> next-TX timing checks."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "audit_d2_followup_window", ROOT / "tools" / "audit_d2_followup_window.py")
import sys
sys.path.insert(0, str(ROOT / "tools"))
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

FIRST = bytes.fromhex("8F 50 F9 FB 57 00 30 66")
D2FB = bytes.fromhex("CB 50 B9 FB 00 00 00 00")
A3 = bytes.fromhex("CF 50 A3 02 03 A5 A5 00")


def marker(name, payload=None, pid="ABCDEF12", host="PRIVATE_CLIENT"):
    data = "" if payload is None else " " + payload.hex(" ").upper()
    return f"[PID={pid} {host}] {name}{data}"


def words(*values):
    return b"".join(value.to_bytes(4, "big") for value in values)


def tx(payload=D2FB, *, channel=1, baud=500000, at=1_000_000,
       pid="ABCDEF12", can=0xFFFFE, protocol=5):
    return [
        marker(tool.CTX_TX, words(channel, protocol, 0x100, baud, at), pid=pid),
        marker("TX (app request)", can.to_bytes(4, "big") + payload, pid=pid),
    ]


def rx(payload, *, channel=1, baud=500000, at=1_020_000, pid="ABCDEF12",
       can=0x01200003):
    return [
        marker(tool.CTX_RX, words(channel, 5, 0, baud, at), pid=pid),
        marker("PassThruReadMsgs -> delivered",
               can.to_bytes(4, "big") + payload, pid=pid),
    ]


def response(*, channel=1, baud=500000, first=1_020_000, pid="ABCDEF12",
             can=0x01200003, include_final=True):
    heads = [9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F]
    payloads = [FIRST] + [bytes((x,)) + b"\x00" * 7 for x in heads]
    if not include_final:
        payloads = payloads[:-1]
    result = []
    for index, payload in enumerate(payloads):
        result.extend(rx(payload, channel=channel, baud=baud,
                         at=(first + index * 1000) % (1 << 32),
                         pid=pid, can=can))
    return result


class FollowupWindowTests(unittest.TestCase):
    def test_01_a3_within_500ms_same_process_channel(self):
        end = 1_032_000
        lines = tx() + response()
        lines += tx(A3, at=end + 490_000)
        report = tool.audit("\n".join(lines))
        self.assertEqual(report["completed_b9fb_count"], 1)
        a = report["observations"][0]
        self.assertEqual(a["b9fb_rx_frames"], 13)
        self.assertEqual(a["b9fb_tx_to_last_rx_ms"], 32)
        self.assertEqual(a["first_next_tx_service"], "d2_a3_target_known")
        self.assertEqual(a["last_rx_to_first_next_tx_ms"], 490)
        self.assertEqual(a["within_500_ms"], "first_tx_within_window")
        self.assertEqual(a["within_1000_ms"], "first_tx_within_window")
        self.assertTrue(a["first_next_tx_same_channel"])
        self.assertFalse(a["client_accepted_b9fb"])
        self.assertFalse(report["same_run_with_sectorv_client_verified"])

    def test_02_a3_at_750ms_different_channel_and_baud(self):
        lines = tx() + response()
        lines += tx(bytes.fromhex("CF 40 A3 02 03 A5 A5 00"),
                    channel=2, baud=125000, at=1_782_000)
        a = tool.audit("\n".join(lines))["observations"][0]
        self.assertEqual(a["first_next_tx_service"], "d2_a3_target_known")
        self.assertEqual(a["last_rx_to_first_next_tx_ms"], 750)
        self.assertEqual(a["within_500_ms"], "first_tx_later_than_window")
        self.assertEqual(a["within_1000_ms"], "first_tx_within_window")
        self.assertFalse(a["first_next_tx_same_channel"])
        self.assertFalse(a["first_next_tx_same_baud"])

    def test_03_unattributed_tx_stays_unknown_not_silence(self):
        lines = tx() + response()
        lines += [marker("TX (app request) MALFORMED_PRIVATE_FRAME")]
        record = tool.audit("\n".join(lines))["observations"][0]
        self.assertEqual(record["followup_observation"], "next_tx_unattributed")
        self.assertEqual(record["within_500_ms"], "timestamp_unverified")
        self.assertEqual(record["within_1000_ms"], "timestamp_unverified")
        self.assertEqual(record["first_next_tx_service"], "unclassified_unattributed_tx")
        self.assertIsNone(record["last_rx_to_first_next_tx_ms"])

    def test_03_first_other_tx_precedes_later_a3(self):
        lines = tx() + response()
        lines += tx(bytes.fromhex("02 09 02 00 00 00 00 00"),
                    channel=2, baud=500000, can=0x7DF, at=1_132_000)
        lines += tx(A3, at=1_232_000)
        report = tool.audit("\n".join(lines))
        self.assertEqual(report["completed_b9fb_count"], 1)
        item = report["observations"][0]
        self.assertEqual(item["last_rx_to_first_next_tx_ms"], 100)
        self.assertEqual(item["first_next_tx_service"], "other_or_unclassified_tx")
        self.assertEqual(item["followup_observation"], "first_next_tx_observed")

    def test_04_observed_tx_after_both_windows(self):
        lines = tx() + response() + tx(A3, at=2_232_000)
        a = tool.audit("\n".join(lines))["observations"][0]
        self.assertEqual(a["last_rx_to_first_next_tx_ms"], 1200)
        self.assertEqual(a["within_500_ms"], "first_tx_later_than_window")
        self.assertEqual(a["within_1000_ms"], "first_tx_later_than_window")

    def test_05_no_next_tx_is_not_inferred_1000ms_timeout(self):
        lines = tx() + response()
        lines += [marker("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",
                         words(1, 500, 1))]
        a = tool.audit("\n".join(lines))["observations"][0]
        self.assertEqual(a["followup_observation"], "end_of_log_no_next_tx_observed")
        self.assertTrue(a["read_timeout_after_b9fb_on_original_channel"])
        self.assertIsNone(a["last_rx_to_first_next_tx_ms"])
        self.assertEqual(a["within_1000_ms"], "no_next_tx_observed")

    def test_06_partial_or_off_route_b9fb_is_not_completed(self):
        partial = tx() + response(include_final=False) + tx(A3, at=2_000_000)
        report = tool.audit("\n".join(partial))
        self.assertEqual(report["completed_b9fb_count"], 0)
        self.assertEqual(report["incomplete_b9fb_count"], 1)
        wrong = tx() + response(can=0x01200004)
        audit = tool.audit("\n".join(wrong))
        self.assertEqual(audit["completed_b9fb_count"], 0)
        self.assertEqual(audit["parse_errors"]["off_route_b9fb_rx"], 13)

    def test_07_pid_and_epoch_boundaries_prevent_false_followup(self):
        lines = tx() + response()
        lines += tx(A3, pid="FEEDBEEF", at=1_100_000)
        lines += [marker("PassThruClose")]
        lines += tx(A3, at=1_232_000)
        a = tool.audit("\n".join(lines))["observations"][0]
        self.assertEqual(a["followup_observation"], "close_before_next_tx")
        self.assertIsNone(a["last_rx_to_first_next_tx_ms"])
        reset = tx() + response() + [marker("PassThruOpen -> device 1")]
        reset += tx(A3, at=1_432_000)
        b = tool.audit("\n".join(reset))["observations"][0]
        self.assertEqual(b["followup_observation"], "open_before_next_tx")

    def test_08_wraparound_privacy_cli_and_exclusive_output(self):
        rollover_tx = (1 << 32) - 50_000
        lines = tx(at=rollover_tx) + response(
            first=(rollover_tx + 20_000) % (1 << 32))
        last = (rollover_tx + 32_000) % (1 << 32)
        lines += tx(A3, at=(last + 100_000) % (1 << 32))
        observation = tool.audit("\n".join(lines))["observations"][0]
        self.assertEqual(observation["last_rx_to_first_next_tx_ms"], 100)
        self.assertEqual(observation["b9fb_tx_to_last_rx_ms"], 32)
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            file, output = p / "private.log", p / "result.json"
            private = "PRIVATE_VIN_HOST_NAME"
            file.write_text("\n".join(lines + [private]), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(file), "--output", str(output)]), 0)
            content = output.read_text(encoding="utf-8")
            self.assertNotIn(private, content)
            self.assertNotIn("ABCDEF12", content)
            self.assertNotIn("PRIVATE_CLIENT", content)
            self.assertNotIn("CB 50 B9", content)
            self.assertEqual(json.loads(content)["completed_b9fb_count"], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(file), "--output", str(output)]), 2)
                self.assertEqual(tool.main([str(file), "--output", str(file)]), 2)


if __name__ == "__main__":
    unittest.main()
