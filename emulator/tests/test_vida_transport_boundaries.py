"""Transport-boundary regressions motivated by an external generic CAN/ISO-TP stack.

All examples are synthetic. They prove D2 framing behavior only, never a
Volvo identity, diagnostic-app acceptance, or an OEM ECU response.
"""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from import_p2_trace import validate_response
from audit_p2_b9fb_shape import audit_frames

CAN_ID = 0x01200003  # synthetic, not asserted for the target car


def synthetic_d2(target=0x50, opcode=0xFB):
    # 91 bytes / 7 per D2 continuation fragment = 13 full frames.
    data = bytes((target, 0xF9, opcode)) + bytes(88)
    payloads = [data[i:i + 7] for i in range(0, len(data), 7)]
    assert len(payloads) == 13 and all(len(p) == 7 for p in payloads)
    return [(CAN_ID, bytes((0x8F if i == 0 else
                            0x4F if i == 12 else
                            (0x08 | (i & 7)),)) + chunk)
            for i, chunk in enumerate(payloads)]


class VolvoVidaTransportBoundaryTests(unittest.TestCase):
    def test_01_valid_d2_transport_is_not_identity(self):
        frames = synthetic_d2()
        validate_response(frames, 0x50, 0xFB)
        result = audit_frames(frames)
        self.assertEqual((result["transport"], result["rx_frames"]), ("complete", 13))
        self.assertFalse(result["vehicle_identity_verified"])
        self.assertFalse(result["replay_approved"])
        self.assertFalse(result["vin_shaped_field"])

    def test_02_iso_tp_single_or_first_frame_cannot_be_d2(self):
        cases = (
            [(CAN_ID, bytes.fromhex("03 62 F1 90 00 00 00 00"))],
            [(CAN_ID, bytes.fromhex("10 0A 62 F1 90 00 00 00")),
             (CAN_ID, bytes.fromhex("21 00 00 00 00 00 00 00"))],
        )
        for frames in cases:
            with self.subTest(frames=len(frames)):
                with self.assertRaises(ValueError):
                    validate_response(frames, 0x50, 0xFB)
                self.assertEqual(audit_frames(frames)["transport"], "invalid")

    def test_03_iso_tp_flow_control_cannot_replace_d2_fragment(self):
        frames = synthetic_d2()
        frames[1] = (CAN_ID, bytes.fromhex("30 00 00 00 00 00 00 00"))
        with self.assertRaises(ValueError):
            validate_response(frames, 0x50, 0xFB)

    def test_04_target_and_service_are_both_part_of_response_identity(self):
        frames = synthetic_d2()
        for target, opcode in ((0x40, 0xFB), (0x50, 0xF0), (0x50, 0xFC)):
            with self.subTest(target=target, opcode=opcode):
                with self.assertRaises(ValueError):
                    validate_response(frames, target, opcode)

    def test_05_fragments_from_two_can_ids_cannot_mix(self):
        frames = synthetic_d2()
        frames[6] = (CAN_ID + 1, frames[6][1])
        with self.assertRaises(ValueError):
            validate_response(frames, 0x50, 0xFB)

    def test_06_j2534_metadata_is_not_part_of_eight_byte_d2_frame(self):
        for payload in (b"\x00" * 7, b"\x00" * 9, b"\x00" * 12):
            with self.subTest(length=len(payload)):
                frames = synthetic_d2()
                frames[3] = (CAN_ID, payload)
                with self.assertRaises(ValueError):
                    validate_response(frames, 0x50, 0xFB)

    def test_07_d2_sequence_and_final_marker_are_required(self):
        for mode in ("wrong_sequence", "missing_final", "wrong_final"):
            frames = synthetic_d2()
            if mode == "wrong_sequence":
                frames[4] = (CAN_ID, b"\x0F" + frames[4][1][1:])
            elif mode == "missing_final":
                frames.pop()
            else:
                frames[-1] = (CAN_ID, b"\x4E" + frames[-1][1][1:])
            with self.subTest(mode=mode):
                with self.assertRaises(ValueError):
                    validate_response(frames, 0x50, 0xFB)

    def test_08_unrelated_raw_broadcast_is_not_a_d2_response(self):
        broadcast = [(CAN_ID, bytes.fromhex("FF C8 00 00 00 00 00 00"))]
        with self.assertRaises(ValueError):
            validate_response(broadcast, 0x50, 0xFB)
        self.assertEqual(audit_frames(broadcast)["transport"], "invalid")


if __name__ == "__main__":
    unittest.main()
