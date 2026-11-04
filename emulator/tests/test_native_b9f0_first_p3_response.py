"""Eight synthetic post-B9F0 first P3 DID RX checks.

The first P3 request and its RX belong to one local native J2534 PID epoch.
No authenticated XC90 ECU identity, client acceptance or part number exists.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import audit_native_b9f0_response as audit_tool
from test_native_b9f0_response import F0, f0_response, disconnect, clear
from test_audit_d2_followup_window import D2FB, marker, response, tx, rx, words
from test_prepare_p2_capture import tool as capture

P3 = bytes.fromhex("05 22 F1 90 00 00 00 00")
POS = bytes.fromhex("05 62 F1 90 41 42 00 00")
NEG = bytes.fromhex("03 7F 22 13 00 00 00 00")
PENDING = bytes.fromhex("03 7F 22 78 00 00 00 00")
MISMATCH = bytes.fromhex("05 62 F1 87 41 42 00 00")
FF = bytes.fromhex("10 0A 62 F1 90 41 42 43")
CF = bytes.fromhex("21 44 45 46 47 00 00 00")


def chain():
    return tx(F0, at=1_000_000) + f0_response(start=1_040_000)


def p3_tx(*, channel=1, can=0x726, protocol=5, at=1_120_000):
    if protocol == 6:
        result = [marker(audit_tool.TX_CTX,
                         words(channel, 6, 0x100, 500000, at)),
                  marker("TX (app request)",
                         can.to_bytes(4, "big") +
                         bytes.fromhex("22 F1 90"))]
        return result
    return tx(P3, channel=channel, can=can, at=at)


def p3_rx(payload=POS, *, channel=1, can=0x72E, protocol=5,
          at=1_140_000, status=0, pid="ABCDEF12"):
    if protocol == 5 and status == 0:
        return rx(payload, channel=channel, can=can, at=at, pid=pid)
    return [
        marker(audit_tool.RX_CTX,
               words(channel, protocol, status, 500000, at), pid=pid),
        marker("PassThruReadMsgs -> delivered",
               can.to_bytes(4, "big") + payload, pid=pid),
    ]


def run(*extra):
    data = audit_tool.audit("\n".join(chain() + [
        line for segment in extra for line in segment]))
    positive = [x for x in data["observations"]
                if x["positive_echo_transport_complete"]]
    if len(positive) != 1:
        raise AssertionError("expected exactly one positive B9F0 in fixture")
    return positive[0], data


class P3FirstResponseAfterB9F0Tests(unittest.TestCase):
    def test_01_can_single_frame_positive_checks_header_not_identity(self):
        obs, data = run(p3_tx(), p3_rx())
        self.assertEqual(obs["first_next_p3_response_status"],
                         "positive_transport_complete")
        self.assertTrue(obs["first_next_p3_positive_transport_complete"])
        self.assertEqual(obs["first_next_p3_rx_frames"], 1)
        self.assertEqual(obs["first_next_p3_tx_to_last_rx_ms"], 20)
        self.assertEqual(data["post_positive_first_p3_positive_transport_count"], 1)
        self.assertEqual(data["post_positive_first_p3_response_status_counts"],
                         {"positive_transport_complete": 1})
        self.assertFalse(obs["ecu_enumeration_verified"])
        self.assertFalse(data["client_acceptance_verified"])

    def test_02_variable_size_iso15765_positive_on_29bit_route(self):
        obs, data = run(p3_tx(channel=2, can=0x18DA50F1, protocol=6),
                        p3_rx(bytes.fromhex("62 F1 90 41 42"),
                              channel=2, can=0x18DAF150,
                              protocol=6, status=0x100))
        self.assertEqual(obs["first_next_p3_response_status"],
                         "positive_transport_complete")
        self.assertFalse(obs["first_next_app_tx_same_channel"])
        self.assertEqual(obs["first_next_p3_rx_frames"], 1)
        self.assertFalse(data["ecu_enumeration_verified"])

    def test_03_negative_pending_and_later_positive_are_distinct(self):
        negative, _ = run(p3_tx(), p3_rx(NEG))
        self.assertEqual(negative["first_next_p3_response_status"],
                         "negative_response")
        self.assertFalse(negative["first_next_p3_positive_transport_complete"])
        resolved, _ = run(p3_tx(),
                          p3_rx(PENDING, at=1_140_000),
                          p3_rx(POS, at=1_160_000))
        self.assertEqual(resolved["first_next_p3_response_status"],
                         "positive_transport_complete")
        self.assertEqual(resolved["first_next_p3_pending_count"], 1)
        pending_only, _ = run(
            p3_tx(), p3_rx(PENDING),
            [marker("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",
                    words(1, 500, 1))])
        self.assertEqual(pending_only["first_next_p3_response_status"],
                         "response_pending_timeout")
        self.assertFalse(pending_only["first_next_p3_positive_transport_complete"])

    def test_04_mismatched_did_and_empty_positive_record_fail_closed(self):
        mismatch, _ = run(p3_tx(), p3_rx(MISMATCH))
        self.assertEqual(mismatch["first_next_p3_response_status"],
                         "mismatched_did_or_service")
        no_record, _ = run(p3_tx(),
                           p3_rx(bytes.fromhex("03 62 F1 90 00 00 00 00")))
        self.assertEqual(no_record["first_next_p3_response_status"],
                         "missing_did_record")
        self.assertFalse(no_record["first_next_p3_positive_transport_complete"])

    def test_05_can_isotp_multiframe_partial_complete_and_wrong_sequence(self):
        complete, _ = run(p3_tx(), p3_rx(FF), p3_rx(CF, at=1_150_000))
        self.assertEqual(complete["first_next_p3_response_status"],
                         "positive_transport_complete")
        self.assertEqual(complete["first_next_p3_rx_frames"], 2)
        partial, _ = run(p3_tx(), p3_rx(FF), [marker("PassThruClose")])
        self.assertEqual(partial["first_next_p3_response_status"], "partial_rx")
        corrupt, _ = run(
            p3_tx(), p3_rx(FF),
            p3_rx(bytes.fromhex("22 44 45 46 47 00 00 00"), at=1_150_000))
        self.assertEqual(corrupt["first_next_p3_response_status"],
                         "invalid_transport")

    def test_06_foreign_pid_channel_canid_baud_and_indication_do_not_count(self):
        foreign, _ = run(
            p3_tx(), p3_rx(POS, channel=2),
            p3_rx(POS, can=0x72F),
            p3_rx(POS, pid="FEEDBEEF"),
            p3_rx(POS, status=0x08))
        self.assertEqual(foreign["first_next_p3_response_status"],
                         "off_route_rx_only")
        self.assertEqual(foreign["first_next_p3_off_route_rx_count"], 1)
        self.assertEqual(foreign["first_next_p3_ignored_indication_count"], 1)
        self.assertEqual(foreign["first_next_p3_rx_frames"], 0)
        self.assertFalse(foreign["first_next_p3_positive_transport_complete"])
        wrong_baud = [
            marker(audit_tool.RX_CTX, words(1, 5, 0, 125000, 1_150_000)),
            marker("PassThruReadMsgs -> delivered",
                   (0x72E).to_bytes(4, "big") + POS),
        ]
        wrong, _ = run(p3_tx(), wrong_baud)
        self.assertEqual(wrong["first_next_p3_response_status"],
                         "off_route_rx_only")

    def test_07_supersession_clear_disconnect_and_epoch_block_stale_rx(self):
        other_channel, _ = run(p3_tx(), disconnect(2), p3_rx())
        self.assertEqual(other_channel["first_next_p3_response_status"],
                         "positive_transport_complete")
        same_disconnect, _ = run(p3_tx(), disconnect(1), p3_rx())
        self.assertEqual(same_disconnect["first_next_p3_response_status"],
                         "no_matched_rx")
        same_clear, _ = run(p3_tx(), clear(1), p3_rx())
        self.assertEqual(same_clear["first_next_p3_response_status"],
                         "no_matched_rx")
        superseded, _ = run(p3_tx(), tx(F0, at=1_130_000), p3_rx())
        self.assertEqual(superseded["first_next_p3_response_status"],
                         "no_matched_rx")
        epoch, _ = run(
            p3_tx(), ["=== SECTORV VIRTUALCAR SESSION PRIVATE_EPOCH ==="],
            p3_rx())
        self.assertEqual(epoch["first_next_p3_response_status"],
                         "no_matched_rx")

    def test_08_integrated_summary_redacts_did_and_has_no_client_verdict(self):
        private = "PRIVATE_CUSTOMER_ECU_VIN_AND_HARDWARE_ID"
        source = "\n".join(
            tx(D2FB) + response() + tx(F0, at=1_132_000)
            + f0_response(start=1_142_000)
            + p3_tx(at=1_202_000)
            + p3_rx(POS, at=1_222_000)
            + [marker("PassThruClose"), private])
        reports = capture.prepare(source)
        evidence = reports["capture-summary.json"]["b9f0_native_transport_audit"]
        self.assertEqual(
            evidence["post_positive_first_p3_response_status_counts"],
            {"positive_transport_complete": 1})
        self.assertEqual(
            evidence["post_positive_first_p3_positive_transport_count"], 1)
        self.assertFalse(evidence["client_acceptance_verified"])
        self.assertFalse(evidence["ecu_enumeration_verified"])
        self.assertFalse(reports["capture-summary.json"]["b9f0_response_verified"])
        safe = json.dumps(reports)
        for secret in (private, "ABCDEF12", "FEEDBEEF", "F1 90", "YV1"):
            self.assertNotIn(secret, safe)


if __name__ == "__main__":
    unittest.main()
