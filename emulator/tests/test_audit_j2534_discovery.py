"""Eight synthetic regression groups for J2534 CEM evidence audit."""
import importlib.util
import json
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py"
spec = importlib.util.spec_from_file_location("audit_j2534_discovery", path)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def event(name, data=b"", pid="DEADBEEF", host="DiagnosticClient.exe"):
    return f"[PID={pid} {host}] {name}" + ((" " + data.hex(" ").upper()) if data else "")


def be(*words):
    return b"".join(word.to_bytes(4, "big") for word in words)


def tx(can, payload, ch=None, proto=5, flags=0, baud=500000, time_us=100000):
    out = []
    if ch is not None:
        out.append(event("TX context channel/protocol/flags/baud/time-us (BE)",
                         be(ch, proto, flags, baud, time_us)))
    out.append(event("TX (app request)", can.to_bytes(4, "big") + payload))
    return out


def rx(can, payload, ch=None, proto=5, flags=0, baud=500000, time_us=102000):
    out = []
    if ch is not None:
        out.append(event("RX context channel/protocol/status/baud/time-us (BE)",
                         be(ch, proto, flags, baud, time_us)))
    out.append(event("PassThruReadMsgs -> delivered", can.to_bytes(4, "big") + payload))
    return out


D2FB = bytes.fromhex("CB 50 B9 FB 00 00 00 00")
D2F0 = bytes.fromhex("CB 50 B9 F0 00 00 00 00")
A3 = bytes.fromhex("A3 02 03 A5 A5 00 00 00")
P3 = bytes.fromhex("03 22 F1 14 00 00 00 00")
FIRST = bytes.fromhex("8F 50 F9 FB 57 00 30 66")
F0FIRST = bytes.fromhex("8F 50 F9 F0 00 00 00 00")


def frames13(ch=1, time_us=102000):
    hdr = [9, 10, 11, 12, 13, 14, 15, 8, 9, 10, 11, 0x4F]
    payloads = [FIRST] + [bytes((h,)) + b"\x00" * 7 for h in hdr]
    out = []
    for i, data in enumerate(payloads):
        out.extend(rx(0x01200003, data, ch=ch, time_us=time_us + i * 1000))
    return out


class J2534EvidenceTests(unittest.TestCase):
    def test_01_d2_13_frame_complete_and_timing(self):
        lines = tx(0xFFFFE, D2FB, ch=1) + frames13()
        data = tool.audit(lines)
        item = data["transactions"][0]
        self.assertEqual((item["status"], item["rx_frames"]), ("delivered", 13))
        self.assertEqual(item["reason"], "complete_d2_transport_only")
        self.assertEqual((item["channel"], item["protocol"], item["baud_bps"]), (1, "CAN", 500000))
        self.assertEqual(item["window_ms"], 14)
        self.assertFalse(data["replay_approved"])

    def test_02_partial_wrong_sequence_and_missing_final(self):
        wrong = tx(0xFFFFE, D2FB, ch=1)
        wrong += rx(0x01200003, FIRST, ch=1)
        wrong += rx(0x01200003, bytes.fromhex("0B 00 00 00 00 00 00 00"), ch=1)
        wrong += rx(0x01200003, bytes.fromhex("4F 00 00 00 00 00 00 00"), ch=1)
        wrong += tx(0xFFFFE, D2FB, ch=1)
        wrong += rx(0x01200003, FIRST, ch=1)
        wrong += rx(0x01200003, bytes.fromhex("09 00 00 00 00 00 00 00"), ch=1)
        states = tool.audit(wrong)["transactions"]
        self.assertEqual([x["status"] for x in states], ["partial_rx", "partial_rx"])
        self.assertEqual(states[0]["reason"], "invalid_d2_sequence")
        self.assertEqual(states[1]["reason"], "incomplete_or_unverified_transport")

    def test_03_explicit_no_fixture_unsupported_and_timeout(self):
        lines = tx(0xFFFFE, D2F0, ch=1)
        lines += [event("P2 D2 read command: no validated response fixture", D2F0[:4])]
        lines += tx(0xFFFFE, D2FB, ch=1)
        lines += [event("P2 D2 strict route rejected (no fixture emitted)", D2FB[:4])]
        lines += tx(0xFFFFE, A3, ch=1)
        lines += [event("PassThruReadMsgs timeout: channel / wait-ms / consecutive-count (BE)",
                        be(1, 500, 1))]
        states = tool.audit(lines)["transactions"]
        self.assertEqual([x["status"] for x in states], ["no_fixture", "unsupported", "timeout"])
        self.assertNotIn("delivered", [x["status"] for x in states])

    def test_04_multichannel_and_11_vs_29bit_routing(self):
        lines = tx(0x726, P3, ch=1, proto=6, flags=0, baud=500000)
        lines += tx(0x18DA50F1, P3, ch=2, proto=6, flags=0x100, baud=500000)
        lines += rx(0x18DAF150, bytes.fromhex("06 62 F1 14 00 00 00 00"),
                    ch=2, proto=6, flags=0x100)
        lines += rx(0x72E, bytes.fromhex("06 62 F1 14 00 00 00 00"),
                    ch=1, proto=6)
        states = tool.audit(lines)["transactions"]
        self.assertEqual([(x["channel"], x["id_format"]) for x in states],
                         [(1, "11bit"), (2, "29bit")])
        self.assertEqual([x["status"] for x in states], ["delivered", "delivered"])
        self.assertIn("does not prove", tool.audit(lines)["notes"][0])

    def test_05_off_route_does_not_complete_d2(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200004, FIRST, ch=1)
        lines += rx(0x01200003, FIRST, ch=1)
        lines += rx(0x01200004, bytes.fromhex("09 00 00 00 00 00 00 00"), ch=1)
        lines += rx(0x01200003, bytes.fromhex("09 00 00 00 00 00 00 00"), ch=1)
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual((one["status"], one["rx_frames"], one["off_route_rx"]),
                         ("partial_rx", 2, 2))

    def test_06_clear_rx_prevents_stale_generation_completion(self):
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200003, FIRST, ch=1)
        lines += [event("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)",
                        be(1, 5, 0, 500000, 110000))]
        lines += [event("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")]
        lines += tx(0xFFFFE, D2FB, ch=1)
        lines += frames13(ch=1)
        states = tool.audit(lines)["transactions"]
        self.assertEqual([x["rx_frames"] for x in states], [1, 13])
        self.assertEqual([x["status"] for x in states], ["partial_rx", "delivered"])

    def test_07_legacy_timestamp_and_unknown_channel(self):
        lines = [
            "02:42:50,578 0100 000004 PassThruWriteMsgs() msg[0].Data = [" +
            ", ".join(f"0x{x:02x}" for x in (0xFFFFE).to_bytes(4, "big") + D2FB) + "]",
            "02:42:50,640 0100 000004 PassThruReadMsgs() msg[0].Data = [" +
            ", ".join(f"0x{x:02x}" for x in (0x01200003).to_bytes(4, "big") + FIRST) + "]",
            "02:42:50,655 0100 000004 PassThruReadMsgs() msg[0].Data = [" +
            ", ".join(f"0x{x:02x}" for x in (0x01200003).to_bytes(4, "big") +
                      bytes.fromhex("4F 00 00 00 00 00 00 00")) + "]",
        ]
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual((one["channel"], one["id_format"], one["protocol"]), (None, "29bit", "unknown"))
        self.assertEqual((one["status"], one["window_ms"]), ("delivered", 77))

    def test_08_no_private_identifiers_or_client_acceptance(self):
        vin = b"YV1CZ0002A0000001"  # synthetic test only
        lines = tx(0xFFFFE, D2FB, ch=1)
        lines += rx(0x01200003, FIRST, ch=1, time_us=102000)
        for i, h in enumerate((9, 10, 11)):
            lines += rx(0x01200003, bytes([h]) + vin[i*7:i*7+7].ljust(7, b"0"),
                        ch=1, time_us=103000+i*1000)
        lines += [event("PassThruClose")]
        raw = json.dumps(tool.audit(lines))
        self.assertNotIn(vin.decode(), raw)
        self.assertNotIn("DEADBEEF", raw)
        self.assertNotIn("DiagnosticClient", raw)
        self.assertNotIn("59 56 31", raw)
        one = tool.audit(lines)["transactions"][0]
        self.assertEqual(one["status"], "partial_rx")
        self.assertFalse(tool.audit(lines)["contains_payload_data"])


if __name__ == "__main__":
    unittest.main()
