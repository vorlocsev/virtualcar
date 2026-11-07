"""Eight synthetic groups for the VDASH 2.0-style OBD observation boundary.

No historical VDASH capture, real VIN, CEM identity or client acceptance fixture.
"""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

from test_audit_j2534_discovery import tool, event, be, tx, rx, D2FB, frames13
from test_audit_vida_text import connect, tx as vida_tx, rx as vida_rx

FIXTURE = Path(__file__).parent / "fixtures" / "vdash20_obd_synthetic.txt"
VIN_RECORD = b"\x49\x02\x01" + b"0" * 17  # Deliberately not a vehicle identity.


def request(ch=1, proto=6, can=0x7DF, **kwargs):
    data = b"\x09\x02" if proto == 6 else b"\x02\x09\x02" + bytes(5)
    return tx(can, data, ch=ch, proto=proto, **kwargs)


def reply(data=VIN_RECORD, ch=1, proto=6, can=0x7E8, **kwargs):
    return rx(can, data, ch=ch, proto=proto, **kwargs)


def report(lines):
    return tool.audit(lines, include_obd=True)


def records(lines):
    return report(lines)["transactions"]


def can_frames():
    return [b"\x10\x14" + VIN_RECORD[:6], b"\x21" + VIN_RECORD[6:13],
            b"\x22" + VIN_RECORD[13:]]


class ObdObservationTests(unittest.TestCase):
    def test_01_fixture_separates_rxstart_vin_and_client_result(self):
        data = report(FIXTURE.read_text(encoding="utf-8").splitlines())
        vin, keepalive = data["transactions"]
        self.assertEqual((vin["service"], vin["status"], vin["rx_frames"], vin["start_indications"]),
                         ("0902", "delivered", 1, 1))
        self.assertEqual(vin["window_ms"], 20)
        self.assertLess(vin["request_line"], vin["last_rx_line"])
        self.assertLess(vin["last_rx_line"], keepalive["request_line"])
        self.assertEqual(keepalive["service"], "3E80")
        self.assertEqual(keepalive["status"], "unverified")
        self.assertEqual(keepalive["id_format"], "29bit")
        self.assertEqual(data["obd_observation"]["recognized_d2_p3_probes"], 0)
        self.assertEqual(data["obd_observation"]["client_result"], "client_result_unknown")
        self.assertFalse(data["obd_observation"]["vehicle_identity_verified"])
        self.assertFalse(data["replay_approved"])
        # A message-start indication alone does not contain VIN data.
        start_only = records(request() + reply(b"", flags=2))[0]
        self.assertEqual((start_only["status"], start_only["start_indications"], start_only["rx_frames"]),
                         ("unverified", 1, 0))

    def test_02_lengths_echo_negative_and_pending_are_not_identity(self):
        for payload, status in [(b"\x49\x02", "partial_rx"), (VIN_RECORD[:-1], "partial_rx"),
                                (VIN_RECORD + b"0", "partial_rx"), (b"\x49\x02\x02" + bytes(17), "unverified"),
                                (b"\x62\xF1\x90" + bytes(17), "unverified"),
                                (b"\x7F\x09\x11", "negative_response"),
                                (b"\x7F\x09\x78", "unverified")]:
            with self.subTest(payload_size=len(payload), status=status):
                self.assertEqual(records(request() + reply(payload))[0]["status"], status)
        pending = request() + reply(b"\x7F\x09\x78")
        self.assertEqual(records(pending + reply())[0]["status"], "delivered")
        timeout = event("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)", be(1, 500, 1))
        self.assertEqual(records(pending + [timeout])[0]["status"], "timeout")
        self.assertEqual(records(request() + [timeout])[0]["status"], "timeout")
        self.assertEqual(records(request())[0]["status"], "unverified")

    def test_03_routes_channels_protocol_and_indications(self):
        lines = request(ch=1) + request(ch=2, can=0x7E0)
        lines += reply(ch=1, can=0x18DAF110) + reply(ch=2, can=0x7E9)
        lines += reply(ch=1, baud=125000) + reply(ch=1, flags=0x100)
        lines += reply(ch=1) + reply(ch=2)
        items = records(lines)
        self.assertEqual([x["status"] for x in items], ["delivered", "delivered"])
        self.assertEqual([x["off_route_rx"] for x in items], [3, 1])
        for flags in (1, 8):
            self.assertEqual(records(request() + reply(flags=flags))[0]["rx_frames"], 0)
        self.assertEqual(records(request() + reply(flags=2))[0]["reason"], "invalid_obd_start_indication")
        self.assertNotEqual(records(request(flags=0x100) + reply())[0]["status"], "delivered")
        self.assertNotEqual(records(request(flags=0x80) + reply())[0]["status"], "delivered")
        self.assertNotEqual(records(request() + reply(proto=5))[0]["status"], "delivered")
        self.assertNotEqual(records(request(ch=None) + reply(ch=None))[0]["status"], "delivered")
        # A functional response from another ECU must not splice into the first.
        pieces = can_frames()
        mixed = request(proto=5) + reply(pieces[0], proto=5)
        mixed += reply(pieces[1], proto=5, can=0x7E9) + reply(pieces[2], proto=5)
        self.assertEqual(records(mixed)[0]["status"], "partial_rx")

    def test_04_raw_can_reuses_transport_sequence_validation(self):
        frames = can_frames()
        lines = request(proto=5) + reply(frames[0], proto=5)
        lines += tx(0x7E0, b"\x30\x00\x00" + bytes(5), ch=1, proto=5)
        lines += reply(frames[1], proto=5) + reply(frames[2], proto=5)
        self.assertEqual((records(lines)[0]["status"], records(lines)[0]["rx_frames"]), ("delivered", 3))
        interrupted = request(proto=5) + reply(frames[0], proto=5)
        interrupted += tx(0x7E0, b"\x3E\x80", ch=1, proto=5)
        interrupted += reply(frames[1], proto=5) + reply(frames[2], proto=5)
        self.assertEqual(records(interrupted)[0]["status"], "partial_rx")
        malformed_fc = tx(0x7E0, b"\x30\x00\x00" + bytes(5), ch=1, proto=5)
        malformed_fc[-1] += " ZZ"
        malformed = request(proto=5) + reply(frames[0], proto=5) + malformed_fc
        malformed += reply(frames[1], proto=5) + reply(frames[2], proto=5)
        self.assertNotEqual(records(malformed)[0]["status"], "delivered")
        for bad in ([frames[0]], [frames[0], frames[2]], [frames[0], frames[1], frames[1], frames[2]],
                    [frames[0], frames[1], frames[2][:-1]], [frames[0] + b"0"]):
            with self.subTest(frame_lengths=list(map(len, bad))):
                seq = request(proto=5)
                for frame in bad:
                    seq += reply(frame, proto=5)
                self.assertEqual(records(seq)[0]["status"], "partial_rx")
        # Unframed ISO15765 request bytes cannot validate a raw-CAN VIN response.
        mixed = tx(0x7DF, b"\x09\x02", ch=1, proto=5) + reply(frames[0], proto=5)
        self.assertEqual(records(mixed)[0]["reason"], "obd_unknown_or_mismatched_transport")

    def test_05_repeats_clear_disconnect_and_open_boundaries(self):
        clear = [event("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)", be(1, 6, 0, 500000, 110000)),
                 event("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")]
        lines = request() + clear + reply() + request() + reply()
        items = records(lines)
        self.assertEqual([x["status"] for x in items], ["unverified", "delivered"])
        self.assertEqual([x["repeat_index"] for x in items], [1, 2])
        self.assertEqual(items[0]["ended_by"], "clear_rx_buffer")
        superseded = records(request() + request() + reply())
        self.assertEqual([x["status"] for x in superseded], ["unverified", "delivered"])
        for boundary in ([event("PassThruClose")],
                         [event("PassThruDisconnect channel (BE)", be(1)), event("PassThruDisconnect")],
                         [event("PassThruOpen -> device 1")]):
            with self.subTest(boundary=boundary[-1]):
                self.assertNotEqual(records(request() + boundary + reply())[0]["status"], "delivered")
        opened = records(request() + [event("PassThruOpen -> device 1")] + request() + reply())
        self.assertEqual([x["repeat_index"] for x in opened], [1, 1])

    def test_06_event_markers_privacy_malformed_and_no_filter_guess(self):
        lines = FIXTURE.read_text(encoding="utf-8").splitlines()
        data = report(lines)
        for name in ("open", "connect_result", "set_config", "filter_start", "close", "tx_record", "rx_delivery_record"):
            self.assertGreater(data["observed_event_markers"][name], 0)
        self.assertEqual(data["obd_observation"]["filter_effect"], "not_observed")
        text = json.dumps(data)
        for private in ("DEADBEEF", "SyntheticVDASH", "00000000000000000", "30 30 30", "C:\\Private"):
            self.assertNotIn(private, text)
        for location in ("tx", "rx", "tx_context", "rx_context"):
            damaged = request() + reply()
            index = {"tx": 1, "rx": 3, "tx_context": 0, "rx_context": 2}[location]
            damaged[index] += " ZZ"
            self.assertNotEqual(records(damaged)[0]["status"], "delivered")
        fake = request()
        fake[1] = fake[1].replace("TX (app request)", "Client said TX (app request)")
        self.assertNotEqual(records(fake + reply())[0]["status"], "delivered")
        unrelated = request() + [event("P2 D2 read command: no validated response fixture")]
        self.assertNotEqual(records(unrelated)[0]["status"], "no_fixture")

    def test_07_existing_d2_binary_validation_remains_separate(self):
        path = Path(__file__).resolve().parents[1] / "tools" / "import_p2_trace.py"
        spec = importlib.util.spec_from_file_location("obd_test_d2_import", path)
        importer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(importer)
        lines = tx(0xFFFFE, D2FB, ch=1) + frames13()
        frames = importer.sessions(lines, 0x50, 0xFB)[0]
        importer.validate_response(frames, 0x50, 0xFB)
        binary = b"".join(frame[1:] for _, frame in frames)
        self.assertEqual(len(binary), 91)
        self.assertIn(b"\x00", binary[:7])
        self.assertEqual(len(binary[3:]), 88)  # Synthetic shape, not verified donor layout.
        for bad in (frames[:-1], frames[:1] + frames[2:],
                    frames[:-1] + [(frames[-1][0], frames[-1][1][:-1])]):
            with self.assertRaises(ValueError):
                importer.validate_response(bad, 0x50, 0xFB)
        self.assertEqual(report(lines)["transactions"], tool.audit(lines)["transactions"])
        self.assertFalse(report(lines)["replay_approved"])

    def test_08_vida_default_compatibility_and_exclusive_cli_output(self):
        lines = [connect()] + vida_tx(bytes.fromhex("00 00 07 DF 09 02"))
        lines += vida_rx(bytes.fromhex("00 00 07 E8"))
        lines += vida_rx(bytes.fromhex("00 00 07 E8") + VIN_RECORD)
        item = records(lines)[0]
        self.assertEqual((item["status"], item["rx_frames"], item["start_indications"]), ("delivered", 1, 0))
        native = FIXTURE.read_text(encoding="utf-8").splitlines()
        self.assertEqual(tool.audit(native)["transactions"], [])
        self.assertNotIn("obd_observation", tool.audit(native))
        id_only = tx(0x726, bytes.fromhex("22 F1 14"), ch=1, proto=6)
        id_only += rx(0xFFFFFFFF, b"", ch=1, proto=6)
        self.assertEqual(tool.audit(id_only)["parse_errors"], {})
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "safe.json"
            with contextlib.redirect_stdout(io.StringIO()):
                tool.main([str(FIXTURE), "--include-obd", "--output", str(output)])
            saved = output.read_bytes()
            self.assertEqual(json.loads(saved)["obd_observation"]["vin_delivered"], 1)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                tool.main([str(FIXTURE), "--include-obd", "--output", str(output)])
            self.assertEqual(output.read_bytes(), saved)
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                tool.main([str(FIXTURE), "--include-obd", "--output", str(FIXTURE)])


if __name__ == "__main__":
    unittest.main()
