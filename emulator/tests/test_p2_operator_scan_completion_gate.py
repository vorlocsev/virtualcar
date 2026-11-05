"""Eight fail-closed operator observation gates for real-client capture.

A valid synthetic J2534 B9FB/B9F0/P3 chain never proves a completed
client scan. In particular, a manually reported ECU list is not a
same-run observation unless virtual adapter selection and scan finish
are explicitly TRUE, and no executable family mismatch is present.

All fixtures are synthetic; no diagnostic software or ECU is run.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import prepare_p2_client_run as capture
from test_prepare_p2_client_run import session, ui


def report(*, client_label="SectorV.exe", **changes):
    bundle = capture.prepare(
        session(native_label=client_label), ui(**changes))
    return bundle["client-boundary.json"]


class FinishedOperatorScanAttributionTests(unittest.TestCase):
    def assert_no_identity(self, note):
        self.assertFalse(note["client_ecu_inventory_verified"])
        self.assertFalse(note["vehicle_identity_verified"])
        self.assertFalse(note["xc90_v8_my2009_verified"])
        self.assertFalse(note["same_run_independently_verified"])
        self.assertFalse(note["native_executable_identity_verified"])
        self.assertEqual(note["b9fb_positive_transport_count"], 1)
        self.assertEqual(note["b9f0_positive_transport_count"], 1)
        self.assertEqual(note["first_p3_positive_transport_count"], 1)

    def test_01_finished_selected_attested_nonempty_is_only_operator_report(self):
        note = report(
            ecu_list="nonempty", vin_display="visible",
            same_run_operator_attested=True)
        self.assertEqual(note["operator_inventory_observation_gate"],
                         "completed_scan_operator_report_only")
        self.assertTrue(note["operator_ecu_list_attributable_to_completed_scan"])
        self.assertEqual(note["diagnostic_focus"],
                         "operator_reports_nonempty_ecu_list_identity_unverified")
        self.assert_no_identity(note)

    def test_02_finished_selected_attested_empty_is_only_operator_report(self):
        note = report(
            ecu_list="empty", same_run_operator_attested=True)
        self.assertEqual(note["operator_inventory_observation_gate"],
                         "completed_scan_operator_report_only")
        self.assertTrue(note["operator_ecu_list_attributable_to_completed_scan"])
        self.assertEqual(note["diagnostic_focus"],
                         "transport_positive_but_operator_reports_empty_ecu_list")
        self.assert_no_identity(note)

    def test_03_false_virtual_adapter_selection_rejects_apparent_ecu_list(self):
        for state in ("empty", "nonempty"):
            with self.subTest(state=state):
                note = report(
                    virtual_adapter_selected=False, scan_finished=True,
                    ecu_list=state, same_run_operator_attested=True)
                self.assertEqual(note["operator_inventory_observation_gate"],
                                 "virtual_adapter_not_selected")
                self.assertEqual(
                    note["diagnostic_focus"],
                    "operator_ecu_list_not_attributable_to_completed_virtual_scan")
                self.assertFalse(
                    note["operator_ecu_list_attributable_to_completed_scan"])
                self.assert_no_identity(note)

    def test_04_unknown_virtual_adapter_selection_is_not_assumed_true(self):
        note = report(
            virtual_adapter_selected=None, scan_finished=True,
            ecu_list="nonempty", same_run_operator_attested=True)
        self.assertEqual(note["operator_inventory_observation_gate"],
                         "virtual_adapter_selection_unknown")
        self.assertEqual(
            note["diagnostic_focus"],
            "operator_ecu_list_not_attributable_to_completed_virtual_scan")
        self.assert_no_identity(note)

    def test_05_unfinished_scan_does_not_confirm_empty_or_nonempty_list(self):
        for state in ("empty", "nonempty"):
            with self.subTest(state=state):
                note = report(
                    scan_finished=False, ecu_list=state,
                    same_run_operator_attested=True)
                self.assertEqual(note["operator_inventory_observation_gate"],
                                 "client_scan_not_finished")
                self.assertEqual(
                    note["diagnostic_focus"],
                    "operator_ecu_list_not_attributable_to_completed_virtual_scan")
                self.assertFalse(
                    note["operator_ecu_list_attributable_to_completed_scan"])
                self.assert_no_identity(note)

    def test_06_unknown_scan_completion_stays_unverified(self):
        note = report(
            scan_finished=None, ecu_list="nonempty",
            same_run_operator_attested=True)
        self.assertEqual(note["operator_inventory_observation_gate"],
                         "client_scan_completion_unknown")
        self.assertEqual(
            note["diagnostic_focus"],
            "operator_ecu_list_not_attributable_to_completed_virtual_scan")
        self.assert_no_identity(note)

    def test_07_no_same_run_attestation_does_not_attribute_ui(self):
        note = report(
            ecu_list="nonempty", same_run_operator_attested=False)
        self.assertEqual(note["operator_inventory_observation_gate"],
                         "operator_not_attested_same_run")
        self.assertEqual(
            note["diagnostic_focus"],
            "operator_ecu_list_not_attributable_to_completed_virtual_scan")
        self.assertFalse(note["operator_ecu_list_attributable_to_completed_scan"])
        self.assert_no_identity(note)

    def test_08_unknown_or_inconsistent_client_and_unknown_list_stay_safe(self):
        # "other" cannot be confirmed as the named proprietary client.
        other = report(
            client="other", ecu_list="nonempty",
            same_run_operator_attested=True)
        self.assertEqual(other["operator_inventory_observation_gate"],
                         "operator_client_unspecified")
        self.assertEqual(
            other["diagnostic_focus"],
            "operator_ecu_list_not_attributable_to_completed_virtual_scan")
        self.assertFalse(other["operator_ecu_list_attributable_to_completed_scan"])
        self.assert_no_identity(other)

        # A mismatch takes diagnostic priority over operator UI claims.
        mismatch = report(
            client_label="VDASH.exe", client="sectorv",
            ecu_list="nonempty", same_run_operator_attested=True)
        self.assertEqual(
            mismatch["operator_inventory_observation_gate"],
            "client_native_label_not_consistent")
        self.assertEqual(
            mismatch["diagnostic_focus"],
            "operator_client_native_executable_label_mismatch")
        self.assertFalse(
            mismatch["operator_ecu_list_attributable_to_completed_scan"])
        self.assert_no_identity(mismatch)

        unknown_list = report(same_run_operator_attested=True)
        self.assertEqual(unknown_list["operator_inventory_observation_gate"],
                         "completed_scan_operator_report_only")
        self.assertEqual(
            unknown_list["diagnostic_focus"],
            "native_transport_positive_client_ui_result_unknown")
        self.assertFalse(
            unknown_list["operator_ecu_list_attributable_to_completed_scan"])
        self.assert_no_identity(unknown_list)

        # The exported report is allowlisted: no executable name, PID,
        # VIN or native CAN source payload is serialized.
        redacted = json.dumps((other, mismatch, unknown_list))
        for secret in ("ABCDEF12", "VDASH.exe", "SectorV.exe",
                       "VCARLAB0000000000", "62 F1 14"):
            self.assertNotIn(secret, redacted)


if __name__ == "__main__":
    unittest.main()
