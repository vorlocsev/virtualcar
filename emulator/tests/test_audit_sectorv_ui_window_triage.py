"""Synthetic privacy and provenance checks for redacted SectorV GUI/J2534 triage."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_sectorv_ui_window_triage as triage
from audit_sectorv_fresh_window import REPORT_SCHEMA, SERVICES
from audit_sectorv_ui_observation import SCHEMA as GUI_SCHEMA


def _empty_d2():
    return {
        "requests": 0,
        "statuses": {},
        "rx_frame_buckets": {
            "zero": 0, "one_to_twelve": 0,
            "thirteen": 0, "fourteen_plus": 0,
        },
        "known_can_500k": 0,
        "unknown_protocol_or_baud": 0,
    }


def window(*, run=True, provider="same_at_endpoints_only"):
    metadata = {
        "new_bytes": 32, "complete_lines": 1,
        "dropped_first": False, "dropped_last": False,
        "source_present": True, "prefix_verified": True,
    }
    return {
        "schema_version": REPORT_SCHEMA,
        "source": "local_bounded_append_only",
        "read_only_audit": True,
        "contains_raw_can_or_vin": False,
        "operator_one_run_confirmed": run,
        "cross_log_transaction_attribution": "not_established",
        "client_ui_result": "not_observed_by_this_tool",
        "client_vehicle_identity_accepted": "not_verified",
        "replay_approved": False,
        "connect": {"attempts": 0, "statuses": {}},
        "discovery": {
            "transactions": 0, "statuses": {}, "p3_count": 0,
            "d2": {target: {s: _empty_d2() for s in SERVICES}
                   for target in ("0x40", "0x50")},
        },
        "backend": {
            "requests": 0, "invalid_lines": 0,
            "statuses": {},
            "d2_probe_coverage": {
                f"D2_{target}_{service}": {"requests": 0, "statuses": {}}
                for target in ("40", "50") for service in SERVICES
            },
        },
        "next_gate": "review_b9fb_d2_transport_and_client_ui_independently",
        "note": "No common event clock, no VIN accepted.",
        "windows": {"j2534": dict(metadata), "backend": dict(metadata)},
        "registered_provider": {
            "baseline_category": "installed_library_x86",
            "postrun_category": "installed_library_x86",
            "binary_endpoint_consistency": provider,
            "loaded_in_sectorv_client": "not_observed",
            "during_run_immutability": "not_verified",
            "same_guest_independently_attested": False,
        },
    }


def ui(*, identity="not_displayed", ecus="empty", error="vin_read_failed",
       connection="connected"):
    return {
        "schema_version": GUI_SCHEMA,
        "client": "SectorV", "scenario": "P2_MY2009_lab",
        "source": "human_ui_observation",
        "run_scope": "single_vm_client_run",
        "read_only": True,
        "physical_adapter_disconnected": True,
        "observations": {
            "adapter_listed": "yes", "adapter_selected": "yes",
            "connection": connection, "ecu_list": ecus,
            "vehicle_identity": identity, "error_category": error,
        },
    }


def set_b9(window_report, *, rx=False, target="0x50"):
    entry = window_report["discovery"]["d2"][target]["B9FB"]
    entry["requests"] = 1
    entry["statuses"] = {"delivered": 1} if rx else {"no_fixture": 1}
    entry["rx_frame_buckets"]["one_to_twelve" if rx else "zero"] = 1
    entry["known_can_500k"] = 1
    window_report["discovery"]["transactions"] = 1
    window_report["discovery"]["statuses"] = dict(entry["statuses"])
    return window_report


def module_snapshot(*, observation="registered_library_loaded_in_name_matched_client",
                    comparison="exact_bytes_at_snapshot"):
    return {
        "schema_version": triage.MODULE_SCHEMA,
        "scope": "operator_requested_current_host_snapshot_only",
        "observation": observation,
        "installed_vs_reference_dll": comparison,
        "next_safe_gate": triage._module_next_gate(observation, comparison),
        "name_matched_executable_authenticity": "not_verified",
        "operator_same_run_pairing": "not_independently_attested",
        "registered_provider_unchanged_during_run": "not_verified",
        "reference_dll_pe32": "not_assessed_by_this_tool",
        "client_was_launched_by_audit": False,
        "accepted_vin_or_ecu": "not_verified",
    }


class SectorVUiWindowTriageTests(unittest.TestCase):
    def test_01_without_explicit_pairing_no_same_run_claim(self):
        result = triage.triage(window(), ui())
        self.assertEqual(result["run_pairing"], "unpaired")
        self.assertEqual(result["first_next_gate"],
                         "establish_isolated_same_run_evidence")
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")

    def test_02_operator_pairing_is_only_an_unverified_assertion(self):
        result = triage.triage(window(), ui(), operator_pair_confirmed=True)
        self.assertEqual(result["run_pairing"], "operator_asserted_not_independently_verified")
        self.assertFalse(result["same_guest_independently_attested"])
        self.assertEqual(result["transaction_level_correlation"], "not_established")
        self.assertEqual(result["first_next_gate"],
                         "review_absent_b9fb_in_bounded_j2534_window")

    def test_03_disallow_pairing_if_bounded_window_not_one_run(self):
        with self.assertRaises(ValueError):
            triage.triage(window(run=False), ui(), operator_pair_confirmed=True)

    def test_04_screenshot_cannot_claim_same_guest(self):
        case = ui()
        case.update({
            "scenario": "unknown_lab",
            "source": "screenshot_ui_observation",
            "run_scope": "single_client_ui_observation",
            "read_only": None, "physical_adapter_disconnected": None,
        })
        with self.assertRaises(ValueError):
            triage.triage(window(), case, operator_pair_confirmed=True)
        result = triage.triage(window(), case)
        self.assertEqual(result["run_pairing"], "unpaired")

    def test_05_provider_changed_takes_priority_over_vin_failure(self):
        case = window(provider="changed_between_endpoints")
        result = triage.triage(case, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"], "resolve_provider_endpoint_change")
        self.assertEqual(result["provider_unchanged_during_run"], "not_verified")

    def test_06_failed_connect_takes_priority(self):
        case = ui(identity="unknown", ecus="not_opened",
                  error="connect_error", connection="failed")
        result = triage.triage(window(), case, operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"], "verify_j2534_provider_and_connect")

    def test_07_observed_b9fb_with_zero_rx_is_not_valid_vin(self):
        result = triage.triage(set_b9(window()), ui(), operator_pair_confirmed=True)
        self.assertEqual(result["b9fb_request_count_in_window"], 1)
        self.assertEqual(result["b9fb_requests_with_nonzero_rx_in_window"], 0)
        self.assertEqual(result["first_next_gate"], "review_b9fb_without_observed_rx")

    def test_08_nonzero_rx_still_does_not_correlate_to_gui_or_acceptance(self):
        result = triage.triage(set_b9(window(), rx=True), ui(),
                               operator_pair_confirmed=True)
        self.assertEqual(result["b9fb_requests_with_nonzero_rx_in_window"], 1)
        self.assertEqual(result["first_next_gate"],
                         "review_client_vin_failure_after_unlinked_rx")
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")
        self.assertEqual(result["transaction_level_correlation"], "not_established")

    def test_09_displayed_identity_with_ecus_requires_provenance(self):
        case = ui(identity="displayed", ecus="populated", error="none")
        result = triage.triage(set_b9(window(), rx=True), case,
                               operator_pair_confirmed=True)
        self.assertTrue(result["gui_vehicle_identity_displayed"])
        self.assertTrue(result["gui_ecu_list_populated"])
        self.assertFalse(result["oem_vin_and_ecu_verified"])
        self.assertEqual(result["first_next_gate"],
                         "review_identity_display_without_oem_validation")

    def test_10_identity_displayed_without_ecus_needs_ecu_gate(self):
        case = ui(identity="displayed", ecus="empty", error="none")
        result = triage.triage(window(), case, operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"],
                         "review_ecu_identification_after_ui_identity")

    def test_11_reject_unexpected_fields_vin_and_private_log_values(self):
        case = ui()
        case["observations"]["VIN"] = "YV1SYNTHETIC01234"
        with self.assertRaises(ValueError):
            triage.triage(window(), case)
        report = window()
        report["raw_log"] = "C:/private/j2534.txt"
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_12_reject_bad_counts_and_forged_delivery(self):
        for changed in (-1, True, 3):
            report = set_b9(window())
            report["discovery"]["d2"]["0x50"]["B9FB"]["requests"] = changed
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                triage.triage(report, ui())
        report = window()
        report["registered_provider"]["same_guest_independently_attested"] = True
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_13_changed_private_provider_category_is_not_promoted(self):
        report = window()
        report["registered_provider"]["baseline_category"] = "canonical_provider_absent"
        with self.assertRaises(ValueError):
            triage.triage(report, ui(), operator_pair_confirmed=True)

    def test_14_non_boolean_operator_confirmation_rejected(self):
        with self.assertRaises(ValueError):
            triage.triage(window(), ui(), operator_pair_confirmed=1)

    def test_15_cli_only_creates_redacted_exclusive_report(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "private-window.json"
            gui_path = root / "private-gui.json"
            output = root / "redacted-triage.json"
            source.write_text(json.dumps(set_b9(window(), rx=True)), encoding="utf-8")
            gui_path.write_text(json.dumps(ui()), encoding="utf-8")
            args = [
                "--window-report", str(source), "--ui-observation",
                str(gui_path), "--output", str(output),
                "--operator-same-run-confirmed",
            ]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(triage.main(args), 0)
            saved = output.read_text(encoding="utf-8")
            obj = json.loads(saved)
            self.assertEqual(obj["first_next_gate"],
                             "review_client_vin_failure_after_unlinked_rx")
            for private in (str(root), "private-window", "YV1", "sha256",
                            "PassThruOpen", "0x50", "C:/"):
                self.assertNotIn(private, saved)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main(args), 2)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), obj)

    def test_16_reject_forged_gui_source_and_unsafe_output_location(self):
        case = ui()
        case["source"] = "client_log_inferred"
        with self.assertRaises(ValueError):
            triage.triage(window(), case)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            win = root / "window.json"
            gui_path = root / "ui.json"
            win.write_text(json.dumps(window()), encoding="utf-8")
            gui_path.write_text(json.dumps(ui()), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main([
                    "--window-report", str(win),
                    "--ui-observation", str(gui_path),
                    "--output", str(win)]), 2)


    def test_17_missing_j2534_log_is_not_no_b9fb_request(self):
        report = window()
        report["windows"]["j2534"].update({
            "source_present": False, "prefix_verified": False,
            "new_bytes": 0, "complete_lines": 0,
        })
        result = triage.triage(report, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"],
                         "obtain_bounded_j2534_window_evidence")
        self.assertEqual(result["b9fb_request_count_in_window"], 0)

    def test_18_unknown_provider_is_not_treated_as_changed(self):
        report = window(provider="not_verified")
        result = triage.triage(report, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"],
                         "obtain_provider_endpoint_evidence")

    def test_19_absent_log_cannot_contain_new_bytes(self):
        report = window()
        report["windows"]["j2534"].update({
            "source_present": False, "prefix_verified": False
        })
        with self.assertRaises(ValueError):
            triage.triage(report, ui(), operator_pair_confirmed=True)

    def test_20_empty_new_log_has_no_analyzable_b9fb_window(self):
        report = window()
        report["windows"]["j2534"]["new_bytes"] = 0
        report["windows"]["j2534"]["complete_lines"] = 0
        result = triage.triage(report, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"],
                         "obtain_bounded_j2534_window_evidence")


    def test_21_reject_free_text_connect_status_even_if_count_matches(self):
        report = window()
        report["connect"] = {"attempts": 1, "statuses": {"untrusted_private_text": 1}}
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_22_reject_missing_connect_status_accounting(self):
        report = window()
        report["connect"] = {"attempts": 1, "statuses": {}}
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_23_reject_wrong_discovery_status_total_and_vocabulary(self):
        report = window()
        report["discovery"]["transactions"] = 2
        report["discovery"]["statuses"] = {"unverified": 1}
        with self.assertRaises(ValueError):
            triage.triage(report, ui())
        report["discovery"]["statuses"] = {"untrusted_private_text": 2}
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_24_reject_d2_count_larger_than_discovery_total(self):
        report = set_b9(window())
        report["discovery"]["transactions"] = 0
        report["discovery"]["statuses"] = {}
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_25_reject_unknown_backend_probe_or_forged_status(self):
        report = window()
        report["backend"]["d2_probe_coverage"]["unexpected_key"] = {
            "requests": 0, "statuses": {}
        }
        with self.assertRaises(ValueError):
            triage.triage(report, ui())
        report = window()
        report["backend"]["statuses"] = {"untrusted_private_text": 1}
        report["backend"]["requests"] = 1
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_26_reject_backend_probe_exceeding_request_summary(self):
        report = window()
        report["backend"]["d2_probe_coverage"]["D2_50_B9FB"] = {
            "requests": 1, "statuses": {"delivered": 1}
        }
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_27_reject_counted_events_without_fresh_log_lines(self):
        report = set_b9(window())
        report["windows"]["j2534"]["complete_lines"] = 0
        with self.assertRaises(ValueError):
            triage.triage(report, ui())
        report = window()
        report["backend"]["requests"] = 1
        report["backend"]["statuses"] = {"unverified": 1}
        report["windows"]["backend"]["complete_lines"] = 0
        with self.assertRaises(ValueError):
            triage.triage(report, ui())

    def test_28_valid_synthetic_delivery_remains_unverified_identity(self):
        report = set_b9(window(), rx=True)
        output = triage.triage(report, ui(), operator_pair_confirmed=True)
        self.assertEqual(output["b9fb_request_count_in_window"], 1)
        self.assertEqual(output["first_next_gate"],
                         "review_client_vin_failure_after_unlinked_rx")
        self.assertEqual(output["client_vehicle_identity_accepted"], "not_verified")
        self.assertFalse(output["oem_vin_and_ecu_verified"])



    def test_29_discarded_first_j2534_line_cannot_prove_absent_b9fb(self):
        case = window()
        case["windows"]["j2534"]["dropped_first"] = True
        result = triage.triage(case, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"],
                         "review_discarded_j2534_line_boundaries")
        self.assertTrue(result["j2534_discarded_partial_boundary_lines"])
        self.assertEqual(result["b9fb_request_count_in_window"], 0)
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")

    def test_30_discarded_last_j2534_line_cannot_prove_absent_b9fb(self):
        case = window()
        case["windows"]["j2534"]["dropped_last"] = True
        result = triage.triage(case, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"],
                         "review_discarded_j2534_line_boundaries")

    def test_31_observed_b9fb_still_available_when_other_lines_dropped(self):
        case = set_b9(window(), rx=True)
        case["windows"]["j2534"].update({
            "dropped_first": True, "dropped_last": True
        })
        result = triage.triage(case, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["b9fb_request_count_in_window"], 1)
        self.assertEqual(result["first_next_gate"],
                         "review_client_vin_failure_after_unlinked_rx")
        self.assertTrue(result["j2534_discarded_partial_boundary_lines"])
        self.assertFalse(result["oem_vin_and_ecu_verified"])

    def test_32_missing_log_priority_is_unchanged(self):
        case = window()
        case["windows"]["j2534"] = {
            "new_bytes": 0, "complete_lines": 0,
            "dropped_first": False, "dropped_last": False,
            "source_present": False, "prefix_verified": False,
        }
        result = triage.triage(case, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["first_next_gate"],
                         "obtain_bounded_j2534_window_evidence")
        self.assertFalse(result["j2534_discarded_partial_boundary_lines"])

    def test_33_reject_absent_log_claiming_discarded_lines(self):
        case = window()
        case["windows"]["j2534"] = {
            "new_bytes": 0, "complete_lines": 0,
            "dropped_first": False, "dropped_last": True,
            "source_present": False, "prefix_verified": False,
        }
        with self.assertRaises(ValueError):
            triage.triage(case, ui())

    def test_34_reject_first_boundary_drop_without_old_prefix(self):
        case = window()
        case["windows"]["j2534"].update({
            "dropped_first": True, "prefix_verified": False
        })
        with self.assertRaises(ValueError):
            triage.triage(case, ui())

    def test_35_reject_last_boundary_drop_without_appended_bytes(self):
        case = window()
        case["windows"]["j2534"].update({
            "dropped_last": True, "new_bytes": 0, "complete_lines": 0
        })
        with self.assertRaises(ValueError):
            triage.triage(case, ui())

    def test_36_cli_partial_line_gate_is_redacted_and_exclusive(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            private = root / "private-window.json"
            gui = root / "private-gui.json"
            output = root / "redacted-triage.json"
            case = window()
            case["windows"]["j2534"]["dropped_first"] = True
            private.write_text(json.dumps(case), encoding="utf-8")
            gui.write_text(json.dumps(ui()), encoding="utf-8")
            args = ["--window-report", str(private), "--ui-observation",
                    str(gui), "--output", str(output),
                    "--operator-same-run-confirmed"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(triage.main(args), 0)
            saved = output.read_text(encoding="utf-8")
            parsed = json.loads(saved)
            self.assertEqual(parsed["first_next_gate"],
                             "review_discarded_j2534_line_boundaries")
            self.assertTrue(parsed["j2534_discarded_partial_boundary_lines"])
            for forbidden in (str(root), "private-window", "PassThruReadMsgs",
                              "sha256", "YV1", "0x50"):
                self.assertNotIn(forbidden, saved)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main(args), 2)

    def test_37_optional_module_does_not_change_legacy_contract(self):
        original = triage.triage(set_b9(window(), rx=True), ui(),
                                operator_pair_confirmed=True)
        with_module = triage.triage(set_b9(window(), rx=True), ui(),
                                   operator_pair_confirmed=True,
                                   module_snapshot=module_snapshot())
        self.assertNotIn("operator_module_snapshot", original)
        self.assertEqual(with_module["first_next_gate"], original["first_next_gate"])
        self.assertEqual(with_module["j2534_binary_loaded_in_gui_client"], "not_verified")
        self.assertEqual(with_module["client_vehicle_identity_accepted"], "not_verified")
        self.assertFalse(with_module["oem_vin_and_ecu_verified"])
        self.assertEqual(with_module["operator_module_snapshot"]["observation"],
                         "registered_library_loaded_in_name_matched_client")
        self.assertFalse(with_module["operator_module_snapshot"]["same_guest_or_run_attested"])

    def test_38_name_matched_module_and_reference_bytes_never_verify_identity(self):
        report = triage.triage(window(), ui(identity="displayed", ecus="populated",
                                            error="none"), operator_pair_confirmed=True,
                               module_snapshot=module_snapshot())
        observed = report["operator_module_snapshot"]
        self.assertEqual(observed["reference_byte_comparison"], "exact_bytes_at_snapshot")
        self.assertEqual(observed["module_used_for_j2534_requests"], "not_verified")
        self.assertEqual(observed["client_executable_authenticity"], "not_verified")
        self.assertEqual(report["transaction_level_correlation"], "not_established")
        self.assertFalse(report["oem_vin_and_ecu_verified"])

    def test_39_missing_client_and_reference_mismatch_are_separate_categories(self):
        absent = module_snapshot(observation="client_not_observed_in_local_snapshot",
                                 comparison="not_compared")
        result = triage.triage(window(), ui(), module_snapshot=absent,
                               operator_pair_confirmed=True)
        self.assertEqual(result["operator_module_snapshot"]["next_safe_gate"],
                         "observe_client_with_gui_open")
        self.assertEqual(result["first_next_gate"],
                         "review_absent_b9fb_in_bounded_j2534_window")
        mismatch = module_snapshot(comparison="different_bytes_at_snapshot")
        result = triage.triage(window(), ui(), module_snapshot=mismatch)
        self.assertEqual(result["operator_module_snapshot"]["next_safe_gate"],
                         "resolve_reference_vs_registered_dll_difference")
        self.assertEqual(result["run_pairing"], "unpaired")

    def test_40_reject_private_path_vin_raw_text_and_unknown_snapshot_fields(self):
        for key, value in (("registered_path", r"C:\PRIVATE\J2534.dll"),
                           ("sha256", "A" * 64), ("vin", "YV1LAB00000000001"),
                           ("raw_module", "PassThruOpen")):
            bad = module_snapshot()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                triage.triage(window(), ui(), module_snapshot=bad)

    def test_41_reject_forged_module_provenance_and_verified_client_claims(self):
        mutations = (
            ("scope", "current_ci_runner_process_snapshot_only"),
            ("name_matched_executable_authenticity", "verified"),
            ("operator_same_run_pairing", "independently_verified"),
            ("registered_provider_unchanged_during_run", "verified"),
            ("reference_dll_pe32", "verified"),
            ("client_was_launched_by_audit", True),
            ("accepted_vin_or_ecu", "verified"),
        )
        for key, value in mutations:
            bad = module_snapshot()
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                triage.triage(window(), ui(), module_snapshot=bad)

    def test_42_reject_unknown_categories_and_forged_next_gate(self):
        for key, value in (
            ("observation", "VIN was accepted"),
            ("installed_vs_reference_dll", "hash:private"),
            ("next_safe_gate", "collect_same_run_redacted_j2534_and_gui_evidence")
        ):
            bad = module_snapshot(observation="client_not_observed_in_local_snapshot",
                                  comparison="not_compared")
            bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                triage.triage(window(), ui(), module_snapshot=bad)

    def test_45_reference_pe32_preflight_has_eight_bounded_evidence_cases(self):
        cases = (
            ("x86_pe32_header", "exact_bytes_at_snapshot",
             "collect_same_run_redacted_j2534_and_gui_evidence"),
            ("other_pe", "exact_bytes_at_snapshot",
             "verify_reference_pe32_before_gui"),
            ("invalid_pe", "exact_bytes_at_snapshot",
             "verify_reference_pe32_before_gui"),
            ("unverifiable", "exact_bytes_at_snapshot",
             "verify_reference_pe32_before_gui"),
            ("not_compared", "not_compared",
             "collect_gui_evidence_without_reference_attestation"),
            ("not_assessed_by_this_tool", "exact_bytes_at_snapshot",
             "collect_same_run_redacted_j2534_and_gui_evidence"),
            ("x86_pe32_header", "different_bytes_at_snapshot",
             "resolve_reference_vs_registered_dll_difference"),
            ("x86_pe32_header", "comparison_unverifiable",
             "verify_reference_and_registered_dll_equivalence"),
        )
        for status, comparison, gate in cases:
            with self.subTest(status=status, comparison=comparison):
                snapshot = module_snapshot(comparison=comparison)
                snapshot["reference_dll_pe32"] = status
                snapshot["next_safe_gate"] = triage._module_next_gate(
                    snapshot["observation"], comparison, status)
                report = triage.triage(window(), ui(), module_snapshot=snapshot)
                observed = report["operator_module_snapshot"]
                self.assertEqual(observed["reference_pe32_header"], status)
                self.assertEqual(observed["next_safe_gate"], gate)
                self.assertFalse(observed["same_guest_or_run_attested"])
                self.assertEqual(report["j2534_binary_loaded_in_gui_client"],
                                 "not_verified")
                self.assertFalse(report["oem_vin_and_ecu_verified"])

    def test_46_reference_pe32_preflight_rejects_unknown_and_spoofed_gate(self):
        for status in ("x86 PE32 verified", "C:/private/j2534.dll",
                       "sha256:aabb", "x64_driver_accepted"):
            snapshot = module_snapshot()
            snapshot["reference_dll_pe32"] = status
            with self.subTest(status=status), self.assertRaises(ValueError):
                triage.triage(window(), ui(), module_snapshot=snapshot)
        snapshot = module_snapshot()
        snapshot["reference_dll_pe32"] = "other_pe"
        # A forged old "all clear" recommendation must not pass strict parsing.
        with self.assertRaises(ValueError):
            triage.triage(window(), ui(), module_snapshot=snapshot)

    def test_43_cli_accepts_third_redacted_snapshot_without_exporting_private_data(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wp, up, mp = (root / name for name in
                          ("private-window.json", "private-gui.json",
                           "private-module.json"))
            output = root / "redacted-triage.json"
            wp.write_text(json.dumps(set_b9(window(), rx=True)), encoding="utf-8")
            up.write_text(json.dumps(ui()), encoding="utf-8")
            mp.write_text(json.dumps(module_snapshot()), encoding="utf-8")
            args = ["--window-report", str(wp), "--ui-observation", str(up),
                    "--module-snapshot", str(mp), "--output", str(output),
                    "--operator-same-run-confirmed"]
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(triage.main(args), 0)
            raw = output.read_text(encoding="utf-8")
            result = json.loads(raw)
            self.assertEqual(result["b9fb_requests_with_nonzero_rx_in_window"], 1)
            self.assertEqual(result["operator_module_snapshot"]["observation"],
                             "registered_library_loaded_in_name_matched_client")
            for secret in (str(root), "PRIVATE", "PassThruOpen", "sha256",
                           "YV1", "C:/", "0x50", "module_path"):
                self.assertNotIn(secret, raw)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main(args), 2)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), result)

    def test_44_cli_rejects_duplicate_oversized_and_forged_module_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wp, up, mp = (root / name for name in
                          ("window.json", "ui.json", "module.json"))
            output = root / "result.json"
            wp.write_text(json.dumps(window()), encoding="utf-8")
            up.write_text(json.dumps(ui()), encoding="utf-8")
            mp.write_text(json.dumps(module_snapshot()), encoding="utf-8")
            args = ["--window-report", str(wp), "--ui-observation", str(up),
                    "--module-snapshot", str(mp), "--output", str(output)]
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main(args), 0)
            original = output.read_bytes()
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main(args), 2)
            self.assertEqual(output.read_bytes(), original)
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main([
                    "--window-report", str(wp), "--ui-observation", str(up),
                    "--module-snapshot", str(wp),
                    "--output", str(root / "duplicate.json")]), 2)
            mp.write_text("X" * (triage.MAX_MODULE_FILE + 1), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main([
                    "--window-report", str(wp), "--ui-observation", str(up),
                    "--module-snapshot", str(mp),
                    "--output", str(root / "oversized.json")]), 2)
            forged = module_snapshot()
            forged["accepted_vin_or_ecu"] = "verified"
            mp.write_text(json.dumps(forged), encoding="utf-8")
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(triage.main([
                    "--window-report", str(wp), "--ui-observation", str(up),
                    "--module-snapshot", str(mp),
                    "--output", str(root / "forged.json")]), 2)
            self.assertFalse((root / "forged.json").exists())


    def test_45_reject_d2_and_p3_double_counting_one_transaction(self):
        case = set_b9(window())
        case["discovery"]["p3_count"] = 1
        # Each individual route fits the total, but their sum does not.
        with self.assertRaises(ValueError):
            triage.triage(case, ui(), operator_pair_confirmed=True)

    def test_46_reject_overlapping_known_and_unknown_d2_transport(self):
        case = set_b9(window())
        entry = case["discovery"]["d2"]["0x50"]["B9FB"]
        entry["unknown_protocol_or_baud"] = 1
        with self.assertRaises(ValueError):
            triage.triage(case, ui())

    def test_47_reject_d2_service_status_not_present_in_global_summary(self):
        case = set_b9(window())
        case["discovery"]["statuses"] = {"unverified": 1}
        with self.assertRaises(ValueError):
            triage.triage(case, ui())

    def test_48_reject_aggregate_d2_status_inflation_across_targets(self):
        case = set_b9(window())
        case["discovery"]["d2"]["0x40"]["A3"] = copy.deepcopy(
            case["discovery"]["d2"]["0x50"]["B9FB"])
        case["discovery"]["transactions"] = 2
        case["discovery"]["statuses"] = {"no_fixture": 1, "unverified": 1}
        with self.assertRaises(ValueError):
            triage.triage(case, ui())

    def test_49_reject_two_backend_probes_claiming_one_tx(self):
        case = window()
        case["backend"]["requests"] = 1
        case["backend"]["statuses"] = {"delivered": 1}
        for probe in ("D2_40_B9FB", "D2_50_B9FB"):
            case["backend"]["d2_probe_coverage"][probe] = {
                "requests": 1, "statuses": {"delivered": 1}}
        with self.assertRaises(ValueError):
            triage.triage(case, ui())

    def test_50_reject_backend_probe_status_not_in_total(self):
        case = window()
        case["backend"]["requests"] = 1
        case["backend"]["statuses"] = {"no_fixture": 1}
        case["backend"]["d2_probe_coverage"]["D2_50_B9FB"] = {
            "requests": 1, "statuses": {"delivered": 1}}
        with self.assertRaises(ValueError):
            triage.triage(case, ui())

    def test_51_valid_mixed_d2_p3_and_unattributed_probes_stay_unverified(self):
        case = set_b9(window(), rx=True)
        case["discovery"]["transactions"] = 3
        case["discovery"]["p3_count"] = 1
        case["discovery"]["statuses"] = {"delivered": 1, "unverified": 2}
        case["backend"]["requests"] = 3
        case["backend"]["statuses"] = {
            "no_fixture": 1, "unsupported": 1, "unverified": 1}
        case["backend"]["d2_probe_coverage"]["D2_50_B9FB"] = {
            "requests": 1, "statuses": {"no_fixture": 1}}
        case["backend"]["d2_probe_coverage"]["D2_40_A3"] = {
            "requests": 1, "statuses": {"unsupported": 1}}
        case["windows"]["j2534"].update({
            "complete_lines": 10, "new_bytes": 1024})
        case["windows"]["backend"].update({
            "complete_lines": 10, "new_bytes": 1024})
        result = triage.triage(case, ui(), operator_pair_confirmed=True)
        self.assertEqual(result["b9fb_request_count_in_window"], 1)
        self.assertEqual(result["first_next_gate"],
                         "review_client_vin_failure_after_unlinked_rx")
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")
        self.assertFalse(result["oem_vin_and_ecu_verified"])

    def test_52_cli_rejects_contradiction_without_leaking_private_input(self):
        with tempfile.TemporaryDirectory() as td:
            private = Path(td)
            win = private / "private-window.json"
            gui_path = private / "private-gui.json"
            output = private / "redacted-output.json"
            case = set_b9(window())
            case["discovery"]["p3_count"] = 1
            win.write_text(json.dumps(case), encoding="utf-8")
            gui_path.write_text(json.dumps(ui()), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = triage.main([
                    "--window-report", str(win),
                    "--ui-observation", str(gui_path),
                    "--output", str(output),
                    "--operator-same-run-confirmed",
                ])
            self.assertEqual(result, 2)
            self.assertFalse(output.exists())
            self.assertNotIn(str(private), stderr.getvalue())
            self.assertNotIn("VIN", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
