"""dev33: eight synthetic evidence groups for UDS responsePending and DID completeness.

These are not MY2009 ECU recordings or positive response fixtures.
"""
import importlib.util
import json
from pathlib import Path
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py"
spec = importlib.util.spec_from_file_location("audit_j2534_discovery", SCRIPT)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def words(*values):
    return b"".join(v.to_bytes(4, "big") for v in values)


def line(label, data=b"", pid="DEADBEEF", host="SyntheticDiagnostics.exe"):
    return f"[PID={pid} {host}] {label}" + (
        (" " + data.hex(" ").upper()) if data else "")


def tx(ch=1, proto=5, can=0x726, data=b"\x03\x22\xf1\x14\x00\x00\x00\x00", now=100000):
    return [
        line("TX context channel/protocol/flags/baud/time-us (BE)",
             words(ch, proto, 0x100 if can > 0x7FF else 0, 500000, now)),
        line("TX (app request)", can.to_bytes(4, "big") + data),
    ]


def rx(data, ch=1, proto=5, can=0x72E, now=102000):
    return [
        line("RX context channel/protocol/status/baud/time-us (BE)",
             words(ch, proto, 0, 500000, now)),
        line("PassThruReadMsgs -> delivered", can.to_bytes(4, "big") + data),
    ]


PENDING = bytes.fromhex("03 7F 22 78 00 00 00 00")
REJECT = bytes.fromhex("03 7F 22 31 00 00 00 00")
HEADER_ONLY = bytes.fromhex("03 62 F1 14 00 00 00 00")
POSITIVE = bytes.fromhex("04 62 F1 14 41 00 00 00")
MISMATCH = bytes.fromhex("04 62 F1 90 41 00 00 00")


def analyze(lines):
    return audit.audit(lines)


class PendingEvidenceTests(unittest.TestCase):
    def test_01_pending_only_is_unverified_not_negative_or_delivered(self):
        report = analyze(tx() + rx(PENDING))
        one = report["transactions"][0]
        self.assertEqual((one["status"], one["reason"]),
                         ("unverified", "uds_response_pending_only"))
        self.assertEqual((one["rx_frames"], one["response_pending_frames"]), (1, 1))
        self.assertEqual(report["counts"], {"unverified": 1})

    def test_02_pending_followed_by_matching_positive(self):
        logs = tx() + rx(PENDING, now=101000) + rx(POSITIVE, now=108000)
        one = analyze(logs)["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"], one["response_pending_frames"]),
                         ("delivered", 2, 1))
        self.assertEqual(one["window_ms"], 8)
        self.assertEqual(one["reason"], "p3_uds_transport_only")

    def test_03_repeated_pending_followed_by_final_negative(self):
        logs = tx() + rx(PENDING, now=101000) + rx(PENDING, now=103000)
        logs += rx(REJECT, now=111000)
        one = analyze(logs)["transactions"][0]
        self.assertEqual(one["status"], "negative_response")
        self.assertEqual(one["response_pending_frames"], 2)
        self.assertEqual(one["rx_frames"], 3)
        self.assertNotEqual(one["reason"], "uds_response_pending_only")

    def test_04_pending_and_explicit_j2534_timeout(self):
        logs = tx() + rx(PENDING)
        logs += [line("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",
                      words(1, 500, 1))]
        one = analyze(logs)["transactions"][0]
        self.assertEqual((one["status"], one["reason"]),
                         ("timeout", "j2534_timeout_after_response_pending"))
        self.assertEqual(one["response_pending_frames"], 1)

    def test_05_reassembled_iso15765_pending_then_final_positive(self):
        logs = tx(proto=6, data=bytes.fromhex("22 F1 14"))
        logs += rx(bytes.fromhex("7F 22 78"), proto=6, now=101000)
        logs += rx(bytes.fromhex("62 F1 14 41"), proto=6, now=104000)
        one = analyze(logs)["transactions"][0]
        self.assertEqual((one["status"], one["response_pending_frames"]), ("delivered", 1))
        self.assertEqual(one["window_ms"], 4)

    def test_06_header_only_positive_is_not_complete(self):
        for proto, req_data, answer in (
            (5, bytes.fromhex("03 22 F1 14 00 00 00 00"), HEADER_ONLY),
            (6, bytes.fromhex("22 F1 14"), bytes.fromhex("62 F1 14")),
        ):
            with self.subTest(proto=proto):
                one = analyze(tx(proto=proto, data=req_data) +
                              rx(answer, proto=proto))["transactions"][0]
                self.assertEqual((one["status"], one["reason"]),
                                 ("partial_rx", "missing_uds_identifier_data"))

    def test_07_positive_with_one_data_record_byte_is_transport_only(self):
        for proto, req_data, answer in (
            (5, bytes.fromhex("03 22 F1 14 00 00 00 00"), POSITIVE),
            (6, bytes.fromhex("22 F1 14"), bytes.fromhex("62 F1 14 41")),
        ):
            with self.subTest(proto=proto):
                report = analyze(tx(proto=proto, data=req_data) + rx(answer, proto=proto))
                one = report["transactions"][0]
                self.assertEqual(one["status"], "delivered")
                self.assertFalse(report["replay_approved"])
                self.assertFalse(report["contains_payload_data"])

    def test_08_multichannel_mismatch_and_redaction(self):
        logs = tx(ch=1) + tx(ch=2, can=0x18DA50F1)
        logs += rx(PENDING, ch=1)
        logs += rx(POSITIVE, ch=2, can=0x18DAF150)
        logs += rx(MISMATCH, ch=1)
        report = analyze(logs)
        one, two = report["transactions"]
        self.assertEqual((one["channel"], one["status"], one["response_pending_frames"]),
                         (1, "unverified", 1))
        self.assertEqual(one["reason"], "uds_response_does_not_match_request")
        self.assertEqual((two["channel"], two["status"], two["id_format"]),
                         (2, "delivered", "29bit"))
        data = json.dumps(report)
        self.assertNotIn("DEADBEEF", data)
        self.assertNotIn("SyntheticDiagnostics", data)
        self.assertNotIn("62 F1 14", data)
        self.assertNotIn("7F 22 78", data)
        self.assertNotIn("41 00 00", data)


if __name__ == "__main__":
    unittest.main()
