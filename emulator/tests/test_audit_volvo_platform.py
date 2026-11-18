"""Eight synthetic platform identity groups; none proves OEM ECU responses."""
import importlib.util
from pathlib import Path
import unittest

PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_volvo_platform.py"
spec = importlib.util.spec_from_file_location("audit_volvo_platform", PATH)
platform = importlib.util.module_from_spec(spec)
spec.loader.exec_module(platform)


class VolvoPlatformGenerationTests(unittest.TestCase):
    def test_01_xc90_2009_v8_is_p2_restyling(self):
        r = platform.audit_platform("XC90", 2009, engine="B8444S")
        self.assertEqual(r["generation"], platform.P2_RESTYLING)
        self.assertEqual(r["platform_family"], "P2")
        self.assertTrue(r["p2_restyling"])
        self.assertFalse(r["approved_for_ecu_response_selection"])

    def test_02_xc90_before_and_after_facelift(self):
        self.assertEqual(platform.suggest_generation("XC90", 2006), platform.P2)
        self.assertEqual(platform.suggest_generation("XC90", 2007), platform.P2_RESTYLING)
        self.assertEqual(platform.suggest_generation("XC90", 2014), platform.P2_RESTYLING)
        self.assertEqual(platform.suggest_generation("XC90", 2015), platform.UNKNOWN)
        self.assertEqual(platform.suggest_generation("XC90", 2020), platform.UNKNOWN)

    def test_03_s60_v70_xc70_2005_facelift(self):
        for model in ("S60", "V70", "XC70"):
            with self.subTest(model=model):
                self.assertEqual(platform.suggest_generation(model, 2004), platform.P2)
                self.assertEqual(platform.suggest_generation(model, 2005), platform.P2_RESTYLING)
        self.assertEqual(platform.suggest_generation("S60", 2009), platform.P2_RESTYLING)
        self.assertEqual(platform.suggest_generation("S60", 2010), platform.UNKNOWN)
        self.assertEqual(platform.suggest_generation("S60", 2011), platform.P3)

    def test_04_platform_switch_s80_v70_xc70(self):
        self.assertEqual(platform.suggest_generation("S80", 2003), platform.P2)
        self.assertEqual(platform.suggest_generation("S80", 2004), platform.P2_RESTYLING)
        self.assertEqual(platform.suggest_generation("S80", 2006), platform.P2_RESTYLING)
        self.assertEqual(platform.suggest_generation("S80", 2007), platform.P3)
        for model in ("V70", "XC70"):
            self.assertEqual(platform.suggest_generation(model, 2007), platform.P2_RESTYLING)
            self.assertEqual(platform.suggest_generation(model, 2008), platform.P3)

    def test_05_p3_specific_models_do_not_become_p2(self):
        for model, year in (("XC60", 2010), ("V60", 2012), ("S80", 2009), ("V70", 2009)):
            with self.subTest(model=model, year=year):
                r = platform.audit_platform(model, year)
                self.assertEqual(r["platform_family"], "P3")
                self.assertIsNone(r["p2_restyling"])

    def test_06_hw_and_d2_ggd_do_not_choose_platform(self):
        for hw in ("H", "L", "Unknown"):
            for proto in ("D2", "GGD", "Unknown"):
                with self.subTest(hw=hw, proto=proto):
                    r = platform.audit_platform("XC90", 2009, engine="B8444S",
                                                cem_hardware=hw, diagnostic_protocol=proto)
                    self.assertEqual(r["generation"], platform.P2_RESTYLING)
                    self.assertFalse(r["protocol_inferred_from_generation"])
                    self.assertFalse(r["cem_hardware_inferred_from_generation"])

    def test_07_conflicting_manual_platform_fails_closed(self):
        r = platform.audit_platform("XC90", 2009, declared_generation="P3")
        self.assertEqual(r["suggested_generation"], platform.P2_RESTYLING)
        self.assertEqual(r["generation"], platform.UNKNOWN)
        self.assertEqual(r["evidence_level"], "conflict")
        self.assertIn("DECLARED_GENERATION_CONFLICT: do not select a platform automatically", r["warnings"])
        r = platform.audit_platform("XC90", 2015, declared_generation="P3")
        self.assertEqual(r["evidence_level"], "declared_metadata")
        self.assertFalse(r["approved_for_ecu_response_selection"])

    def test_08_invalid_and_unsupported_never_become_p3(self):
        with self.assertRaises(ValueError):
            platform.audit_platform("S40", 2009)
        with self.assertRaises(ValueError):
            platform.audit_platform("XC90", True)
        with self.assertRaises(ValueError):
            platform.audit_platform("XC90", 999)
        with self.assertRaises(ValueError):
            platform.audit_platform("XC90", 2009, declared_generation="P2-HS-CAN")
        with self.assertRaises(ValueError):
            platform.audit_platform("XC90", 2009, diagnostic_protocol="ISO15765")
        r = platform.audit_platform("V70", 2000)
        self.assertEqual(r["generation"], platform.UNKNOWN)
        self.assertFalse(r["approved_for_ecu_response_selection"])


if __name__ == "__main__":
    unittest.main()
