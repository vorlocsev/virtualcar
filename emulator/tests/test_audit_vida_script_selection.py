"""Eight synthetic VIDA trace evidence tests; no authentic vehicle identifiers."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_script_selection import audit_lines, audit_file, main


def event(t, component, thread, payload):
    return f"16:51:{t} [{component:<14}][{thread:03}][Event] {payload}\n"


def get(t="31,544", thread=1, script_type="VehCommSpecification"):
    return event(t, "ScriptProvider", thread,
                 "Database: DiagSwdlRepository, SP: GetScript, Type: '" + script_type
                 + "' ScriptId: '' Language: 'en-US' EcuType: '123' Profile: 'PRIVATE' ")


def fetched(t="31,576", thread=1, name="INTERNAL-TEST-ID"):
    return event(t, "ScriptProvider", thread, "Fetched script: '"+name+"' title: 'SYNTHETIC'")


def running(t="31,591", thread=1, name="INTERNAL-TEST-ID"):
    return event(t, "Script", thread, "Running script: '"+name+"' title: 'SYNTHETIC'")


class VidaSelectionTraceTests(unittest.TestCase):
    def test_01_ordered_triplet_is_not_identity_verification(self):
        r = audit_lines([get(), fetched(), running()])
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 1)
        self.assertEqual(r["events"]["matched_veh_comm_specification_triplets"], 1)
        self.assertFalse(r["script_selected_for_identify_vehicle_verified"])

    def test_02_other_getscript_type_not_cem_identity(self):
        r = audit_lines([get(script_type="SpecialUnverifiedType"), fetched(), running()])
        self.assertEqual(r["events"]["requests_other_type"], 1)
        self.assertEqual(r["events"]["matched_veh_comm_specification_triplets"], 0)
        self.assertFalse(r["b9fb_to_vin_mapping_verified"])

    def test_03_wrong_script_id_fails_correlation(self):
        r = audit_lines([get(), fetched(name="SCRIPT-A"), running(name="SCRIPT-B")])
        self.assertEqual(r["events"]["different_script_running_events"], 1)
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 0)

    def test_04_cross_thread_cannot_be_joined(self):
        r = audit_lines([get(thread=1), fetched(thread=2), running(thread=2)])
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 0)
        self.assertEqual(r["events"]["orphan_fetched_script_events"], 1)
        self.assertEqual(r["events"]["unmatched_running_script_events"], 1)

    def test_05_superseding_lookup_and_deadline(self):
        r = audit_lines([get(), get(t="31,600"), fetched(t="31,700"), running(t="31,800")])
        self.assertEqual(r["events"]["superseded_incomplete_get_script_requests"], 1)
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 1)
        r = audit_lines([get(), fetched(t="59,900"), running(t="59,950")])
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 1)
        r = audit_lines([get(t="00,000"), fetched(t="31,100"), running(t="31,101")])
        self.assertEqual(r["events"]["matched_get_fetch_run_triplets"], 0)

    def test_06_error_and_identity_method_mention_are_not_selection(self):
        r = audit_lines([get(), "Vcc.ScriptMissingException: Lookup failed\n",
                         "RunScriptService.GetVehCommSpecification threw an exception\n",
                         " at RunScriptService.RunIdentifyVehicleScript\n"])
        self.assertEqual(r["events"]["script_missing_exception_mentions"], 1)
        self.assertEqual(r["events"]["get_vehcomm_specification_error_mentions"], 1)
        self.assertEqual(r["events"]["run_identify_vehicle_method_mentions"], 1)
        self.assertFalse(r["script_selected_for_identify_vehicle_verified"])

    def test_07_source_bounds_malformed_and_encoding(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "PRIVATE.log")
            p.write_bytes(b"\xff\xfe")
            with self.assertRaises(UnicodeError): audit_file(p)
            p.write_text("A" * 8200, encoding="utf8")
            with self.assertRaises(ValueError): audit_file(p)
            with self.assertRaises(ValueError): audit_lines([get(t="61,544")])

    def test_08_cli_privacy_exclusive_and_no_content_export(self):
        with tempfile.TemporaryDirectory() as d:
            src = Path(d, "PRIVATE-VIN-DO-NOT-SHARE.log")
            src.write_text(get() + fetched(name="YV1PRIVATE_S123") + running(name="YV1PRIVATE_S123"), encoding="utf8")
            out = Path(d, "SAFE.json")
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(src), "--output", str(out)])
            data = out.read_text()
            for secret in ("YV1PRIVATE", "PRIVATE-VIN", "PRIVATE'", str(src), "INTERNAL-TEST-ID"):
                self.assertNotIn(secret, data)
            self.assertEqual(json.loads(data)["events"]["matched_get_fetch_run_triplets"], 1)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(src), "--output", str(out)])


    def test_09_readvin_triplet_without_identity_claim(self):
        report = audit_lines([get(script_type="ReadVin"), fetched(), running()])
        self.assertEqual(report["events"]["requests_read_vin"], 1)
        self.assertEqual(report["events"]["requests_other_type"], 0)
        self.assertEqual(report["events"]["matched_read_vin_triplets"], 1)
        self.assertEqual(report["events"]["matched_read_vin_explicit_empty_profile_triplets"], 0)
        self.assertFalse(report["script_selected_for_identify_vehicle_verified"])
        self.assertFalse(report["b9fb_to_vin_mapping_verified"])

    def test_10_exact_empty_profile_readvin_correlation(self):
        request = get(script_type="ReadVin").replace(
            "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'")
        report = audit_lines([request, fetched(), running()])
        events = report["events"]
        self.assertEqual(events["requests_read_vin_explicit_empty_profile"], 1)
        self.assertEqual(events["matched_read_vin_explicit_empty_profile_triplets"], 1)
        self.assertTrue(report["empty_profile_token_is_not_verified_vehicle_profile"])

    def test_11_readvin_wrong_case_and_other_type_not_promoted(self):
        for case in ("ReadVIN", "readvin", "CarConfig", "VehCommSpecification"):
            request = get(script_type=case).replace(
                "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'")
            with self.subTest(case=case):
                report = audit_lines([request, fetched(), running()])
                self.assertEqual(report["events"]["requests_read_vin"], 0)
                self.assertEqual(report["events"]["matched_read_vin_triplets"], 0)
                self.assertEqual(report["events"]["requests_read_vin_explicit_empty_profile"], 0)

    def test_12_bare_empty_profile_in_title_is_not_request_profile(self):
        request = get(script_type="ReadVin")
        report = audit_lines([request,
                              fetched(name="EMPTYPROFILE, SYNTHETIC"),
                              running(name="EMPTYPROFILE, SYNTHETIC")])
        self.assertEqual(report["events"]["matched_read_vin_triplets"], 1)
        self.assertEqual(report["events"]["requests_read_vin_explicit_empty_profile"], 0)

    def test_13_mismatched_readvin_script_ids_not_same_script(self):
        request = get(script_type="ReadVin").replace(
            "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'")
        report = audit_lines([request, fetched(name="PRIVATE_A"), running(name="PRIVATE_B")])
        self.assertEqual(report["events"]["matched_read_vin_triplets"], 0)
        self.assertEqual(report["events"]["matched_read_vin_explicit_empty_profile_triplets"], 0)
        self.assertEqual(report["events"]["different_script_running_events"], 1)

    def test_14_readvin_cross_thread_and_deadline_are_not_joined(self):
        request = get(script_type="ReadVin").replace(
            "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'")
        report = audit_lines([request, fetched(thread=2), running(thread=2)])
        self.assertEqual(report["events"]["matched_read_vin_triplets"], 0)
        report = audit_lines([get(t="00,000", script_type="ReadVin"),
                              fetched(t="31,100"), running(t="31,120")])
        self.assertEqual(report["events"]["matched_read_vin_triplets"], 0)

    def test_15_readvin_getscript_only_is_not_execution_or_b9fb_proof(self):
        request = get(script_type="ReadVin").replace(
            "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'")
        report = audit_lines([request,
                              "16:51:31,550 [DiagConnection][001][VehCom] request B9FB\n"])
        self.assertEqual(report["events"]["requests_read_vin"], 1)
        self.assertEqual(report["events"]["matched_read_vin_triplets"], 0)
        self.assertFalse(report["script_content_provenance_verified"])
        self.assertFalse(report["actual_vida_client_identity_verified"])

    def test_16_readvin_cli_remains_redacted_without_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d, "PRIVATE-CAR-DO-NOT-SHARE.log")
            request = get(script_type="ReadVin").replace(
                "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'")
            name = "SYNTHETIC_SECRET_SCRIPT_ID"
            private.write_text(request + fetched(name=name) + running(name=name),
                               encoding="utf8")
            out = Path(d, "SAFE.json")
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(private), "--output", str(out)])
            data = out.read_text(encoding="utf8")
            for forbidden in (name, "PRIVATE-CAR", "EMPTYPROFILE,", str(private)):
                self.assertNotIn(forbidden, data)
            report = json.loads(data)
            self.assertEqual(report["events"]["matched_read_vin_explicit_empty_profile_triplets"], 1)
            self.assertFalse(report["replay_approved"])
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(private), "--output", str(out)])


if __name__ == "__main__":
    unittest.main()
