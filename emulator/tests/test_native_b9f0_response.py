"""Eight read-only synthetic/native B9F0 transport evidence regressions.

All payload content is invented zero-filled framing. Neither B9F0 headers
nor B9FB responses establish original CEM hardware identity.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import audit_native_b9f0_response as tool
from test_audit_d2_followup_window import D2FB, marker, response, tx, rx, words
from test_prepare_p2_capture import tool as capture

F0 = bytes.fromhex("CB 50 B9 F0 00 00 00 00")
F0_40 = bytes.fromhex("CB 40 B9 F0 00 00 00 00")
POS = (
    bytes.fromhex("8F 50 F9 F0 00 00 00 00"),
    bytes.fromhex("09 00 00 00 00 00 00 00"),
    bytes.fromhex("4C 00 00 00 00 00 00 00"),
)
NEG = bytes.fromhex("CC 50 7F B9 31 00 00 00")


def f0_response(*, pid="ABCDEF12", channel=1, can=0x01000003,
                baud=500000, start=1_040_000, payloads=POS):
    lines = []
    for i, payload in enumerate(payloads):
        lines.extend(rx(payload, channel=channel, baud=baud, pid=pid,
                        can=can, at=start + 1000*i))
    return lines


def report(lines):
    return tool.audit("\n".join(lines))


def disconnect(channel):
    return [marker("PassThruDisconnect channel (BE)",
                   channel.to_bytes(4, "big")), marker("PassThruDisconnect")]


def clear(channel):
    return [
        marker(tool.CLEAR_CTX, words(channel, 5, 0, 500000, 1_055_000)),
        marker("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped"),
    ]


class NativeB9F0ResponseTests(unittest.TestCase):
    def test_01_synthetic_three_frame_positive_transport_only(self):
        data = report(tx(F0, at=1_000_000) + f0_response()
                      + [marker("PassThruClose")])
        self.assertEqual(data["request_count"], 1)
        self.assertEqual(data["status_counts"], {"positive_transport_complete": 1})
        item = data["observations"][0]
        self.assertEqual(item["rx_frames"], 3)
        self.assertTrue(item["positive_echo_transport_complete"])
        self.assertEqual(item["tx_to_last_matched_rx_ms"], 42)
        self.assertFalse(item["part_number_decoded"])
        self.assertFalse(item["vehicle_identity_verified"])
        self.assertFalse(data["client_acceptance_verified"])

    def test_02_b9_negative_is_not_a_positive_identity(self):
        data = report(tx(F0) + f0_response(payloads=(NEG,)))
        item = data["observations"][0]
        self.assertEqual(item["status"], "negative_b9_service_reply")
        self.assertTrue(item["negative_b9_service_reply_observed"])
        self.assertFalse(item["positive_echo_transport_complete"])
        self.assertFalse(data["any_positive_transport_observed"])

    def test_03_incomplete_no_reply_and_timeout_are_distinct(self):
        incomplete = report(tx(F0) + f0_response(payloads=POS[:2]))
        self.assertEqual(incomplete["observations"][0]["status"], "partial_rx")
        empty = report(tx(F0) + [marker("PassThruClose")])
        self.assertEqual(empty["observations"][0]["status"], "no_matched_rx")
        timeout = [marker("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",
                          words(1, 500, 1))]
        delayed = report(tx(F0) + timeout + [marker("PassThruClose")])
        self.assertEqual(delayed["observations"][0]["status"], "read_timeout_observed")
        self.assertTrue(delayed["observations"][0]["read_timeout_observed"])

    def test_04_foreign_rx_and_tx_indications_cannot_complete_transport(self):
        foreign = report(tx(F0)
                         + f0_response(can=0x01200004)
                         + f0_response(channel=2)
                         + [marker("PassThruClose")])
        item = foreign["observations"][0]
        self.assertEqual(item["status"], "off_route_rx_only")
        self.assertEqual(item["off_route_rx_count"], 3)
        signal = [
            marker(tool.RX_CTX, words(1, 5, 0x108, 500000, 1_040_000)),
            marker("PassThruReadMsgs -> delivered",
                   (0x01000003).to_bytes(4, "big") + POS[0]),
        ]
        check = report(tx(F0) + signal + f0_response())
        self.assertEqual(check["observations"][0]["status"],
                         "positive_transport_complete")
        self.assertEqual(check["observations"][0]["ignored_rx_indication_count"], 1)
        only_indication = report(tx(F0) + signal)
        self.assertEqual(only_indication["observations"][0]["status"], "no_matched_rx")

    def test_05_foreign_service_echo_does_not_authenticate_a_positive(self):
        bad = list(POS)
        bad[0] = bytes.fromhex("8F 50 F9 FB 00 00 00 00")
        check = report(tx(F0) + f0_response(payloads=bad))
        self.assertEqual(check["observations"][0]["status"], "invalid_transport")
        self.assertEqual(check["parse_errors"]["invalid_b9f0_transport"], 1)
        self.assertFalse(check["any_positive_transport_observed"])
        wrong = report(tx(F0_40, baud=500000)
                       + f0_response(payloads=POS))
        self.assertEqual(wrong["request_count"], 0)
        self.assertEqual(wrong["parse_errors"]["b9f0_wrong_bus_request"], 1)

    def test_06_scoped_disconnect_and_clear_reset_only_the_named_channel(self):
        other = report(tx(F0) + f0_response(payloads=POS[:1])
                       + disconnect(2)
                       + f0_response(payloads=POS[1:]))
        self.assertEqual(other["observations"][0]["status"],
                         "positive_transport_complete")
        own = report(tx(F0) + f0_response(payloads=POS[:1])
                     + disconnect(1)
                     + f0_response(payloads=POS[1:]))
        self.assertEqual(own["observations"][0]["status"], "partial_rx")
        reset = report(tx(F0) + f0_response(payloads=POS[:1])
                       + clear(1) + f0_response(payloads=POS[1:]))
        self.assertEqual(reset["observations"][0]["status"], "partial_rx")

    def test_07_new_tx_and_second_pid_never_join_partial_reply(self):
        first = tx(F0) + f0_response(payloads=POS[:1])
        superseded = report(first + tx(F0, at=1_050_000)
                            + f0_response(start=1_060_000))
        self.assertEqual([x["status"] for x in superseded["observations"]],
                         ["partial_rx", "positive_transport_complete"])
        different_pid = report(tx(F0)
                               + f0_response(pid="FEEDBEEF"))
        self.assertEqual(different_pid["observations"][0]["status"],
                         "no_matched_rx")
        self.assertFalse(different_pid["any_positive_transport_observed"])

    def test_08_integrated_three_file_report_privacy_and_exclusive_output(self):
        private = "PRIVATE_CUSTOMER_VIN_PART_NUMBER_NEVER_EXPORT"
        source = "\n".join(tx(D2FB) + response()
                           + tx(F0, at=1_132_000)
                           + f0_response(start=1_142_000)
                           + [marker("PassThruClose"), private])
        reports = capture.prepare(source)
        summary = reports["capture-summary.json"]
        evidence = summary["b9f0_native_transport_audit"]
        self.assertEqual(summary["b9f0_requests_observed"], 1)
        self.assertEqual(evidence["request_count"], 1)
        self.assertEqual(evidence["status_counts"],
                         {"positive_transport_complete": 1})
        self.assertTrue(evidence["positive_echo_transport_observed"])
        self.assertFalse(evidence["part_number_decoded"])
        self.assertFalse(evidence["client_acceptance_verified"])
        self.assertFalse(summary["b9f0_response_verified"])
        self.assertNotIn(private, json.dumps(reports))
        self.assertNotIn("ABCDEF12", json.dumps(reports))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            native, result = root / "private.log", root / "report.json"
            native.write_text(source, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(native), "--output", str(result)]), 0)
            output = result.read_text(encoding="utf-8")
            for secret in (private, "ABCDEF12", "PRIVATE_CLIENT",
                           "CB 50 B9 F0", str(native)):
                self.assertNotIn(secret, output)
            self.assertEqual(json.loads(output)["request_count"], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(native), "--output", str(result)]), 2)
                self.assertEqual(tool.main([str(native), "--output", str(native)]), 2)
            self.assertEqual(native.read_text(encoding="utf-8"), source)


if __name__ == "__main__":
    unittest.main()
