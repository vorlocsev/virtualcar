"""Eight offline evidence/privilege/privacy gates for the backend JSONL auditor."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / "tools" / "audit_backend_evidence.py"
spec = importlib.util.spec_from_file_location("audit_backend_evidence", MODULE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def evt(kind, *, sid="0123456789abcdef", rid=1001, tick=1000000, channel=1,
        protocol=5, baud=500000, route="UNKNOWN", reason="none",
        outcome="unknown", **extra):
    value = {
        "format": "virtualcar-backend-v1", "session_id": sid,
        "request_id": rid, "kind": kind, "tick": tick, "freq": 1000000,
        "channel": channel, "protocol": protocol, "baud": baud,
        "route": route, "reason": reason, "outcome": outcome,
    }
    value.update(extra)
    return json.dumps(value) + "\n"


def audit(*events):
    return tool.audit(events)


class BackendEvidenceTests(unittest.TestCase):
    def test_01_delivered_is_not_ecu_identification(self):
        r = audit(evt("tx_received"), evt("route_selected", route="CEM"),
                  evt("response_generated"), evt("rx_queued"),
                  evt("rx_dequeued", tick=1025000),
                  evt("request_completed", outcome="responded", tick=1025000))
        one = r["transactions"][0]
        self.assertEqual((one["status"], one["reason"]), ("delivered", "j2534_rx_only"))
        self.assertEqual((one["channel"], one["protocol"], one["baud_bps"]), (1, "CAN", 500000))
        self.assertEqual(one["elapsed_ms"], 25)
        self.assertIsNone(one["service"])
        self.assertIsNone(one["can_id"])
        self.assertEqual(one["id_format"], "unknown")
        self.assertFalse(r["client_acceptance_verified"])

    def test_02_missing_fixture_and_unsupported_are_distinct(self):
        r = audit(evt("tx_received", rid=1),
                  evt("request_completed", rid=1, route="CEM",
                      reason="missing_profile", outcome="no_response"),
                  evt("tx_received", rid=2),
                  evt("request_completed", rid=2, route="CEM",
                      reason="unsupported_bus", outcome="no_response"),
                  evt("tx_received", rid=3),
                  evt("request_completed", rid=3, route="UNHANDLED",
                      reason="unhandled_request", outcome="no_response"))
        self.assertEqual([x["status"] for x in r["transactions"]],
                         ["no_fixture", "unsupported", "unsupported"])

    def test_03_partial_delivery_abort_and_pre_delivery_abort(self):
        r = audit(evt("tx_received", rid=1), evt("rx_queued", rid=1),
                  evt("rx_dequeued", rid=1),
                  evt("response_aborted", rid=1, reason="flow_overflow"),
                  evt("request_completed", rid=1, reason="flow_overflow",
                      outcome="aborted"),
                  evt("tx_received", rid=2), evt("rx_queued", rid=2),
                  evt("request_completed", rid=2, reason="clear_rx_buffer",
                      outcome="aborted"))
        self.assertEqual([(t["status"], t["reason"]) for t in r["transactions"]],
                         [("partial_rx", "rx_delivery_interrupted"),
                          ("unverified", "aborted_or_dropped_before_rx")])

    def test_04_sessions_and_channels_are_not_mixed_or_leaked(self):
        second_sid = "fedcba9876543210"
        r = audit(evt("tx_received", rid=7, channel=1),
                  evt("tx_received", rid=7, channel=2, sid=second_sid),
                  evt("rx_queued", rid=7, channel=2, sid=second_sid),
                  evt("rx_dequeued", rid=7, channel=2, sid=second_sid),
                  evt("request_completed", rid=7, channel=2, sid=second_sid,
                      outcome="responded"),
                  evt("request_completed", rid=7, channel=1, outcome="no_response",
                      reason="no_response"))
        self.assertEqual(r["summary"]["sessions"], 2)
        self.assertEqual([x["status"] for x in r["transactions"]],
                         ["unverified", "delivered"])
        s = json.dumps(r)
        self.assertNotIn(second_sid, s)
        self.assertNotIn("0123456789abcdef", s)
        self.assertNotIn('"request_id"', s)

    def test_05_double_terminal_and_conflicting_route_cannot_succeed(self):
        r = audit(evt("tx_received", rid=1),
                  evt("route_selected", rid=1, route="CEM"),
                  evt("route_selected", rid=1, route="ECM"),
                  evt("rx_dequeued", rid=1),
                  evt("request_completed", rid=1, outcome="responded"),
                  evt("tx_received", rid=2), evt("rx_dequeued", rid=2),
                  evt("request_completed", rid=2, outcome="responded"),
                  evt("request_completed", rid=2, outcome="responded"))
        self.assertEqual([t["reason"] for t in r["transactions"]],
                         ["inconsistent_route_or_channel", "inconsistent_event_lifecycle"])

    def test_06_fail_closed_privacy_and_untrusted_extra_fields(self):
        marker = "YV1CZ0002A0000001"  # Synthetic, never a vehicle source.
        r = audit(evt("tx_received", private_vin=marker,
                      raw_can=marker, source_path="C:/private/secret"),
                  evt("request_completed", outcome="responded",
                      private_vin=marker),
                  '{"format":"virtualcar-backend-v1","kind":"wrong","VIN":"' + marker + '"}\n',
                  evt("tx_received", reason=marker),
                  evt("tx_received", route=[marker]),
                  marker * 300 + "\n")
        data = json.dumps(r)
        self.assertNotIn(marker, data)
        self.assertNotIn("secret", data)
        self.assertEqual(r["summary"]["invalid_lines"], 4)
        self.assertEqual(r["transactions"][0]["status"], "unverified")

    def test_07_no_timeout_inference_and_explicit_timeout(self):
        r = audit(evt("tx_received", rid=1),
                  evt("tx_received", rid=2),
                  evt("request_completed", rid=2, reason="device_close",
                      outcome="aborted"),
                  evt("tx_received", rid=3),
                  evt("request_completed", rid=3, reason="read_timeout",
                      outcome="no_response"),
                  evt("tx_received", rid=4), evt("rx_dequeued", rid=4))
        self.assertEqual([x["status"] for x in r["transactions"]],
                         ["unverified", "unverified", "timeout", "unverified"])

    def test_08_cli_creates_only_new_report_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "private.jsonl"
            dest = Path(directory) / "report.json"
            original = evt("tx_received") + evt("rx_queued") + evt("rx_dequeued") + evt(
                "request_completed", outcome="responded")
            source.write_text(original, encoding="utf-8")
            self.assertEqual(tool.main([str(source), "--output", str(dest)]), 0)
            self.assertEqual(source.read_text(encoding="utf-8"), original)
            self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))[
                "transactions"][0]["status"], "delivered")
            self.assertEqual(tool.main([str(source), "--output", str(dest)]), 2)
            self.assertEqual(tool.main([str(source), "--output", str(source)]), 2)
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_09_known_d2_probes_are_specific_and_privacy_safe(self):
        r = audit(evt("tx_received", rid=1),
                  evt("probe_classified", rid=1, probe="D2_40_B9FB"),
                  evt("request_completed", rid=1, route="CEM", reason="missing_profile",
                      outcome="no_response"),
                  evt("tx_received", rid=2),
                  evt("probe_classified", rid=2, probe="D2_50_B9F0"),
                  evt("request_completed", rid=2, route="CEM", reason="missing_profile",
                      outcome="no_response"))
        a, b = r["transactions"]
        self.assertTrue(r["probe_detail_available"])
        self.assertEqual((a["service"], a["target"], a["can_id"], a["id_format"]),
                         ("B9FB", "0x40", "0x000FFFFE", "29bit"))
        self.assertEqual((b["service"], b["target"]), ("B9F0", "0x50"))
        self.assertEqual((a["status"], b["status"]), ("no_fixture", "no_fixture"))

    def test_10_p3_11_29bit_and_iso15765(self):
        r = audit(evt("tx_received", rid=1, protocol=5),
                  evt("probe_classified", rid=1, probe="P3_726_F114", protocol=5),
                  evt("rx_queued", rid=1, protocol=5),
                  evt("rx_dequeued", rid=1, protocol=5),
                  evt("request_completed", rid=1, protocol=5, outcome="responded"),
                  evt("tx_received", rid=2, protocol=6),
                  evt("probe_classified", rid=2, probe="P3_29_F1B0", protocol=6),
                  evt("request_completed", rid=2, protocol=6, outcome="no_response",
                      reason="unhandled_request"))
        a, b = r["transactions"]
        self.assertEqual((a["service"], a["can_id"], a["id_format"]),
                         ("22F114", "0x726", "11bit"))
        self.assertEqual((b["service"], b["can_id"], b["id_format"], b["protocol"]),
                         ("22F1B0", "0x18DA50F1", "29bit", "ISO15765"))
        self.assertEqual((a["status"], b["status"]), ("delivered", "unsupported"))

    def test_11_conflicting_probe_tags_fail_closed(self):
        r = audit(evt("tx_received"),
                  evt("probe_classified", probe="D2_40_B9FB"),
                  evt("probe_classified", probe="D2_50_B9F0"),
                  evt("rx_dequeued"),
                  evt("request_completed", outcome="responded"))
        one = r["transactions"][0]
        self.assertEqual((one["status"], one["reason"]),
                         ("unverified", "conflicting_probe_evidence"))
        self.assertEqual((one["service"], one["can_id"], one["id_format"]),
                         (None, None, "unknown"))

    def test_12_invalid_probe_and_raw_identifiers_never_leak(self):
        fake_vin = "YV1CZ0002A0000001"
        r = audit(evt("tx_received", private_vin=fake_vin),
                  evt("probe_classified", probe=fake_vin),
                  evt("probe_classified", probe={"private": fake_vin}),
                  evt("probe_classified", probe="D2_50_A6", payload=fake_vin),
                  evt("request_completed", outcome="no_response", reason="unhandled_request"))
        raw = json.dumps(r)
        self.assertNotIn(fake_vin, raw)
        self.assertEqual(r["summary"]["invalid_lines"], 2)
        self.assertEqual(r["transactions"][0]["service"], "A6")

    def test_13_legacy_jsonl_does_not_acquire_invented_probe(self):
        r = audit(evt("tx_received"),
                  evt("route_selected", route="CEM"),
                  evt("rx_dequeued"),
                  evt("request_completed", outcome="responded"))
        self.assertFalse(r["probe_detail_available"])
        self.assertIsNone(r["transactions"][0]["service"])
        self.assertEqual(r["transactions"][0]["id_format"], "unknown")


    def test_14_orphan_dequeue_cannot_prove_delivery(self):
        r = audit(evt("tx_received"), evt("rx_dequeued"),
                  evt("request_completed", outcome="responded"))
        self.assertEqual((r["transactions"][0]["status"], r["transactions"][0]["reason"]),
                         ("unverified", "dequeue_without_queue"))

    def test_15_queued_frame_not_delivered_cannot_prove_delivery(self):
        r = audit(evt("tx_received"), evt("rx_queued"),
                  evt("rx_queued"), evt("rx_dequeued"),
                  evt("request_completed", outcome="responded"))
        self.assertEqual(r["transactions"][0]["status"], "unverified")
        self.assertEqual(r["transactions"][0]["reason"], "terminal_without_clean_rx")

    def test_16_duplicate_tx_is_not_two_successful_requests(self):
        r = audit(evt("tx_received"), evt("tx_received"),
                  evt("rx_queued"), evt("rx_dequeued"),
                  evt("request_completed", outcome="responded"))
        self.assertEqual(r["summary"]["requests"], 1)
        self.assertEqual(r["transactions"][0]["reason"], "inconsistent_event_lifecycle")

    def test_17_reverse_clock_cannot_prove_delivery_or_duration(self):
        r = audit(evt("tx_received", tick=2000),
                  evt("rx_queued", tick=1000),
                  evt("rx_dequeued", tick=3000),
                  evt("request_completed", tick=4000, outcome="responded"))
        self.assertEqual(r["transactions"][0]["reason"], "inconsistent_clock")
        self.assertIsNone(r["transactions"][0]["elapsed_ms"])

    def test_18_changed_counter_frequency_fails_closed(self):
        changed = json.loads(evt("rx_queued"))
        changed["freq"] = 2000000
        r = audit(evt("tx_received"), json.dumps(changed),
                  evt("rx_dequeued"), evt("request_completed", outcome="responded"))
        self.assertEqual(r["transactions"][0]["reason"], "inconsistent_clock")

    def test_19_probe_after_rx_is_not_attributed(self):
        r = audit(evt("tx_received"), evt("rx_queued"),
                  evt("probe_classified", probe="D2_40_B9FB"),
                  evt("rx_dequeued"), evt("request_completed", outcome="responded"))
        one = r["transactions"][0]
        self.assertEqual(one["reason"], "inconsistent_event_lifecycle")
        self.assertIsNone(one["service"])
        self.assertEqual(one["id_format"], "unknown")

    def test_20_explicit_missing_fixture_with_rx_is_inconsistent(self):
        r = audit(evt("tx_received"), evt("probe_classified", probe="D2_50_B9F0"),
                  evt("rx_queued"),
                  evt("request_completed", outcome="no_response", reason="missing_profile"))
        self.assertEqual(r["transactions"][0]["reason"], "rx_evidence_with_no_response")
        self.assertEqual(r["transactions"][0]["status"], "unverified")

    def test_21_drop_during_enqueue_is_not_a_queue_dequeue(self):
        r = audit(evt("tx_received"), evt("rx_dropped", reason="queue_full"),
                  evt("request_completed", outcome="dropped", reason="queue_full"))
        self.assertEqual(r["transactions"][0]["reason"], "aborted_or_dropped_before_rx")


def coverage(report, probe):
    for item in report["coverage"]["probes"]:
        if item["probe"] == probe:
            return item
    raise AssertionError("missing allowlisted coverage probe")


class BackendCoverageTests(unittest.TestCase):
    def test_22_empty_session_does_not_imply_failure(self):
        r = audit()
        self.assertEqual(r["summary"]["requests"], 0)
        self.assertFalse(r["probe_detail_available"])
        self.assertTrue(r["coverage"]["not_observed_is_not_unsupported"])
        self.assertEqual(r["coverage"]["attributed_requests"], 0)
        self.assertEqual(r["coverage"]["unattributed_requests"], 0)
        self.assertEqual(len(r["coverage"]["probes"]), len(tool.PROBES))
        self.assertTrue(all(p["status_counts"] == {} for p in r["coverage"]["probes"]))

    def test_23_known_a3_missing_fixture_is_not_b9fb_failure(self):
        r = audit(evt("tx_received"),
                  evt("probe_classified", probe="D2_50_A3"),
                  evt("request_completed", route="CEM", outcome="no_response",
                      reason="missing_profile"))
        self.assertEqual(coverage(r, "D2_50_A3")["status_counts"], {"no_fixture": 1})
        self.assertEqual(coverage(r, "D2_50_B9FB")["observed_requests"], 0)
        self.assertEqual(coverage(r, "D2_50_B9FB")["status_counts"], {})

    def test_24_p3_11bit_29bit_are_separate_shape_counts(self):
        r = audit(evt("tx_received", rid=1),
                  evt("probe_classified", rid=1, probe="P3_726_F114"),
                  evt("rx_queued", rid=1), evt("rx_dequeued", rid=1),
                  evt("request_completed", rid=1, outcome="responded"),
                  evt("tx_received", rid=2),
                  evt("probe_classified", rid=2, probe="P3_29_F114"),
                  evt("request_completed", rid=2, reason="unhandled_request",
                      outcome="no_response"))
        self.assertEqual(coverage(r, "P3_726_F114")["status_counts"], {"delivered": 1})
        self.assertEqual(coverage(r, "P3_29_F114")["status_counts"], {"unsupported": 1})
        self.assertEqual(r["coverage"]["attributed_requests"], 2)

    def test_25_unclassified_tx_does_not_count_as_a_cem_probe(self):
        r = audit(evt("tx_received"),
                  evt("request_completed", outcome="no_response",
                      reason="unhandled_request"))
        self.assertEqual(r["coverage"]["unattributed_requests"], 1)
        self.assertFalse(r["probe_detail_available"])
        self.assertTrue(all(not p["observed_requests"] for p in r["coverage"]["probes"]))

    def test_26_conflicting_labels_do_not_increment_both_counters(self):
        r = audit(evt("tx_received"),
                  evt("probe_classified", probe="D2_40_A3"),
                  evt("probe_classified", probe="D2_50_A6"),
                  evt("request_completed", outcome="no_response"))
        self.assertEqual(r["coverage"]["unattributed_requests"], 1)
        self.assertEqual(coverage(r, "D2_40_A3")["observed_requests"], 0)
        self.assertEqual(coverage(r, "D2_50_A6")["observed_requests"], 0)
        self.assertEqual(r["transactions"][0]["status"], "unverified")

    def test_27_invalid_probe_does_not_leak_or_count(self):
        marker = "YV1CZ0002A0000001"  # Synthetic test-only marker.
        r = audit(evt("tx_received"),
                  evt("probe_classified", probe=marker),
                  evt("request_completed", outcome="no_response"))
        self.assertEqual(r["summary"]["invalid_lines"], 1)
        self.assertEqual(r["coverage"]["unattributed_requests"], 1)
        self.assertNotIn(marker, json.dumps(r))

    def test_28_two_sessions_same_probe_have_distinct_transactions(self):
        second = "abcdefabcdefabcd"
        r = audit(evt("tx_received", sid=second, rid=1),
                  evt("probe_classified", sid=second, rid=1,
                      probe="D2_40_B9FB"),
                  evt("request_completed", sid=second, rid=1,
                      outcome="no_response", reason="missing_profile"),
                  evt("tx_received", rid=1),
                  evt("probe_classified", rid=1, probe="D2_40_B9FB"),
                  evt("request_completed", rid=1, outcome="no_response",
                      reason="unhandled_request"))
        self.assertEqual(r["summary"]["sessions"], 2)
        self.assertEqual(coverage(r, "D2_40_B9FB")["status_counts"],
                         {"no_fixture": 1, "unsupported": 1})
        self.assertNotIn(second, json.dumps(r))

    def test_29_late_probe_is_not_accepted_as_an_attributed_request(self):
        r = audit(evt("tx_received"), evt("rx_queued"),
                  evt("probe_classified", probe="P3_726_F190"),
                  evt("rx_dequeued"),
                  evt("request_completed", outcome="responded"))
        self.assertEqual(r["coverage"]["unattributed_requests"], 1)
        self.assertEqual(coverage(r, "P3_726_F190")["observed_requests"], 0)
        self.assertIsNone(r["transactions"][0]["service"])


class UnimplementedCemProbeTests(unittest.TestCase):
    def test_30_a3_target_40_is_known_but_unsupported_by_emulator(self):
        r = audit(evt("tx_received"), evt("probe_classified", probe="D2_40_A3"),
                  evt("route_selected", route="CEM"),
                  evt("request_completed", route="CEM",
                      reason="unimplemented_probe", outcome="no_response"))
        t = r["transactions"][0]
        self.assertEqual((t["status"], t["reason"]), ("unsupported", "unimplemented_probe"))
        self.assertEqual((t["service"], t["target"], t["rx_dequeued"]), ("A3", "0x40", 0))
        self.assertEqual(coverage(r, "D2_40_A3")["status_counts"], {"unsupported": 1})

    def test_31_a6_target_50_has_no_fake_positive(self):
        r = audit(evt("tx_received"), evt("probe_classified", probe="D2_50_A6"),
                  evt("route_selected", route="CEM"),
                  evt("request_completed", route="CEM", reason="unimplemented_probe",
                      outcome="no_response"))
        self.assertEqual(r["transactions"][0]["service"], "A6")
        self.assertEqual(r["transactions"][0]["status"], "unsupported")
        self.assertEqual(r["transactions"][0]["rx_queued"], 0)
        self.assertFalse(r["identity_verified"])

    def test_32_unimplemented_reason_is_only_valid_for_no_response(self):
        r = audit(evt("tx_received"),
                  evt("request_completed", reason="unimplemented_probe",
                      outcome="responded"))
        self.assertEqual(r["transactions"][0]["status"], "unverified")

    def test_33_known_unimplemented_does_not_override_missing_b9_fixture(self):
        r = audit(evt("tx_received", rid=1),
                  evt("probe_classified", rid=1, probe="D2_40_A3"),
                  evt("request_completed", rid=1, route="CEM",
                      reason="unimplemented_probe", outcome="no_response"),
                  evt("tx_received", rid=2),
                  evt("probe_classified", rid=2, probe="D2_40_B9FB"),
                  evt("request_completed", rid=2, route="CEM",
                      reason="missing_profile", outcome="no_response"))
        self.assertEqual([t["status"] for t in r["transactions"]],
                         ["unsupported", "no_fixture"])
        self.assertEqual(coverage(r, "D2_40_A3")["status_counts"], {"unsupported": 1})
        self.assertEqual(coverage(r, "D2_40_B9FB")["status_counts"], {"no_fixture": 1})

    def test_34_conflicting_routes_stay_unverified(self):
        r = audit(evt("tx_received"), evt("probe_classified", probe="D2_50_A3"),
                  evt("route_selected", route="CEM"),
                  evt("route_selected", route="UNHANDLED"),
                  evt("request_completed", route="CEM", reason="unimplemented_probe",
                      outcome="no_response"))
        self.assertEqual(r["transactions"][0]["status"], "unverified")
        self.assertEqual(r["transactions"][0]["reason"], "inconsistent_route_or_channel")

    def test_35_unimplemented_cannot_claim_delivered_with_dequeued_rx(self):
        r = audit(evt("tx_received"), evt("probe_classified", probe="D2_50_A6"),
                  evt("rx_queued"), evt("rx_dequeued"),
                  evt("request_completed", route="CEM", reason="unimplemented_probe",
                      outcome="no_response"))
        self.assertEqual(r["transactions"][0]["reason"], "rx_evidence_with_no_response")

    def test_36_injected_private_fields_do_not_escape_unimplemented_report(self):
        private = "SYNTHETIC_PRIVATE_VIN_NOT_FROM_CAR"
        r = audit(evt("tx_received", raw_payload=private),
                  evt("probe_classified", probe="D2_40_A6", secret=private),
                  evt("request_completed", route="CEM", reason="unimplemented_probe",
                      outcome="no_response", vin=private))
        self.assertNotIn(private, json.dumps(r))
        self.assertEqual(r["transactions"][0]["status"], "unsupported")


if __name__ == "__main__":
    unittest.main()
