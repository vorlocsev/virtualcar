"""Eight synthetic first-next-app-TX checks after positive B9F0 transport.

These observe only native read-only J2534 log events, never the client's ECU
inventory, original vehicle identity, application parse result or security.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import audit_native_b9f0_response as tool
from test_native_b9f0_response import F0, POS, f0_response, disconnect, clear
from test_audit_d2_followup_window import (
    D2FB, A3, marker, response, tx, words)
from test_prepare_p2_capture import tool as capture

P3 = bytes.fromhex("03 22 F1 90 00 00 00 00")
OTHER = bytes.fromhex("02 09 02 00 00 00 00 00")


def b9f0_complete(*, at=1_000_000, rx_at=1_040_000):
    return tx(F0, at=at) + f0_response(start=rx_at)


def audit(lines):
    return tool.audit("\n".join(lines))


def first(lines):
    result = audit(lines)
    positive = [x for x in result["observations"]
                if x["positive_echo_transport_complete"]]
    assert len(positive) == 1
    return positive[0], result


class PostB9F0RequestTransitionTests(unittest.TestCase):
    def test_01_first_p3_did_read_is_request_not_ecu_enumeration(self):
        candidate, data = first(
            b9f0_complete() + tx(P3, can=0x726, at=1_100_000))
        self.assertEqual(candidate["first_next_app_tx_observation"],
                         "first_next_tx_observed")
        self.assertEqual(candidate["first_next_app_tx_service"],
                         "p3_read_data_by_identifier")
        self.assertTrue(candidate["first_next_app_tx_same_channel"])
        self.assertTrue(candidate["first_next_app_tx_same_baud"])
        self.assertEqual(candidate["last_b9f0_rx_to_first_next_tx_ms"], 58)
        self.assertEqual(data["post_positive_first_next_tx_observed_count"], 1)
        self.assertFalse(candidate["ecu_enumeration_verified"])

    def test_02_variable_size_iso15765_p3_read_is_classified_by_header(self):
        variable = [
            marker(tool.TX_CTX, words(2, 6, 0, 500000, 1_102_000)),
            marker("TX (app request)",
                   (0x18DA50F1).to_bytes(4, "big") +
                   bytes.fromhex("22 F1 90")),
        ]
        candidate, data = first(b9f0_complete() + variable)
        self.assertEqual(candidate["first_next_app_tx_service"],
                         "p3_read_data_by_identifier")
        self.assertFalse(candidate["first_next_app_tx_same_channel"])
        self.assertEqual(candidate["last_b9f0_rx_to_first_next_tx_ms"], 60)
        self.assertFalse(data["client_acceptance_verified"])

    def test_03_repeated_b9f0_and_a3_are_not_inventory_discovery(self):
        reread, result = first(b9f0_complete() + tx(F0, at=1_110_000))
        self.assertEqual(reread["first_next_app_tx_service"], "d2_b9f0")
        self.assertEqual(result["request_count"], 2)
        self.assertFalse(reread["ecu_enumeration_verified"])
        a3, _ = first(b9f0_complete() + tx(A3, at=1_120_000))
        self.assertEqual(a3["first_next_app_tx_service"], "d2_a3")
        self.assertFalse(a3["client_acceptance_verified"])

    def test_04_first_unrelated_tx_blocks_later_p3_relabeling(self):
        candidate, _ = first(b9f0_complete()
                             + tx(OTHER, can=0x7DF, at=1_110_000)
                             + tx(P3, can=0x726, at=1_130_000))
        self.assertEqual(candidate["first_next_app_tx_service"],
                         "other_or_unclassified_tx")
        self.assertEqual(candidate["last_b9f0_rx_to_first_next_tx_ms"], 68)
        # ISO-TP FC is a transport continuation, not a new ECU probe.
        flow = bytes.fromhex("30 00 00 00 00 00 00 00")
        after_fc, data = first(b9f0_complete()
                               + tx(flow, can=0x726, at=1_110_000)
                               + tx(P3, can=0x726, at=1_130_000))
        self.assertEqual(after_fc["first_next_app_tx_service"],
                         "p3_read_data_by_identifier")
        self.assertEqual(after_fc["last_b9f0_rx_to_first_next_tx_ms"], 88)
        self.assertEqual(data["post_positive_first_next_tx_observed_count"], 1)
        # The raw UDS 3E 80 TesterPresent on ISO15765 is NOT an
        # ISO-TP FC, despite sharing the high nibble 0x3.
        tester = [
            marker(tool.TX_CTX, words(2, 6, 0, 500000, 1_115_000)),
            marker("TX (app request)",
                   (0x18DA50F1).to_bytes(4, "big") +
                   bytes.fromhex("3E 80")),
        ]
        after_tester, _ = first(b9f0_complete()
                                + tester
                                + tx(P3, can=0x726, at=1_130_000))
        self.assertEqual(after_tester["first_next_app_tx_observation"],
                         "first_next_tx_observed")
        self.assertEqual(after_tester["first_next_app_tx_service"],
                         "other_or_unclassified_tx")
        self.assertEqual(after_tester["last_b9f0_rx_to_first_next_tx_ms"], 73)

    def test_05_per_channel_disconnect_and_clear_are_boundaries(self):
        other, _ = first(b9f0_complete() + disconnect(2)
                         + tx(P3, can=0x726, at=1_150_000))
        self.assertEqual(other["first_next_app_tx_service"],
                         "p3_read_data_by_identifier")
        own, _ = first(b9f0_complete() + disconnect(1)
                       + tx(P3, can=0x726, at=1_150_000))
        self.assertEqual(own["first_next_app_tx_observation"],
                         "disconnect_before_next_tx")
        self.assertIsNone(own["first_next_app_tx_service"])
        cleared, _ = first(b9f0_complete() + clear(1)
                           + tx(P3, can=0x726, at=1_150_000))
        self.assertEqual(cleared["first_next_app_tx_observation"],
                         "rx_buffer_clear_before_next_tx")

    def test_06_pid_session_and_malformed_tx_prevent_false_transition(self):
        pid, _ = first(b9f0_complete()
                       + tx(P3, can=0x726, pid="FEEDBEEF", at=1_120_000)
                       + [marker("PassThruClose")])
        self.assertEqual(pid["first_next_app_tx_observation"],
                         "close_before_next_tx")
        epoch, _ = first(b9f0_complete()
                         + ["=== SECTORV VIRTUALCAR SESSION synthetic ==="]
                         + tx(P3, can=0x726, at=1_120_000))
        self.assertEqual(epoch["first_next_app_tx_observation"],
                         "session_marker_before_next_tx")
        invalid, _ = first(b9f0_complete()
                           + [marker("TX (app request) PRIVATE_BAD_FRAME")])
        self.assertEqual(invalid["first_next_app_tx_observation"],
                         "next_tx_unattributed")
        self.assertEqual(invalid["first_next_app_tx_service"],
                         "unattributed_app_tx")

    def test_07_no_next_tx_and_wrapped_native_clock_are_not_silence_proof(self):
        closed, _ = first(b9f0_complete() + [marker("PassThruClose")])
        self.assertEqual(closed["first_next_app_tx_observation"],
                         "close_before_next_tx")
        self.assertIsNone(closed["last_b9f0_rx_to_first_next_tx_ms"])
        unfinished, _ = first(b9f0_complete())
        self.assertEqual(unfinished["first_next_app_tx_observation"],
                         "end_of_log_no_next_tx_observed")
        rollover = (1 << 32) - 50_000
        after_rx = rollover + 22_000
        at = (after_rx + 100_000) % (1 << 32)
        wrapped, _ = first(
            b9f0_complete(at=rollover, rx_at=rollover + 20_000)
            + tx(P3, can=0x726, at=at))
        self.assertEqual(wrapped["last_b9f0_rx_to_first_next_tx_ms"], 100)

    def test_08_three_file_summary_is_sanitized_and_not_a_client_verdict(self):
        secret = "PRIVATE_VIN_ECU_HARDWARE_PART_NUMBER"
        text = "\n".join(tx(D2FB) + response()
                         + tx(F0, at=1_132_000)
                         + f0_response(start=1_142_000)
                         + tx(P3, can=0x726, at=1_202_000)
                         + [marker("PassThruClose"), secret])
        reports = capture.prepare(text)
        summary = reports["capture-summary.json"]
        evidence = summary["b9f0_native_transport_audit"]
        self.assertEqual(evidence["status_counts"],
                         {"positive_transport_complete": 1})
        self.assertEqual(evidence["post_positive_first_next_tx_observed_count"], 1)
        self.assertEqual(evidence["post_positive_first_next_tx_service_counts"],
                         {"p3_read_data_by_identifier": 1})
        self.assertFalse(evidence["ecu_enumeration_verified"])
        self.assertFalse(evidence["client_acceptance_verified"])
        self.assertFalse(summary["b9f0_response_verified"])
        safe = json.dumps(reports)
        for fragment in (secret, "ABCDEF12", "PRIVATE_CLIENT",
                         "22 F1 90", "03 22 F1 90"):
            self.assertNotIn(fragment, safe)


if __name__ == "__main__":
    unittest.main()
