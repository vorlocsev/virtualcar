"""Eight synthetic B9FB year-code consistency groups. No OEM identity replay."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import audit_p2_b9fb_shape as audit
from test_audit_p2_b9fb_shape import content, frames, log_for, LAB_VIN


class B9FBVinYearCodeEvidenceTests(unittest.TestCase):
    def test_01_2010_code_matches_synthetic_A_without_vehicle_acceptance(self):
        report = audit.audit_frames(frames(), expected_model_year=2010)
        self.assertEqual(report["transport"], "complete")
        self.assertTrue(report["vin_shaped_field"])
        self.assertEqual(report["expected_model_year"], 2010)
        self.assertEqual(report["vin_year_code_comparison"], "matches_expected_code")
        self.assertFalse(report["vehicle_identity_verified"])
        self.assertFalse(report["replay_approved"])

    def test_02_2009_code_disagrees_with_synthetic_A(self):
        report = audit.audit_frames(frames(), expected_model_year=2009)
        self.assertEqual(report["vin_year_code_comparison"], "differs_from_expected_code")
        self.assertEqual(report["six_digit_field_compared_with_vin_suffix"], "equal")
        self.assertFalse(report["vehicle_identity_verified"])

    def test_03_synthetic_2009_code_matches_without_check_digit_claim(self):
        vin = LAB_VIN[:9] + b"9" + LAB_VIN[10:]
        self.assertEqual(len(vin), 17)
        report = audit.audit_frames(frames(content(vin=vin)), expected_model_year=2009)
        self.assertEqual(report["vin_year_code_comparison"], "matches_expected_code")
        self.assertEqual(report["checksum_status"], "unknown")
        self.assertEqual(report["client_result"], "client_result_unknown")

    def test_04_no_expected_year_is_not_auto_assigned_from_sample(self):
        report = audit.audit_frames(frames())
        self.assertIsNone(report["expected_model_year"])
        self.assertEqual(report["vin_year_code_comparison"], "not_requested")
        self.assertTrue(report["vin_shaped_field"])

    def test_05_unsupported_year_or_boolean_fails_closed(self):
        for value in (2004, 2015, True, False, "2009", 0, -1, 2009.0):
            with self.subTest(value=str(value)), self.assertRaises(ValueError):
                audit.audit_frames(frames(), expected_model_year=value)

    def test_06_bad_shape_and_bad_vin_cannot_pass_year_gate(self):
        bad_year = audit.audit_frames(
            frames(content(vin=b"AB-CDE0002A000000")), expected_model_year=2009)
        self.assertFalse(bad_year["vin_shaped_field"])
        self.assertEqual(bad_year["vin_year_code_comparison"], "not_assessable")
        bad_fields = audit.audit_frames(
            frames(content(fields=False)), expected_model_year=2009)
        self.assertEqual(bad_fields["vin_year_code_comparison"], "not_assessable")

    def test_07_negative_and_invalid_transport_cannot_pass_year_gate(self):
        negative = [(0x01200003, bytes.fromhex("CB 50 7F B9 11 00 00 00"))]
        neg = audit.audit_frames(negative, expected_model_year=2009)
        self.assertEqual(neg["vin_year_code_comparison"], "not_assessable")
        self.assertEqual(neg["transport"], "negative_or_unknown")
        invalid = frames()[:-1]
        rep = audit.audit_frames(invalid, expected_model_year=2009)
        self.assertEqual(rep["transport"], "invalid")
        self.assertEqual(rep["vin_year_code_comparison"], "not_assessable")

    def test_08_cli_redaction_exclusive_output_and_no_identity_inference(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "private-vin-raw.log"
            output = Path(td) / "safe-year-gate.json"
            raw = log_for(frames())
            src.write_text(raw, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                audit.main([str(src), "--target", "50", "--expected-model-year",
                            "2009", "--output", str(output)])
            data = output.read_text(encoding="utf-8")
            report = json.loads(data)
            self.assertEqual(report["vin_year_code_comparison"], "differs_from_expected_code")
            self.assertFalse(report["replay_approved"])
            self.assertFalse(report["vehicle_identity_verified"])
            for excluded in (LAB_VIN.decode(), "private-vin-raw.log",
                             "SecretHost", "DEADBEEF"):
                self.assertNotIn(excluded, data)
            self.assertEqual(src.read_text(encoding="utf-8"), raw)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    audit.main([str(src), "--expected-model-year", "2009",
                                "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
