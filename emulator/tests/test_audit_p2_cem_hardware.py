"""B3A309 synthetic H/L vs D2/GGD classification tests.

No OEM hardware inventory, VIN, unlock, J2534 or VIDA execution.
"""
import importlib.util
from pathlib import Path
import unittest

TOOL = Path(__file__).resolve().parents[1] / "tools" / "audit_p2_cem_hardware.py"
SPEC = importlib.util.spec_from_file_location("audit_p2_cem_hardware", TOOL)
cem = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cem)


class CemHardwareIdentityTests(unittest.TestCase):
    def test_01_defaults_do_not_claim_class(self):
        item = cem.audit_cem()
        self.assertEqual(item["hardware_class"], "UNKNOWN")
        self.assertEqual(item["diagnostic_protocol"], "UNKNOWN")
        self.assertFalse(item["hardware_class_accepted_for_fixture_selection"])

    def test_02_h_from_declared_case_label(self):
        item = cem.audit_cem("CEM H", "30765148", "30682825 A", "GGD")
        self.assertEqual(item["hardware_class"], "H")
        self.assertEqual(item["community_part_candidates"], ["H"])
        self.assertEqual(item["diagnostic_protocol"], "GGD")

    def test_03_l_from_declared_case_label(self):
        item = cem.audit_cem("CEM-L", "30765149", "31296075 AA", "D2")
        self.assertEqual(item["hardware_class"], "L")
        self.assertEqual(item["community_part_candidates"], ["L"])
        self.assertEqual(item["diagnostic_protocol"], "D2")

    def test_04_h_is_not_bound_to_ggd(self):
        item = cem.audit_cem("H", diagnostic_protocol="D2")
        self.assertEqual(item["hardware_class"], "H")
        self.assertEqual(item["diagnostic_protocol"], "D2")

    def test_05_l_is_not_bound_to_d2(self):
        item = cem.audit_cem("L", diagnostic_protocol="GGD")
        self.assertEqual(item["hardware_class"], "L")
        self.assertEqual(item["diagnostic_protocol"], "GGD")

    def test_06_duplicate_part_number_is_not_decisive(self):
        item = cem.audit_cem(hardware_part_number="30682982")
        self.assertEqual(item["hardware_class"], "UNKNOWN")
        self.assertEqual(item["community_part_candidates"], ["L", "H"])
        self.assertIn("PART_LIST_CONFLICT: same hardware part number appears as H and L", item["warnings"])
        item = cem.audit_cem("CEM-H", "30682982")
        self.assertEqual(item["hardware_class"], "H")

    def test_07_single_part_hint_or_conflict_never_auto_promoted(self):
        item = cem.audit_cem(hardware_part_number="30765148")
        self.assertEqual(item["hardware_class"], "UNKNOWN")
        self.assertEqual(item["community_part_candidates"], ["H"])
        item = cem.audit_cem("L", "30765148")
        self.assertEqual(item["hardware_class"], "UNKNOWN")
        self.assertIn("LABEL_PART_CONFLICT: recheck physical CEM label and part number", item["warnings"])

    def test_08_diagnostic_id_and_can_buses_are_not_hardware_evidence(self):
        for protocol in ("D2", "GGD"):
            with self.subTest(protocol=protocol):
                item = cem.audit_cem(diagnostic_number="31296075 AA", diagnostic_protocol=protocol)
                self.assertEqual(item["hardware_class"], "UNKNOWN")
        for invalid_marking in ("HS-CAN", "0x50", "HIGH", "GGD"):
            with self.subTest(marking=invalid_marking), self.assertRaises(ValueError):
                cem.audit_cem(hardware_marking=invalid_marking)
        with self.assertRaises(ValueError):
            cem.audit_cem(hardware_part_number="30682825 AA")
        self.assertEqual(cem.normalize_marking(" UNKNOWN "), "UNKNOWN")


if __name__ == "__main__":
    unittest.main()
