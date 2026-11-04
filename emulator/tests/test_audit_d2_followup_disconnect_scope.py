"""Eight native-only regression groups for per-channel J2534 Disconnect.

All events are synthetic read-only J2534 observations. This validates source
ordering and channel boundaries, not a real SectorV/VDASH acceptance result.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
from test_audit_d2_followup_window import A3, D2FB, marker, response, tx, tool
from test_prepare_p2_capture import tool as prepare_tool


def disconnect(channel=None, *, malformed=False):
    if malformed:
        return [
            marker("PassThruDisconnect channel (BE)", b"\x00\x00"),
            marker("PassThruDisconnect"),
        ]
    if channel is None:
        return [marker("PassThruDisconnect")]
    return [
        marker("PassThruDisconnect channel (BE)", channel.to_bytes(4, "big")),
        marker("PassThruDisconnect"),
    ]


def inspected(lines):
    return tool.audit("\n".join(lines))


class NativeChannelScopedDisconnectTests(unittest.TestCase):
    def test_01_other_channel_disconnect_preserves_direct_first_a3(self):
        data = inspected(tx(D2FB) + response() + disconnect(2)
                         + tx(A3, at=1_132_000))
        self.assertEqual(data["completed_b9fb_count"], 1)
        record = data["observations"][0]
        self.assertEqual(record["followup_observation"], "first_next_tx_observed")
        self.assertEqual(record["first_next_tx_service"], "d2_a3_target_known")
        self.assertEqual(record["last_rx_to_first_next_tx_ms"], 100)
        self.assertTrue(record["first_next_tx_same_channel"])
        self.assertEqual(record["within_500_ms"], "first_tx_within_window")
        self.assertNotIn("unattributed_disconnect", data["parse_errors"])

    def test_02_original_channel_disconnect_ends_waiting_response(self):
        data = inspected(tx(D2FB) + response() + disconnect(1)
                         + tx(A3, at=1_132_000))
        record = data["observations"][0]
        self.assertEqual(record["followup_observation"], "disconnect_before_next_tx")
        self.assertIsNone(record["first_next_tx_service"])
        self.assertIsNone(record["last_rx_to_first_next_tx_ms"])
        self.assertEqual(record["within_1000_ms"], "no_next_tx_observed")

    def test_03_other_channel_disconnect_does_not_truncate_active_b9fb(self):
        rx_frames = response()
        # response() alternates native RX-context and delivered-frame records.
        data = inspected(tx(D2FB) + rx_frames[:8] + disconnect(2)
                         + rx_frames[8:] + tx(A3, at=1_132_000))
        self.assertEqual(data["completed_b9fb_count"], 1)
        self.assertEqual(data["incomplete_b9fb_count"], 0)
        self.assertEqual(data["observations"][0]["b9fb_rx_frames"], 13)
        self.assertEqual(data["observations"][0]["first_next_tx_service"],
                         "d2_a3_target_known")

    def test_04_original_channel_disconnect_truncates_active_b9fb(self):
        rx_frames = response()
        data = inspected(tx(D2FB) + rx_frames[:8] + disconnect(1)
                         + rx_frames[8:] + tx(A3, at=1_132_000))
        self.assertEqual(data["completed_b9fb_count"], 0)
        self.assertEqual(data["incomplete_b9fb_count"], 1)

    def test_05_missing_disconnect_channel_is_conservative_barrier(self):
        data = inspected(tx(D2FB) + response() + disconnect()
                         + tx(A3, at=1_132_000))
        record = data["observations"][0]
        self.assertEqual(record["followup_observation"], "disconnect_before_next_tx")
        self.assertEqual(data["parse_errors"]["unattributed_disconnect"], 1)
        self.assertIsNone(record["first_next_tx_service"])

    def test_06_malformed_channel_context_does_not_guess_a_channel(self):
        data = inspected(tx(D2FB) + response() + disconnect(malformed=True)
                         + tx(A3, at=1_132_000))
        self.assertEqual(data["parse_errors"]["invalid_disconnect_context"], 1)
        self.assertEqual(data["parse_errors"]["unattributed_disconnect"], 1)
        self.assertEqual(data["observations"][0]["followup_observation"],
                         "disconnect_before_next_tx")
        self.assertIsNone(data["observations"][0]["last_rx_to_first_next_tx_ms"])

    def test_07_only_waiting_candidate_on_disconnected_channel_is_finalized(self):
        data = inspected(tx(D2FB, channel=1) + response(channel=1)
                         + tx(D2FB, channel=2, at=2_000_000)
                         + response(channel=2, first=2_020_000)
                         + disconnect(1) + tx(A3, channel=2, at=2_132_000))
        self.assertEqual(data["completed_b9fb_count"], 2)
        outcomes = [x["followup_observation"] for x in data["observations"]]
        self.assertEqual(outcomes.count("disconnect_before_next_tx"), 1)
        self.assertEqual(outcomes.count("first_next_tx_observed"), 1)
        timed = next(x for x in data["observations"]
                     if x["followup_observation"] == "first_next_tx_observed")
        self.assertEqual(timed["last_rx_to_first_next_tx_ms"], 100)
        self.assertTrue(timed["first_next_tx_same_channel"])

    def test_08_independent_capture_auditors_agree_without_private_leak(self):
        secret = "PRIVATE_VIN_HOST_PATH_NEVER_EXPORT"
        raw = "\n".join(
            tx(D2FB) + response() + disconnect(2)
            + tx(A3, at=1_132_000) + [marker("PassThruClose")]
        ) + "\n" + secret
        reports = prepare_tool.prepare(raw)
        summary = reports["capture-summary.json"]
        cross = summary["cross_audit_consistency"]
        self.assertTrue(cross["transport_completion_count_agrees"])
        self.assertEqual(cross["first_a3_cross_audit_status"],
                         "first_a3_same_channel_target_clock_agrees")
        self.assertEqual(cross["first_a3_gap_ms_when_cross_verified"], 100)
        self.assertTrue(summary["all_native_epochs_closed"])
        self.assertFalse(summary["same_run_with_sectorv_client_verified"])
        self.assertNotIn(secret, json.dumps(reports))
        self.assertNotIn("ABCDEF12", json.dumps(reports))


if __name__ == "__main__":
    unittest.main()
