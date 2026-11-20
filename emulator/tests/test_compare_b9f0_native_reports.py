"""Eight synthetic comparison checks; no original client, CAN trace or ECU dump."""
import contextlib
from copy import deepcopy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import compare_b9f0_native_reports as tool
sys.path.pop(0)


def sample(paired=2, *, protocol_mismatch=0, observer=0, rows=100):
    tags = paired + protocol_mismatch + observer
    categories = {}
    if paired:
        categories["paired_strict_native_rx_tag"] = paired
    if protocol_mismatch:
        categories["mismatch_protocol_not_can"] = protocol_mismatch
    if observer:
        categories["unpaired_intervening_hardware_observer"] = observer
    return {
        "schema_version": tool.SCHEMA,
        "complete_source_scan": True,
        "source_scan_counts": {
            "source_rows_scanned": rows,
            "tag_rows": tags,
            "oversized_rows_ignored": 0,
        },
        "native_d2_delivery_tags": {
            "source": "local_emulator_native_d2_delivery_tags_only",
            "observed": bool(tags),
            "tag_records": tags,
            "paired_tag_records": paired,
            "unpaired_tag_records": observer,
            "malformed_tag_records": 0,
            "route_or_metadata_mismatch": protocol_mismatch,
            "generation_groups": paired,
            "groups_with_frame_indices_1_to_n": paired,
            "groups_with_missing_duplicate_or_out_of_order_indices": 0,
            "b9fb_13frame_control_sequence_groups": 0,
            "b9f0_emitter_rx_groups": [],
            "b9f0_emitter_rx_groups_with_positive_first_echo": 0,
            "b9f0_emitter_rx_groups_with_contiguous_terminal": 0,
            "physical_can_or_ecu_provenance": "not_verified",
            "client_vin_and_ecu_acceptance": "not_verified",
            "replay_approved": False,
            "b9f0_replay_stage_correlated_to_rx": False,
            "b9f0_original_client_ecu_identity_accepted": False,
        },
        "tag_adjacency_diagnostics": {
            "scope": "categorical_same_pid_native_rx_adjacency_only",
            "categories": categories,
            "total_tag_records_classified": tags,
            "category_totals_agree_with_legacy_auditor": True,
            "missing_rx_context_predecessor_categories": {},
            "missing_rx_context_predecessor_counts_reconcile": True,
            "non_CAN_protocol_categories": {"other_non_CAN": protocol_mismatch} if protocol_mismatch else {},
            "non_CAN_protocol_counts_reconcile": True,
            "non_CAN_other_protocol_values": {"other_protocol_value": protocol_mismatch} if protocol_mismatch else {},
            "non_CAN_other_values_reconcile": True,
            "non_CAN_wide_protocol_shapes": {"other_32bit_value": protocol_mismatch} if protocol_mismatch else {},
            "non_CAN_wide_protocol_shapes_reconcile": True,
            "no_prior_rx_previous_event_classes": {},
            "no_prior_rx_previous_events_reconcile": True,
            "observer_only_bridge_candidates_started": observer,
            "observer_only_bridge_outcomes": {"native_shape_consistent_only": observer} if observer else {},
            "observer_only_bridge_incomplete_at_scan_end": 0,
            "observer_only_bridge_counts_reconcile": True,
            "observer_only_bridge_is_strict_delivery_evidence": False,
            "b9f0_specific_causal_attribution_verified": False,
        },
        "real_ecu_response_verified": False,
        "sectorv_ecu_identity_accepted_verified": False,
    }


class BeforeAfterTests(unittest.TestCase):
    def test_01_same_reports_do_not_claim_verified_acceptance(self):
        r = tool.compare(sample(), sample())
        self.assertTrue(r["report_inputs_validated"])
        self.assertTrue(r["sample_sizes_equal"])
        self.assertEqual(r["metric_differences"]["strict_paired"]["delta"], 0)
        for k in ("same_diagnostic_workload_verified",
                  "logger_fix_causal_effect_verified",
                  "original_vida_or_sectorv_vin_accepted_verified",
                  "b9f0_ecu_identity_accepted_verified"):
            self.assertIs(r[k], False)

    def test_02_wide_protocol_reduction_is_only_observation(self):
        result = tool.compare(sample(paired=2, protocol_mismatch=2),
                              sample(paired=4))
        wide = result["metric_differences"]["wide_protocol_value"]
        self.assertEqual((wide["before"], wide["after"], wide["delta"]), (2, 0, -2))
        self.assertEqual(wide["before_per_1000_d2_tags"], 500.0)
        self.assertFalse(result["logger_fix_causal_effect_verified"])

    def test_03_empty_before_no_divide_by_zero_and_no_false_green(self):
        result = tool.compare(sample(paired=0, rows=1), sample(paired=4))
        self.assertTrue(result["insufficient_tag_evidence"])
        self.assertIsNone(result["metric_differences"]["strict_paired"]
                          ["before_per_1000_d2_tags"])
        self.assertFalse(result["physical_can_ecu_provenance_verified"])

    def test_04_different_workload_gets_a_denominator_not_causal_label(self):
        result = tool.compare(sample(paired=2, rows=100), sample(paired=4, rows=200))
        paired = result["metric_differences"]["strict_paired"]
        self.assertEqual(paired["delta"], 2)
        self.assertEqual(paired["before_per_1000_d2_tags"], 1000)
        self.assertEqual(paired["after_per_1000_d2_tags"], 1000)
        self.assertFalse(result["sample_sizes_equal"])
        self.assertFalse(result["same_diagnostic_workload_verified"])

    def test_05_reject_old_schema_and_unverified_claim_promotions(self):
        for path, value in (
            (("schema_version",), "old-schema"),
            (("complete_source_scan",), False),
            (("sectorv_ecu_identity_accepted_verified",), True),
            (("tag_adjacency_diagnostics", "observer_only_bridge_is_strict_delivery_evidence"), True),
        ):
            with self.subTest(path=path):
                bad = sample()
                parent = bad
                for key in path[:-1]:
                    parent = parent[key]
                parent[path[-1]] = value
                with self.assertRaises(tool.CompareError):
                    tool.compare(bad, sample())

    def test_06_reject_inconsistent_counts_unknown_categories_and_bool_as_int(self):
        for mutate in (
            lambda d: d["source_scan_counts"].update(tag_rows=5),
            lambda d: d["tag_adjacency_diagnostics"]["categories"].update(vin_private=4),
            lambda d: d["native_d2_delivery_tags"].update(paired_tag_records=True),
            lambda d: d["native_d2_delivery_tags"].update(b9f0_emitter_rx_groups=[{"target": "secret", "baud_bps": 500000, "delivery_shape": "partial_or_ambiguous", "count": 1}]),
            lambda d: d["tag_adjacency_diagnostics"].update(observer_only_bridge_candidates_started=5),
        ):
            with self.subTest(mutate=repr(mutate)):
                bad = sample()
                mutate(bad)
                with self.assertRaises(tool.CompareError):
                    tool.compare(sample(), bad)

    def test_07_observer_shape_only_and_untrusted_keys_never_exported(self):
        private = "YV1PRIVATE17BYTES"
        left = sample(paired=1, observer=1)
        right = sample(paired=2)
        left["raw_private_record"] = "[PID=DEADBEEF] " + private
        left["source_scan_counts"]["private_source_path"] = "C:/" + private
        output = json.dumps(tool.compare(left, right))
        for secret in (private, "DEADBEEF", "raw_private_record", "private_source_path"):
            self.assertNotIn(secret, output)
        self.assertIn('"observer_only_shape_consistent"', output)
        self.assertFalse(json.loads(output)["b9f0_ecu_identity_accepted_verified"])

    def test_08_cli_duplicate_json_symlink_and_output_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            before = Path(tmp) / "private-before.json"
            after = Path(tmp) / "private-after.json"
            before.write_text(json.dumps(sample()), encoding="utf-8")
            after.write_text(json.dumps(sample()), encoding="utf-8")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(tool.main(["--before-report", str(before),
                                            "--after-report", str(after)]), 0)
            self.assertNotIn(tmp, out.getvalue())
            self.assertNotIn("private-before", out.getvalue())
            after.write_text('{"schema_version":1,"schema_version":2}', encoding="utf-8")
            with self.assertRaises(tool.CompareError):
                tool.read_report(after)
            after.write_text(json.dumps(sample()), encoding="utf-8")
            link = Path(tmp) / "link.json"
            try:
                link.symlink_to(after)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(tool.CompareError):
                    tool.read_report(link)
            after.write_text("x" * (tool.MAX_INPUT_BYTES + 1), encoding="utf-8")
            with self.assertRaises(tool.CompareError):
                tool.read_report(after)


if __name__ == "__main__":
    unittest.main()
