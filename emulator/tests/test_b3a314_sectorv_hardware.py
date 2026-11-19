"""Synthetic privacy and provenance regression groups for B3A314 offline audit."""
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from contextlib import redirect_stdout

MODULE = pathlib.Path(__file__).resolve().parents[1] / "tools" / "audit_b3a314_sectorv_hardware.py"
spec = importlib.util.spec_from_file_location("b3a314_audit", MODULE)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
PREFIX = "[PID=DEADBEEF SectorV.exe] "
TIME = "2026-11-19 03:27:02.040 +03:00 [client] "
VIN = "P2 VIN RX v3 comm=0x50: result=received, observed=13, ignored=0, matched=13, elapsedMs=147."
HW50 = "P2 hardware-session RX v3 comm=0x50: result=no-reply, observed=0, ignored=0, matched=0, elapsedMs=5015."
HW40 = "P2 hardware-session RX v3 comm=0x40: result=no-reply, observed=0, ignored=0, matched=0, elapsedMs=5003."
FAILURE = "P2 automatic identification failed at Hardware: TimeoutException: P2 CEM hardware-session: no-reply."


def n(*lines):
    return [PREFIX + x for x in lines]


def c(*lines):
    return [TIME + x for x in lines]


class SectorVHardwareTests(unittest.TestCase):
    def test_1_successful_b9fb_transport_but_hardware_failure(self):
        r = audit.analyze(n(audit.NATIVE_B9FB, audit.NATIVE_UNIMPLEMENTED), c(VIN, HW50, HW40, FAILURE))
        self.assertEqual(r["client_ordered_vin50_rx_then_hw50_no_reply_then_hardware_failure"], 1)
        self.assertEqual(r["native_event_counts"]["A3_A6_UNIMPLEMENTED"], 1)
        self.assertEqual(r["client_event_counts"]["HW_50_timeout_observed"], 1)
        self.assertFalse(r["positive_hardware_session_verified"])

    def test_2_hardware_labels_are_unverified_not_positive_rx(self):
        lines = n(*(audit.NATIVE_HARDWARE_MARKERS.values()))
        r = audit.analyze(lines, [])
        for key in audit.NATIVE_HARDWARE_MARKERS:
            self.assertEqual(r["native_event_counts"][key], 1)
        self.assertFalse(r["positive_hardware_session_verified"])

    def test_3_no_cross_attempt_pairing_without_full_client_order(self):
        r = audit.analyze([], c(HW50, FAILURE, VIN))
        self.assertEqual(r["client_ordered_vin50_rx_then_hw50_no_reply_then_hardware_failure"], 0)

    def test_4_wrong_prefix_and_unrecognized_hardware_are_not_attributed(self):
        r = audit.analyze(["P2_HW_TX_A3_OBSERVED", PREFIX + "P2_HW_TX_FORGED", "[PID=OTHER HOST] P2_HW_TX_A3_OBSERVED"], [])
        self.assertEqual(r["native_event_counts"]["A3_TX_OBSERVED"], 0)
        self.assertEqual(r["malformed_or_unknown_native_hardware_markers"], 1)

    def test_5_empty_or_redacted_raw_lines_do_not_imply_rx(self):
        r = audit.analyze(n("PassThruReadMsgs -> delivered [PAYLOAD_REDACTED]", "TX (app request) [PAYLOAD_REDACTED]"), [])
        self.assertEqual(r["native_event_counts"]["B9FB_50_STAGED"], 0)
        self.assertEqual(r["client_event_counts"]["HW_50_received"], 0)

    def test_6_zero_matched_vin_does_not_pretend_receive(self):
        invalid = VIN.replace("matched=13", "matched=0")
        r = audit.analyze([], c(invalid, HW50, FAILURE))
        self.assertEqual(r["client_event_counts"]["VIN_50_received"], 1)
        self.assertEqual(r["client_ordered_vin50_rx_then_hw50_no_reply_then_hardware_failure"], 0)

    def test_7_privacy_unknown_native_payload_not_exported(self):
        secret = "SENSITIVE_PRIVATE_VIN_ABCDEFGH"  # fake, non-VIN text
        r = audit.analyze(n("Active INI: C:\\private\\" + secret, "TX (app request) " + secret), c("unrecognized " + secret))
        self.assertNotIn(secret, json.dumps(r))
        self.assertNotIn("DEADBEEF", json.dumps(r))
        self.assertNotIn("2026-11-19", json.dumps(r))
        self.assertFalse(r["native_and_client_same_session_attested"])

    def test_8_mixed_routes_counted_separately(self):
        r = audit.analyze(n(audit.NATIVE_BUS_MISMATCH), c(HW40, HW50))
        self.assertEqual(r["client_event_counts"]["HW_40_no_reply"], 1)
        self.assertEqual(r["client_event_counts"]["HW_50_no_reply"], 1)
        self.assertEqual(r["native_event_counts"]["A3_A6_BUS_MISMATCH"], 1)

    def test_9_bounded_size_fails_without_echoing_lines(self):
        with self.assertRaisesRegex(ValueError, "maximum_log_rows_exceeded"):
            audit.analyze(("untrusted " for _ in range(audit.MAX_ROWS + 1)), [])
        r = audit.analyze(["x" * (audit.MAX_LINE + 1)], [])
        self.assertEqual(r["malformed_or_unknown_native_hardware_markers"], 1)

    def test_10_cli_outputs_only_metadata_and_no_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            native = pathlib.Path(tmp) / "secret_native.log"
            client = pathlib.Path(tmp) / "secret_client.log"
            native.write_text(PREFIX + audit.NATIVE_UNIMPLEMENTED, encoding="utf-8")
            client.write_text(TIME + HW50, encoding="utf-8")
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(audit.main(["--native", str(native), "--client", str(client)]), 0)
            report = json.loads(out.getvalue())
            self.assertEqual(report["native_event_counts"]["A3_A6_UNIMPLEMENTED"], 1)
            self.assertNotIn(str(native), out.getvalue())


if __name__ == "__main__":
    unittest.main()
