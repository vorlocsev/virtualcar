"""Eight fail-closed Connect-channel to first CEM B9FB binding regressions.

The DLL now records channel/protocol/baud at successful PassThruConnect.
A global Connect OK must never be credited to a different or later B9FB.
All identifiers and frames here are deliberately synthetic.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import audit_native_connect_b9fb_channel as channel
import prepare_p2_client_run as client
from test_prepare_p2_client_run import session
from test_audit_d2_followup_window import marker, words


BIND_NAME = "J2534 Connect bound channel/protocol/flags/baud (BE)"
RESULT_NAME = "J2534 Connect result protocol/flags/baud/status (BE)"


def event(name, *numbers):
    return marker(name, words(*numbers))


def analyzed(lines):
    return channel.audit("\n".join(lines))


class NativeConnectB9FBChannelTests(unittest.TestCase):
    def test_01_exact_prior_successful_connect_matches_b9fb_tx_channel(self):
        report = channel.audit(session())
        self.assertEqual(report["status"],
                         "one_b9fb_bound_to_prior_successful_channel_connect")
        self.assertTrue(report["one_b9fb_bound_to_prior_successful_channel_connect"])
        self.assertEqual(report["b9fb_request_count"], 1)
        self.assertEqual(report["successful_channel_bindings_count"], 1)
        self.assertFalse(report["client_accepted_b9fb_verified"])
        self.assertFalse(report["vehicle_identity_verified"])
        summary = client.prepare(session())["client-boundary.json"]
        self.assertEqual(summary["diagnostic_focus"],
                         "native_transport_positive_client_ui_result_unknown")

    def test_02_aggregate_connect_success_after_b9fb_is_not_prerequisite(self):
        lines = session().splitlines()
        bind = lines.pop(1)
        result = lines.pop(1)
        # Insert successful Connect immediately AFTER B9FB app TX.
        first_tx = next(i for i, line in enumerate(lines)
                        if "TX (app request)" in line)
        lines[first_tx + 1:first_tx + 1] = [bind, result]
        result = analyzed(lines)
        self.assertEqual(result["connect_success_count"], 1)
        self.assertFalse(result["one_b9fb_bound_to_prior_successful_channel_connect"])
        self.assertEqual(result["status"],
                         "b9fb_not_bound_to_prior_successful_channel_connect")
        summary = client.prepare("\n".join(lines))["client-boundary.json"]
        self.assertEqual(summary["diagnostic_focus"],
                         "b9fb_channel_connect_provenance_missing_or_invalid")
        self.assertEqual(summary["b9fb_positive_transport_count"], 1)

    def test_03_successful_connect_for_other_channel_not_same_channel(self):
        lines = session().splitlines()
        lines[1] = event(BIND_NAME, 2, 5, 0x800, 500000)
        result = analyzed(lines)
        self.assertEqual(result["connect_success_count"], 1)
        self.assertEqual(result["successful_channel_bindings_count"], 1)
        self.assertFalse(result["one_b9fb_bound_to_prior_successful_channel_connect"])
        self.assertEqual(result["status"],
                         "b9fb_not_bound_to_prior_successful_channel_connect")

    def test_04_wrong_baud_or_protocol_not_valid_channel_provenance(self):
        for protocol, baud in ((5, 125000), (6, 500000)):
            with self.subTest(protocol=protocol, baud=baud):
                lines = session().splitlines()
                lines[1] = event(BIND_NAME, 1, protocol, 0x800, baud)
                lines[2] = event(RESULT_NAME, protocol, 0x800, baud, 0)
                note = analyzed(lines)
                self.assertEqual(note["connect_success_count"], 1)
                self.assertEqual(
                    note["status"],
                    "b9fb_not_bound_to_prior_successful_channel_connect")
                self.assertFalse(
                    note["one_b9fb_bound_to_prior_successful_channel_connect"])

    def test_05_claimed_binding_with_failed_result_is_rejected(self):
        lines = session().splitlines()
        lines[2] = event(RESULT_NAME, 5, 0x800, 500000, 25)
        result = analyzed(lines)
        self.assertEqual(result["status"], "invalid_connect_channel_evidence")
        self.assertEqual(result["error_counts"]["bound_marker_with_failed_connect"], 1)
        self.assertEqual(result["connect_success_count"], 0)
        self.assertFalse(result["one_b9fb_bound_to_prior_successful_channel_connect"])

    def test_06_disconnected_channel_before_b9fb_cannot_be_reused(self):
        lines = session().splitlines()
        lines.insert(3, event("PassThruDisconnect channel (BE)", 1))
        report = analyzed(lines)
        self.assertEqual(report["status"],
                         "b9fb_not_bound_to_prior_successful_channel_connect")
        self.assertEqual(report["connect_success_count"], 1)
        self.assertFalse(report["one_b9fb_bound_to_prior_successful_channel_connect"])

    def test_07_legacy_success_without_channel_metadata_is_unverified(self):
        lines = [l for l in session().splitlines() if BIND_NAME not in l]
        report = analyzed(lines)
        self.assertEqual(report["status"],
                         "legacy_no_channel_connect_binding_metadata")
        self.assertEqual(report["connect_success_count"], 1)
        self.assertEqual(report["connect_success_without_channel_marker_count"], 1)
        self.assertFalse(report["one_b9fb_bound_to_prior_successful_channel_connect"])
        note = client.prepare("\n".join(lines))["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "b9fb_channel_connect_provenance_missing_or_invalid")
        self.assertFalse(note["client_ecu_inventory_verified"])

    def test_08_repeated_request_or_corrupt_marker_never_proves_one_handoff(self):
        lines = session().splitlines()
        first = next(i for i, line in enumerate(lines)
                     if "TX context channel/protocol" in line)
        # Repeat exact native request pair before its positive RX frames.
        duplicated = lines[:first + 2] + lines[first:first + 2] + lines[first + 2:]
        double = analyzed(duplicated)
        self.assertEqual(double["b9fb_request_count"], 2)
        self.assertEqual(double["status"],
                         "multiple_b9fb_requests_not_one_handoff")
        self.assertFalse(double["one_b9fb_bound_to_prior_successful_channel_connect"])

        malformed = lines[:]
        malformed[1] = marker(BIND_NAME, b"\x01")
        invalid = analyzed(malformed)
        self.assertEqual(invalid["status"], "invalid_connect_channel_evidence")
        self.assertEqual(invalid["error_counts"]["malformed_connect_channel_marker"], 1)
        self.assertFalse(invalid["one_b9fb_bound_to_prior_successful_channel_connect"])

        result = json.dumps((double, invalid))
        for token in ("ABCDEF12", "SectorV.exe", "01200003",
                      "F9 FB", "0x000FFFFE", "VCARLAB0000000000"):
            self.assertNotIn(token, result)


if __name__ == "__main__":
    unittest.main()
