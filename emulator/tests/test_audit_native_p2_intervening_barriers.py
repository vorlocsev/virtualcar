"""Eight source-local barriers preventing accidental B9FB -> A3 pairing."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from test_audit_d2_followup_window import A3, D2FB, marker, response, tx

spec = importlib.util.spec_from_file_location(
    "channel_chronology_barrier_tests",
    ROOT / "tools" / "audit_native_p2_channel_chronology.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

OTHER = bytes.fromhex("02 09 02 00 00 00 00 00")
B9F0 = bytes.fromhex("CB 50 B9 F0 00 00 00 00")


def epoch(lines):
    result = tool.audit("\n".join(lines))
    assert result["epochs_with_events"] == 1
    return result["epochs"][0]


def completed():
    return tx(D2FB) + response()


def first(epoch_):
    return epoch_["first_completed_b9fb_to_later_a3"]


class ChannelChronologyBarrierTests(unittest.TestCase):
    def test_01_other_obd_tx_between_b9fb_and_a3_blocks_same_channel(self):
        e = epoch(completed() + tx(OTHER, can=0x7DF, at=1_050_000)
                  + tx(A3, at=1_060_000))
        self.assertEqual(first(e)["status"], "intervening_other_app_tx")
        self.assertEqual(e["outcome"], "a3_after_b9fb_intervening_other_app_tx")
        self.assertFalse(first(e)["same_channel_target_generation_verified"])
        self.assertIsNone(first(e)["last_b9fb_rx_to_first_later_a3_ms"])

    def test_02_other_channel_tx_still_blocks_direct_causal_pair(self):
        e = epoch(completed() + tx(OTHER, can=0x7DF, channel=2,
                                   at=1_050_000) + tx(A3, at=1_060_000))
        self.assertEqual(first(e)["status"], "intervening_other_app_tx")
        self.assertFalse(e["same_channel_proven_for_observed_order"])

    def test_03_other_d2_service_b9f0_blocks_direct_pair(self):
        e = epoch(completed() + tx(B9F0, at=1_050_000)
                  + tx(A3, at=1_060_000))
        self.assertEqual(first(e)["status"], "intervening_other_app_tx")
        self.assertEqual(e["a3_requested"], 1)

    def test_04_clear_rx_after_completed_b9fb_blocks_pair(self):
        e = epoch(completed() +
                  [marker("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")]
                  + tx(A3, at=1_060_000))
        self.assertEqual(first(e)["status"], "clear_rx_between_events")
        self.assertEqual(e["outcome"], "a3_after_b9fb_clear_rx_between_events")
        self.assertFalse(first(e)["same_channel_target_generation_verified"])

    def test_05_clear_rx_before_b9fb_completes_prevents_completion(self):
        full = completed()
        e = epoch(full[:12] +
                  [marker("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")]
                  + full[12:] + tx(A3, at=1_100_000))
        self.assertEqual(e["b9fb_completed"], 0)
        self.assertEqual(e["b9fb_incomplete"], 1)
        self.assertEqual(first(e)["status"], "no_completed_b9fb_observed")

    def test_06_other_tx_before_b9fb_does_not_invalidate_future_pair(self):
        e = epoch(tx(OTHER, can=0x7DF, at=900_000)
                  + completed() + tx(A3, at=1_060_000))
        self.assertEqual(first(e)["status"], "same_channel_target_timed")
        self.assertTrue(first(e)["same_channel_target_generation_verified"])
        self.assertEqual(first(e)["last_b9fb_rx_to_first_later_a3_ms"], 28)

    def test_07_other_tx_after_first_a3_not_retroactively_a_barrier(self):
        e = epoch(completed() + tx(A3, at=1_060_000)
                  + tx(OTHER, can=0x7DF, at=1_080_000))
        self.assertEqual(first(e)["status"], "same_channel_target_timed")
        self.assertEqual(first(e)["first_later_a3_order"], 3)
        self.assertEqual(e["outcome"], "a3_after_b9fb_same_channel_and_target")

    def test_08_other_pid_cannot_splice_into_same_process(self):
        e = epoch(completed() + tx(A3, at=1_060_000))
        self.assertEqual(first(e)["status"], "same_channel_target_timed")
        different_pid = completed() + tx(OTHER, can=0x7DF,
                                       pid="FEEDBEEF", at=1_050_000)
        different_pid += tx(A3, at=1_060_000)
        results = tool.audit("\n".join(different_pid))
        self.assertEqual(results["epochs_with_events"], 1)
        self.assertEqual(first(results["epochs"][0])["status"],
                         "same_channel_target_timed")
        self.assertNotIn("FEEDBEEF", str(results))
        self.assertFalse(results["client_b9fb_acceptance_verified"])


if __name__ == "__main__":
    unittest.main()
