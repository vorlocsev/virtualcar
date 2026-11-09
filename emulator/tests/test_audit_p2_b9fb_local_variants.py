"""Eight private B9FB comparison gates: never infer origin from VIN-only variants."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import audit_p2_b9fb_local_variants as variants

SYNTHETIC_A = b"YV1CZ0002A0000001"
SYNTHETIC_B = b"YV1CZ0003A0000002"
REQUEST = "TX (app request) 00 0F FF FE CB 50 B9 FB 00 00 00 00"


def response(vin=SYNTHETIC_A, can_id=0x01200003, body=None):
    if body is None:
        body = (b"\x57\x00" + b"\x00" * 4 + b"005\r\n" + vin
                + b"\r\n000000000\r\n275\r\n000001\r\n00\r\n"
                + b"200900\r\n00000000000000000000\r\n")
    assert len(body) == 88, len(body)
    raw = b"\x50\xF9\xFB" + body
    pieces = [raw[i:i+7] for i in range(0, len(raw), 7)]
    assert len(pieces) == 13 and all(len(piece) == 7 for piece in pieces)
    return [(can_id, bytes((0x8F if i == 0 else
                            0x4F if i == 12 else 0x08 | (i & 7),)) + piece)
            for i, piece in enumerate(pieces)]


def log_for(frames, simulated=False):
    rows = [REQUEST]
    for can_id, data in frames:
        raw = can_id.to_bytes(4, "big") + data
        if simulated:
            rows.append("RX (simulated) " + raw.hex(" ").upper())
        else:
            rows.append("PassThruReadMsgs() msg[0].Data = [" +
                        ", ".join(f"0x{byte:02x}" for byte in raw) + "]")
    return rows


def native_log(generated, received):
    def records(label, frames):
        return [f"[PID=00000001 Synthetic.exe] {label} "
                + (can_id.to_bytes(4, "big") + data).hex(" ")
                for can_id, data in frames]

    return ([REQUEST] + records("RX (simulated)", generated)
            + records("PassThruReadMsgs -> delivered", received))


class B9FBLocalCandidateTests(unittest.TestCase):
    def test_01_single_valid_candidate_still_not_oem_or_approved(self):
        report = variants.audit_local_logs([log_for(response())])
        self.assertEqual((report["sources_checked"], report["candidate_count"]), (1, 1))
        self.assertEqual(report["transport_categories"], {"complete": 1})
        self.assertEqual(report["comparison_groups"][0]["candidate_count"], 1)
        self.assertFalse(report["replay_approved"])
        self.assertEqual(report["authentic_vehicle_provenance"], "not_verified")
        self.assertEqual(report["candidates"][0]["origin_marker"],
                         "unverified_trace_origin")

    def test_02_vin_field_only_change_is_counted_not_exposed(self):
        report = variants.audit_local_logs([
            log_for(response(SYNTHETIC_A)),
            log_for(response(SYNTHETIC_B)),
        ])
        groups = report["comparison_groups"]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["candidate_count"], 2)
        self.assertEqual(groups[0]["distinct_observed_17byte_field_values"], 2)
        self.assertFalse(groups[0]["oem_origin_verified"])
        self.assertEqual([x["comparison_group"] for x in report["candidates"]], [0, 0])
        encoded = json.dumps(report)
        for forbidden in (SYNTHETIC_A.decode(), SYNTHETIC_B.decode(),
                          "01200003", "200900", "000001"):
            self.assertNotIn(forbidden, encoded)

    def test_03_non_field_byte_difference_must_not_merge_groups(self):
        base = response()
        changed = response(body=(
            b"\x57\x00" + b"\x00" * 4 + b"005\r\n" + SYNTHETIC_A
            + b"\r\n000000000\r\n276\r\n000001\r\n00\r\n"
            + b"200900\r\n00000000000000000000\r\n"))
        self.assertEqual(len(changed), len(base))
        report = variants.audit_local_logs([log_for(base), log_for(changed)])
        self.assertEqual(len(report["comparison_groups"]), 2)
        self.assertEqual([g["candidate_count"] for g in report["comparison_groups"]],
                         [1, 1])

    def test_04_different_can_id_does_not_count_as_same_variant(self):
        report = variants.audit_local_logs([
            log_for(response(can_id=0x01200003)),
            log_for(response(can_id=0x01210003)),
        ])
        self.assertEqual(len(report["comparison_groups"]), 2)
        serialized = json.dumps(report)
        self.assertNotIn("01200003", serialized)
        self.assertNotIn("01210003", serialized)

    def test_05_simulator_marker_is_not_independent_ecu_capture(self):
        report = variants.audit_local_logs([
            log_for(response(SYNTHETIC_A), simulated=True),
            log_for(response(SYNTHETIC_B), simulated=False),
        ])
        self.assertEqual(report["origin_marker_categories"],
                         {"emulator_tagged_rx": 1, "unverified_trace_origin": 1})
        group = report["comparison_groups"][0]
        self.assertEqual(group["emulator_tagged_count"], 1)
        self.assertEqual(group["unverified_origin_count"], 1)
        self.assertFalse(report["replay_approved"])
        self.assertFalse(group["oem_origin_verified"])

    def test_06_invalid_sequence_does_not_become_comparable(self):
        broken = response()
        broken[1] = (broken[1][0], b"\x0B" + broken[1][1][1:])
        report = variants.audit_local_logs([log_for(broken)])
        self.assertEqual(report["candidate_count"], 1)
        self.assertEqual(report["transport_categories"], {"invalid": 1})
        self.assertIsNone(report["candidates"][0]["comparison_group"])
        self.assertEqual(report["comparison_groups"], [])

    def test_07_negative_or_unknown_shape_never_becomes_vin_variant(self):
        negative = [(0x01200003, bytes.fromhex("CB 50 7F B9 11 00 00 00"))]
        nonshape = response(body=(
            b"\x57\x00" + b"\x00" * 4 + b"005\rX" + SYNTHETIC_A
            + b"\r\n000000000\r\n275\r\n000001\r\n00\r\n"
            + b"200900\r\n00000000000000000000\r\n"))
        report = variants.audit_local_logs([log_for(negative), log_for(nonshape)])
        self.assertEqual(report["candidate_count"], 2)
        self.assertEqual(report["comparison_groups"], [])
        self.assertEqual([r["transport"] for r in report["candidates"]],
                         ["negative_or_unknown", "complete"])
        self.assertTrue(all(row["comparison_group"] is None
                            for row in report["candidates"]))
        empty = variants.audit_local_logs([[REQUEST]])
        self.assertEqual(empty["candidate_count"], 0)

    def test_08_cli_redaction_exclusive_output_and_alias_guards(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            local = directory / "PRIVATE_SOURCE_VIN.log"
            output = directory / "safe.json"
            local.write_text("\n".join(log_for(response())) + "\n",
                             encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with redirect_stdout(out), redirect_stderr(err):
                variants.main([str(local), "--output", str(output)])
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["candidate_count"], 1)
            self.assertNotIn(str(local), output.read_text(encoding="utf-8"))
            self.assertNotIn(SYNTHETIC_A.decode(), output.read_text(encoding="utf-8"))
            old = output.read_bytes()
            with redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    variants.main([str(local), "--output", str(output)])
                with self.assertRaises(SystemExit):
                    variants.main([str(local), "--output", str(local)])
                with self.assertRaises(SystemExit):
                    variants.main([str(local), str(local), "--output",
                                   str(directory / "new.json")])
            self.assertEqual(output.read_bytes(), old)
            self.assertFalse((directory / "new.json").exists())

    def test_09_generation_and_delivery_are_one_observed_response(self):
        frames = response()
        report = variants.audit_local_logs([native_log(frames, frames)])
        row, = report["candidates"]
        self.assertEqual((row["rx_frames"], row["transport"], row["origin_marker"]),
                         (13, "complete", "emulator_tagged_rx"))

    def test_10_queued_tail_does_not_complete_partial_delivery(self):
        frames = response()
        report = variants.audit_local_logs([native_log(frames, frames[:-1])])
        row, = report["candidates"]
        self.assertEqual((row["rx_frames"], row["transport"]), (12, "invalid"))
        self.assertEqual(report["comparison_groups"], [])

    def test_11_duplicate_reads_are_not_removed_as_queue_markers(self):
        frames = response()
        report = variants.audit_local_logs([native_log(frames, frames + frames)])
        row, = report["candidates"]
        self.assertEqual((row["rx_frames"], row["transport"]), (26, "invalid"))

    def test_12_generated_only_stays_an_emulator_candidate(self):
        report = variants.audit_local_logs([native_log(response(), [])])
        row, = report["candidates"]
        self.assertEqual((row["rx_frames"], row["transport"], row["origin_marker"]),
                         (13, "complete", "emulator_tagged_rx"))

    def test_13_delivery_only_stays_an_emulator_candidate(self):
        report = variants.audit_local_logs([native_log([], response())])
        row, = report["candidates"]
        self.assertEqual((row["rx_frames"], row["transport"], row["origin_marker"]),
                         (13, "complete", "emulator_tagged_rx"))

    def test_14_legacy_reads_do_not_borrow_generated_frames(self):
        frames = response()
        rows = native_log(frames, []) + log_for(frames, simulated=False)[1:]
        report = variants.audit_local_logs([rows])
        row, = report["candidates"]
        self.assertEqual((row["rx_frames"], row["transport"], row["origin_marker"]),
                         (13, "complete", "emulator_tagged_rx"))

    def test_15_read_stream_resets_at_session_boundary(self):
        first, second = response(), response(SYNTHETIC_B)
        rows = native_log(first, first) + ["PassThruClose"] + native_log(second, [])
        report = variants.audit_local_logs([rows])
        self.assertEqual(report["transport_categories"], {"complete": 2})
        self.assertEqual(report["comparison_groups"][0]["distinct_observed_17byte_field_values"], 2)


if __name__ == "__main__":
    unittest.main()
