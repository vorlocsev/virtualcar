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



if __name__ == "__main__":
    unittest.main()
