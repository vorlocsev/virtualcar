"""Eight strict native J2534 Open/Close lifecycle regressions.

No real Volvo identifiers, physical ECU, external client, or secrets.
Only one complete Open/Close cycle in one untrusted source PID is eligible
for a same-device read-only diagnostic handoff.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import audit_native_j2534_lifecycle as tool
import prepare_p2_client_run as capture
from test_audit_d2_followup_window import marker, tx, response
from test_prepare_p2_client_run import session, ui

OPEN = marker("PassThruOpen -> device 1")
CLOSE = marker("PassThruClose")


def audited(lines):
    return tool.audit("\n".join(lines))


class NativeDeviceLifecycleTests(unittest.TestCase):
    def test_01_single_closed_device_cycle_is_eligible_not_client_identity(self):
        source = [OPEN] + tx() + response() + [CLOSE]
        result = audited(source)
        self.assertEqual(result["status"], "single_closed_device_cycle")
        self.assertEqual(result["device_open_count"], 1)
        self.assertEqual(result["device_close_count"], 1)
        self.assertTrue(result["single_closed_device_cycle_verified"])
        self.assertFalse(result["client_process_identity_verified"])
        self.assertFalse(result["client_acceptance_verified"])

    def test_02_two_sequential_cycles_same_pid_are_not_one_device_run(self):
        result = audited([OPEN, CLOSE, OPEN, CLOSE])
        self.assertEqual(result["status"], "multiple_closed_device_cycles")
        self.assertEqual(result["device_open_count"], 2)
        self.assertEqual(result["device_close_count"], 2)
        self.assertFalse(result["single_closed_device_cycle_verified"])

    def test_03_nested_open_with_single_close_fails_closed(self):
        report = audited([OPEN, OPEN, CLOSE])
        self.assertEqual(report["status"], "invalid_or_incomplete_device_lifecycle")
        self.assertEqual(report["error_counts"], {"nested_open": 1})
        self.assertFalse(report["single_closed_device_cycle_verified"])

    def test_04_orphan_or_duplicate_close_never_completes_a_device(self):
        for lines in ([CLOSE], [OPEN, CLOSE, CLOSE]):
            with self.subTest(lines=lines):
                report = audited(lines)
                self.assertEqual(report["status"],
                                 "invalid_or_incomplete_device_lifecycle")
                self.assertEqual(report["error_counts"]["close_without_open"], 1)

    def test_05_unclosed_open_is_not_a_finished_session(self):
        report = audited([OPEN] + tx() + response())
        self.assertEqual(report["status"], "invalid_or_incomplete_device_lifecycle")
        self.assertEqual(report["error_counts"]["open_not_closed"], 1)
        self.assertFalse(report["single_closed_device_cycle_verified"])

    def test_06_app_traffic_outside_open_is_not_a_clean_device_cycle(self):
        for lines in ([tx()[0], OPEN, CLOSE],
                      [OPEN, CLOSE, tx()[0]],
                      [marker("J2534 Connect result protocol/flags/baud/status (BE)"),
                       OPEN, CLOSE]):
            with self.subTest(lines=lines):
                report = audited(lines)
                self.assertEqual(report["status"],
                                 "invalid_or_incomplete_device_lifecycle")
                self.assertGreater(report["error_counts"]["traffic_outside_open"], 0)

    def test_07_pid_reuse_label_switch_and_other_pid_cannot_correlate(self):
        altered_label = [
            OPEN,
            marker("PassThruClose", pid="ABCDEF12", host="OTHER_CLIENT"),
        ]
        changed = audited(altered_label)
        self.assertEqual(changed["status"], "invalid_or_incomplete_device_lifecycle")
        self.assertEqual(changed["error_counts"]["pid_process_label_changed"], 1)
        separate = audited([
            OPEN,
            marker("PassThruOpen -> device 1", pid="DEAD1234"),
            CLOSE,
            marker("PassThruClose", pid="DEAD1234"),
        ])
        self.assertEqual(separate["status"], "multiple_native_process_scopes")
        self.assertEqual(separate["process_scope_count"], 2)
        self.assertFalse(separate["single_closed_device_cycle_verified"])

    def test_08_full_capture_integration_does_not_upgrade_multiple_cycles(self):
        clean = capture.prepare(session(), ui(
            ecu_list="nonempty", same_run_operator_attested=True))
        note = clean["client-boundary.json"]
        self.assertEqual(note["native_device_lifecycle"]["status"],
                         "single_closed_device_cycle")
        self.assertEqual(note["diagnostic_focus"],
                         "operator_reports_nonempty_ecu_list_identity_unverified")
        bad = capture.prepare(
            session() + "\n" + marker("PassThruOpen -> device 1", host="SectorV.exe")
            + "\n" + marker("PassThruClose", host="SectorV.exe"), ui(
            ecu_list="nonempty", same_run_operator_attested=True))
        blocked = bad["client-boundary.json"]
        self.assertEqual(blocked["diagnostic_focus"],
                         "multiple_native_j2534_device_cycles")
        self.assertFalse(blocked["native_p2_single_closed_epoch"])
        self.assertFalse(blocked["client_ecu_inventory_verified"])
        self.assertFalse(blocked["same_run_independently_verified"])
        # Strict allowlist: lifecycle and capture reports do not export
        # source PID or the arbitrary process label.
        safe = json.dumps(bad)
        for secret in ("ABCDEF12", "PRIVATE_CLIENT", "DEAD1234"):
            self.assertNotIn(secret, safe)


if __name__ == "__main__":
    unittest.main()
