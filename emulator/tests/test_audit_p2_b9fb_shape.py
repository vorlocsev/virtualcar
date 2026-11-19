"""Eight synthetic, privacy-safe P2 B9FB structure audit regression groups."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import audit_p2_b9fb_shape as audit


# Synthetic layout only, NOT captured XC90 MY2009 or a valid vehicle identity.
LAB_VIN = b"YV1CZ0002A0000001"


def content(vin=LAB_VIN, suffix=b"000001", marker=b"\x57\x00", fields=True):
    result = marker + b"\x00" * 4
    result += (b"005\r\n" + vin + b"\r\n" + b"000000000\r\n" +
               b"275\r\n" + suffix + b"\r\n" + b"00\r\n" +
               b"200900\r\n" + b"00000000000000000000\r\n")
    assert len(result) == 88, len(result)
    if not fields:
        result = result.replace(b"005\r\n", b"005\rX")
    return result


def frames(blob=None, target=0x50, can_id=0x01200003):
    raw = bytes((target, 0xF9, 0xFB)) + (content() if blob is None else blob)
    pieces = [raw[i:i + 7] for i in range(0, len(raw), 7)]
    result = []
    for i, piece in enumerate(pieces):
        if i == 0:
            control = 0x8F
        elif i == len(pieces) - 1:
            control = 0x48 + len(piece)
        else:
            control = 0x08 | (i & 7)
        result.append((can_id, bytes([control]) + piece.ljust(7, bytes([0]))))
    return result


def log_for(fixture):
    tx = bytes.fromhex("00 0F FF FE CB 50 B9 FB 00 00 00 00")
    rows = ["[PID=DEADBEEF SecretHost.exe] TX (app request) " + tx.hex(" ").upper()]
    rows.extend("[PID=DEADBEEF SecretHost.exe] PassThruReadMsgs -> delivered " +
                (can_id.to_bytes(4, "big") + data).hex(" ").upper()
                for can_id, data in fixture)
    return "\n".join(rows) + "\n"


class B9FBShapeEvidenceTests(unittest.TestCase):
    def test_01_matched_88_byte_layout_is_not_vehicle_acceptance(self):
        out = audit.audit_frames(frames())
        self.assertEqual((out["transport"], out["rx_frames"], out["payload_byte_count"]),
                         ("complete", 13, 88))
        self.assertEqual(out["published_88_byte_shape"], "matches_one_observed_example")
        self.assertEqual(out["vin_field_offset"], 11)
        self.assertTrue(out["embedded_nul"] and out["vin_shaped_field"])
        self.assertEqual(out["observed_crlf_count"], 8)
        self.assertEqual(out["observed_length_marker_relation"],
                         "first_byte_equals_remaining_byte_count")
        self.assertEqual(out["six_digit_field_compared_with_vin_suffix"], "equal")
        self.assertFalse(out["vehicle_identity_verified"] or out["replay_approved"])
        self.assertEqual((out["client_result"], out["normal_mode_result"]),
                         ("client_result_unknown", "unknown"))

    def test_02_synthetic_chassis_suffix_disagrees_without_exposing_values(self):
        out = audit.audit_frames(frames(content(suffix=b"999999")))
        self.assertEqual(out["six_digit_field_compared_with_vin_suffix"], "different")
        serialized = json.dumps(out)
        self.assertNotIn("999999", serialized)
        self.assertNotIn(LAB_VIN.decode(), serialized)

    def test_03_invalid_vin_shape_is_not_promoted_to_identity(self):
        invalid = b"AB-CDE0002A000000"
        self.assertEqual(len(invalid), 17)
        out = audit.audit_frames(frames(content(vin=invalid)))
        self.assertEqual(out["transport"], "complete")
        self.assertEqual(out["published_88_byte_shape"], "matches_one_observed_example")
        self.assertFalse(out["vin_shaped_field"])
        self.assertIsNone(out["vin_field_offset"])

    def test_04_wrong_sequence_and_missing_final_rejected(self):
        bad = frames()
        bad[1] = (bad[1][0], b"\x0B" + bad[1][1][1:])
        self.assertEqual(audit.audit_frames(bad)["transport"], "invalid")
        short = frames()[:-1]
        self.assertEqual(audit.audit_frames(short)["transport"], "invalid")

    def test_09_alternative_last_markers_are_invalid_transport_not_identity(self):
        # The 13-frame synthetic 0x08-series sample ends with seven bytes:
        # marker 4F. A shorter 48..4E header is not a 4F equivalent.
        good = frames()
        self.assertEqual(audit.audit_frames(good)["transport"], "complete")
        for last in range(0x48, 0x4F):
            with self.subTest(last=f"{last:02X}"):
                mutated = list(good)
                mutated[-1] = (mutated[-1][0],
                               bytes([last]) + mutated[-1][1][1:])
                out = audit.audit_frames(mutated)
                self.assertEqual(out["transport"], "invalid")
                self.assertEqual(out["transport_reason"],
                                 "d2_frame_sequence_or_response_route_invalid")
                self.assertIsNone(out["payload_byte_count"])
                self.assertFalse(out["vin_shaped_field"])
                self.assertFalse(out["vehicle_identity_verified"])
                self.assertFalse(out["replay_approved"])
                self.assertNotIn(LAB_VIN.decode(), json.dumps(out))

    def test_10_terminal_marker_length_excludes_padding(self):
        # A 166-byte blob is the *catalog-declared size*, not a real ECU
        # capture. Exercise 0x49/0x4A terminal lengths without fake identity.
        for size in (88, 89, 166, 167):
            with self.subTest(size=size):
                out = audit.audit_frames(frames(blob=bytes(size)))
                self.assertEqual(out["transport"], "complete")
                self.assertEqual(out["payload_byte_count"], size)
                self.assertEqual(out["published_88_byte_shape"], "unknown")
                self.assertFalse(out["vehicle_identity_verified"])
                self.assertFalse(out["replay_approved"])

    def test_05_negative_reply_not_taken_as_positive_b9fb(self):
        negative = [(0x01200003, bytes.fromhex("CB 50 7F B9 11 00 00 00"))]
        out = audit.audit_frames(negative)
        self.assertEqual((out["transport"], out["transport_reason"]),
                         ("negative_or_unknown", "no_positive_b9fb_echo"))
        self.assertFalse(out["vin_shaped_field"])

    def test_06_unknown_text_layout_not_rejected_as_invalid_transport(self):
        out = audit.audit_frames(frames(content(fields=False)))
        self.assertEqual(out["transport"], "complete")
        self.assertEqual(out["published_88_byte_shape"], "unknown")
        self.assertFalse(out["vin_shaped_field"])
        self.assertFalse(out["replay_approved"])

    def test_07_target_and_can_id_provenance_cannot_be_mixed(self):
        good = frames(target=0x40, can_id=0x00800003)
        self.assertEqual(audit.audit_frames(good, 0x40)["transport"], "complete")
        self.assertEqual(audit.audit_frames(good, 0x50)["transport"], "invalid")
        bad = frames()
        bad[5] = (0x01000003, bad[5][1])
        self.assertEqual(audit.audit_frames(bad, 0x50)["transport"], "invalid")

    def test_08_cli_ambiguous_sessions_privacy_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "private-source.log"
            output = root / "audit.json"
            source.write_text(log_for(frames()) + log_for(frames()),
                              encoding="utf-8")
            args = [str(source), "--target", "50", "--output", str(output)]
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    audit.main(args)  # Must NOT silently pick the longest capture.
            self.assertFalse(output.exists())
            with contextlib.redirect_stdout(io.StringIO()):
                audit.main(args + ["--session-index", "1"])
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual((report["sessions_found"], report["selected_session_index"]),
                             (2, 1))
            self.assertFalse(report["channel_and_baud_verified"])
            data = output.read_text(encoding="utf-8")
            for forbidden in (LAB_VIN.decode(), "SecretHost", "DEADBEEF",
                              str(source), "000001", "275"):
                self.assertNotIn(forbidden, data)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    audit.main(args + ["--session-index", "1"])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), report)


if __name__ == "__main__":
    unittest.main()
