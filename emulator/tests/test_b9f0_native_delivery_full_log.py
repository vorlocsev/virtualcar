"""Synthetic tests: native B9F0 delivery is not OEM/VIDA ECU acceptance."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_b9f0_native_delivery as audit
sys.path.pop(0)

HOST = "[PID=ABCD1234 PrivateDiagnosticClient.exe] "


def be(*values):
    return b"".join(v.to_bytes(4, "big") for v in values)


def event(label, data=b""):
    return HOST + label + (" " + data.hex(" ").upper() if data else "") + "\n"


def frames(target=0x40):
    return [
        bytes((0x8F, target, 0xF9, 0xF0, 0x00, 0x08, 0x68, 0x85)),
        bytes((0x09, 0x13, 0x20, 0x20, 0x41, 0x30, 0x65, 0x70)),
        bytes((0x4C, 0x24, 0x20, 0x20, 0x41, 0x00, 0x00, 0x00)),
    ]


def delivered(payloads, baud=125000, channel=1, generation=1):
    out = []
    for frame, payload in enumerate(payloads, 1):
        out.extend([
            event("RX context channel/protocol/status/baud/time-us (BE)",
                  be(channel, 5, 0, baud, 102000)),
            event("PassThruReadMsgs -> delivered",
                  be(0x00800003) + payload),
            event("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
                  be(channel, generation, frame, 102000, 104000)),
        ])
    return out


class B9F0NativeRxTests(unittest.TestCase):
    def test_01_three_tagged_frames_are_emitter_delivery_shape_only(self):
        r = audit.analyze_source(delivered(frames()))
        n = r["native_d2_delivery_tags"]
        self.assertEqual(n["b9f0_emitter_rx_groups_with_positive_first_echo"], 1)
        self.assertEqual(n["b9f0_emitter_rx_groups_with_contiguous_terminal"], 1)
        self.assertEqual((n["b9f0_emitter_rx_groups"][0]["target"],
                          n["b9f0_emitter_rx_groups"][0]["baud_bps"]), ("0x40", 125000))
        self.assertFalse(r["sectorv_ecu_identity_accepted_verified"])

    def test_02_missing_terminal_is_partial(self):
        n = audit.analyze_source(delivered(frames()[:2]))["native_d2_delivery_tags"]
        self.assertEqual(n["b9f0_emitter_rx_groups_with_contiguous_terminal"], 0)
        self.assertEqual(n["b9f0_emitter_rx_groups"][0]["delivery_shape"],
                         "partial_or_ambiguous")

    def test_03_wrong_service_echo_is_excluded(self):
        src = frames()
        src[0] = bytes((0x8F, 0x40, 0xF9, 0xFB, 0, 0, 0, 0))
        n = audit.analyze_source(delivered(src))["native_d2_delivery_tags"]
        self.assertEqual(n["b9f0_emitter_rx_groups_with_positive_first_echo"], 0)

    def test_04_missing_tag_does_not_prove_complete(self):
        src = delivered(frames())
        src.pop()
        n = audit.analyze_source(src)["native_d2_delivery_tags"]
        self.assertEqual(n["b9f0_emitter_rx_groups_with_contiguous_terminal"], 0)

    def test_05_full_cli_over_old_20k_transaction_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "PRIVATE_NATIVE.log"
            with src.open("w", encoding="utf-8") as writer:
                writer.write("unrelated private event\n" * 20001)
                writer.writelines(delivered(frames()))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(audit.main(["--native", str(src)]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["source_scan_counts"]["source_rows_scanned"], 20010)
            self.assertEqual(report["native_d2_delivery_tags"][
                "b9f0_emitter_rx_groups_with_contiguous_terminal"], 1)
            self.assertNotIn("ABCD1234", output.getvalue())
            self.assertNotIn(str(src), output.getvalue())

    def test_06_oversized_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "PRIVATE_NATIVE.log"
            src.write_text("hello", encoding="utf-8")
            with patch.object(audit, "MAX_SOURCE_BYTES", 1):
                with self.assertRaises(SystemExit) as ctx:
                    audit.main(["--native", str(src)])
            self.assertEqual(ctx.exception.code, 2)

    def test_07_staged_marker_cannot_confirm_client_identity(self):
        records = [event("P2 D2 read-only recorded frames staged",
                         bytes((0xCB, 0x40, 0xB9, 0xF0)))]
        records.extend(delivered(frames()))
        r = audit.analyze_source(records)
        self.assertFalse(r["real_ecu_response_verified"])
        self.assertFalse(r["native_d2_delivery_tags"]["b9f0_replay_stage_correlated_to_rx"])
        self.assertFalse(r["native_d2_delivery_tags"]["b9f0_original_client_ecu_identity_accepted"])


if __name__ == "__main__":
    unittest.main()
