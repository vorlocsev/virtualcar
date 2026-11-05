"""Eight synthetic native J2534 RxStatus groups for the B9FB followup audit.

These do not reproduce authentic CEM replies: dummy zero-filled blocks are
only used to test the D2 transport control sequence and J2534 RX metadata.
"""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
spec = importlib.util.spec_from_file_location(
    "audit_d2_followup_window", ROOT / "tools" / "audit_d2_followup_window.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

from test_audit_d2_followup_window import marker, words, tx, FIRST, A3


HEADS = [9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F]
FRAMES = [FIRST] + [bytes((head,)) + bytes(7) for head in HEADS]


def rx_status(payload, *, status=0x100, time_us=1_020_000,
              channel=1, baud=500000, can=0x01200003):
    """Emit exact native context + RX record; status is *not* payload."""
    return [
        marker(tool.CTX_RX, words(channel, 5, status, baud, time_us)),
        marker("PassThruReadMsgs -> delivered",
               can.to_bytes(4, "big") + payload),
    ]


def frame_stream(status=0x100, start=1_020_000):
    result = []
    for index, frame in enumerate(FRAMES):
        result.extend(rx_status(frame, status=status,
                                time_us=start + index * 1000))
    return result


def observation(lines):
    return tool.audit("\n".join(lines))


class B9FBStatusTests(unittest.TestCase):
    def test_01_can_29bit_id_status_is_legitimate_ecu_frame(self):
        record = observation(tx() + frame_stream() + tx(A3, at=1_132_000))
        self.assertEqual(record["completed_b9fb_count"], 1)
        result = record["observations"][0]
        self.assertEqual(result["b9fb_rx_frames"], 13)
        self.assertEqual(result["last_rx_to_first_next_tx_ms"], 100)
        self.assertFalse(record["parse_errors"].get("rx_indication_not_ecu_frame", 0))

    def test_02_tx_msg_type_first_frame_does_not_initiate_response(self):
        lines = tx() + rx_status(FIRST, status=0x101, time_us=1_010_000)
        lines += frame_stream() + tx(A3, at=1_132_000)
        record = observation(lines)
        self.assertEqual(record["completed_b9fb_count"], 1)
        self.assertEqual(record["observations"][0]["b9fb_rx_frames"], 13)
        self.assertEqual(record["parse_errors"]["rx_indication_not_ecu_frame"], 1)

    def test_03_start_of_message_first_frame_is_not_ecu_data(self):
        lines = tx() + rx_status(FIRST, status=0x102, time_us=1_009_000)
        lines += frame_stream() + tx(A3, at=1_132_000)
        record = observation(lines)
        self.assertEqual(record["completed_b9fb_count"], 1)
        self.assertEqual(record["observations"][0]["b9fb_tx_to_last_rx_ms"], 32)
        self.assertEqual(record["parse_errors"]["rx_indication_not_ecu_frame"], 1)

    def test_04_tx_indication_fake_final_cannot_finish_sequence(self):
        lines = tx()
        for i, frame in enumerate(FRAMES[:-1]):
            lines += rx_status(frame, time_us=1_020_000 + i * 1000)
        # A TX indication carrying the final-control byte is not a CEM RX.
        lines += rx_status(FRAMES[-1], status=0x108, time_us=1_031_500)
        lines += rx_status(FRAMES[-1], time_us=1_032_000)
        lines += tx(A3, at=1_232_000)
        record = observation(lines)
        self.assertEqual(record["completed_b9fb_count"], 1)
        self.assertEqual(record["observations"][0]["b9fb_rx_frames"], 13)
        self.assertEqual(record["observations"][0]["last_rx_to_first_next_tx_ms"], 200)
        self.assertEqual(record["parse_errors"]["rx_indication_not_ecu_frame"], 1)

    def test_05_combined_tx_indication_and_tx_message_type_is_not_rx(self):
        lines = tx() + rx_status(FIRST, status=0x109, time_us=1_019_000)
        lines += frame_stream()
        record = observation(lines)
        self.assertEqual(record["completed_b9fb_count"], 1)
        self.assertEqual(record["observations"][0]["followup_observation"],
                         "end_of_log_no_next_tx_observed")
        self.assertEqual(record["parse_errors"]["rx_indication_not_ecu_frame"], 1)

    def test_06_only_tx_indications_never_complete_b9fb(self):
        lines = tx() + frame_stream(status=0x108)
        record = observation(lines)
        self.assertEqual(record["completed_b9fb_count"], 0)
        self.assertEqual(record["incomplete_b9fb_count"], 1)
        self.assertEqual(record["parse_errors"]["rx_indication_not_ecu_frame"], 13)

    def test_07_interleaved_indications_cannot_shift_last_rx_clock(self):
        lines = tx()
        for i, frame in enumerate(FRAMES):
            lines += rx_status(frame, time_us=1_020_000 + i * 1000)
            if i in (2, 6, 11):
                lines += rx_status(
                    bytes((0x4F,)) + bytes(7),
                    status={2: 0x101, 6: 0x102, 11: 0x108}[i],
                    time_us=1_500_000 + i * 1000)
        lines += tx(A3, at=1_132_000)
        record = observation(lines)
        self.assertEqual(record["completed_b9fb_count"], 1)
        self.assertEqual(record["observations"][0]["last_rx_to_first_next_tx_ms"], 100)
        self.assertEqual(record["parse_errors"]["rx_indication_not_ecu_frame"], 3)

    def test_08_indication_only_response_must_not_prove_a3_transition(self):
        lines = tx()
        lines += frame_stream(status=0x108)
        lines += tx(A3, at=1_132_000)
        record = observation(lines)
        self.assertEqual(record["completed_b9fb_count"], 0)
        self.assertEqual(record["incomplete_b9fb_count"], 1)
        self.assertEqual(record["observations"], [])
        self.assertFalse(record["client_acceptance_verified"])
        self.assertFalse(record["xc90_v8_my2009_verified"])


if __name__ == "__main__":
    unittest.main()
