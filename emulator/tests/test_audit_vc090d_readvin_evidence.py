"""Eight synthetic VC090D evidence groups; no real vehicle or client."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_vc090d_readvin_evidence as audit
from test_audit_p2_b9fb_shape import LAB_VIN, frames
sys.path.pop(0)

PID = 0x1234
HOST = "lab.exe"
VIN = LAB_VIN.decode()
OTHER = "YV1CZ0002A0000002"
P = f"[PID={PID:08X} {HOST}] "


def line(event, data=None, prefix=P):
    return prefix + event + (" " + data.hex(" ").upper() if data is not None else "") + "\n"


def message(direction, channel, protocol, flags, baud, can_id, data, prefix=P):
    return (line(audit.TX if direction == "tx" else audit.RX,
                 struct.pack(">5I", channel, protocol, flags, baud, 1), prefix) +
            line(audit.TX_DATA if direction == "tx" else audit.RX_DATA,
                 can_id.to_bytes(4, "big") + data, prefix))


def f190(vin=VIN, channel=1, prefix=P):
    return message("tx", channel, 6, 0, 500000, 0x7e0, b"\x22\xf1\x90", prefix) + \
        message("rx", channel, 6, 0, 500000, 0x7e8, b"\x62\xf1\x90"+vin.encode(), prefix)


def d2(*, bad_generation=False, missing_tag=False):
    body = message("tx", 1, 5, 0x100, 500000, 0xffffe, bytes.fromhex("CB 50 B9 FB 00 00 00 00"))
    for i, (can_id, data) in enumerate(frames(), 1):
        body += message("rx", 1, 5, 0x100, 500000, can_id, data)
        if missing_tag and i == 5:
            continue
        body += line(audit.TAG, struct.pack(">5I", 1, 2 if bad_generation and i == 5 else 1, i, i, i))
    return body


def closed(body):
    return line(audit.OPEN) + body + line(audit.CLOSE)


class ReadVinEvidenceTests(unittest.TestCase):
    def test_01_f190_positive_with_gui_transcription(self):
        report = audit.audit(closed(f190()), PID, HOST, VIN, VIN)
        self.assertEqual(report["native_evidence_gate"], "matching_lab_identity_delivery_observed")
        self.assertEqual(report["counts"]["f190_vin_equal"], 1)
        self.assertEqual(report["owner_displayed_vin_matches_delivered"], "equal")
        self.assertFalse(report["original_vida_vin_accepted_verified"])

    def test_02_b9fb_tagged_complete_shape(self):
        report = audit.audit(closed(d2()), PID, HOST, VIN)
        self.assertEqual(report["native_evidence_gate"], "matching_lab_identity_delivery_observed")
        self.assertEqual(report["counts"]["b9fb_positive"], 1)
        self.assertEqual(report["counts"]["b9fb_vin_equal"], 1)
        self.assertFalse(report["readvin_script_execution_verified"])

    def test_03_identity_disagreement(self):
        report = audit.audit(closed(f190(OTHER)), PID, HOST, VIN, VIN)
        self.assertEqual(report["native_evidence_gate"], "delivered_identity_differs")
        self.assertEqual(report["owner_displayed_vin_matches_delivered"], "different")
        report = audit.audit(closed(f190()), PID, HOST, VIN, OTHER)
        self.assertEqual(report["owner_transcribed_displayed_vin_comparison"], "different_from_expected")
        self.assertEqual(report["owner_displayed_vin_matches_delivered"], "different")

    def test_04_prefix_and_channel_isolation(self):
        tx, rx = f190().split(line(audit.RX, struct.pack(">5I", 1, 6, 0, 500000, 1)), 1)
        other = "[PID=00001235 lab.exe] "
        body = tx + message("rx", 1, 6, 0, 500000, 0x7e8, b"\x62\xf1\x90"+VIN.encode(), other)
        report = audit.audit(closed(body), PID, HOST, VIN)
        self.assertEqual(report["counts"]["f190_positive"], 0)
        self.assertEqual(report["native_evidence_gate"], "incomplete_or_ambiguous_native_evidence")
        body = tx + message("rx", 2, 6, 0, 500000, 0x7e8, b"\x62\xf1\x90"+VIN.encode())
        self.assertEqual(audit.audit(closed(body), PID, HOST, VIN)["counts"]["f190_positive"], 0)

    def test_05_generation_tag_and_missing_frame_refused(self):
        for body in (d2(bad_generation=True), d2(missing_tag=True)):
            report = audit.audit(closed(body), PID, HOST, VIN)
            self.assertEqual(report["counts"]["b9fb_positive"], 0)
            self.assertEqual(report["native_evidence_gate"], "incomplete_or_ambiguous_native_evidence")

    def test_06_boundaries_and_retry_refused(self):
        for log in (closed(f190()) + closed(f190()), line(audit.OPEN)+f190()):
            report = audit.audit(log, PID, HOST, VIN)
            self.assertFalse(report["single_closed_logger_session"])
            self.assertEqual(report["native_evidence_gate"], "incomplete_or_ambiguous_native_evidence")
        tx = message("tx", 1, 6, 0, 500000, 0x7e0, b"\x22\xf1\x90")
        report = audit.audit(closed(tx+f190()), PID, HOST, VIN)
        self.assertEqual(report["native_evidence_gate"], "incomplete_or_ambiguous_native_evidence")
        self.assertEqual(report["counts"]["incomplete"], 1)

    def test_07_indications_queue_and_clear_are_not_positive(self):
        tx = message("tx", 1, 6, 0, 500000, 0x7e0, b"\x22\xf1\x90")
        start = message("rx", 1, 6, 2, 500000, 0x7e8, b"")
        queued = line("RX (simulated)", b"\0\0\x07\xe8\x62\xf1\x90"+VIN.encode())
        report = audit.audit(closed(tx+start+queued), PID, HOST, VIN)
        self.assertEqual(report["counts"]["start_indications"], 1)
        self.assertEqual(report["counts"]["f190_positive"], 0)
        report = audit.audit(closed(tx+line("J2534 CLEAR_RX_BUFFER: queued D2/raw ISO-TP and staged CF dropped")+
                                  message("rx", 1, 6, 0, 500000, 0x7e8, b"\x62\xf1\x90"+VIN.encode())), PID, HOST, VIN)
        self.assertEqual(report["counts"]["f190_positive"], 0)
        self.assertEqual(audit.audit(closed(""), PID, HOST, VIN)["native_evidence_gate"],
                         "no_positive_identity_delivery_observed")

    def test_08_bounds_privacy_and_input_integrity(self):
        with self.assertRaises(ValueError):
            audit.audit(closed(f190()).rstrip("\n"), PID, HOST, VIN)
        with self.assertRaises(ValueError):
            audit.audit(closed(f190()), PID, HOST, "invalid")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"private.log"
            source = closed(f190()).encode()
            path.write_bytes(source)
            self.assertEqual(audit.read_frozen(path, len(source)), source)
            with self.assertRaises(ValueError):
                audit.read_frozen(path, len(source)-1)
            self.assertEqual(path.read_bytes(), source)
        encoded = json.dumps(audit.audit(closed(f190()), PID, HOST, VIN))
        for secret in (VIN, HOST, "00001234", "62 F1 90"):
            self.assertNotIn(secret, encoded)
        for field in ("original_vida_process_authenticated", "loaded_module_identity_verified",
                      "readvin_script_execution_verified", "original_vida_vin_accepted_verified",
                      "ecu_identity_accepted_verified", "physical_j2534_verified"):
            self.assertFalse(json.loads(encoded)[field])


if __name__ == "__main__":
    unittest.main()
