"""dev32: eight synthetic evidence groups; never use donor VIN or real captures."""
import importlib.util
import json
from pathlib import Path
import unittest

script = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py"
spec = importlib.util.spec_from_file_location("audit_p3_transport", script)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def be(*values):
    return b"".join(x.to_bytes(4, "big") for x in values)


def log(label, data=b"", pid="DEADBEEF"):
    return f"[PID={pid} SyntheticLab.exe] {label}" + ((" " + data.hex(" ").upper()) if data else "")


def tx(can=0x726, data=b"\x03\x22\xf1\x14\x00\x00\x00\x00",
       ch=1, proto=5, flags=0, now=100000):
    return [
        log("TX context channel/protocol/flags/baud/time-us (BE)",
            be(ch, proto, flags, 500000, now)),
        log("TX (app request)", can.to_bytes(4, "big") + data),
    ]


def rx(data, can=0x72E, ch=1, proto=5, flags=0, now=102000):
    return [
        log("RX context channel/protocol/status/baud/time-us (BE)",
            be(ch, proto, flags, 500000, now)),
        log("PassThruReadMsgs -> delivered", can.to_bytes(4, "big") + data),
    ]


def first_frame():
    return bytes.fromhex("10 14 62 F1 14 41 42 43")


def continuations():
    return [bytes.fromhex("21 44 45 46 47 48 49 4A"),
            bytes.fromhex("22 4B 4C 4D 4E 4F 50 51")]


def result(lines):
    return audit.audit(lines)["transactions"]


class P3TransportEvidenceTests(unittest.TestCase):
    def test_01_can_single_frame_11bit_and_29bit(self):
        lines = tx(ch=1) + rx(bytes.fromhex("03 62 F1 14 00 00 00 00"), ch=1)
        lines += tx(can=0x18DA50F1, ch=2, flags=0x100)
        lines += rx(bytes.fromhex("03 62 F1 14 00 00 00 00"),
                    can=0x18DAF150, ch=2, flags=0x100)
        data = result(lines)
        self.assertEqual([x["status"] for x in data], ["delivered", "delivered"])
        self.assertEqual([x["id_format"] for x in data], ["11bit", "29bit"])
        self.assertTrue(all(x["reason"] == "p3_uds_transport_only" for x in data))

    def test_02_reassembled_iso15765_and_direct_uds_request(self):
        lines = tx(data=bytes.fromhex("22 F1 14"), proto=6)
        lines += [log("PassThruReadMsgs -> delivered", (0x72E).to_bytes(4, "big"))]
        lines += rx(bytes.fromhex("62 F1 14 53 59 4E 54 48 45 54 49 43"),
                    proto=6, now=106000)
        data = result(lines)
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["service"], "22F114")
        self.assertEqual((data[0]["status"], data[0]["rx_frames"]),
                         ("delivered", 1))
        self.assertEqual(data[0]["window_ms"], 6)

    def test_03_first_frame_is_partial_until_all_consecutive_frames(self):
        lines = tx() + rx(first_frame())
        partial = result(lines)[0]
        self.assertEqual((partial["status"], partial["rx_frames"]),
                         ("partial_rx", 1))
        self.assertFalse(partial["status"] == "delivered")
        complete = list(lines)
        complete += rx(continuations()[0], now=105000)
        complete += rx(continuations()[1], now=110000)
        one = result(complete)[0]
        self.assertEqual((one["status"], one["rx_frames"], one["window_ms"]),
                         ("delivered", 3, 10))

    def test_04_flow_control_does_not_supersede_multiframe(self):
        lines = tx() + rx(first_frame())
        lines += tx(data=bytes.fromhex("30 00 00 00 00 00 00 00"), now=104000)
        lines += rx(continuations()[0], now=107000)
        lines += rx(continuations()[1], now=108000)
        self.assertEqual(len(result(lines)), 1)
        self.assertEqual(result(lines)[0]["status"], "delivered")
        # The diagnostic request still has its original timestamp.
        self.assertEqual(result(lines)[0]["window_ms"], 8)

    def test_05_duplicate_or_wrong_sequence_and_invalid_length(self):
        wrong = tx() + rx(first_frame())
        wrong += rx(continuations()[0]) + rx(continuations()[0])
        self.assertEqual(result(wrong)[0]["status"], "partial_rx")
        self.assertEqual(result(wrong)[0]["reason"], "invalid_iso_tp_framing")
        out_of_order = tx() + rx(first_frame()) + rx(continuations()[1])
        self.assertEqual(result(out_of_order)[0]["reason"], "invalid_iso_tp_framing")
        bad_single = tx() + rx(bytes.fromhex("09 62 F1 14 00 00 00 00"))
        self.assertEqual(result(bad_single)[0]["reason"], "invalid_iso_tp_framing")
        bad_first = tx() + rx(bytes.fromhex("10 06 62 F1 14 00 00 00"))
        self.assertEqual(result(bad_first)[0]["reason"], "invalid_iso_tp_framing")

    def test_06_negative_response_not_positive_discovery(self):
        lines = tx() + rx(bytes.fromhex("03 7F 22 31 00 00 00 00"))
        one = result(lines)[0]
        self.assertEqual((one["status"], one["reason"]),
                         ("negative_response", "uds_negative_response_observed"))
        self.assertNotIn("successful", json.dumps(audit.audit(lines)).lower())
        direct = tx(data=bytes.fromhex("22 F1 14"), proto=6)
        direct += rx(bytes.fromhex("7F 22 31"), proto=6)
        self.assertEqual(result(direct)[0]["status"], "negative_response")

    def test_07_mismatched_did_and_off_route_rx(self):
        mismatched = tx() + rx(bytes.fromhex("03 62 F1 90 00 00 00 00"))
        one = result(mismatched)[0]
        self.assertEqual(one["status"], "unverified")
        self.assertEqual(one["reason"], "uds_response_does_not_match_request")
        bad_route = tx()
        bad_route += rx(bytes.fromhex("03 62 F1 14 00 00 00 00"), can=0x7E8)
        one = result(bad_route)[0]
        self.assertEqual((one["status"], one["off_route_rx"], one["rx_frames"]),
                         ("unverified", 1, 0))

    def test_08_concurrent_channels_clear_rx_and_privacy(self):
        lines = tx(ch=1)
        lines += tx(ch=2)
        lines += rx(first_frame(), ch=1)
        lines += [log("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)",
                      be(1, 5, 0, 500000, 105000))]
        lines += [log("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped")]
        lines += rx(bytes.fromhex("03 62 F1 14 00 00 00 00"), ch=2)
        items = result(lines)
        self.assertEqual([(x["channel"], x["status"]) for x in items],
                         [(1, "partial_rx"), (2, "delivered")])
        dump = json.dumps(audit.audit(lines))
        self.assertNotIn("SyntheticLab", dump)
        self.assertNotIn("DEADBEEF", dump)
        self.assertNotIn("62 F1 14", dump)
        self.assertFalse(audit.audit(lines)["replay_approved"])


if __name__ == "__main__":
    unittest.main()
