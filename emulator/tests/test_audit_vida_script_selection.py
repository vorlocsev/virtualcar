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


    def test_17_vida2014d_literal_log_marker_not_build_incompatibility(self):
        records = ["Starting new logsession: 2026-09-25 22:22:30\n",
                   "VIDA release: VIDA2014D\n",
                   get(script_type="ReadVin"), fetched(), running()]
        audit = audit_lines(records)
        ev = audit["events"]
        self.assertEqual(ev["declared_vida2014d_release_lines"], 1)
        self.assertEqual(ev["declared_vida2015a_release_lines"], 0)
        self.assertEqual(ev["readvin_triplets_declared_vida2014d"], 1)
        self.assertEqual(ev["readvin_triplets_declared_vida2015a"], 0)
        self.assertTrue(audit["literal_release_marker_does_not_prove_incompatible_diagnostic_engine"])
        self.assertFalse(audit["actual_vida_client_identity_verified"])

    def test_18_vida2015a_explicit_tag_is_still_not_vin_acceptance(self):
        audit = audit_lines(["VIDA release: VIDA2015A\n",
                             get(script_type="ReadVin"), fetched(), running()])
        self.assertEqual(audit["events"]["readvin_triplets_declared_vida2015a"], 1)
        self.assertEqual(audit["events"]["readvin_triplets_declared_vida2014d"], 0)
        self.assertFalse(audit["script_selected_for_identify_vehicle_verified"])
        self.assertFalse(audit["xc90_v8_my2009_verified"])

    def test_19_cross_session_same_thread_cannot_complete_script_triplet(self):
        audit = audit_lines(["VIDA release: VIDA2014D\n",
                             get(script_type="ReadVin"), fetched(),
                             "Starting new logsession: 2026-09-26 12:34:13\n",
                             "VIDA release: VIDA2014D\n", running()])
        ev = audit["events"]
        self.assertEqual(ev["matched_read_vin_triplets"], 0)
        self.assertEqual(ev["unmatched_running_script_events"], 1)
        self.assertEqual(ev["session_boundary_lines"], 1)

    def test_20_release_change_without_session_boundary_invalidates_pending(self):
        audit = audit_lines(["VIDA release: VIDA2014D\n",
                             get(script_type="ReadVin"), fetched(),
                             "VIDA release: VIDA2015A\n", running()])
        ev = audit["events"]
        self.assertEqual(ev["matched_read_vin_triplets"], 0)
        self.assertEqual(ev["unmatched_running_script_events"], 1)
        self.assertEqual(ev["declared_vida2014d_release_lines"], 1)
        self.assertEqual(ev["declared_vida2015a_release_lines"], 1)

    def test_21_image_repository_login_failure_not_getscript_failure(self):
        audit = audit_lines(["VIDA release: VIDA2014D\n",
                             '12:36:35,013 [VehicleInformati][001][Error] '
                             'System.Data.SqlClient.SqlException: '
                             'Cannot open database "ImageRepository" requested by the login.\n',
                             "Login failed for user 'SYNTHETIC_PRIVATE_USER'.\n",
                             "12:36:38,711 [NavImageProvider][001][Info] "
                             "Database: DiagSwdlRepository, SP: GetNavImage\n"])
        ev = audit["events"]
        self.assertEqual(ev["image_repository_login_failure_mentions"], 1)
        self.assertEqual(ev["diagswdl_repository_sp_mentions"], 1)
        self.assertEqual(ev["get_script_requests"], 0)
        self.assertTrue(audit["image_repository_login_failure_is_not_getscript_failure"])
        self.assertNotIn("SYNTHETIC_PRIVATE_USER", json.dumps(audit))

    def test_22_j2534_load_attempt_does_not_prove_connect_success(self):
        audit = audit_lines(["VIDA release: VIDA2014D\n",
                             r"12:36:48,574 [J2534ChannelMana][001][VehCom] "
                             r"Loading J2534 driver: C:\PRIVATE\SECRET\diag.dll" + "\n"])
        self.assertEqual(audit["events"]["j2534_driver_load_attempts"], 1)
        self.assertFalse(audit["actual_j2534_connection_success_verified"])
        self.assertTrue(audit["j2534_driver_load_attempt_is_not_connection_success"])
        self.assertNotIn("SECRET", json.dumps(audit))

    def test_23_mixed_versions_and_unlabelled_are_kept_distinct(self):
        records = [get(script_type="ReadVin"), fetched(), running(),
                   "Starting new logsession: 2026-09-25 22:22:30\n",
                   "VIDA release: VIDA2014D\n",
                   get(script_type="ReadVin"), fetched(), running(),
                   "Starting new logsession: 2026-09-26 12:34:13\n",
                   "VIDA release: VIDA2015A\n",
                   get(script_type="ReadVin"), fetched(), running()]
        result = audit_lines(records)
        ev = result["events"]
        self.assertEqual(ev["matched_read_vin_triplets"], 3)
        self.assertEqual(ev["readvin_triplets_version_unreported"], 1)
        self.assertEqual(ev["readvin_triplets_declared_vida2014d"], 1)
        self.assertEqual(ev["readvin_triplets_declared_vida2015a"], 1)
        self.assertFalse(result["cross_file_or_cross_date_correlation_established"])

    def test_24_untrusted_release_label_and_cli_no_private_export(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            private_path = p / "PRIVATE-ORIGINAL-VIDA-LOG.txt"
            private_path.write_text(
                "Starting new logsession: 2026-09-25 22:22:30\n"
                "VIDA release: VIDA2014D SPOOFED\n"
                + get(script_type="ReadVin")
                + fetched(name="PRIVATE_SCRIPT_IDENTIFIER")
                + running(name="PRIVATE_SCRIPT_IDENTIFIER"), encoding="utf8")
            output = p / "SAFE.json"
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(private_path), "--output", str(output)])
            result = json.loads(output.read_text(encoding="utf8"))
            self.assertEqual(result["events"]["declared_vida2014d_release_lines"], 0)
            self.assertEqual(result["events"]["readvin_triplets_version_unreported"], 1)
            for secret in ("PRIVATE-ORIGINAL", "PRIVATE_SCRIPT_IDENTIFIER",
                           "VIDA2014D SPOOFED", str(private_path)):
                self.assertNotIn(secret, json.dumps(result))
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(private_path), "--output", str(output)])


    def test_25_running_timestamp_before_fetch_is_not_executed_triplet(self):
        request = get(t="31,544", script_type="ReadVin")
        report = audit_lines([request, fetched(t="31,576"), running(t="31,550")])
        events = report["events"]
        self.assertEqual(events["out_of_order_running_script_events"], 1)
        self.assertEqual(events["unmatched_running_script_events"], 1)
        self.assertEqual(events["matched_get_fetch_run_triplets"], 0)
        self.assertEqual(events["matched_read_vin_triplets"], 0)
        self.assertFalse(report["script_selected_for_identify_vehicle_verified"])

    def test_26_same_timestamp_fetch_run_still_correlation_only(self):
        report = audit_lines([get(script_type="ReadVin"),
                              fetched(t="31,576"), running(t="31,576")])
        self.assertEqual(report["events"]["matched_read_vin_triplets"], 1)
        self.assertEqual(report["events"]["out_of_order_running_script_events"], 0)
        self.assertFalse(report["actual_vida_client_identity_verified"])

    def test_27_unbound_emptyprofile_readvin_bootstrap_shape(self):
        request = get(script_type="ReadVin").replace(
            "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'").replace(
            "EcuType: '123'", "EcuType: '-1'")
        result = audit_lines([request, fetched(), running()])
        events = result["events"]
        self.assertEqual(events["requests_read_vin_unbound_bootstrap_shape"], 1)
        self.assertEqual(events["matched_read_vin_unbound_bootstrap_shape_triplets"], 1)
        self.assertEqual(events["matched_read_vin_explicit_empty_profile_triplets"], 1)
        self.assertTrue(result["empty_profile_unbound_ecu_type_is_only_request_shape"])
        self.assertFalse(result["script_selected_for_identify_vehicle_verified"])
        self.assertFalse(result["actual_vida_client_identity_verified"])

    def test_28_bootstrap_requires_all_three_literal_request_fields(self):
        base = get(script_type="ReadVin").replace(
            "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'").replace(
            "EcuType: '123'", "EcuType: '-1'")
        for request in (
            base.replace("ScriptId: ''", "ScriptId: 'ID-ON-DISK'"),
            base.replace("ScriptId: ''", ""),
            base.replace("EcuType: '-1'", "EcuType: '0'"),
            base.replace("Profile: 'EMPTYPROFILE,'", "Profile: 'PRIVATE'"),
            base.replace("Type: 'ReadVin'", "Type: 'Other'"),
        ):
            with self.subTest(request=request):
                result = audit_lines([request, fetched(), running()])
                self.assertEqual(result["events"]["requests_read_vin_unbound_bootstrap_shape"], 0)
                self.assertEqual(result["events"]["matched_read_vin_unbound_bootstrap_shape_triplets"], 0)

    def test_29_out_of_order_bootstrap_never_promotes_match(self):
        request = get(script_type="ReadVin").replace(
            "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'").replace(
            "EcuType: '123'", "EcuType: '-1'")
        result = audit_lines([request, fetched(t="31,700"), running(t="31,600")])
        self.assertEqual(result["events"]["requests_read_vin_unbound_bootstrap_shape"], 1)
        self.assertEqual(result["events"]["matched_read_vin_unbound_bootstrap_shape_triplets"], 0)
        self.assertEqual(result["events"]["out_of_order_running_script_events"], 1)
        self.assertFalse(result["replay_approved"])

    def test_30_bootstrap_counters_stay_redacted_in_cli_output(self):
        with tempfile.TemporaryDirectory() as d:
            private = Path(d) / "YV1SYNTHETIC_PRIVATE_ORIGINAL.log"
            request = get(script_type="ReadVin").replace(
                "Profile: 'PRIVATE'", "Profile: 'EMPTYPROFILE,'").replace(
                "EcuType: '123'", "EcuType: '-1'")
            script = "SYNTHETIC_PRIVATE_IDENTIFIER"
            private.write_text(request + fetched(name=script) + running(name=script),
                               encoding="utf-8")
            output = Path(d) / "summary.json"
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(private), "--output", str(output)])
            text = output.read_text(encoding="utf-8")
            self.assertEqual(json.loads(text)["events"]
                             ["matched_read_vin_unbound_bootstrap_shape_triplets"], 1)
            for secret in ("YV1SYNTHETIC", script, "EMPTYPROFILE,", str(private)):
                self.assertNotIn(secret, text)


    def test_31_readvin_triplet_spanning_midnight_correlates(self):
        request = get(script_type="ReadVin").replace(
            "16:51:31,544", "23:59:59,980")
        fetch = fetched().replace("16:51:31,576", "00:00:00,005")
        run = running().replace("16:51:31,591", "00:00:00,017")
        result = audit_lines([request, fetch, run])
        self.assertEqual(result["events"]["matched_read_vin_triplets"], 1)
        self.assertEqual(result["events"]["matched_midnight_rollover_triplets"], 1)
        self.assertEqual(result["events"]["matched_read_vin_midnight_rollover_triplets"], 1)
        self.assertEqual(result["events"]["out_of_order_running_script_events"], 0)
        self.assertTrue(result["midnight_rollover_is_clock_only_inference"])
        self.assertFalse(result["actual_vida_client_identity_verified"])

    def test_32_fetch_before_midnight_run_after_midnight(self):
        request = get(script_type="ReadVin").replace(
            "16:51:31,544", "23:59:59,900")
        fetch = fetched().replace("16:51:31,576", "23:59:59,985")
        run = running().replace("16:51:31,591", "00:00:00,001")
        result = audit_lines([request, fetch, run])
        self.assertEqual(result["events"]["matched_get_fetch_run_triplets"], 1)
        self.assertEqual(result["events"]["matched_read_vin_triplets"], 1)
        self.assertEqual(result["events"]["matched_read_vin_midnight_rollover_triplets"], 1)
        self.assertFalse(result["script_selected_for_identify_vehicle_verified"])

    def test_33_backdated_running_before_midnight_fetch_is_rejected(self):
        request = get(script_type="ReadVin").replace(
            "16:51:31,544", "23:59:59,950")
        fetch = fetched().replace("16:51:31,576", "00:00:00,025")
        run = running().replace("16:51:31,591", "23:59:59,985")
        result = audit_lines([request, fetch, run])
        self.assertEqual(result["events"]["matched_read_vin_triplets"], 0)
        self.assertEqual(result["events"]["out_of_order_running_script_events"], 1)
        self.assertEqual(result["events"]["matched_midnight_rollover_triplets"], 0)

    def test_34_midnight_crossing_beyond_30_second_limit_rejected(self):
        request = get(script_type="ReadVin").replace(
            "16:51:31,544", "23:59:40,000")
        fetch = fetched().replace("16:51:31,576", "00:00:11,001")
        run = running().replace("16:51:31,591", "00:00:11,020")
        result = audit_lines([request, fetch, run])
        self.assertEqual(result["events"]["orphan_fetched_script_events"], 1)
        self.assertEqual(result["events"]["matched_get_fetch_run_triplets"], 0)

    def test_35_backdated_non_midnight_clock_does_not_wrap(self):
        request = get(script_type="ReadVin").replace(
            "16:51:31,544", "12:01:00,500")
        fetch = fetched().replace("16:51:31,576", "12:00:59,900")
        run = running().replace("16:51:31,591", "12:01:01,000")
        result = audit_lines([request, fetch, run])
        self.assertEqual(result["events"]["orphan_fetched_script_events"], 1)
        self.assertEqual(result["events"]["matched_read_vin_triplets"], 0)

    def test_36_midnight_session_boundary_clears_pending_lookup(self):
        request = get(script_type="ReadVin").replace(
            "16:51:31,544", "23:59:59,950")
        fetch = fetched().replace("16:51:31,576", "00:00:00,010")
        run = running().replace("16:51:31,591", "00:00:00,025")
        result = audit_lines([request, "Starting new logsession: 2026-11-11\n",
                              fetch, run])
        self.assertEqual(result["events"]["matched_read_vin_triplets"], 0)
        self.assertEqual(result["events"]["orphan_fetched_script_events"], 1)
        self.assertEqual(result["events"]["session_boundary_lines"], 1)


if __name__ == "__main__":
    unittest.main()
