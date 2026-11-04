"""Eight source-grounded, fail-closed P2 D2 fixture provenance regressions.

The published XC70-era B9FB/B9F0 examples are not verified XC90 V8
MY2009 CEM identities. This suite never tests a proprietary client.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import audit_p2_d2_fixture_provenance as tool
from test_import_safety import call_import


def profile(name):
    return (ROOT / name).read_text(encoding="utf-8")


def row(summary, service, target="0x50"):
    return next(x for x in summary["fixtures"]
                if x["service"] == service and x["target"] == target)


class P2D2FixtureSourceTests(unittest.TestCase):
    def test_01_default_ini_emits_no_fake_cem_identity(self):
        result = tool.audit(profile("virtualcar.ini"))
        self.assertEqual(result["active_fixture_count"], 0)
        self.assertEqual(len(result["fixtures"]), 6)
        self.assertTrue(all(x["status"] == "disabled_no_fixture"
                            for x in result["fixtures"]))
        self.assertFalse(result["xc90_v8_my2009_identity_verified"])
        self.assertFalse(result["sectorv_vdash_client_acceptance_verified"])

    def test_02_historical_three_frame_b9f0_is_only_transport_shape(self):
        summary = tool.audit(profile("virtualcar-p2-historical-demo.ini"))
        entry = row(summary, "B9F0")
        self.assertEqual(summary["active_fixture_count"], 1)
        self.assertEqual(entry["response_frames"], 3)
        self.assertTrue(entry["positive_transport_observed"])
        self.assertTrue(entry["transport_framing_verified"])
        self.assertTrue(entry["published_example_shape_matched"])
        self.assertEqual(entry["source_class"], "section_undeclared")
        self.assertFalse(entry["ecu_identity_verified"])
        self.assertFalse(entry["application_checksum_verified"])
        self.assertIn("active_fixture_lacks_per_section_origin",
                      summary["source_warnings"])

    def test_03_donor_b9fb_13_frames_88_bytes_not_oem_schema(self):
        summary = tool.audit(profile("virtualcar-p2-b9fb-lab-vin.ini"))
        entry = row(summary, "B9FB")
        self.assertEqual(entry["response_frames"], 13)
        self.assertTrue(entry["published_example_shape_matched"])
        fb = summary["b9fb_donor_shape_coherence"]
        self.assertTrue(fb["donor_88_byte_footprint"])
        self.assertTrue(fb["configured_vin_matches_embedded"])
        self.assertFalse(fb["candidate_chassis_suffix_matches_embedded_vin"])
        self.assertFalse(fb["schema_semantics_verified"])
        self.assertEqual(summary["global_provenance_claim"],
                         "historical_public_label_only")
        self.assertFalse(summary["fixture_source_consistency_verified"])

    def test_04_redacted_public_vin_is_not_private_vehicle_identity(self):
        summary = tool.audit(profile("virtualcar-p2-b9fb-demo.ini"))
        self.assertEqual(summary["b9fb_donor_shape_coherence"]["embedded_vin_shape"],
                         "redacted_mask")
        self.assertIsNone(summary["b9fb_donor_shape_coherence"][
            "configured_vin_matches_embedded"])
        self.assertFalse(summary["xc90_v8_my2009_identity_verified"])

    def test_05_malformed_framing_and_incorrect_echo_fail_closed(self):
        origin = profile("virtualcar-p2-historical-demo.ini")
        for mutated in (
            origin.replace("FrameCount = 3", "FrameCount = 4", 1),
            origin.replace("09 13 20 20", "0F 13 20 20", 1),
            origin.replace("8F 50 F9 F0", "8F 50 F9 FB", 1),
            origin.replace("Frame2 = 4C", "Frame2 = ZZ", 1),
        ):
            with self.subTest(variation=mutated[-80:]), self.assertRaises(ValueError):
                tool.audit(mutated)

    def test_06_negative_response_never_becomes_part_number(self):
        source = profile("virtualcar-p2-historical-demo.ini")
        source = source.replace(
            "FrameCount = 3\nFrame0 = 8F 50 F9 F0 00 08 68 85\n"
            "Frame1 = 09 13 20 20 41 30 65 70\n"
            "Frame2 = 4C 24 20 20 41 00 00 00",
            "FrameCount = 1\nFrame0 = CC 50 7F B9 31 00 00 00",
        )
        result = tool.audit(source)
        entry = row(result, "B9F0")
        self.assertEqual(entry["status"], "negative_transport")
        self.assertFalse(entry["positive_transport_observed"])
        self.assertFalse(entry["published_example_shape_matched"])
        self.assertFalse(entry["ecu_identity_verified"])

    def test_07_imported_b9f0_invalidates_inherited_b9fb_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = root / "donor.ini"
            trace = root / "public-b9f0.txt"
            output = root / "composite.ini"
            # Adversarial donor template was explicitly opted into
            # replay before a different trace was imported. The importer
            # MUST revoke that inherited approval.
            original.write_text(
                profile("virtualcar-p2-b9fb-lab-vin.ini").replace(
                    "FixtureProvenance = historical_public_2005_fixture_with_replaced_VIN",
                    "FixtureProvenance = historical_public_2005_fixture_with_replaced_VIN\n"
                    "AllowCompositeReplay = 1\n"
                    "allowcompositereplay = 1"),
                encoding="utf-8")
            trace.write_text((ROOT / "samples/p2_b9f0_public_excerpt.txt").read_text(
                encoding="utf-8"), encoding="utf-8")
            private_original = original.read_bytes()
            self.assertEqual(call_import(trace, original, output,
                                         "--opcode", "F0"), 0)
            text = output.read_text(encoding="utf-8")
            self.assertIn("FixtureProvenance = local_composite_unverified_trace_import",
                          text)
            self.assertIn("FixtureSourceClass = local_redaction_attempt_unverified", text)
            self.assertIn("AllowCompositeReplay = 0", text)
            self.assertNotIn("AllowCompositeReplay = 1", text)
            self.assertNotIn("allowcompositereplay =", text)
            self.assertEqual(text.count("AllowCompositeReplay = 0"), 1)
            self.assertNotIn("FixtureProvenance = historical_public_", text)
            summary = tool.audit(text)
            self.assertEqual(summary["active_fixture_count"], 2)
            self.assertEqual(summary["global_provenance_claim"],
                             "local_composite_unverified")
            self.assertTrue(summary["composite_replay_tag_gate"][
                "stored_d2_fixtures_blocked_without_opt_in"])
            self.assertFalse(row(summary, "B9F0")[
                "replay_allowed_by_profile_gate"])
            self.assertFalse(row(summary, "B9FB")[
                "replay_allowed_by_profile_gate"])
            self.assertEqual(row(summary, "B9F0")["source_class"],
                             "local_redaction_attempt_unverified")
            self.assertEqual(row(summary, "B9FB")["source_class"],
                             "section_undeclared")
            self.assertIn("multi_section_sources_not_proven_same_donor",
                          summary["source_warnings"])
            self.assertFalse(summary["fixture_source_consistency_verified"])
            self.assertEqual(original.read_bytes(), private_original)

    def test_08_cli_redaction_no_overwrite_and_synthetic_vin_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            raw = root / "private.ini"
            safe = root / "safe.json"
            original = profile("virtualcar-p2-b9fb-lab-vin.ini")
            secret = "PRIVATE_SOURCE_TOKEN_NEVER_EXPORT"
            original += "\n[Private]\nSecret=" + secret + "\n"
            raw.write_text(original, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(raw), "--output", str(safe)]), 0)
            exported = safe.read_text(encoding="utf-8")
            for private in (secret, "YV1CZ0002A0000001", "198625",
                            "8688513", str(raw), "01200003"):
                self.assertNotIn(private, exported)
            self.assertFalse(json.loads(exported)["xc90_v8_my2009_identity_verified"])
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(tool.main([str(raw), "--output", str(safe)]), 2)
                self.assertEqual(tool.main([str(raw), "--output", str(raw)]), 2)
            self.assertEqual(raw.read_text(encoding="utf-8"), original)
            trace = root / "masked-b9fb.txt"
            template = root / "starting.ini"
            result = root / "lab-import.ini"
            trace.write_text((ROOT / "samples/p2_b9fb_public_redacted.txt")
                             .read_text(encoding="utf-8"), encoding="utf-8")
            template.write_text(
                profile("virtualcar-p2-historical-demo.ini").replace(
                    "ReplaySpacingMs = 12",
                    "ReplaySpacingMs = 12\nAllowCompositeReplay = 1"),
                encoding="utf-8")
            self.assertEqual(call_import(
                trace, template, result, "--lab-vin", "VCARLAB0000000000"), 0)
            self.assertIn("AllowCompositeReplay = 0",
                          result.read_text(encoding="utf-8"))
            lab_result = tool.audit(result.read_text(encoding="utf-8"))
            self.assertEqual(row(lab_result, "B9FB")["source_class"],
                             "local_synthetic_vin_unverified")
            self.assertTrue(lab_result["composite_replay_tag_gate"][
                "stored_d2_fixtures_blocked_without_opt_in"])
            self.assertFalse(row(lab_result, "B9FB")[
                "replay_allowed_by_profile_gate"])
            # Read-only local opt-in enables lab transport only, never
            # upgrades source authentication or XC90 hardware identity.
            allow = result.read_text(encoding="utf-8").replace(
                "AllowCompositeReplay = 0", "AllowCompositeReplay = 1")
            allowed = tool.audit(allow)
            self.assertTrue(row(allowed, "B9FB")[
                "replay_allowed_by_profile_gate"])
            self.assertFalse(allowed["xc90_v8_my2009_identity_verified"])
            self.assertFalse(allowed["fixture_source_consistency_verified"])
            self.assertFalse(lab_result["fixture_source_consistency_verified"])


if __name__ == "__main__":
    unittest.main()
