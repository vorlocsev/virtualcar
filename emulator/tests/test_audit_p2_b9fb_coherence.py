"""Eight source-grounded checks of donor-only B9FB identity coherence."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location(
    "audit_p2_b9fb_coherence", ROOT / "tools" / "audit_p2_b9fb_coherence.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def lab():
    return (ROOT / "virtualcar-p2-b9fb-lab-vin.ini").read_text(encoding="utf-8")


def masked():
    return (ROOT / "virtualcar-p2-b9fb-demo.ini").read_text(encoding="utf-8")


class DonorB9FBCoherenceTests(unittest.TestCase):
    def test_01_lab_vin_matches_b9fb_but_chassis_candidate_differs(self):
        result = tool.audit(lab())
        self.assertTrue(result["transport_framing_valid"])
        self.assertTrue(result["positive_b9fb_echo"])
        self.assertTrue(result["known_donor_13frame_layout_matched"])
        self.assertEqual(result["post_echo_bytes"], 88)
        self.assertEqual(result["embedded_vin_shape"], "17_ascii_vin_characters")
        self.assertTrue(result["configured_vin_matches_embedded"])
        self.assertFalse(result["candidate_chassis_suffix_matches_embedded_vin"])
        self.assertTrue(result["declared_model_year_matches_vin_code"])
        self.assertIn("donor_chassis_candidate_differs_from_vin",
                      result["possible_profile_inconsistencies"])
        self.assertFalse(result["sectorv_vin_acceptance_verified"])

    def test_02_target_2009_and_provisional_type_275_do_not_match_lab(self):
        result = tool.audit(lab(), expected_year=2009, expected_type_code="275")
        self.assertFalse(result["expected_model_year_matches_vin_code"])
        self.assertFalse(result["candidate_type_code_matches_supplied_expectation"])
        self.assertIn("donor_type_candidate_differs_from_expectation",
                      result["possible_profile_inconsistencies"])
        self.assertIn("supplied_expected_year_differs_from_vin_code",
                      result["possible_profile_inconsistencies"])
        self.assertFalse(result["xc90_v8_my2009_identity_verified"])

    def test_03_masked_public_demo_does_not_infer_vin_or_chassis_match(self):
        result = tool.audit(masked(), expected_year=2009, expected_type_code="275")
        self.assertEqual(result["embedded_vin_shape"], "redacted_mask")
        self.assertIsNone(result["configured_vin_matches_embedded"])
        self.assertIsNone(result["candidate_chassis_suffix_matches_embedded_vin"])
        self.assertIsNone(result["expected_model_year_matches_vin_code"])
        self.assertIsNone(result["candidate_type_code_matches_supplied_expectation"])
        self.assertEqual(result["possible_profile_inconsistencies"], [])

    def test_04_configured_vin_or_year_mismatch_separate_from_transport(self):
        changed = lab().replace("VIN = YV1CZ0002A0000001",
                                "VIN = YV1CZ0002A0000002")
        changed = changed.replace("ModelYear = 2010", "ModelYear = 2009")
        result = tool.audit(changed)
        self.assertTrue(result["transport_framing_valid"])
        self.assertFalse(result["configured_vin_matches_embedded"])
        self.assertFalse(result["declared_model_year_matches_vin_code"])
        self.assertEqual(result["embedded_vin_shape"], "17_ascii_vin_characters")
        self.assertFalse(result["schema_semantics_verified"])

    def test_05_bad_frame_control_or_echo_cannot_pass_transport(self):
        original = lab()
        for mutation in (
            original.replace("8F 50 F9 FB", "8F 50 F9 F0", 1),
            original.replace("09 70 28", "0F 70 28", 1),
            original.replace("4F 30 36", "0B 30 36", 1),
        ):
            with self.subTest(which=mutation[:35]), self.assertRaises(ValueError):
                tool.audit(mutation)

    def test_06_bad_counts_extra_frames_and_illegal_expected_values(self):
        original = lab()
        for source in (
            original.replace("B9FBFrameCount = 13", "B9FBFrameCount = 14", 1),
            original.replace("[D2_40_B9F0]",
                             "B9FBFrameD = 00 00 00 00 00 00 00 00\\n[D2_40_B9F0]", 1),
            original.replace("B9FBFrameA = 0A 30", "B9FBFrameA = 0A XX", 1),
        ):
            with self.subTest(length=len(source)), self.assertRaises(ValueError):
                tool.audit(source)
        for expected in (1999, 2031, "2009"):
            with self.subTest(year=expected), self.assertRaises(ValueError):
                tool.audit(original, expected_year=expected)
        with self.assertRaises(ValueError):
            tool.audit(original, expected_type_code="XC90")

    def test_07_source_fields_are_never_exposed_in_safe_report(self):
        secret = "PRIVATE_VIN_AND_PASSWORD_NEVER_EXPORT"
        source = lab() + "\n[LocalSecret]\nToken = " + secret + "\n"
        summary = json.dumps(tool.audit(source, expected_year=2009,
                                        expected_type_code="275"))
        self.assertNotIn(secret, summary)
        self.assertNotIn("YV1CZ0002A0000001", summary)
        self.assertNotIn("198625", summary)
        self.assertNotIn("01200003", summary)
        self.assertNotIn("295", summary)
        self.assertNotIn("SYNTHETIC", summary.upper())
        self.assertFalse(json.loads(summary)["contains_payload_data"])

    def test_08_cli_writes_new_safe_report_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, out = root / "private-p2.ini", root / "safe.json"
            body = lab()
            source.write_text(body, encoding="utf-8")
            args = [str(source), "--expected-year", "2009",
                    "--expected-type-code", "275", "--output", str(out)]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main(args), 0)
            safe = json.loads(out.read_text(encoding="utf-8"))
            self.assertFalse(safe["expected_model_year_matches_vin_code"])
            first = out.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main(args), 2)
                self.assertEqual(tool.main([str(source), "--output", str(source)]), 2)
            self.assertEqual(out.read_bytes(), first)
            self.assertEqual(source.read_text(encoding="utf-8"), body)
            self.assertNotIn("YV1CZ0002A0000001", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
