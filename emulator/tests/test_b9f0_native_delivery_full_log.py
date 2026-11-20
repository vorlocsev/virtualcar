"""Synthetic tests: native B9F0 delivery is not OEM/VIDA ECU acceptance."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_b9f0_native_delivery as audit
sys.path.pop(0)

HOST = "[PID=ABCD1234 PrivateDiagnosticClient.exe] "


def be(*values):
    return b"".join(v.to_bytes(4, "big") for v in values)


def event(label, data=b""):
    return HOST + label + (" " + data.hex(" ").upper() if data else "") + "\n"


def frames(target=0x40):
    return [
        bytes((0x8F, target, 0xF9, 0xF0, 0x00, 0x08, 0x68, 0x85)),
        bytes((0x09, 0x13, 0x20, 0x20, 0x41, 0x30, 0x65, 0x70)),
        bytes((0x4C, 0x24, 0x20, 0x20, 0x41, 0x00, 0x00, 0x00)),
    ]


def delivered(payloads, baud=125000, channel=1, generation=1):
    out = []
    for frame, payload in enumerate(payloads, 1):
        out.extend([
            event("RX context channel/protocol/status/baud/time-us (BE)",
                  be(channel, 5, 0, baud, 102000)),
            event("PassThruReadMsgs -> delivered",
                  be(0x00800003) + payload),
            event("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
                  be(channel, generation, frame, 102000, 104000)),
        ])
    return out


class B9F0NativeRxTests(unittest.TestCase):
    def test_01_three_tagged_frames_are_emitter_delivery_shape_only(self):
        r = audit.analyze_source(delivered(frames()))
        n = r["native_d2_delivery_tags"]
        self.assertEqual(n["b9f0_emitter_rx_groups_with_positive_first_echo"], 1)
        self.assertEqual(n["b9f0_emitter_rx_groups_with_contiguous_terminal"], 1)
        self.assertEqual((n["b9f0_emitter_rx_groups"][0]["target"],
                          n["b9f0_emitter_rx_groups"][0]["baud_bps"]), ("0x40", 125000))
        self.assertFalse(r["sectorv_ecu_identity_accepted_verified"])

    def test_02_missing_terminal_is_partial(self):
        n = audit.analyze_source(delivered(frames()[:2]))["native_d2_delivery_tags"]
        self.assertEqual(n["b9f0_emitter_rx_groups_with_contiguous_terminal"], 0)
        self.assertEqual(n["b9f0_emitter_rx_groups"][0]["delivery_shape"],
                         "partial_or_ambiguous")

    def test_03_wrong_service_echo_is_excluded(self):
        src = frames()
        src[0] = bytes((0x8F, 0x40, 0xF9, 0xFB, 0, 0, 0, 0))
        n = audit.analyze_source(delivered(src))["native_d2_delivery_tags"]
        self.assertEqual(n["b9f0_emitter_rx_groups_with_positive_first_echo"], 0)

    def test_04_missing_tag_does_not_prove_complete(self):
        src = delivered(frames())
        src.pop()
        n = audit.analyze_source(src)["native_d2_delivery_tags"]
        self.assertEqual(n["b9f0_emitter_rx_groups_with_contiguous_terminal"], 0)

    def test_05_full_cli_over_old_20k_transaction_cap(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "PRIVATE_NATIVE.log"
            with src.open("w", encoding="utf-8") as writer:
                writer.write("unrelated private event\n" * 20001)
                writer.writelines(delivered(frames()))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(audit.main(["--native", str(src)]), 0)
            report = json.loads(output.getvalue())
            self.assertEqual(report["source_scan_counts"]["source_rows_scanned"], 20010)
            self.assertEqual(report["native_d2_delivery_tags"][
                "b9f0_emitter_rx_groups_with_contiguous_terminal"], 1)
            self.assertNotIn("ABCD1234", output.getvalue())
            self.assertNotIn(str(src), output.getvalue())

    def test_06_oversized_file_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            src = Path(temp) / "PRIVATE_NATIVE.log"
            src.write_text("hello", encoding="utf-8")
            with patch.object(audit, "MAX_SOURCE_BYTES", 1):
                with self.assertRaises(SystemExit) as ctx:
                    audit.main(["--native", str(src)])
            self.assertEqual(ctx.exception.code, 2)


    def test_09_categorical_diagnostics_match_native_tag_totals(self):
        r = audit.analyze_source(delivered(frames()))
        d = r["tag_adjacency_diagnostics"]
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])
        self.assertEqual(d["categories"]["paired_strict_native_rx_tag"], 3)
        self.assertEqual(d["total_tag_records_classified"], 3)
        self.assertFalse(d["b9f0_specific_causal_attribution_verified"])

    def test_10_known_hw_rx_observer_between_delivery_and_tag(self):
        items = delivered(frames()[:1])
        items.insert(2, event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"))
        r = audit.analyze_source(items)
        diag = r["tag_adjacency_diagnostics"]
        self.assertEqual(
            diag["categories"]["unpaired_intervening_hardware_observer"], 1)
        self.assertEqual(r["native_d2_delivery_tags"]["unpaired_tag_records"], 1)
        self.assertTrue(diag["category_totals_agree_with_legacy_auditor"])

    def test_11_delivery_without_context_is_not_paired(self):
        r = audit.analyze_source(delivered(frames()[:1])[1:])
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(
            d["categories"]["unpaired_delivery_without_valid_rx_context"], 1)
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_12_short_raw_rx_is_not_complete_delivery(self):
        items = delivered(frames()[:1])
        items[1] = event("PassThruReadMsgs -> delivered", bytes(11))
        r = audit.analyze_source(items)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(
            d["categories"]["unpaired_nonclassic_or_invalid_rx_record"], 1)
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_13_protocol_mismatch_and_privacy(self):
        items = delivered(frames()[:1])
        items[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                         be(1, 6, 0, 125000, 102000))
        r = audit.analyze_source(items)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["categories"]["mismatch_protocol_not_can"], 1)
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])
        contents = json.dumps(r)
        self.assertNotIn("ABCD1234", contents)
        self.assertNotIn("PrivateDiagnosticClient", contents)

    def test_14_other_pid_events_leave_same_pid_adjacency(self):
        items = delivered(frames()[:1])
        items.insert(2, "[PID=0BADF00D Other.exe] unrelated event\n")
        d = audit.analyze_source(items)["tag_adjacency_diagnostics"]
        self.assertEqual(d["categories"]["paired_strict_native_rx_tag"], 1)
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])


    def test_15_missing_context_from_no_prior_rx_is_categorized(self):
        r = audit.analyze_source(delivered(frames()[:1])[1:])
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(
            d["missing_rx_context_predecessor_categories"]["unpaired_no_prior_rx"], 1)
        self.assertTrue(d["missing_rx_context_predecessor_counts_reconcile"])
        self.assertTrue(d["non_CAN_protocol_counts_reconcile"])

    def test_16_missing_context_due_to_malformed_context_is_categorized(self):
        items = delivered(frames()[:1])
        items[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                         be(1, 5, 0, 125000))
        d = audit.analyze_source(items)["tag_adjacency_diagnostics"]
        self.assertEqual(
            d["missing_rx_context_predecessor_categories"]["unpaired_invalid_rx_context"], 1)
        self.assertTrue(d["missing_rx_context_predecessor_counts_reconcile"])

    def test_17_missing_context_due_to_intervening_same_pid(self):
        items = delivered(frames()[:1])
        items.insert(1, event("J2534 unrelated local native event"))
        d = audit.analyze_source(items)["tag_adjacency_diagnostics"]
        self.assertEqual(
            d["missing_rx_context_predecessor_categories"][
                "unpaired_intervening_j2534_event"], 1)
        self.assertTrue(d["missing_rx_context_predecessor_counts_reconcile"])

    def test_18_protocol_6_is_counted_separately_without_promoting_d2(self):
        items = delivered(frames()[:1])
        items[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                         be(1, 6, 0, 125000, 102000))
        d = audit.analyze_source(items)["tag_adjacency_diagnostics"]
        self.assertEqual(d["non_CAN_protocol_categories"]["ISO15765_6"], 1)
        self.assertTrue(d["non_CAN_protocol_counts_reconcile"])
        self.assertFalse(d["b9f0_specific_causal_attribution_verified"])

    def test_19_other_pid_between_context_and_delivery_does_not_break(self):
        items = delivered(frames()[:1])
        items.insert(1, "[PID=0BADF00D External.exe] unrelated record\n")
        d = audit.analyze_source(items)["tag_adjacency_diagnostics"]
        self.assertEqual(d["categories"]["paired_strict_native_rx_tag"], 1)
        self.assertEqual(d["missing_rx_context_predecessor_categories"], {})
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])


    def test_20_no_prior_rx_last_event_class_is_bounded(self):
        rows = delivered(frames()[:1])[1:]
        r = audit.analyze_source(rows)
        diag = r["tag_adjacency_diagnostics"]
        self.assertEqual(
            diag["no_prior_rx_previous_event_classes"]["none"], 1)
        self.assertTrue(diag["no_prior_rx_previous_events_reconcile"])
        self.assertNotIn("ABCD1234", json.dumps(r))

    def test_21_no_prior_rx_from_previous_same_pid_d2_tag(self):
        rows = [event("P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
                      be(1, 7, 1, 102000, 104000))]
        rows += delivered(frames()[:1])[1:]
        diag = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(
            diag["no_prior_rx_previous_event_classes"]["d2_delivery_tag"], 1)
        self.assertTrue(diag["no_prior_rx_previous_events_reconcile"])

    def test_22_unrecognized_protocol_zero_is_not_iso15765(self):
        rows = delivered(frames()[:1])
        rows[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                        be(1, 0, 0, 125000, 102000))
        diag = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(diag["non_CAN_other_protocol_values"]["protocol_0"], 1)
        self.assertEqual(diag["non_CAN_protocol_categories"]["other_non_CAN"], 1)
        self.assertTrue(diag["non_CAN_other_values_reconcile"])

    def test_23_unknown_wide_protocol_buckets_safely(self):
        rows = delivered(frames()[:1])
        rows[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                        be(1, 0xF123ABCD, 0, 125000, 102000))
        r = audit.analyze_source(rows)
        diag = r["tag_adjacency_diagnostics"]
        self.assertEqual(diag["non_CAN_other_protocol_values"]["other_protocol_value"], 1)
        self.assertNotIn("F123ABCD", json.dumps(r))
        self.assertTrue(diag["non_CAN_other_values_reconcile"])


    def test_24_hw_rx_observer_is_bounded_prior_event_not_lost_frame(self):
        rows = [event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED")]
        rows += delivered(frames()[:1])[1:]
        r = audit.analyze_source(rows)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["no_prior_rx_previous_event_classes"],
                         {"hardware_rx_observer": 1})
        self.assertEqual(d["categories"]["unpaired_delivery_without_valid_rx_context"], 1)
        self.assertEqual(r["native_d2_delivery_tags"]["paired_tag_records"], 0)
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_25_hw_tx_observer_is_distinct_from_unclassified_native(self):
        rows = [event("P2_HW_A3_TX")] + delivered(frames()[:1])[1:]
        d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(d["no_prior_rx_previous_event_classes"],
                         {"hardware_other_observer": 1})
        self.assertTrue(d["no_prior_rx_previous_events_reconcile"])

    def test_26_tx_request_predecessors_remain_unpaired(self):
        for label, expected in (
            ("TX context channel/protocol/flags/baud/time-us (BE)", "tx_context"),
            ("TX (app request)", "tx_request"),
        ):
            with self.subTest(label=expected):
                rows = [event(label)] + delivered(frames()[:1])[1:]
                d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
                self.assertEqual(d["no_prior_rx_previous_event_classes"],
                                 {expected: 1})
                self.assertEqual(d["categories"]
                                 ["unpaired_delivery_without_valid_rx_context"], 1)

    def test_27_periodic_context_predecessor(self):
        rows = [event("Periodic TX context channel/protocol/flags/baud/time-us (BE)")]
        rows += delivered(frames()[:1])[1:]
        d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(d["no_prior_rx_previous_event_classes"],
                         {"periodic_tx_context": 1})
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_28_clear_rx_context_predecessor(self):
        rows = [event("CLEAR_RX context channel/protocol/flags/baud/time-us (BE)")]
        rows += delivered(frames()[:1])[1:]
        d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(d["no_prior_rx_previous_event_classes"],
                         {"clear_rx_context": 1})
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_29_byte_swapped_protocol_shape_is_not_CAN_success(self):
        rows = delivered(frames()[:1])
        rows[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                        be(1, 0x05000000, 0, 125000, 102000))
        r = audit.analyze_source(rows)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["non_CAN_other_protocol_values"],
                         {"other_protocol_value": 1})
        self.assertEqual(d["non_CAN_wide_protocol_shapes"],
                         {"byte_swapped_known_id_shape": 1})
        self.assertTrue(d["non_CAN_wide_protocol_shapes_reconcile"])
        self.assertEqual(r["native_d2_delivery_tags"]["paired_tag_records"], 0)

    def test_30_all_bits_set_protocol_keeps_private_bytes_private(self):
        rows = delivered(frames()[:1])
        rows[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                        be(1, 0xFFFFFFFF, 0, 125000, 102000))
        r = audit.analyze_source(rows)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["non_CAN_wide_protocol_shapes"], {"all_bits_set": 1})
        self.assertNotIn("FFFFFFFF", json.dumps(r))
        self.assertNotIn("ABCD1234", json.dumps(r))
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_31_wide_protocol_shapes_reconcile_without_changing_categories(self):
        rows = []
        for value in (13, 0x12340000, 0x12345678, 0x05000000):
            part = delivered(frames()[:1])
            part[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                            be(1, value, 0, 125000, 102000))
            rows.extend(part)
        r = audit.analyze_source(rows)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["non_CAN_wide_protocol_shapes"], {
            "byte_swapped_known_id_shape": 1,
            "low_word_zero": 1,
            "other_16bit_value": 1,
            "other_32bit_value": 1,
        })
        self.assertEqual(d["non_CAN_other_protocol_values"],
                         {"other_protocol_value": 4})
        self.assertEqual(d["categories"], {"mismatch_protocol_not_can": 4})
        self.assertTrue(d["non_CAN_wide_protocol_shapes_reconcile"])
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])
        self.assertFalse(r["sectorv_ecu_identity_accepted_verified"])


    def test_32_exact_single_hw_rx_observer_bridge_is_shape_only(self):
        rows = delivered(frames()[:1])
        rows.insert(2, event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"))
        r = audit.analyze_source(rows)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["categories"],
                         {"unpaired_intervening_hardware_observer": 1})
        self.assertEqual(r["native_d2_delivery_tags"]["paired_tag_records"], 0)
        self.assertEqual(d["observer_only_bridge_candidates_started"], 1)
        self.assertEqual(d["observer_only_bridge_outcomes"],
                         {"native_shape_consistent_only": 1})
        self.assertFalse(d["observer_only_bridge_is_strict_delivery_evidence"])
        self.assertTrue(d["observer_only_bridge_counts_reconcile"])
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_33_observer_without_valid_rx_delivery_never_bridges(self):
        rows = delivered(frames()[:1])[1:]
        rows.insert(1, event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"))
        d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(d["observer_only_bridge_candidates_started"], 0)
        self.assertEqual(d["observer_only_bridge_outcomes"], {})
        self.assertTrue(d["observer_only_bridge_counts_reconcile"])
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_34_observer_bridge_wrong_channel_is_metadata_mismatch(self):
        rows = delivered(frames()[:1])
        rows.insert(2, event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"))
        rows[-1] = event(
            "P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)",
            be(2, 1, 1, 102000, 104000))
        d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(d["observer_only_bridge_outcomes"],
                         {"metadata_mismatch": 1})
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_35_non_can_protocol_cannot_be_promoted_by_observer(self):
        rows = delivered(frames()[:1])
        rows[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                        be(1, 6, 0, 125000, 102000))
        rows.insert(2, event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"))
        r = audit.analyze_source(rows)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["observer_only_bridge_outcomes"],
                         {"metadata_mismatch": 1})
        self.assertEqual(r["native_d2_delivery_tags"]["paired_tag_records"], 0)
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_36_second_observer_interrupts_first_bridge(self):
        rows = delivered(frames()[:1])
        rows[2:2] = [
            event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"),
            event("P2_HW_RX_DUPLICATE_E3_CANDIDATE")]
        d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(d["observer_only_bridge_outcomes"],
                         {"interrupted_before_tag": 1})
        self.assertEqual(d["observer_only_bridge_candidates_started"], 1)
        self.assertTrue(d["observer_only_bridge_counts_reconcile"])

    def test_37_intervening_same_pid_event_clears_bridge(self):
        rows = delivered(frames()[:1])
        rows[2:2] = [event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"),
                     event("J2534 unrelated local event")]
        d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(d["observer_only_bridge_outcomes"],
                         {"interrupted_before_tag": 1})
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_38_other_pid_event_does_not_interrupt_bridge(self):
        rows = delivered(frames()[:1])
        rows[2:2] = [event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"),
                     "[PID=0BADF00D Other.exe] unrelated event\n"]
        d = audit.analyze_source(rows)["tag_adjacency_diagnostics"]
        self.assertEqual(d["observer_only_bridge_outcomes"],
                         {"native_shape_consistent_only": 1})
        self.assertTrue(d["observer_only_bridge_counts_reconcile"])
        self.assertTrue(d["category_totals_agree_with_legacy_auditor"])

    def test_39_incomplete_bridge_at_end_is_not_completion(self):
        rows = delivered(frames()[:1])[:2]
        rows.append(event("P2_HW_RX_TIMED_LEGACY_ID_CANDIDATE_UNVERIFIED"))
        r = audit.analyze_source(rows)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["observer_only_bridge_candidates_started"], 1)
        self.assertEqual(d["observer_only_bridge_incomplete_at_scan_end"], 1)
        self.assertEqual(d["observer_only_bridge_outcomes"], {})
        self.assertTrue(d["observer_only_bridge_counts_reconcile"])
        self.assertNotIn("ABCD1234", json.dumps(r))
        self.assertFalse(r["sectorv_ecu_identity_accepted_verified"])


    def test_40_non_native_tag_text_is_not_a_d2_generation_tag(self):
        fake = "unrelated line: P2 D2 delivered channel/generation/frame/rx-us/delivery-us (BE)\n"
        rows = [fake] + delivered(frames()[:1])
        result = audit.analyze_source(rows)
        scan = result["source_scan_counts"]
        self.assertEqual(scan["source_rows_scanned"], 4)
        self.assertEqual(scan["non_native_prefix_rows"], 1)
        self.assertEqual(scan["native_prefix_rows"], 3)
        self.assertEqual(scan["tag_rows"], 1)
        self.assertEqual(result["native_d2_delivery_tags"]["tag_records"], 1)
        self.assertTrue(result["tag_adjacency_diagnostics"]
                        ["category_totals_agree_with_legacy_auditor"])

    def test_41_native_crlf_and_unterminated_rows_are_separate(self):
        rows = [line.replace("\n", "\r\n") for line in delivered(frames()[:1])]
        rows += ["external note\n", "unterminated note"]
        result = audit.analyze_source(rows)
        scan = result["source_scan_counts"]
        self.assertEqual(scan["source_rows_scanned"], 5)
        self.assertEqual(scan["native_prefix_rows"], 3)
        self.assertEqual(scan["non_native_prefix_rows"], 2)
        self.assertEqual(scan["non_crlf_rows"], 2)
        self.assertEqual(scan["unterminated_rows"], 1)
        self.assertEqual(scan["tag_rows"], 1)

    def test_42_repeated_pid_and_replacement_counts_redacted(self):
        malformed = event("unrelated note [PID=0BADF00D \ufffd")
        result = audit.analyze_source([malformed] + delivered(frames()[:1]))
        scan = result["source_scan_counts"]
        self.assertEqual(scan["repeated_pid_marker_rows"], 1)
        self.assertEqual(scan["replacement_character_rows"], 1)
        self.assertEqual(scan["native_prefix_rows"], 4)
        self.assertEqual(scan["tag_rows"], 1)
        output = json.dumps(result)
        self.assertNotIn("0BADF00D", output)
        self.assertNotIn("ABCD1234", output)
        self.assertFalse(result["real_ecu_response_verified"])

    def test_43_cli_preserves_crlf_for_native_logger_audit(self):
        with tempfile.TemporaryDirectory() as td:
            logfile = Path(td) / "PRIVATE_NATIVE.log"
            lines = [line.replace("\n", "\r\n") for line in delivered(frames()[:1])]
            logfile.write_bytes("".join(lines).encode("utf-8"))
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(audit.main(["--native", str(logfile)]), 0)
            result = json.loads(output.getvalue())
            scan = result["source_scan_counts"]
            self.assertEqual(scan["source_rows_scanned"], 3)
            self.assertEqual(scan["non_crlf_rows"], 0)
            self.assertEqual(scan["unterminated_rows"], 0)
            self.assertEqual(scan["tag_rows"], 1)
            self.assertNotIn(str(logfile), output.getvalue())


    def test_44_wide_protocol_clean_crlf_and_zero_status(self):
        rows = delivered(frames()[:1])
        rows[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                        be(1, 0x05000000, 0, 125000, 102000)
                        ).replace("\n", "\r\n")
        r = audit.analyze_source(rows)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["non_CAN_wide_protocol_shapes"],
                         {"byte_swapped_known_id_shape": 1})
        self.assertEqual(d["wide_protocol_rx_context_line_endings"],
                         {"native_crlf": 1})
        self.assertEqual(d["wide_protocol_rx_context_previous_event_classes"],
                         {"none": 1})
        self.assertEqual(d["wide_protocol_rx_status_shapes"],
                         {"zero_rx_status": 1})
        self.assertEqual(d["wide_protocol_affected_native_pid_count"], 1)
        self.assertTrue(d["wide_protocol_context_fingerprints_reconcile"])
        self.assertEqual(d["categories"]["mismatch_protocol_not_can"], 1)
        self.assertEqual(r["native_d2_delivery_tags"]["paired_tag_records"], 0)

    def test_45_wide_protocol_lf_previous_event_and_indication_status(self):
        rows = [event("P2 D2 request unverified predecessor")]
        case = delivered(frames()[:1])
        case[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                        be(1, 0xF123ABCD, 0x02, 125000, 102000))
        r = audit.analyze_source(rows + case)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["wide_protocol_rx_context_line_endings"],
                         {"non_crlf": 1})
        self.assertEqual(d["wide_protocol_rx_context_previous_event_classes"],
                         {"d2_request": 1})
        self.assertEqual(d["wide_protocol_rx_status_shapes"],
                         {"j2534_indication_bits_present": 1})
        self.assertTrue(d["wide_protocol_context_fingerprints_reconcile"])
        self.assertFalse(d["b9f0_specific_causal_attribution_verified"])
        self.assertNotIn("F123ABCD", json.dumps(r))

    def test_46_wide_protocol_counts_distinct_native_pid_cohorts_only(self):
        first = delivered(frames()[:1])
        first[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                         be(1, 0x99990001, 0, 125000, 102000))
        second = delivered(frames()[:1])
        second[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                          be(1, 0x99990002, 0, 125000, 102000))
        third = [line.replace("ABCD1234", "0BADF00D") for line in first]
        r = audit.analyze_source(first + second + third)
        d = r["tag_adjacency_diagnostics"]
        self.assertEqual(d["wide_protocol_affected_native_pid_count"], 2)
        self.assertEqual(sum(d["wide_protocol_rx_context_line_endings"].values()), 3)
        self.assertEqual(d["non_CAN_other_protocol_values"],
                         {"other_protocol_value": 3})
        self.assertEqual(d["wide_protocol_rx_status_shapes"],
                         {"zero_rx_status": 3})
        self.assertTrue(d["wide_protocol_context_fingerprints_reconcile"])
        self.assertNotIn("0BADF00D", json.dumps(r))
        self.assertNotIn("ABCD1234", json.dumps(r))

    def test_47_known_iso_and_nonwide_values_do_not_make_wide_context(self):
        cases = []
        for proto in (6, 12):
            rows = delivered(frames()[:1])
            rows[0] = event("RX context channel/protocol/status/baud/time-us (BE)",
                            be(1, proto, 0, 125000, 102000))
            cases.extend(rows)
        d = audit.analyze_source(cases)["tag_adjacency_diagnostics"]
        self.assertEqual(d["categories"]["mismatch_protocol_not_can"], 2)
        self.assertEqual(d["non_CAN_protocol_categories"],
                         {"ISO15765_6": 1, "other_non_CAN": 1})
        self.assertEqual(d["wide_protocol_rx_context_line_endings"], {})
        self.assertEqual(d["wide_protocol_rx_context_previous_event_classes"], {})
        self.assertEqual(d["wide_protocol_rx_status_shapes"], {})
        self.assertEqual(d["wide_protocol_affected_native_pid_count"], 0)
        self.assertTrue(d["wide_protocol_context_fingerprints_reconcile"])

    def test_08_existing_general_j2534_schema_remains_identical_by_default(self):
        import audit_j2534_discovery as general
        legacy = general._native_d2_delivery_tags(delivered(frames()))
        self.assertNotIn("b9f0_emitter_rx_groups", legacy)
        self.assertNotIn("b9f0_emitter_rx_groups_with_contiguous_terminal", legacy)
        expanded = general._native_d2_delivery_tags(
            delivered(frames()), include_b9f0=True)
        self.assertEqual(expanded["b9f0_emitter_rx_groups_with_contiguous_terminal"], 1)
        self.assertEqual(set(expanded) - set(legacy), {
            "b9f0_emitter_rx_groups",
            "b9f0_emitter_rx_groups_with_positive_first_echo",
            "b9f0_emitter_rx_groups_with_contiguous_terminal",
            "b9f0_replay_stage_correlated_to_rx",
            "b9f0_original_client_ecu_identity_accepted",
        })

    def test_07_staged_marker_cannot_confirm_client_identity(self):
        records = [event("P2 D2 read-only recorded frames staged",
                         bytes((0xCB, 0x40, 0xB9, 0xF0)))]
        records.extend(delivered(frames()))
        r = audit.analyze_source(records)
        self.assertFalse(r["real_ecu_response_verified"])
        self.assertFalse(r["native_d2_delivery_tags"]["b9f0_replay_stage_correlated_to_rx"])
        self.assertFalse(r["native_d2_delivery_tags"]["b9f0_original_client_ecu_identity_accepted"])


if __name__ == "__main__":
    unittest.main()
