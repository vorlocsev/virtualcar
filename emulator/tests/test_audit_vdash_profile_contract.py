"""Eight offline synthetic/profile tests for VDASH P2/P3 configuration provenance."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    "vdash_profile_contract", ROOT / "tools" / "audit_vdash_profile_contract.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class ProfileContractTests(unittest.TestCase):
    def test_01_existing_mixed_vdash_lab_profile_has_no_b9fb(self):
        raw = (ROOT / "virtualcar-vdash-lab.ini").read_text(encoding="utf-8")
        report = tool.audit(raw)
        self.assertEqual(report["profile_research_focus"], "mixed_p2_p3_lab_configuration")
        self.assertTrue(report["has_726_72e_p3_route"])
        self.assertTrue(report["has_7e0_7e8_obd_route"])
        self.assertEqual(report["indexed_ecu_sections"], 2)
        self.assertTrue(report["ecu_section_count_consistent"])
        for entry in report["d2_service_fixtures"]:
            if entry["service"] == "B9FB":
                self.assertEqual(entry["state"], "zero_declared")
                self.assertEqual(entry["frame_count"], 0)
        self.assertFalse(report["xc90_v8_my2009_verified"])

    def test_02_existing_strict_p2_profile_has_zero_read_fixtures(self):
        raw = (ROOT / "virtualcar-p2.ini").read_text(encoding="utf-8")
        report = tool.audit(raw)
        self.assertEqual(report["profile_research_focus"], "strict_p2_no_d2_read_fixtures")
        self.assertTrue(report["p2_strict_routing"])
        self.assertFalse(report["has_726_72e_p3_route"])
        self.assertEqual(report["ecu_count_declared"], 1)
        self.assertTrue(report["ecu_section_count_consistent"])
        self.assertTrue(all(entry["frame_count"] == 0 for entry in
                            report["d2_service_fixtures"]))
        self.assertFalse(report["vdash_acceptance_verified"])

    def test_03_no_selected_d2_service_stays_unreported(self):
        raw = "[Vehicle]\nECUCount=0\n[PassiveCAN]\nEnabled=0\n"
        report = tool.audit(raw)
        self.assertEqual(report["profile_research_focus"],
                         "configuration_only_no_acceptance_evidence")
        self.assertTrue(all(x["state"] == "unreported" for x in
                            report["d2_service_fixtures"]))
        self.assertTrue(report["ecu_section_count_consistent"])

    def test_04_nonzero_d2_count_remains_unverified_without_payload(self):
        raw = ("[Vehicle]\nECUCount=0\n[P2]\nStrictRouting=1\n"
               "[D2_50]\nB9FBFrameCount=13\n"
               "B9FBFrame0=PRIVATE_FRAME_NEVER_EXPORT\n")
        report = tool.audit(raw)
        self.assertEqual(report["profile_research_focus"],
                         "declared_d2_frames_need_source_validation")
        record = next(x for x in report["d2_service_fixtures"]
                      if x["bus"] == "50" and x["service"] == "B9FB")
        self.assertEqual(record["frame_count"], 13)
        self.assertEqual(record["state"], "nonzero_unverified")
        self.assertNotIn("PRIVATE_FRAME_NEVER_EXPORT", json.dumps(report))
        self.assertFalse(report["ecu_identity_verified"])

    def test_05_strict_p2_with_p3_route_is_provenance_warning(self):
        raw = ("[Vehicle]\nECUCount=1\n[ECU0]\nRequestId=726\n"
               "ResponseId=72E\n[P2]\nStrictRouting=1\n"
               "[D2_50]\nB9FBFrameCount=0\n")
        result = tool.audit(raw)
        self.assertEqual(result["profile_research_focus"],
                         "strict_p2_with_p3_route_unverified")
        self.assertFalse(result["vdash_acceptance_verified"])

    def test_06_invalid_profile_counts_ids_and_duplicate_fields_rejected(self):
        bad = [
            "[Vehicle]\nECUCount=-1\n",
            "[Vehicle]\nECUCount=33\n",
            "[Vehicle]\nECUCount=1\n[ECU0]\nRequestId=0x20000000\n",
            "[P2]\nStrictRouting=2\n",
            "[D2_50]\nB9FBFrameCount=0\nB9FBFrame0=XX\n",
            "[Vehicle]\nECUCount=0\nECUCount=1\n",
        ]
        for text in bad:
            with self.subTest(raw=text[:20]), self.assertRaises(ValueError):
                tool.audit(text)

    def test_07_ecu_count_mismatch_not_fabricated_ecu_discovery(self):
        raw = ("[Vehicle]\nECUCount=2\n"
               "[ECU0]\nRequestId=7E0\nResponseId=7E8\n")
        report = tool.audit(raw)
        self.assertEqual(report["profile_research_focus"], "ecu_count_mismatch")
        self.assertFalse(report["ecu_section_count_consistent"])
        self.assertEqual(report["indexed_ecu_sections"], 1)
        self.assertFalse(report["vdash_acceptance_verified"])

    def test_08_cli_redacts_vin_and_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            source, output = p / "private.ini", p / "summary.json"
            private = "PRIVATE_VIN_CUSTOMER_ABC"
            source.write_text(
                "[Vehicle]\nECUCount=0\nVIN=" + private +
                "\n[Private]\nToken=PRIVATE_TOKEN\n",
                encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(source), "--output", str(output)]), 0)
            dumped = output.read_text(encoding="utf-8")
            self.assertNotIn(private, dumped)
            self.assertNotIn("PRIVATE_TOKEN", dumped)
            self.assertNotIn(str(source), dumped)
            self.assertEqual(json.loads(dumped)["format"], tool.FORMAT)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                self.assertEqual(tool.main([str(source), "--output", str(output)]), 2)
                self.assertEqual(tool.main([str(source), "--output", str(source)]), 2)
            self.assertNotIn(private, err.getvalue())


if __name__ == "__main__":
    unittest.main()
