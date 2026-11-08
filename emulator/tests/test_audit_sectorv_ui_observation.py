"""Eight offline synthetic tests for the isolated SectorV human GUI observation gate."""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_sectorv_ui_observation import SCHEMA, audit, main


def example():
    return {
        "schema_version": SCHEMA,
        "client": "SectorV",
        "scenario": "P2_MY2009_lab",
        "source": "human_ui_observation",
        "run_scope": "single_vm_client_run",
        "read_only": True,
        "physical_adapter_disconnected": True,
        "observations": {
            "adapter_listed": "yes",
            "adapter_selected": "yes",
            "connection": "connected",
            "ecu_list": "empty",
            "vehicle_identity": "not_displayed",
            "error_category": "vehicle_unrecognized"
        }
    }


class SectorVUiObservationTests(unittest.TestCase):
    def test_01_connected_but_no_identity_never_becomes_verified(self):
        result = audit(example())
        self.assertTrue(result["connection_displayed_in_gui"])
        self.assertFalse(result["vehicle_identity_displayed_in_gui"])
        self.assertFalse(result["ecu_list_populated_in_gui"])
        self.assertEqual(result["first_next_gate"], "review_same_run_b9fb_delivery_and_verified_fixture")
        self.assertEqual(result["client_acceptance_e2e"], "not_verified")
        self.assertFalse(result["replay_approved"])

    def test_02_positive_gui_still_needs_independent_provenance(self):
        case = example()
        case["observations"].update({
            "ecu_list": "populated", "vehicle_identity": "displayed", "error_category": "none"
        })
        report = audit(case)
        self.assertTrue(report["vehicle_identity_displayed_in_gui"])
        self.assertTrue(report["ecu_list_populated_in_gui"])
        self.assertEqual(report["first_next_gate"],
                         "independently_validate_displayed_identity_and_ecu_provenance")
        self.assertEqual(report["vehicle_identity_validated_against_xc90_my2009"],
                         "not_verified")
        self.assertEqual(report["j2534_transaction_correlation"], "not_established")

    def test_03_missing_adapter_and_partial_observations_are_distinct(self):
        case = example()
        case["observations"].update({
            "adapter_listed": "no", "adapter_selected": "no",
            "connection": "not_attempted", "ecu_list": "not_opened",
            "vehicle_identity": "unknown", "error_category": "adapter_missing"
        })
        report = audit(case)
        self.assertEqual(report["first_next_gate"],
                         "review_adapter_registration_and_client_provider_list")
        case["observations"].update({
            "adapter_listed": "unknown", "adapter_selected": "unknown",
            "error_category": "unknown"
        })
        self.assertEqual(audit(case)["first_next_gate"],
                         "confirm_explicit_canonical_adapter_selection")

    def test_04_connection_failure_and_no_attempt_priorities(self):
        case = example()
        case["observations"].update({
            "connection": "failed", "ecu_list": "not_opened",
            "vehicle_identity": "unknown", "error_category": "connect_error"
        })
        self.assertEqual(audit(case)["first_next_gate"],
                         "review_same_run_j2534_connect_status")
        case["observations"].update({
            "connection": "not_attempted", "error_category": "unknown"
        })
        self.assertEqual(audit(case)["first_next_gate"], "observe_client_connect_state")

    def test_05_private_payloads_and_free_text_are_rejected(self):
        for field, value in [
            ("vin", "YV1CZ0002A0000001"),
            ("message", "error text from screenshot"),
            ("trace", "0x50 B9FB 57 00 30"),
            ("client_path", "C:/private/sectorv.exe"),
        ]:
            case = example()
            case["observations"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                audit(case)
        case = example()
        case["debug"] = {"private_path": "C:/Users/private"}
        with self.assertRaises(ValueError):
            audit(case)
        case = example()
        case["observations"]["error_category"] = "VIN is 123"
        with self.assertRaises(ValueError):
            audit(case)

    def test_06_reject_contradictory_gui_states(self):
        for changes in [
            {"adapter_listed": "no", "adapter_selected": "yes"},
            {"adapter_selected": "no", "connection": "connected"},
            {"connection": "failed", "ecu_list": "populated"},
            {"connection": "not_attempted", "vehicle_identity": "displayed"},
            {"adapter_listed": "yes", "error_category": "adapter_missing"},
            {"connection": "connected", "error_category": "connect_error"},
            {"connection": "failed", "error_category": "none"},
        ]:
            case = example()
            case["observations"].update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                audit(case)

    def test_07_enforce_single_run_no_hardware_no_writes(self):
        for key, value in [
            ("client", "VDASH"),
            ("source", "j2534_inferred"),
            ("run_scope", "combined_historical_logs"),
            ("read_only", False),
            ("physical_adapter_disconnected", False),
            ("physical_adapter_disconnected", 1),
            ("scenario", "real-vin"),
        ]:
            case = example()
            case[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                audit(case)

    def test_08_cli_exclusive_redaction_and_input_ceiling(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "local-sensitive-input.json"
            dst = Path(td) / "public-summary.json"
            src.write_text(json.dumps(example()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(src), "--output", str(dst)])
            report_text = dst.read_text(encoding="utf-8")
            report = json.loads(report_text)
            self.assertEqual(report["client"], "SectorV")
            for secret in ("YV1CZ0002A0000001", "local-sensitive-input",
                           "sectorv.exe", "0x50 B9FB"):
                self.assertNotIn(secret, report_text)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(src), "--output", str(dst)])
            self.assertEqual(json.loads(dst.read_text(encoding="utf-8")), report)
            src.write_bytes(b"x" * 8193)
            other = Path(td) / "other.json"
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(src), "--output", str(other)])
            self.assertFalse(other.exists())


if __name__ == "__main__":
    unittest.main()
