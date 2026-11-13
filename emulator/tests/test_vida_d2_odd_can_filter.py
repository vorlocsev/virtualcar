"""Synthetic-only regressions for spnda VIDA 2014D D2 RX-ID hypothesis.

The reported filter is not an OEM XC90 MY2009 trace and this suite never
establishes an actual J2534 filter, VIN, ECU identity, or VIDA ReadVin PASS.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_p2_b9fb_shape import (
    audit_frames,
    vida_2014d_d2_response_id_candidate,
)

SYNTHETIC_CAN_ID = 0x01200003


def d2_frames(can_id=SYNTHETIC_CAN_ID, target=0x50):
    # No VIN or OEM payload: 91 bytes, 13 complete D2 transport fragments.
    message = bytes((target, 0xF9, 0xFB)) + bytes(88)
    chunks = [message[i:i + 7] for i in range(0, len(message), 7)]
    assert len(chunks) == 13 and all(len(chunk) == 7 for chunk in chunks)
    return [(can_id,
             bytes((0x8F if i == 0 else
                    0x4F if i == 12 else
                    (0x08 | (i & 7)),)) + chunk)
            for i, chunk in enumerate(chunks)]


class VidaD2OddCanIdEvidenceTests(unittest.TestCase):
    def test_01_odd_extended_candidate_not_acceptance(self):
        report = audit_frames(d2_frames())
        self.assertEqual(report["transport"], "complete")
        self.assertEqual(report["vida2014d_d2_rx_filter_candidate"],
                         "odd_extended_id_candidate")
        self.assertFalse(report["j2534_rx_29bit_flags_verified"])
        self.assertFalse(report["vehicle_identity_verified"])
        self.assertFalse(report["replay_approved"])

    def test_02_even_extended_id_does_not_invalidate_d2_transport(self):
        report = audit_frames(d2_frames(can_id=0x01200002))
        self.assertEqual(report["transport"], "complete")
        self.assertEqual(report["vida2014d_d2_rx_filter_candidate"],
                         "even_extended_id_mask_mismatch")
        self.assertFalse(report["vehicle_identity_verified"])

    def test_03_small_odd_id_requires_actual_j2534_width_flags(self):
        report = audit_frames(d2_frames(can_id=0x701))
        self.assertEqual(report["transport"], "complete")
        self.assertEqual(report["vida2014d_d2_rx_filter_candidate"],
                         "width_unknown_without_j2534_flags")
        self.assertFalse(report["j2534_rx_29bit_flags_verified"])

    def test_04_small_even_id_also_has_unknown_width(self):
        report = audit_frames(d2_frames(can_id=0x700))
        self.assertEqual(report["transport"], "complete")
        self.assertEqual(report["vida2014d_d2_rx_filter_candidate"],
                         "width_unknown_without_j2534_flags")

    def test_05_mixed_response_ids_fail_transport_first(self):
        frames = d2_frames()
        frames[6] = (0x01200005, frames[6][1])
        report = audit_frames(frames)
        self.assertEqual(report["transport"], "invalid")
        self.assertEqual(report["vida2014d_d2_rx_filter_candidate"],
                         "not_evaluated")

    def test_06_bad_frame_order_cannot_be_mask_candidate(self):
        frames = d2_frames()
        frames[2] = (frames[2][0], bytes((0x0F,)) + frames[2][1][1:])
        report = audit_frames(frames)
        self.assertEqual(report["transport"], "invalid")
        self.assertEqual(report["vida2014d_d2_rx_filter_candidate"],
                         "not_evaluated")

    def test_07_negative_response_not_promoted_to_vin(self):
        reply = [(SYNTHETIC_CAN_ID,
                  bytes.fromhex("CB 50 7F B9 11 00 00 00"))]
        report = audit_frames(reply)
        self.assertEqual(report["transport"], "negative_or_unknown")
        self.assertEqual(report["vida2014d_d2_rx_filter_candidate"],
                         "odd_extended_id_candidate")
        self.assertFalse(report["vin_shaped_field"])
        self.assertFalse(report["vehicle_identity_verified"])

    def test_08_target40_privacy_and_invalid_id_fail_closed(self):
        report = audit_frames(d2_frames(target=0x40), target=0x40)
        self.assertEqual(report["transport"], "complete")
        self.assertEqual(report["vida2014d_d2_rx_filter_candidate"],
                         "odd_extended_id_candidate")
        output = json.dumps(report)
        self.assertNotIn("01200003", output)
        self.assertNotIn(str(SYNTHETIC_CAN_ID), output)
        self.assertNotIn('"can_id"', output)
        for invalid in (-1, 0, 0x20000000, "odd", None):
            with self.subTest(invalid=invalid):
                self.assertEqual(vida_2014d_d2_response_id_candidate(invalid),
                                 "not_evaluated")


if __name__ == "__main__":
    unittest.main()
