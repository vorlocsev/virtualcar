"""Eight source-label boundary checks for read-only SectorV / VDASH reports.

The host basename printed in a DLL log is a *claim*, not executable
signature evidence, independent client UI capture, ECU identity or VIN.
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import prepare_p2_client_run as tool
from test_prepare_p2_client_run import session, ui


def boundary(native_label="SectorV.exe", **obs):
    return tool.prepare(session(native_label=native_label), ui(**obs))[
        "client-boundary.json"]


class NativeClientExecutableLabelBoundaryTests(unittest.TestCase):
    def test_01_sectorv_label_agrees_with_report_not_independent_identity(self):
        result = boundary("SectorV.exe",
                          client="sectorv", ecu_list="nonempty",
                          same_run_operator_attested=True)
        self.assertEqual(result["native_executable_label_family"], "sectorv")
        self.assertEqual(result["operator_client_native_label_comparison"],
                         "operator_client_matches_untrusted_native_label")
        self.assertEqual(result["diagnostic_focus"],
                         "operator_reports_nonempty_ecu_list_identity_unverified")
        self.assertFalse(result["native_executable_identity_verified"])
        self.assertFalse(result["client_ecu_inventory_verified"])

    def test_02_both_known_vdash_label_forms_allow_both_reported_versions(self):
        for label, client in (("VDASH.exe", "vdash_2_0"),
                              ("vDaSh2.ExE", "vdash_2_5_115_79")):
            with self.subTest(label=label):
                result = boundary(label, client=client,
                                  same_run_operator_attested=True,
                                  ecu_list="empty")
                self.assertEqual(result["native_executable_label_family"],
                                 "vdash")
                self.assertEqual(result["operator_client_native_label_comparison"],
                                 "operator_client_matches_untrusted_native_label")
                self.assertFalse(result["native_executable_identity_verified"])
                self.assertFalse(result["xc90_v8_my2009_verified"])

    def test_03_sectorv_ui_cannot_be_attributed_to_native_vdash(self):
        result = boundary("VDASH.exe", client="sectorv",
                          ecu_list="nonempty",
                          same_run_operator_attested=True)
        self.assertEqual(result["operator_client_native_label_comparison"],
                         "operator_client_conflicts_with_native_label")
        self.assertEqual(result["diagnostic_focus"],
                         "operator_client_native_executable_label_mismatch")
        self.assertFalse(result["client_ecu_inventory_verified"])

    def test_04_vdash_ui_cannot_be_attributed_to_native_sectorv(self):
        result = boundary("SectorV.exe", client="vdash_2_0",
                          same_run_operator_attested=True,
                          ecu_list="nonempty")
        self.assertEqual(result["diagnostic_focus"],
                         "operator_client_native_executable_label_mismatch")
        self.assertFalse(result["same_run_independently_verified"])

    def test_05_unknown_executable_does_not_guess_proprietary_client(self):
        result = boundary("PRIVATE-LAB-OTHER.exe",
                          client="vdash_2_5_115_79",
                          ecu_list="nonempty",
                          same_run_operator_attested=True)
        self.assertEqual(result["native_executable_label_family"],
                         "unclassified_executable")
        self.assertEqual(result["operator_client_native_label_comparison"],
                         "native_executable_unclassified")
        self.assertEqual(result["diagnostic_focus"],
                         "native_client_executable_label_unverified")
        self.assertNotIn("PRIVATE-LAB-OTHER.exe", json.dumps(result))

    def test_06_no_operator_ui_keeps_transport_without_client_claim(self):
        result = tool.prepare(session(native_label="powershell.exe"))[
            "client-boundary.json"]
        self.assertEqual(result["native_executable_label_family"],
                         "unclassified_executable")
        self.assertEqual(result["operator_client_native_label_comparison"],
                         "no_operator_client_reported")
        self.assertEqual(result["diagnostic_focus"],
                         "native_transport_positive_client_ui_result_unknown")
        self.assertFalse(result["native_executable_identity_verified"])

    def test_07_operator_other_never_matches_known_native_application(self):
        result = boundary("SectorV.exe", client="other",
                          same_run_operator_attested=True,
                          ecu_list="nonempty")
        self.assertEqual(result["operator_client_native_label_comparison"],
                         "operator_client_unspecified")
        self.assertFalse(result["native_executable_identity_verified"])
        self.assertFalse(result["same_run_independently_verified"])

    def test_08_one_pid_switching_executable_labels_is_not_one_client(self):
        lines = session().splitlines()
        index = next(i for i, line in enumerate(lines)
                     if "TX (app request)" in line)
        lines[index] = lines[index].replace("SectorV.exe",
                                           "PRIVATE-REPLACED.exe")
        result = tool.prepare("\n".join(lines), ui(
            client="sectorv", ecu_list="nonempty",
            same_run_operator_attested=True))["client-boundary.json"]
        self.assertEqual(result["native_executable_label_family"],
                         "multiple_untrusted_executable_labels")
        self.assertEqual(result["operator_client_native_label_comparison"],
                         "native_executable_labels_conflict")
        self.assertEqual(result["diagnostic_focus"],
                         "incomplete_or_invalid_native_j2534_device_cycle")
        self.assertFalse(result["native_p2_single_closed_epoch"])
        self.assertFalse(result["client_ecu_inventory_verified"])
        safe = json.dumps(result)
        for item in ("SectorV.exe", "PRIVATE-REPLACED.exe", "ABCDEF12"):
            self.assertNotIn(item, safe)


if __name__ == "__main__":
    unittest.main()
