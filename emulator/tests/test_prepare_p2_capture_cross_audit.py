"""Eight offline consistency tests of independent native P2 safe reports."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from test_prepare_p2_capture import tool, complete, A3_40
from test_audit_d2_followup_window import A3, D2FB, tx, rx, response, marker

NEGATIVE_B9FB = bytes.fromhex("CB 50 7F B9 FB 00 00 00")


class NativeCaptureCrossAuditTests(unittest.TestCase):
    def test_01_native_13_frame_positive_report_agrees(self):
        reports = tool.prepare(complete())
        summary = reports["capture-summary.json"]
        cross = summary["cross_audit_consistency"]
        self.assertTrue(cross["transport_completion_count_agrees"])
        self.assertEqual(cross["first_a3_cross_audit_status"],
                         "first_a3_same_channel_target_clock_agrees")
        self.assertEqual(cross["first_a3_gap_ms_when_cross_verified"], 100)
        self.assertFalse(cross["client_acceptance_verified"])
        self.assertFalse(summary["safe_to_infer_complete_client_session"])

    def test_02_negative_single_frame_b9fb_not_counted_as_positive(self):
        text = "\n".join(tx(D2FB) + rx(NEGATIVE_B9FB)
                         + [marker("PassThruClose")])
        reports = tool.prepare(text)
        s = reports["capture-summary.json"]
        self.assertEqual(s["b9fb_requests_observed"], 1)
        self.assertEqual(s["b9fb_transport_completions_observed"], 0)
        self.assertEqual(reports["b9fb-followup.json"]["completed_b9fb_count"], 0)
        self.assertEqual(reports["channel-chronology.json"]["epochs"][0]
                         ["b9fb_completed"], 0)
        self.assertEqual(s["cross_audit_consistency"]["first_a3_cross_audit_status"],
                         "not_comparable")
        self.assertFalse(s["last_b9fb_to_first_a3_client_acceptance_verified"])

    def test_03_independent_completion_count_divergence_rejected(self):
        normal = tool.audit_followup(complete())
        changed = copy.deepcopy(normal)
        changed["completed_b9fb_count"] += 1
        with patch.object(tool, "audit_followup", return_value=changed):
            with self.assertRaisesRegex(ValueError, "independent_b9fb_transport"):
                tool.prepare(complete())

    def test_04_independent_first_a3_gap_divergence_rejected(self):
        normal = tool.audit_followup(complete())
        changed = copy.deepcopy(normal)
        changed["observations"][0]["last_rx_to_first_next_tx_ms"] += 20
        with patch.object(tool, "audit_followup", return_value=changed):
            with self.assertRaisesRegex(ValueError, "independent_b9fb_a3_clocks"):
                tool.prepare(complete())

    def test_05_independent_wrong_target_or_channel_rejected(self):
        normal = tool.audit_followup(complete())
        for field in ("first_next_tx_same_channel", "first_next_tx_same_target",
                      "first_next_tx_same_baud"):
            changed = copy.deepcopy(normal)
            changed["observations"][0][field] = False
            with self.subTest(field=field), patch.object(
                    tool, "audit_followup", return_value=changed):
                with self.assertRaisesRegex(ValueError, "correlation_disagrees"):
                    tool.prepare(complete())

    def test_06_buffer_clear_after_b9fb_is_not_direct_pair(self):
        text = "\n".join(tx(D2FB) + response() +
                         [marker("J2534 CLEAR_RX_BUFFER: synthetic")]
                         + tx(A3, at=1_132_000)
                         + [marker("PassThruClose")])
        reports = tool.prepare(text)
        cross = reports["capture-summary.json"]["cross_audit_consistency"]
        self.assertTrue(cross["transport_completion_count_agrees"])
        self.assertEqual(cross["first_a3_cross_audit_status"],
                         "no_verified_direct_first_a3_pair")
        self.assertIsNone(cross["first_a3_gap_ms_when_cross_verified"])
        self.assertFalse(cross["client_acceptance_verified"])

    def test_07_multiple_process_epochs_not_time_joined(self):
        source = "\n".join(
            tx(D2FB) + response()
            + [marker("PassThruClose")]
            + tx(D2FB, pid="FEEDBEEF", channel=2, baud=500000, at=2_000_000)
            + response(channel=2, pid="FEEDBEEF", first=2_020_000)
            + tx(A3, pid="FEEDBEEF", channel=2, at=2_232_000)
            + [marker("PassThruClose", pid="FEEDBEEF")])
        reports = tool.prepare(source)
        s = reports["capture-summary.json"]
        self.assertEqual(s["native_epochs"], 2)
        self.assertEqual(s["b9fb_transport_completions_observed"], 2)
        self.assertEqual(s["cross_audit_consistency"]["first_a3_cross_audit_status"],
                         "not_comparable")
        self.assertNotIn("FEEDBEEF", json.dumps(reports))
        self.assertFalse(s["same_run_with_sectorv_client_verified"])

    def test_08_malformed_capture_stays_unverified_and_private(self):
        source = "\n".join(tx(D2FB) + response()
                           + [marker("TX (app request) PRIVATE_BAD_FRAME")]
                           + tx(A3, at=1_132_000)
                           + [marker("PassThruClose")])
        reports = tool.prepare(source)
        cross = reports["capture-summary.json"]["cross_audit_consistency"]
        self.assertEqual(cross["first_a3_cross_audit_status"],
                         "source_context_incomplete")
        self.assertIsNone(cross["first_a3_gap_ms_when_cross_verified"])
        self.assertNotIn("PRIVATE_BAD_FRAME", json.dumps(reports))
        self.assertFalse(reports["capture-summary.json"]
                         ["native_tx_rx_context_complete"])


if __name__ == "__main__":
    unittest.main()
