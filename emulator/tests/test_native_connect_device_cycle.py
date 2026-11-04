"""Eight source-local J2534 device-cycle and recycled-channel regressions.

A positive B9FB Channel Connect binding must belong to exactly one
closed Open/Close cycle. The native PID and executable label are
untrusted; two device cycles within one PID cannot be one handoff.
All events are synthetic, without real client, hardware or identifiers.
"""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))
import audit_native_connect_b9fb_channel as audit
import prepare_p2_client_run as client
from test_prepare_p2_client_run import session
from test_audit_d2_followup_window import marker
from test_native_connect_b9fb_channel import event, BIND_NAME, RESULT_NAME

OPEN = marker("PassThruOpen -> device 1", host="SectorV.exe")
CLOSE = marker("PassThruClose", host="SectorV.exe")
DISCONNECT = event("PassThruDisconnect channel (BE)", 1)
BIND1 = event(BIND_NAME, 1, 5, 0x800, 500000)
OK1 = event(RESULT_NAME, 5, 0x800, 500000, 0)


def analyze(lines):
    return audit.audit("\n".join(lines))


class NativeConnectDeviceEpochTests(unittest.TestCase):
    def test_01_one_closed_device_cycle_and_one_bound_b9fb(self):
        result = audit.audit(session())
        self.assertEqual(result["status"],
                         "one_b9fb_bound_to_prior_successful_channel_connect")
        self.assertEqual(result["native_device_open_count"], 1)
        self.assertEqual(result["native_device_close_count"], 1)
        self.assertTrue(result["single_closed_native_device_cycle"])
        self.assertTrue(result["one_b9fb_bound_to_prior_successful_channel_connect"])
        self.assertFalse(result["client_accepted_b9fb_verified"])

    def test_02_second_sequential_cycle_same_pid_must_fail_closed(self):
        repeated = session().splitlines() + [OPEN, CLOSE]
        report = analyze(repeated)
        self.assertEqual(report["status"], "multiple_native_device_cycles")
        self.assertEqual(report["native_process_scope_count"], 1)
        self.assertEqual(report["native_device_open_count"], 2)
        self.assertEqual(report["native_device_close_count"], 2)
        self.assertFalse(report["single_closed_native_device_cycle"])
        self.assertFalse(report["one_b9fb_bound_to_prior_successful_channel_connect"])
        note = client.prepare("\n".join(repeated))["client-boundary.json"]
        self.assertEqual(note["diagnostic_focus"],
                         "multiple_native_j2534_device_cycles")
        self.assertFalse(note["client_ecu_inventory_verified"])

    def test_03_completed_old_cycle_before_new_bound_b9fb_is_not_one(self):
        merged = [OPEN, CLOSE] + session().splitlines()
        result = analyze(merged)
        self.assertEqual(result["status"], "multiple_native_device_cycles")
        self.assertEqual(result["native_device_open_count"], 2)
        self.assertFalse(result["one_b9fb_bound_to_prior_successful_channel_connect"])

    def test_04_nested_open_is_not_single_closed_epoch(self):
        lines = session().splitlines()
        lines.insert(1, OPEN)
        result = analyze(lines)
        self.assertEqual(result["status"], "multiple_native_device_cycles")
        self.assertEqual(result["error_counts"]["nested_device_open"], 1)
        self.assertFalse(result["single_closed_native_device_cycle"])

    def test_05_orphan_extra_close_is_malformed_not_closed_handoff(self):
        result = analyze(session().splitlines() + [CLOSE])
        self.assertEqual(result["status"], "invalid_connect_channel_evidence")
        self.assertEqual(result["error_counts"]["close_without_device_open"], 1)
        self.assertFalse(result["one_b9fb_bound_to_prior_successful_channel_connect"])

    def test_06_open_without_close_stays_unverified_despite_positive_rx(self):
        lines = session().splitlines()
        self.assertEqual(lines[-1], CLOSE)
        lines.pop()
        result = analyze(lines)
        self.assertEqual(result["status"], "incomplete_native_device_cycle")
        self.assertEqual(result["native_device_open_count"], 1)
        self.assertEqual(result["native_device_close_count"], 0)
        self.assertFalse(result["one_b9fb_bound_to_prior_successful_channel_connect"])
        boundary = client.prepare("\n".join(lines))["client-boundary.json"]
        self.assertEqual(boundary["diagnostic_focus"],
                         "incomplete_or_invalid_native_j2534_device_cycle")

    def test_07_connect_outside_device_or_explicit_separator_is_invalid(self):
        lines = [BIND1, OK1] + session().splitlines()
        report = analyze(lines)
        self.assertEqual(report["status"], "invalid_connect_channel_evidence")
        self.assertEqual(
            report["error_counts"]["connect_binding_outside_device_open"], 1)
        self.assertEqual(
            report["error_counts"]["connect_result_outside_device_open"], 1)
        self.assertFalse(report["one_b9fb_bound_to_prior_successful_channel_connect"])
        with_separator = session().splitlines()
        with_separator.insert(3, "=== SECTORV VIRTUALCAR SESSION PRIVATE_TEXT ===")
        result = analyze(with_separator)
        self.assertEqual(result["status"], "invalid_connect_channel_evidence")
        self.assertEqual(result["error_counts"]["explicit_session_separator"], 1)
        self.assertFalse(result["client_executable_identity_verified"])

    def test_08_recycled_channel_requires_fresh_success_and_no_live_rebind(self):
        lines = session().splitlines()
        # Disconnect channel 1, then reconnect with the same slot index
        # BEFORE its next B9FB: only the fresh explicit OK is credited.
        lines[3:3] = [DISCONNECT, BIND1, OK1]
        valid = analyze(lines)
        self.assertEqual(valid["status"],
                         "one_b9fb_bound_to_prior_successful_channel_connect")
        self.assertEqual(valid["successful_channel_bindings_count"], 2)
        self.assertEqual(valid["native_device_open_count"], 1)
        self.assertTrue(valid["single_closed_native_device_cycle"])
        self.assertFalse(valid["client_accepted_b9fb_verified"])

        # An invented repeated success on an *already live* ID must
        # not overwrite the previous binding or authorize B9FB.
        stale = session().splitlines()
        stale[3:3] = [BIND1, OK1]
        invalid = analyze(stale)
        self.assertEqual(invalid["status"], "invalid_connect_channel_evidence")
        self.assertEqual(invalid["error_counts"]["reused_live_channel"], 1)
        self.assertFalse(invalid["one_b9fb_bound_to_prior_successful_channel_connect"])

        # A new pending marker without its successful status must fail.
        truncated = session().splitlines()
        truncated[3:3] = [DISCONNECT, BIND1]
        incomplete = analyze(truncated)
        self.assertEqual(incomplete["status"], "invalid_connect_channel_evidence")
        self.assertFalse(incomplete["one_b9fb_bound_to_prior_successful_channel_connect"])


if __name__ == "__main__":
    unittest.main()
