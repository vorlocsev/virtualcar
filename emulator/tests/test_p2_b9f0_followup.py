"""Eight synthetic offline checks for the first B9F0 read after a completed B9FB.

No client executable, original VIN, private capture, physical adapter or
ECU reply is used. B9F0 TX is not proof of B9F0 RX or identity acceptance.
"""
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from test_audit_d2_followup_window import A3, D2FB, marker, response, tx
from test_prepare_p2_capture import tool as capture

B9F0_50 = bytes.fromhex("CB 50 B9 F0 00 00 00 00")
B9F0_40 = bytes.fromhex("CB 40 B9 F0 00 00 00 00")


def observation(*tail, start=1_000_000, first=1_020_000):
    return "\n".join(tx(D2FB, at=start) + response(first=first)
                     + [line for segment in tail for line in segment]
                     + [marker("PassThruClose")])


def get(source):
    reports = capture.prepare(source)
    epoch = reports["channel-chronology.json"]["epochs"][0]
    followup = reports["b9fb-followup.json"]["observations"][0]
    cross = reports["capture-summary.json"]["cross_audit_consistency"]
    return reports, epoch, followup, cross


class B9F0FirstLaterTests(unittest.TestCase):
    def test_01_first_b9f0_same_route_same_clock_is_request_only(self):
        reports, epoch, first, cross = get(
            observation(tx(B9F0_50, at=1_132_000)))
        f0 = epoch["first_completed_b9fb_to_later_b9f0"]
        self.assertEqual(first["first_next_tx_service"], "d2_b9f0")
        self.assertEqual(first["last_rx_to_first_next_tx_ms"], 100)
        self.assertEqual(f0["status"], "same_channel_target_timed")
        self.assertEqual(f0["last_b9fb_rx_to_first_later_b9f0_ms"], 100)
        self.assertEqual(cross["first_b9f0_cross_audit_status"],
                         "first_b9f0_same_channel_target_clock_agrees")
        self.assertEqual(cross["first_b9f0_gap_ms_when_cross_verified"], 100)
        self.assertFalse(cross["b9f0_response_verified"])
        self.assertFalse(reports["capture-summary.json"]["b9f0_response_verified"])

    def test_02_other_channel_does_not_become_direct_verified_pair(self):
        _, epoch, first, cross = get(
            observation(tx(B9F0_50, channel=2, at=1_132_000)))
        self.assertEqual(first["first_next_tx_service"], "d2_b9f0")
        self.assertFalse(first["first_next_tx_same_channel"])
        self.assertEqual(epoch["first_completed_b9fb_to_later_b9f0"]["status"],
                         "different_channel")
        self.assertEqual(cross["first_b9f0_cross_audit_status"],
                         "no_verified_direct_first_b9f0_pair")

    def test_03_other_cem_target_not_confused_with_original_target(self):
        _, epoch, first, cross = get(
            observation(tx(B9F0_40, baud=500000, at=1_132_000)))
        self.assertEqual(first["first_next_tx_target"], "0x40")
        self.assertFalse(first["first_next_tx_same_target"])
        self.assertEqual(epoch["first_completed_b9fb_to_later_b9f0"]["status"],
                         "different_target")
        self.assertEqual(cross["first_b9f0_cross_audit_status"],
                         "no_verified_direct_first_b9f0_pair")

    def test_04_first_a3_is_not_rewritten_as_first_b9f0(self):
        _, epoch, first, cross = get(observation(
            tx(A3, at=1_132_000), tx(B9F0_50, at=1_232_000)))
        self.assertEqual(first["first_next_tx_service"], "d2_a3_target_known")
        self.assertEqual(epoch["first_completed_b9fb_to_later_b9f0"]["status"],
                         "intervening_other_app_tx")
        self.assertEqual(cross["first_a3_cross_audit_status"],
                         "first_a3_same_channel_target_clock_agrees")
        self.assertEqual(cross["first_b9f0_cross_audit_status"],
                         "no_verified_direct_first_b9f0_pair")

    def test_05_repeated_b9fb_request_blocks_direct_b9f0_pair(self):
        _, epoch, first, cross = get(observation(
            tx(D2FB, at=1_100_000), tx(B9F0_50, at=1_132_000)))
        self.assertEqual(first["first_next_tx_service"], "d2_b9fb")
        self.assertEqual(epoch["first_completed_b9fb_to_later_b9f0"]["status"],
                         "intervening_b9fb_request")
        self.assertEqual(cross["first_b9f0_cross_audit_status"],
                         "no_verified_direct_first_b9f0_pair")

    def test_06_clear_rx_buffer_blocks_direct_b9f0_claim(self):
        clear = [marker("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")]
        _, epoch, first, cross = get(observation(
            clear, tx(B9F0_50, at=1_132_000)))
        self.assertEqual(first["followup_observation"],
                         "clear_rx_before_next_tx")
        self.assertEqual(epoch["first_completed_b9fb_to_later_b9f0"]["status"],
                         "clear_rx_between_events")
        self.assertEqual(cross["first_b9f0_cross_audit_status"],
                         "no_verified_direct_first_b9f0_pair")

    def test_07_clock_rollover_is_source_local_not_wall_clock(self):
        start = (1 << 32) - 50_000
        first_rx = (start + 20_000) % (1 << 32)
        first_tx = (start + 32_000 + 100_000) % (1 << 32)
        _, epoch, first, cross = get(observation(
            tx(B9F0_50, at=first_tx), start=start, first=first_rx))
        self.assertEqual(first["last_rx_to_first_next_tx_ms"], 100)
        self.assertEqual(
            epoch["first_completed_b9fb_to_later_b9f0"]["status"],
            "same_channel_target_timed")
        self.assertEqual(cross["first_b9f0_gap_ms_when_cross_verified"], 100)

    def test_08_privacy_and_no_synthetic_b9f0_response_assertion(self):
        private = "SENSITIVE_HOST_VIN_SERIAL_DO_NOT_EXPORT"
        # A B9F0 TX and Close do not prove a response or decoded part number.
        source = observation(tx(B9F0_50, at=1_132_000)) + "\n" + private
        with tempfile.TemporaryDirectory() as tmp:
            source_file = Path(tmp, "raw.txt")
            out = Path(tmp, "safe")
            source_file.write_text(source, encoding="utf-8")
            self.assertEqual(capture.main([
                str(source_file), "--output-dir", str(out)]), 0)
            summary = json.loads((out / "capture-summary.json").read_text(
                encoding="utf-8"))
            chrono = json.loads((out / "channel-chronology.json").read_text(
                encoding="utf-8"))
            self.assertEqual(summary["b9f0_requests_observed"], 1)
            self.assertFalse(summary["b9f0_response_verified"])
            self.assertFalse(chrono["epochs"][0][
                "first_completed_b9fb_to_later_b9f0"]["b9f0_response_verified"])
            safe_text = "\n".join(p.read_text(encoding="utf-8")
                                  for p in out.iterdir())
            for item in (private, "ABCDEF12", "PRIVATE_CLIENT",
                         "CB 50 B9 F0", str(source_file)):
                self.assertNotIn(item, safe_text)
            self.assertEqual(source_file.read_text(encoding="utf-8"), source)
            self.assertEqual(capture.main([
                str(source_file), "--output-dir", str(out)]), 2)


if __name__ == "__main__":
    unittest.main()
