"""Eight synthetic A6/E6 audit groups; no ECU replay fixtures or real identities."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from test_audit_j2534_discovery import tool, tx, rx, be, event, frames13, D2FB


IDENTIFIER = bytes.fromhex("24 42")  # arbitrary synthetic parameter, not a vehicle definition


def request(target=0x40, identifier=IDENTIFIER, padded=True, **kwargs):
    data = bytes((0xCD, target, 0xA6)) + identifier + b"\x01"
    return tx(0xFFFFE, data.ljust(8, b"\xA5") if padded else data, **kwargs)


def response(target=0x40, identifier=IDENTIFIER, value=b"S", padded=True):
    body = bytes((target, 0xE6)) + identifier + value
    frame = bytes((0xC8 + len(body),)) + body
    return frame.ljust(8, b"\xA5") if padded else frame


def items(lines):
    return tool.audit(lines)["transactions"]


class D2A6EvidenceTests(unittest.TestCase):
    def test_01_single_frame_targets_lengths_and_timing(self):
        for target, can in ((0x40, 0x00800003), (0x50, 0x01000003), (0x50, 0x01200003)):
            for padded, value in ((False, b"S"), (True, b"S"), (False, b"SI"), (False, b"SIM")):
                with self.subTest(target=target, can=can, padded=padded, value=value):
                    lines = request(target, padded=padded, ch=1, baud=125000, time_us=100000)
                    lines += rx(can, response(target, value=value, padded=padded),
                                ch=1, baud=125000, time_us=104000)
                    one = items(lines)[0]
                    self.assertEqual((one["status"], one["rx_frames"], one["off_route_rx"]),
                                     ("delivered", 1, 0))
                    self.assertEqual(one["reason"], "d2_a6_single_frame_transport_only")
                    self.assertEqual(one["window_ms"], 4)

    def test_02_wrong_id_target_service_and_identifier_do_not_complete(self):
        wrong = [(0x00800004, response()), (0x72E, response()),
                 (0x01200003, response()), (0x000FFFFE, response()),
                 (0x00800003, response(target=0x50)),
                 (0x00800003, response(identifier=b"\x24\x43")),
                 (0x00800003, bytes.fromhex("CD 40 E6 25")),
                 (0x00800003, bytes.fromhex("CD 40 E3 24 42 53 00 00"))]
        for can, data in wrong:
            with self.subTest(can=can, data=data):
                lines = request(ch=1) + rx(can, data, ch=1)
                self.assertEqual((items(lines)[0]["status"], items(lines)[0]["rx_frames"]),
                                 ("unverified", 0))
                lines += rx(0x00800003, response(), ch=1)
                one = items(lines)[0]
                self.assertEqual((one["status"], one["rx_frames"], one["off_route_rx"]),
                                 ("delivered", 1, 1))

    def test_03_channel_protocol_and_baud_context_are_not_mixed(self):
        for context in ({"ch": 2}, {"ch": 1, "proto": 6}, {"ch": 1, "baud": 125000}):
            with self.subTest(context=context):
                one = items(request(ch=1) + rx(0x00800003, response(), **context))[0]
                self.assertEqual((one["status"], one["rx_frames"]), ("unverified", 0))
        one = items(request(ch=1, proto=6) + rx(0x00800003, response(), ch=1, proto=6))[0]
        self.assertEqual(one["status"], "unverified")
        lines = request(ch=1) + request(target=0x50, identifier=b"\x24\x43", ch=2)
        lines += rx(0x00800003, response())  # no channel: ambiguous, attribute to neither
        lines += rx(0x00800003, response(), ch=2)
        lines += rx(0x00800003, response(), ch=1)
        lines += rx(0x01200003, response(target=0x50, identifier=b"\x24\x43"), ch=2)
        self.assertTrue(all(x["status"] == "delivered" for x in items(lines)))
        self.assertEqual([x["rx_frames"] for x in items(lines)], [1, 1])

    def test_04_truncation_missing_data_and_unsupported_framing_are_partial(self):
        malformed = [
            (bytes.fromhex("CD 40 E6 24"), "invalid_d2_a6_length"),
            (bytes.fromhex("CD 40 E6 24 42"), "invalid_d2_a6_length"),
            (bytes.fromhex("CF 40 E6 24 42 53"), "invalid_d2_a6_length"),
            (response() + b"\x00", "invalid_d2_a6_length"),
            (bytes.fromhex("CC 40 E6 24 42 53 00 00"), "missing_d2_a6_data"),
            (bytes.fromhex("D0 40 E6 24 42 53 00 00"), "unsupported_d2_a6_framing"),
            (bytes.fromhex("8F 40 E6 24 42 53 00 00"), "unsupported_d2_a6_framing"),
        ]
        for frame, reason in malformed:
            with self.subTest(frame=frame):
                lines = request(ch=1) + rx(0x00800003, frame, ch=1)
                one = items(lines)[0]
                self.assertEqual((one["status"], one["reason"], one["rx_frames"]),
                                 ("partial_rx", reason, 1))
                # Later bytes cannot erase a malformed response already attributed to this request.
                self.assertEqual(items(lines + rx(0x00800003, response(), ch=1))[0]["status"], "partial_rx")
        lines = request(ch=1) + rx(0x00800003, response(), ch=1, time_us=104000)
        lines += rx(0x00800003, response(), ch=1, time_us=109000)
        one = items(lines)[0]
        self.assertEqual((one["status"], one["rx_frames"], one["off_route_rx"], one["window_ms"]),
                         ("delivered", 1, 1, 4))

    def test_05_opaque_requests_and_security_responses_remain_unverified(self):
        for data in (bytes.fromhex("CB 40 A6 24 42 01 00 00"),
                     bytes.fromhex("CF 40 A6 24 42 01 00 00"),
                     bytes.fromhex("CD 40 A6 24 42 02 00 00"),
                     bytes.fromhex("A6 24 42 01 00 00 00 00"),
                     bytes.fromhex("CF 40 A3 02 03 A5 A5 00")):
            with self.subTest(data=data):
                lines = tx(0xFFFFE, data, ch=1)
                lines += rx(0x00800003, response(), ch=1)
                lines += rx(0x00800003, bytes.fromhex("CB 40 E3 00 00 00 00 00"), ch=1)
                self.assertEqual((items(lines)[0]["status"], items(lines)[0]["rx_frames"]),
                                 ("unverified", 0))

    def test_06_clear_disconnect_supersede_and_process_boundaries(self):
        clear = [event("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)", be(1, 5, 0, 500000, 101000)),
                 event("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")]
        lines = request(ch=1) + clear + rx(0x00800003, response(), ch=1)
        lines += request(identifier=b"\x24\x43", ch=1)
        lines += rx(0x00800003, response(), ch=1)
        lines += rx(0x00800003, response(identifier=b"\x24\x43"), ch=1)
        self.assertEqual([(x["status"], x["rx_frames"]) for x in items(lines)],
                         [("unverified", 0), ("delivered", 1)])
        self.assertEqual(items(lines)[0]["reason"], "clear_rx_buffer")
        for ending in ([event("PassThruDisconnect channel (BE)", be(1)), event("PassThruDisconnect")],
                       [event("PassThruOpen ->")], [event("PassThruClose")]):
            one = items(request(ch=1) + ending + rx(0x00800003, response(), ch=1))[0]
            self.assertEqual((one["status"], one["rx_frames"]), ("unverified", 0))
        lines = request(ch=1) + request(identifier=b"\x24\x43", ch=1)
        lines += rx(0x00800003, response(), ch=1)
        self.assertTrue(all(x["status"] == "unverified" for x in items(lines)))
        other_pid = [line.replace("DEADBEEF", "FEEDCAFE") for line in rx(0x00800003, response(), ch=1)]
        self.assertEqual(items(request(ch=1) + other_pid)[0]["rx_frames"], 0)

    def test_07_b9_and_p3_interleaving_still_deliver(self):
        lines = request(ch=1) + tx(0xFFFFE, D2FB, ch=2)
        lines += tx(0x726, bytes.fromhex("22 F1 14"), ch=3, proto=6)
        lines += frames13(ch=2)
        lines += rx(0x72E, bytes.fromhex("62 F1 14 53"), ch=3, proto=6)
        lines += rx(0x00800003, response(), ch=1)
        result = {x["channel"]: x for x in items(lines)}
        self.assertEqual({ch: x["rx_frames"] for ch, x in result.items()}, {1: 1, 2: 13, 3: 1})
        self.assertTrue(all(x["status"] == "delivered" for x in result.values()))

    def test_08_legacy_unknown_metadata_and_cli_privacy(self):
        lines = request() + rx(0x00800003, response(value=b"SIM"))
        one = items(lines)[0]
        self.assertEqual((one["status"], one["channel"], one["protocol"], one["baud_bps"], one["window_ms"]),
                         ("delivered", None, "unknown", None, None))
        legacy = []
        raw_request = (0xFFFFE).to_bytes(4, "big") + bytes.fromhex("CD 40 A6 24 42 01 00 00")
        raw_response = (0x00800003).to_bytes(4, "big") + response()
        for stamp, call, raw in (("12:00:01,000", "Write", raw_request),
                                 ("12:00:01,007", "Read", raw_response)):
            legacy.append(f"{stamp} PassThru{call}Msgs() msg[0].Data = [" +
                          ", ".join(f"0x{x:x}" for x in raw) + "]")
        known = items(legacy)[0]
        self.assertEqual((known["status"], known["window_ms"], known["channel"], known["baud_bps"]),
                         ("delivered", 7, None, None))
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "private-lab.log", Path(directory) / "audit.json"
            source.write_text("\n".join(lines))
            before = source.read_bytes()
            with contextlib.redirect_stdout(io.StringIO()):
                tool.main([str(source), "--output", str(output)])
            report = json.loads(output.read_text())
            self.assertEqual(source.read_bytes(), before)
            self.assertTrue(report["read_only"])
            self.assertFalse(report["contains_payload_data"])
            self.assertFalse(report["replay_approved"])
            raw = output.read_text()
            for private in ("DEADBEEF", "DiagnosticClient", str(source), "53 49 4D", "24 42", "_a6_identifier"):
                self.assertNotIn(private, raw)
            self.assertEqual(report["transactions"][0]["status"], "delivered")
            self.assertFalse(any(k.startswith("_") or k in ("identifier", "value", "payload")
                                 for k in report["transactions"][0]))


if __name__ == "__main__":
    unittest.main()
