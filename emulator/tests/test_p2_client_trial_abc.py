"""Eight source-grounded A/B/C P2 CEM trial and privacy tests.

These are EXPERIMENTAL donor-era fixtures for observing a real client.
Passing offline checks is not a real SectorV/VDASH acceptance result.
"""
import configparser
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_p2_d2_fixture_provenance as audit
import compare_p2_client_trials as compare

FILENAMES = [
    "profiles/p2-trial-00-no-d2.ini",
    "profiles/p2-trial-01-public-b9fb-only.ini",
    "profiles/p2-trial-02-mixed-b9fb-b9f0-locked.ini",
]
CANONICAL_KEYS = ("vin", "batterymv", "emitisorxstart", "ecucount")
COMPARISON_KEYS = (
    "read_only", "contains_payload_data", "raw_log_exported",
    "client_run_executed_by_tool", "native_executable_identity_verified",
    "client_ecu_inventory_verified", "vehicle_identity_verified",
    "xc90_v8_my2009_verified",
)


def config(number):
    p = configparser.ConfigParser(interpolation=None)
    p.read_string((ROOT / FILENAMES[number]).read_text(encoding="utf-8"))
    return p


def safe(*, records=True, fb=0, f0=0, p3=0, connected=1,
         client="sectorv"):
    obj = {
        "format": compare.BOUNDARY_FORMAT,
        "read_only": True,
        "contains_payload_data": False,
        "raw_log_exported": False,
        "client_run_executed_by_tool": False,
        "native_executable_identity_verified": False,
        "client_ecu_inventory_verified": False,
        "vehicle_identity_verified": False,
        "xc90_v8_my2009_verified": False,
        "new_native_records_observed": records,
        "connect_succeeded": connected,
        "b9fb_positive_transport_count": fb,
        "b9f0_positive_transport_count": f0,
        "first_p3_positive_transport_count": p3,
        "reported_client": client,
        "operator_ecu_list_attributable_to_completed_scan": False,
        "ui_vin_display_reported": "unknown",
        "same_run_operator_attested": False,
    }
    return obj


class ClientTrialABCCases(unittest.TestCase):
    def test_01_same_baseline_vehicle_and_p3_profiles(self):
        cfg = [config(n) for n in range(3)]
        for key in CANONICAL_KEYS:
            self.assertEqual(len({p["Vehicle"][key] for p in cfg}), 1)
        for name in ("ECU0", "ECU1"):
            self.assertEqual(len({tuple(p[name].items()) for p in cfg}), 1)
        self.assertTrue(all(p["P2"]["strictRouting"] == "1" for p in cfg))
        self.assertTrue(all(p["P2"]["replaySpacingMs"] == "12" for p in cfg))

    def test_02_baseline_has_no_cem_d2_frames(self):
        result = audit.audit((ROOT / FILENAMES[0]).read_text(encoding="utf-8"))
        self.assertEqual(result["active_fixture_count"], 0)
        self.assertFalse(result["xc90_v8_my2009_identity_verified"])
        self.assertFalse(result["sectorv_vdash_client_acceptance_verified"])

    def test_03_published_b9fb_13_frames_only_stays_donor(self):
        result = audit.audit((ROOT / FILENAMES[1]).read_text(encoding="utf-8"))
        self.assertEqual(result["active_fixture_count"], 1)
        by_service = {f["service"]: f for f in result["fixtures"]
                      if f["target"] == "0x50"}
        self.assertEqual(by_service["B9FB"]["response_frames"], 13)
        self.assertTrue(by_service["B9FB"]["transport_framing_verified"])
        self.assertEqual(by_service["B9F0"]["response_frames"], 0)
        self.assertEqual(result["global_provenance_claim"],
                         "historical_public_label_only")
        self.assertFalse(result["xc90_v8_my2009_identity_verified"])

    def test_04_mixed_donor_locked_and_explicit_opt_in_lacks_identity(self):
        original = (ROOT / FILENAMES[2]).read_text(encoding="utf-8")
        result = audit.audit(original)
        self.assertEqual(result["active_fixture_count"], 2)
        self.assertTrue(result["composite_replay_tag_gate"][
            "stored_d2_fixtures_blocked_without_opt_in"])
        self.assertEqual(result["global_provenance_claim"],
                         "local_composite_unverified")
        unlocked = audit.audit(original.replace(
            "AllowCompositeReplay=0", "AllowCompositeReplay=1"))
        self.assertTrue(all(x["replay_allowed_by_profile_gate"]
                            for x in unlocked["fixtures"]
                            if x["transport_framing_verified"]))
        self.assertFalse(unlocked["fixture_source_consistency_verified"])
        self.assertFalse(unlocked["xc90_v8_my2009_identity_verified"])
        self.assertFalse(unlocked["sectorv_vdash_client_acceptance_verified"])

    def test_05_safe_compare_reports_only_milestone_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = [Path(tmp) / f"{i}.json" for i in range(3)]
            for path, obj in zip(paths, (
                safe(fb=0), safe(fb=1), safe(fb=1, f0=1, p3=1),
            )):
                path.write_text(json.dumps(obj), encoding="utf-8")
            result = compare.compare(*paths)
            self.assertEqual(len(result["trials"]), 3)
            self.assertEqual(result["trials"][1]["changed_since_previous"],
                             ["b9fb_transport"])
            self.assertEqual(result["trials"][2]["changed_since_previous"],
                             ["b9f0_transport", "p3_transport"])
            self.assertFalse(result["sectorv_vdash_acceptance_verified"])
            self.assertFalse(result["genuine_xc90_v8_my2009_verified"])

    def test_06_mixed_client_or_missing_records_warn_not_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.json", Path(tmp) / "b.json"
            a.write_text(json.dumps(safe(records=False)), encoding="utf-8")
            b.write_text(json.dumps(safe(client="vdash_2_0", fb=1)),
                         encoding="utf-8")
            result = compare.compare(a, b)
            self.assertIn("different_operator_reported_client_families",
                          result["comparability_warning_codes"])
            self.assertIn("one_or_more_runs_have_no_new_native_j2534_records",
                          result["comparability_warning_codes"])
            self.assertFalse(result["same_client_family_self_reported"])

    def test_07_malformed_or_unsafe_source_rejected_without_leak(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp) / "a.json", Path(tmp) / "b.json"
            a.write_text(json.dumps(safe()), encoding="utf-8")
            bad = safe()
            bad["client_ecu_inventory_verified"] = True
            bad["private_vin"] = "CUSTOMER_VIN_NEVER_EXPORT"
            b.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                compare.compare(a, b)
            bad = safe()
            bad["b9fb_positive_transport_count"] = -1
            b.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(ValueError):
                compare.compare(a, b)

    def test_08_cli_exclusive_output_and_guarded_selector(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b, out = [Path(tmp) / x for x in ("a.json", "b.json", "safe.json")]
            a.write_text(json.dumps(safe()), encoding="utf-8")
            b.write_text(json.dumps(safe(fb=1)), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(compare.main(
                    ["--a", str(a), "--b", str(b), "--output", str(out)]), 0)
            self.assertNotIn("CUSTOMER_VIN_NEVER_EXPORT", out.read_text())
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(compare.main(
                    ["--a", str(a), "--b", str(b), "--output", str(out)]), 2)
                self.assertEqual(compare.main(
                    ["--a", str(a), "--b", str(b), "--output", str(a)]), 2)
            selector = (ROOT / "scripts/Select-P2ClientTrialProfile.ps1"
                        ).read_text(encoding="utf-8")
            for term in ("IConfirmClientsClosed",
                         "IUnderstandExperimentalDonorData",
                         "EnableCompositeReplay", "File]::Replace",
                         "TrialProfileBackups"):
                self.assertIn(term, selector)
            self.assertNotIn("Start-Process", selector)


if __name__ == "__main__":
    unittest.main()
