"""Eight bounded synthetic B3A50 D2 route matrix gates."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_b3a50_d2_matrix as audit
sys.path.pop(0)

HOST = "[PID=1234ABCD iexplore.exe] "
OTHER = "[PID=DEADBEEF iexplore.exe] "


def _be(*words):
    return " ".join(f"{byte:02X}" for w in words
                    for byte in w.to_bytes(4, "big")) + " "


def req(target, opcode, baud, host=HOST):
    return host + audit.REQUEST + " " + _be(target, opcode, baud, 0)


def result(kind, target, opcode, host=HOST):
    return host + audit.RESULTS[kind] + " CB %02X B9 %02X " % (target, opcode)


class D2RouteMatrixTests(unittest.TestCase):
    def test_01_target40_strict_250_not_an_ecu_reply(self):
        out = audit.analyze([req(0x40, 0xFB, 250000),
                             result("strict_bus_rejected", 0x40, 0xFB)])
        self.assertEqual(out["same_logger_prefix_paired_outcomes"], 1)
        self.assertTrue(out["paired_route_outcomes"][0]["differs_from_base_fixture_baud"])
        self.assertFalse(out["genuine_ecu_rx_verified"])

    def test_02_target50_missing_verified_fixture(self):
        out = audit.analyze([req(0x50, 0xF0, 500000),
                             result("no_validated_fixture", 0x50, 0xF0)])
        self.assertEqual(out["paired_route_outcomes"][0]["command"], "B9F0")
        self.assertFalse(out["paired_route_outcomes"][0]["differs_from_base_fixture_baud"])

    def test_03_two_opcodes_and_staged_is_not_delivered(self):
        out = audit.analyze([req(0x40, 0xFB, 125000),
                             result("no_validated_fixture", 0x40, 0xFB),
                             req(0x50, 0xFC, 500000),
                             result("recorded_frames_staged", 0x50, 0xFC)])
        self.assertEqual(out["observed_d2_request_count"], 2)
        self.assertEqual(out["same_logger_prefix_paired_outcomes"], 2)
        self.assertFalse(out["vin_accepted_verified"])

    def test_04_other_host_cannot_bind_outcome(self):
        out = audit.analyze([req(0x40, 0xFB, 250000),
                             result("strict_bus_rejected", 0x40, 0xFB, OTHER)])
        self.assertEqual(out["unpaired_outcomes"], 1)
        self.assertEqual(out["unpaired_requests"], 1)

    def test_05_bad_metadata_and_false_d2_shape_fail_closed(self):
        out = audit.analyze([HOST + audit.REQUEST + " 01 GG",
                             result("strict_bus_rejected", 0x40, 0xFB),
                             req(0x40, 0xFB, 250000),
                             HOST + audit.RESULTS["strict_bus_rejected"] + " DD 40 B9 FB "])
        self.assertEqual(out["malformed_request_metadata"], 1)
        self.assertEqual(out["malformed_outcome_metadata"], 1)
        self.assertEqual(out["same_logger_prefix_paired_outcomes"], 0)

    def test_06_reject_far_or_ambiguous_pairs(self):
        out = audit.analyze([req(0x40, 0xFB, 250000)] +
                            [HOST + "unrelated"] * 25 +
                            [result("strict_bus_rejected", 0x40, 0xFB)])
        self.assertEqual(out["unpaired_outcomes"], 1)
        other = audit.analyze([req(0x40, 0xFB, 250000)] * 2 +
                              [result("strict_bus_rejected", 0x40, 0xFB)])
        self.assertEqual(other["ambiguous_pairings"], 1)

    def test_07_no_private_numeric_payload_or_pid_leak(self):
        out = audit.analyze([HOST + "TX (app request) PRIVATE_VIN",
                             req(0x40, 0xFB, 900000),
                             result("no_validated_fixture", 0x40, 0xFB)])
        encoded = json.dumps(out)
        for secret in ("PRIVATE_VIN", "1234ABCD", "900000", "CB 40 B9 FB", "iexplore"):
            self.assertNotIn(secret, encoded)
        self.assertEqual(out["paired_route_outcomes"][0]["baud_bps"], "other")

    def test_08_bounded_input_and_no_fabricated_acceptance(self):
        with self.assertRaisesRegex(ValueError, "bounded_native_lines_exceeded"):
            audit.analyze(["unrelated"] * (audit.MAX_ROWS + 1))
        out = audit.analyze([])
        self.assertEqual(out["observed_d2_request_count"], 0)
        self.assertFalse(out["original_vida_client_verified"])
        self.assertFalse(out["genuine_ecu_rx_verified"])
        self.assertFalse(out["vin_accepted_verified"])


if __name__ == "__main__":
    unittest.main()
