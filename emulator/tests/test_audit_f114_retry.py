"""Eight synthetic F114 retry-attribution regressions. No ECU or VIN fixtures."""
import importlib.util
import json
from pathlib import Path
import unittest

script = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py"
spec = importlib.util.spec_from_file_location("audit_f114_retry", script)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def be(*words):
    return b"".join(x.to_bytes(4, "big") for x in words)


def event(name, data=b""):
    return "[PID=DEADBEEF SyntheticLab.exe] " + name + (
        (" " + data.hex(" ").upper()) if data else ""
    )


def tx(did=0xF114, ch=1, proto=6, at=100000):
    request = (bytes((0x22, did >> 8, did & 0xFF))
               if proto == 6 else
               bytes((0x03, 0x22, did >> 8, did & 0xFF, 0, 0, 0, 0)))
    return [
        event("TX context channel/protocol/flags/baud/time-us (BE)",
              be(ch, proto, 0, 500000, at)),
        event("TX (app request)", (0x726).to_bytes(4, "big") + request),
    ]


def rx(payload, ch=1, proto=6, at=102000, can=0x72E):
    return [
        event("RX context channel/protocol/status/baud/time-us (BE)",
              be(ch, proto, 0, 500000, at)),
        event("PassThruReadMsgs -> delivered", can.to_bytes(4, "big") + payload),
    ]


def clear_rx(ch=1):
    return [
        event("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)",
              be(ch, 6, 0, 500000, 103000)),
        event("J2534 CLEAR_RX_BUFFER: queued and staged D2 dropped"),
    ]


POS = bytes.fromhex("62 F1 14 41 42 43 44")  # synthetic, no VIN
FF = bytes.fromhex("10 14 62 F1 14 41 42 43")
CF1 = bytes.fromhex("21 44 45 46 47 48 49 4A")
CF2 = bytes.fromhex("22 4B 4C 4D 4E 4F 50 51")
SF = bytes.fromhex("04 62 F1 14 41 00 00 00")


def results(lines):
    return audit.audit(lines)["transactions"]


class F114RetryAttributionTests(unittest.TestCase):
    def test_01_iso_retry_without_reply_is_not_attributable(self):
        items = results(tx() + tx(at=101000) + rx(POS))
        self.assertEqual([x["status"] for x in items],
                         ["unverified", "unverified"])
        self.assertEqual(items[1]["reason"], "identical_f114_retry_unattributable")

    def test_02_raw_partial_then_retry_complete_stays_unverified(self):
        lines = tx(proto=5) + rx(FF, proto=5)
        lines += tx(proto=5, at=104000)
        lines += rx(FF, proto=5, at=105000)
        lines += rx(CF1, proto=5, at=106000)
        lines += rx(CF2, proto=5, at=107000)
        items = results(lines)
        self.assertEqual([x["rx_frames"] for x in items], [1, 3])
        self.assertEqual([x["status"] for x in items], ["partial_rx", "unverified"])
        self.assertEqual(items[1]["reason"], "identical_f114_retry_unattributable")

    def test_03_explicit_rx_clear_is_a_boundary(self):
        lines = tx() + clear_rx() + tx(at=104000) + rx(POS)
        items = results(lines)
        self.assertEqual(items[0]["reason"], "clear_rx_buffer")
        self.assertEqual(items[1]["status"], "delivered")

    def test_04_same_did_different_channels_is_not_ambiguous(self):
        lines = tx(ch=1) + tx(ch=2, at=100500)
        lines += rx(POS, ch=1) + rx(POS, ch=2, at=103000)
        self.assertEqual([x["status"] for x in results(lines)],
                         ["delivered", "delivered"])

    def test_05_prior_completed_response_allows_next_read(self):
        lines = tx() + rx(POS)
        lines += tx(at=104000) + rx(POS, at=105000)
        self.assertEqual([x["status"] for x in results(lines)],
                         ["delivered", "delivered"])

    def test_06_other_did_does_not_inherit_f114_ambiguity(self):
        lines = tx() + tx(did=0xF1B0, at=101000)
        lines += rx(bytes.fromhex("62 F1 B0 41"))
        items = results(lines)
        self.assertEqual([x["service"] for x in items],
                         ["22F114", "22F1B0"])
        self.assertEqual(items[1]["status"], "delivered")

    def test_07_invalid_retry_response_remains_partial(self):
        lines = tx(proto=5) + rx(FF, proto=5)
        lines += tx(proto=5, at=104000)
        lines += rx(FF, proto=5) + rx(CF2, proto=5)
        items = results(lines)
        self.assertEqual(items[1]["status"], "partial_rx")
        self.assertEqual(items[1]["reason"], "invalid_iso_tp_framing")

    def test_08_pending_old_and_single_frame_new_is_unattributable(self):
        pending = bytes.fromhex("03 7F 22 78 00 00 00 00")
        lines = tx(proto=5) + rx(pending, proto=5)
        lines += tx(proto=5, at=104000) + rx(SF, proto=5)
        data = audit.audit(lines)
        self.assertEqual(data["transactions"][1]["reason"],
                         "identical_f114_retry_unattributable")
        self.assertFalse(data["replay_approved"])
        report = json.dumps(data)
        self.assertNotIn("SyntheticLab", report)
        self.assertNotIn("DEADBEEF", report)
        self.assertNotIn("41 42 43 44", report)


if __name__ == "__main__":
    unittest.main()
