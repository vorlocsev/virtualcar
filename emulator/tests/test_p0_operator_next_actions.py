"""Synthetic, fixed-vocabulary next diagnostics after SectorV P0 GUI triage.

No client is launched, J2534 loaded, CAN sent, raw logs published, VIN accepted.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_audit_sectorv_ui_window_triage import (
    triage, window, ui, set_b9, module_snapshot,
)


def render(report, gui=None, paired=True):
    return triage.triage(
        report, ui() if gui is None else gui,
        operator_pair_confirmed=paired,
    )


def no_rx_b9(cem40, cem50):
    report = window()
    discovery = report["discovery"]
    for target, statuses in (("0x40", cem40), ("0x50", cem50)):
        probe = discovery["d2"][target]["B9FB"]
        probe["statuses"] = statuses
        probe["requests"] = probe["rx_frame_buckets"]["zero"] = sum(statuses.values())
        discovery["transactions"] += probe["requests"]
        for status, count in statuses.items():
            summary = discovery["statuses"]
            summary[status] = summary.get(status, 0) + count
    return report


class OperatorNextActionTests(unittest.TestCase):
    def test_01_fixed_gate_vocabulary_has_one_safe_action_each(self):
        self.assertEqual(set(triage.NEXT_ACTION_RU), triage.GATES)
        self.assertEqual(len(triage.NEXT_ACTION_RU), 15)
        for gate, action in triage.NEXT_ACTION_RU.items():
            with self.subTest(gate=gate):
                self.assertIs(type(action), str)
                self.assertTrue(45 <= len(action) <= 430)
                self.assertNotIn("\n", action)
                self.assertNotIn("\r", action)
                self.assertNotIn("<", action)
                self.assertNotIn(">", action)
                self.assertNotIn("YV1CZ0002A0000001", action)
                self.assertNotIn("DEADBEEF", action)

    def test_02_no_operator_pairing_must_request_new_same_run_evidence(self):
        result = render(window(), paired=False)
        self.assertEqual(result["first_next_gate"],
                         "establish_isolated_same_run_evidence")
        self.assertIn("Begin", result["first_next_action_ru"])
        self.assertIn("Finish", result["first_next_action_ru"])
        self.assertEqual(result["client_vehicle_identity_accepted"], "not_verified")

    def test_03_provider_change_or_missing_evidence_get_distinct_actions(self):
        for status, gate in (
            ("changed_between_endpoints", "resolve_provider_endpoint_change"),
            ("provider_state_changed", "resolve_provider_endpoint_change"),
            ("not_verified", "obtain_provider_endpoint_evidence"),
        ):
            with self.subTest(status=status):
                result = render(window(provider=status))
                self.assertEqual(result["first_next_gate"], gate)
                self.assertEqual(result["first_next_action_ru"],
                                 triage.NEXT_ACTION_RU[gate])
                self.assertFalse(result["oem_vin_and_ecu_verified"])

    def test_04_failed_or_unattempted_connect_has_adapter_check(self):
        for connection, error in (("failed", "connect_error"),
                                  ("unknown", "unknown"),
                                  ("not_attempted", "unknown")):
            with self.subTest(connection=connection):
                gui = ui(identity="unknown", ecus="not_opened",
                         error=error, connection=connection)
                result = render(window(), gui)
                self.assertEqual(result["first_next_gate"],
                                 "verify_j2534_provider_and_connect")
                self.assertIn("SectorV", result["first_next_action_ru"])

    def test_05_absent_boundary_discard_and_missing_rx_have_separate_actions(self):
        cases = (
            (window(), "review_absent_b9fb_in_bounded_j2534_window"),
            (no_rx_b9({}, {"unverified": 1}), "review_b9fb_without_observed_rx"),
        )
        for report, gate in cases:
            with self.subTest(gate=gate):
                result = render(report)
                self.assertEqual(result["first_next_gate"], gate)
                self.assertEqual(result["first_next_action_ru"],
                                 triage.NEXT_ACTION_RU[gate])
        cropped = window()
        cropped["windows"]["j2534"]["dropped_last"] = True
        self.assertEqual(render(cropped)["first_next_gate"],
                         "review_discarded_j2534_line_boundaries")

    def test_06_vin_failure_and_displayed_identity_stay_unverified(self):
        cases = (
            (set_b9(window(), rx=True), ui(),
             "review_client_vin_failure_after_unlinked_rx"),
            (window(), ui(identity="displayed", ecus="empty", error="none"),
             "review_ecu_identification_after_ui_identity"),
            (window(), ui(identity="displayed", ecus="populated", error="none"),
             "review_identity_display_without_oem_validation"),
        )
        for report, gui, gate in cases:
            with self.subTest(gate=gate):
                result = render(report, gui)
                self.assertEqual(result["first_next_gate"], gate)
                self.assertEqual(result["first_next_action_ru"],
                                 triage.NEXT_ACTION_RU[gate])
                self.assertFalse(result["oem_vin_and_ecu_verified"])
                self.assertFalse(result["replay_approved"])
                self.assertEqual(result["client_vehicle_identity_accepted"],
                                 "not_verified")

    def test_07_no_dynamic_private_data_or_unsupported_guarantees(self):
        private_token = "YV1CZ0002A0000001"
        report = set_b9(window(), rx=True)
        report["note"] = "Private reference " + private_token
        output = render(report)
        serialized = json.dumps(output, ensure_ascii=False)
        self.assertNotIn(private_token, serialized)
        self.assertNotIn("DEADBEEF", serialized)
        self.assertEqual(output["first_next_action_ru"],
                         triage.NEXT_ACTION_RU[output["first_next_gate"]])
        self.assertEqual(output["transaction_level_correlation"],
                         "not_established")
        self.assertFalse(output["same_guest_independently_attested"])

    def test_08_all_b9fb_no_fixture_points_to_active_profile(self):
        result = render(no_rx_b9({"no_fixture": 2}, {"no_fixture": 1}))
        self.assertEqual(result["first_next_gate"], "review_missing_b9fb_fixture")
        self.assertIn("активный профиль", result["first_next_action_ru"])

    def test_09_all_b9fb_rejected_by_route_points_to_can_channel_and_rate(self):
        result = render(no_rx_b9({}, {"unsupported": 2}))
        self.assertEqual(result["first_next_gate"], "review_rejected_b9fb_route")
        self.assertIn("CAN-канал и скорость", result["first_next_action_ru"])

    def test_10_mixed_terminal_markers_retain_both_actions(self):
        report = no_rx_b9({"no_fixture": 5}, {"no_fixture": 5, "unsupported": 1})
        report["discovery"]["d2"]["0x50"]["B9FB"]["known_can_500k"] = 5
        result = render(report)
        self.assertEqual(result["b9fb_request_count_in_window"], 11)
        self.assertEqual(result["first_next_gate"],
                         "review_missing_b9fb_fixture_and_rejected_route")
        self.assertIn("фикстуры", result["first_next_action_ru"])
        self.assertIn("маршрутизации", result["first_next_action_ru"])
        self.assertEqual(result["transaction_level_correlation"], "not_established")
        self.assertFalse(result["replay_approved"])

    def test_11_incomplete_terminal_coverage_keeps_generic_review(self):
        for status in ("unverified", "timeout", "partial_rx"):
            with self.subTest(status=status):
                result = render(no_rx_b9({"no_fixture": 1}, {"unsupported": 1, status: 1}))
                self.assertEqual(result["first_next_gate"], "review_b9fb_without_observed_rx")

    def test_12_matching_backend_counts_cannot_supply_j2534_terminals(self):
        report = no_rx_b9({"no_fixture": 1}, {"unverified": 1})
        backend = report["backend"]
        backend["requests"] = 2
        backend["statuses"] = {"no_fixture": 1, "unsupported": 1}
        for target, status in (("40", "no_fixture"), ("50", "unsupported")):
            backend["d2_probe_coverage"][f"D2_{target}_B9FB"] = {
                "requests": 1, "statuses": {status: 1},
            }
        result = render(report)
        self.assertEqual(result["first_next_gate"], "review_b9fb_without_observed_rx")
        self.assertEqual(result["transaction_level_correlation"], "not_established")

    def test_13_rx_and_partial_boundaries_keep_conservative_actions(self):
        report = no_rx_b9({"no_fixture": 1}, {"delivered": 1})
        buckets = report["discovery"]["d2"]["0x50"]["B9FB"]["rx_frame_buckets"]
        buckets["zero"], buckets["thirteen"] = 0, 1
        self.assertEqual(render(report)["first_next_gate"],
                         "review_client_vin_failure_after_unlinked_rx")
        for boundary in ("dropped_first", "dropped_last"):
            with self.subTest(boundary=boundary):
                report = no_rx_b9({}, {"no_fixture": 1})
                report["windows"]["j2534"][boundary] = True
                self.assertEqual(render(report)["first_next_gate"],
                                 "review_b9fb_without_observed_rx")

    def test_14_provenance_precedence_and_module_action_stay_separate(self):
        report = no_rx_b9({}, {"no_fixture": 1})
        self.assertEqual(render(report, paired=False)["first_next_gate"],
                         "establish_isolated_same_run_evidence")
        result = triage.triage(
            report, ui(), operator_pair_confirmed=True,
            module_snapshot=module_snapshot(comparison="different_bytes_at_snapshot"),
        )
        self.assertEqual(result["first_next_gate"], "review_missing_b9fb_fixture")
        self.assertEqual(result["operator_module_snapshot"]["next_safe_gate"],
                         "resolve_reference_vs_registered_dll_difference")
        report["registered_provider"]["binary_endpoint_consistency"] = "changed_between_endpoints"
        self.assertEqual(render(report)["first_next_gate"], "resolve_provider_endpoint_change")


if __name__ == "__main__":
    unittest.main()
