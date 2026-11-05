"""Eight P2 import regressions against cross-family D2 first/last mixing.

Observed references:
- P2 XC70 historical donor: 8F/09..4F, CAN ID 0x01200003.
- P1 V50 2007 public (TRUNCATED): 97/11..17, CAN ID 0x00400003.
- Existing Virtual Car host C fixture: 97/11/55/8F/4C.

This is framing validation ONLY. Neither a true XC90 identity nor a
successful SectorV Hardware condition is inferred from these examples.
The P1 body below is zero-filled, not the donor's actual VIN.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "p2_import_transport_bridge", ROOT / "tools" / "import_p2_trace.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

P2_ID = 0x01200003
P1_ID = 0x00400003
BRIDGED = [
    bytes.fromhex("97 50 F9 FB 57 00 31 82"),
    bytes.fromhex("11 17 96 30 30 32 0D 0A"),
    bytes.fromhex("55 FF FF FF FF 00 00 00"),
    bytes.fromhex("8F 50 F9 FB FF FF FF FF"),
    bytes.fromhex("4C FF FF FF FF 00 00 00"),
]
P1_TRUNCATED = [
    bytes.fromhex("97 50 F9 FB FE 00 31 82")
] + [bytes([0x10 + n]) + bytes(7) for n in range(1, 8)]


def frames(payloads, can=P2_ID):
    return [(can, data) for data in payloads]


class D2TransportBridgeSafetyTests(unittest.TestCase):
    def test_01_p2_13_frame_redacted_donor_stays_valid(self):
        sample = ROOT / "samples" / "p2_b9fb_public_redacted.txt"
        runs = module.sessions(sample.read_text(encoding="utf-8").splitlines(),
                               0x50, 0xFB)
        self.assertTrue(runs)
        source = runs[0]
        self.assertEqual(len(source), 13)
        self.assertEqual(source[0][1][0], 0x8F)
        module.validate_response(source, 0x50, 0xFB)

    def test_02_existing_vida_97_55_8f_4c_bridge_stays_valid(self):
        module.validate_response(frames(BRIDGED), 0x50, 0xFB)

    def test_03_bare_97_11_4c_crossover_is_not_proven(self):
        corrupted = [BRIDGED[0], BRIDGED[1], BRIDGED[-1]]
        with self.assertRaisesRegex(ValueError, "Unverified"):
            module.validate_response(frames(corrupted), 0x50, 0xFB)

    def test_04_truncated_public_p1_97_1x_is_not_a_complete_p2_block(self):
        with self.assertRaisesRegex(ValueError, "Missing final"):
            module.validate_response(frames(P1_TRUNCATED, P1_ID), 0x50, 0xFB)

    def test_05_false_positive_service_echo_rejected(self):
        corrupted = list(BRIDGED)
        corrupted[0] = bytes.fromhex("97 50 E3 FB 57 00 31 82")
        with self.assertRaises(ValueError):
            module.validate_response(frames(corrupted), 0x50, 0xFB)

    def test_06_other_cem_target_cannot_pair_response(self):
        with self.assertRaises(ValueError):
            module.validate_response(frames(BRIDGED), 0x40, 0xFB)

    def test_07_missing_or_reordered_consecutive_marker_is_rejected(self):
        for changed_control in (0x12, 0x0A, 0x4F):
            broken = list(BRIDGED)
            broken[1] = bytes([changed_control]) + BROKEN_PAYLOAD
            with self.subTest(header=changed_control), self.assertRaises(ValueError):
                module.validate_response(frames(broken), 0x50, 0xFB)

    def test_08_can_id_alone_does_not_authenticate_protocol_family(self):
        # A different 29-bit CAN response ID by itself does NOT identify a
        # P1 or P2 CEM variant. The validator enforces frame/echo coherence
        # but makes no model-year or original-car claims.
        module.validate_response(frames(BRIDGED, P1_ID), 0x50, 0xFB)
        module.validate_response(frames(BRIDGED, P2_ID), 0x50, 0xFB)
        with self.assertRaises(ValueError):
            module.validate_response(
                frames(BRIDGED[:2], P1_ID) + frames(BRIDGED[2:], P2_ID),
                0x50, 0xFB)


BROKEN_PAYLOAD = BRIDGED[1][1:]


if __name__ == "__main__":
    unittest.main()
