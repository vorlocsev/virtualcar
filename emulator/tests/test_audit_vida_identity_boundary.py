"""Eight synthetic, read-only VIDA identity boundary test groups."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_identity_boundary import SCHEMA, audit, main


def sample():
    return {
        "schema_version": SCHEMA,
        "application": "VIDA2015A",
        "run_scope": "same_client_run",
        "evidence_source": "human_reviewed_lab_summary",
        "stages": {
            "b9fb_transport": "complete",
            "identify_script": "not_observed",
            "vin_resolver": "not_observed",
            "ecu_identification": "not_observed",
        },
        "is_x40": None,
    }


class VidaIdentityBoundaryTests(unittest.TestCase):
    def test_01_b9fb_complete_does_not_create_identity(self):
        out = audit(sample())
        self.assertEqual(out["identifyvehicle_il_branch"], "not_observed")
        self.assertIsNone(out["is_identity_vin_property"])
        self.assertFalse(out["vehicle_identity_verified_for_xc90_my2009"])
        self.assertFalse(out["replay_approved"])

    def test_02_empty_script_identity_takes_vin_exception_branch(self):
        d = sample()
        d["stages"]["identify_script"] = "returned_empty"
        out = audit(d)
        self.assertEqual(out["identifyvehicle_il_branch"], "vin_exception_branch")
        self.assertEqual(out["vin_validated_by_observed_run"], "unknown")
        self.assertEqual(out["vehicle_profile_confirmed"], "unknown")

    def test_03_non_x40_script_identity_is_only_property_not_valid_vin(self):
        d = sample()
        d["stages"]["identify_script"] = "returned_identity"
        d["is_x40"] = False
        out = audit(d)
        self.assertTrue(out["is_identity_vin_property"])
        self.assertEqual(out["identity_trimming_rule"], "trailing_CR_LF_only")
        self.assertEqual(out["vin_validated_by_observed_run"], "unknown")
        self.assertEqual(out["direct_b9fb_to_identity_script_dependency"], "not_proven")

    def test_04_x40_serial_does_not_become_vin(self):
        d = sample()
        d["stages"]["identify_script"] = "returned_identity"
        d["is_x40"] = True
        out = audit(d)
        self.assertFalse(out["is_identity_vin_property"])
        self.assertEqual(out["identifyvehicle_il_branch"], "vehicle_identity_constructor_branch")

    def test_05_resolver_without_script_proves_no_direct_dependency(self):
        d = sample()
        d["stages"]["b9fb_transport"] = "not_observed"
        d["stages"]["vin_resolver"] = "profile_created"
        out = audit(d)
        self.assertEqual(out["direct_identifyvehicle_to_resolvevin_dependency"],
                         "not_observed_in_method")
        self.assertEqual(out["vehicle_profile_confirmed"], "unknown")
        self.assertEqual(out["vin_resolver_observation"], "profile_created")

    def test_06_ecu_response_does_not_imply_normal_mode_or_vin(self):
        d = sample()
        d["stages"]["ecu_identification"] = "response_seen"
        out = audit(d)
        self.assertEqual(out["ecu_identification_observation"], "response_seen")
        self.assertEqual(out["sectorv_normal_mode_predicate"], "unknown")
        self.assertFalse(out["vehicle_identity_verified_for_xc90_my2009"])

    def test_07_input_validation_rejects_identity_and_crossrun_leaks(self):
        variants = []
        d = sample(); d["VIN"] = "YV1XX0000A0000001"; variants.append(d)
        d = sample(); d["run_scope"] = "mixed_client_runs"; variants.append(d)
        d = sample(); d["evidence_source"] = "captured_private_log"; variants.append(d)
        d = sample(); d["stages"]["raw_reply"] = "F9FB"; variants.append(d)
        d = sample(); d["is_x40"] = False; variants.append(d)
        d = sample(); d["stages"]["identify_script"] = "returned_identity"; variants.append(d)
        d = sample(); d["stages"]["b9fb_transport"] = True; variants.append(d)
        d = sample(); d["application"] = "SectorV"; variants.append(d)
        for idx, d in enumerate(variants):
            with self.subTest(idx=idx), self.assertRaises(ValueError):
                audit(d)

    def test_08_cli_privacy_new_file_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            inp = path / "private-source-summary.json"
            out = path / "sanitized-audit.json"
            inp.write_text(json.dumps(sample()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(inp), "--output", str(out)])
            content = out.read_text(encoding="utf-8")
            for secret in ("private-source-summary", "YV1XX0000A0000001",
                           "B9FB5700", "F9FB", str(inp)):
                self.assertNotIn(secret, content)
            self.assertEqual(json.loads(content)["vin_validated_by_observed_run"],
                             "unknown")
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(inp), "--output", str(out)])


if __name__ == "__main__":
    unittest.main()
