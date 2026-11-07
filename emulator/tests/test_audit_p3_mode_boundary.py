"""Eight synthetic J2534 P3 transport-mode boundary regressions.

These are not captured Volvo ECU replies and do not validate vehicle identity.
"""
import importlib.util
import json
from pathlib import Path
import unittest

script = Path(__file__).resolve().parents[1] / "tools" / "audit_j2534_discovery.py"
spec = importlib.util.spec_from_file_location("audit_p3_mode_boundary", script)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def be(*words):
    return b"".join(v.to_bytes(4, "big") for v in words)


def log(label, payload=b""):
    return "[PID=DEADBEEF SyntheticLab.exe] " + label + (
        " " + payload.hex(" ").upper() if payload else ""
    )


def tx(proto=6, ch=1, at=100000):
    uds = bytes.fromhex("22 F1 14")
    data = uds if proto == 6 else bytes.fromhex("03 22 F1 14 00 00 00 00")
    return [
        log("TX context channel/protocol/flags/baud/time-us (BE)",
            be(ch, proto, 0, 500000, at)),
        log("TX (app request)", (0x726).to_bytes(4, "big") + data),
    ]


def rx(data, proto=6, ch=1, at=102000, status=0, baud=500000):
    return [
        log("RX context channel/protocol/status/baud/time-us (BE)",
            be(ch, proto, status, baud, at)),
        log("PassThruReadMsgs -> delivered",
            (0x72E).to_bytes(4, "big") + data),
    ]


def report(lines):
    return audit.audit(lines)["transactions"]


UDS = bytes.fromhex("62 F1 14 41 42 43 44")
SF = bytes.fromhex("04 62 F1 14 41 00 00 00")
FF = bytes.fromhex("10 14 62 F1 14 41 42 43")
CF1 = bytes.fromhex("21 44 45 46 47 48 49 4A")
CF2 = bytes.fromhex("22 4B 4C 4D 4E 4F 50 51")


class P3ModeBoundaryTests(unittest.TestCase):
    def test_01_native_uds_and_raw_single_frame_deliver_normally(self):
        lines = tx(proto=6, ch=1) + rx(UDS, proto=6, ch=1)
        lines += tx(proto=5, ch=2) + rx(SF, proto=5, ch=2)
        states = report(lines)
        self.assertEqual([x["status"] for x in states], ["delivered", "delivered"])
        self.assertEqual([x["protocol"] for x in states], ["ISO15765", "CAN"])

    def test_02_raw_multiframe_and_reassembled_uds_are_distinct(self):
        lines = tx(proto=5) + rx(FF, proto=5)
        lines += rx(CF1, proto=5, at=104000)
        lines += rx(CF2, proto=5, at=106000)
        lines += tx(proto=6, ch=2) + rx(UDS, proto=6, ch=2)
        states = report(lines)
        self.assertEqual([x["status"] for x in states], ["delivered", "delivered"])
        self.assertEqual([x["rx_frames"] for x in states], [3, 1])

    def test_03_raw_can_with_reassembled_uds_is_source_mismatch(self):
        one = report(tx(proto=5) + rx(UDS, proto=5))[0]
        self.assertEqual((one["status"], one["reason"]),
                         ("unverified", "p3_uds_without_pci_on_can_channel"))
        self.assertEqual(one["rx_frames"], 1)

    def test_04_iso15765_with_raw_can_single_frame_is_source_mismatch(self):
        one = report(tx(proto=6) + rx(SF, proto=6))[0]
        self.assertEqual((one["status"], one["reason"]),
                         ("unverified", "p3_can_pci_on_iso15765_channel"))

    def test_05_iso15765_with_raw_can_first_frame_is_source_mismatch(self):
        one = report(tx(proto=6) + rx(FF, proto=6))[0]
        self.assertEqual((one["status"], one["reason"]),
                         ("unverified", "p3_can_pci_on_iso15765_channel"))

    def test_06_explicit_rx_protocol_and_baud_conflicts_fail_closed(self):
        wrong_proto = report(tx(proto=5) + rx(UDS, proto=6))[0]
        self.assertEqual(wrong_proto["reason"], "p3_rx_protocol_metadata_mismatch")
        self.assertEqual(wrong_proto["status"], "unverified")
        wrong_baud = report(tx(proto=6) + rx(UDS, proto=6, baud=125000))[0]
        self.assertEqual(wrong_baud["reason"], "p3_rx_baud_metadata_mismatch")
        self.assertEqual(wrong_baud["status"], "unverified")

    def test_07_start_indication_and_tx_echo_cannot_complete_read(self):
        # An ID-only START_OF_MESSAGE indication is not a UDS data reply.
        clean = report(tx() + rx(b"", status=0x02) + rx(UDS))[0]
        self.assertEqual(clean["status"], "delivered")
        invalid = report(tx() + rx(UDS, status=0x02))[0]
        self.assertEqual(invalid["reason"], "p3_invalid_start_indication")
        self.assertEqual(invalid["status"], "unverified")
        echo = report(tx() + rx(UDS, status=0x09))[0]
        self.assertEqual((echo["status"], echo["rx_frames"]), ("unverified", 0))

    def test_08_true_isotp_error_and_identical_retry_stay_separate(self):
        bad = report(tx(proto=5) + rx(FF, proto=5) + rx(CF2, proto=5))[0]
        self.assertEqual((bad["status"], bad["reason"]),
                         ("partial_rx", "invalid_iso_tp_framing"))
        retry = audit.audit(tx() + tx(at=101000) + rx(UDS))
        self.assertEqual(retry["transactions"][1]["reason"],
                         "identical_f114_retry_unattributable")
        self.assertFalse(retry["replay_approved"])
        content = json.dumps(retry)
        self.assertNotIn("SyntheticLab", content)
        self.assertNotIn("DEADBEEF", content)
        self.assertNotIn("41 42 43 44", content)


if __name__ == "__main__":
    unittest.main()
