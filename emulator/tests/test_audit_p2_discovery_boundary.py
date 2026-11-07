"""Eight synthetic regression gates for conservative SectorV/J2534 evidence."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from collections import Counter

source = Path(__file__).resolve().parents[1] / "tools" / "audit_p2_discovery_boundary.py"
spec = importlib.util.spec_from_file_location("audit_p2_discovery_boundary", source)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

def transaction(service, status, target="0x50", baud=500000, channel=1,
                id_format="29bit", route="D2"):
    return {"route": route, "service": service, "status": status,
            "target": target if route == "D2" else None,
            "baud_bps": baud, "channel": channel, "id_format": id_format,
            "protocol": "CAN", "rx_frames": 13 if status == "delivered" else 0,
            "reason": "synthetic_transport_only"}

def j2534(*items):
    return {"format": "virtualcar-j2534-evidence-v1", "read_only": True,
            "contains_payload_data": False, "replay_approved": False,
            "transactions": list(items), "counts": dict(Counter(x["status"] for x in items)),
            "parse_errors": {}, "notes": ["Synthetic fixture, not a vehicle log"]}

def sectorv(matched=True, hardware=True, warning=True):
    return {
        "schema_version": "virtualcar-sectorv-gate-report-v1",
        "client": "SectorV", "client_version": "1.1.0.0",
        "scenario": "P2_MY2005_lab", "same_client_run": True,
        "observation_order": ["b9fb_matcher", "hardware_a3_50"],
        "b9fb_client_matcher": {"observed": 13, "matched": 13 if matched else 12,
                                "ignored": 0 if matched else 1,
                                "frame_matcher_complete": matched},
        "hardware_a3": ({"50": {"outcome": "timeout", "elapsed_ms": 5000}}
                        if hardware else {}),
        "normal_mode_warning_observed": warning,
        "ecu_reachable_observed": 0,
        "normal_mode_predicate": "unknown",
        "expected_e3_response_bytes": "unknown",
        "a3_security_access_authorized": "unknown",
        "b9fb_vehicle_identity_accepted": "unknown",
        "client_ecu_identification_accepted": "unknown",
        "replay_approved": False, "findings": ["Synthetic-only evidence"]}

class BoundaryTests(unittest.TestCase):
    def test_01_complete_b9fb_and_client_matcher_not_vin(self):
        result = tool.audit(j2534(transaction("B9FB", "delivered")),
                            sectorv(), same_run_reviewed=True)
        self.assertEqual(result["stage_evidence"]["B9FB"]["statuses"], {"delivered": 1})
        self.assertEqual(result["client_observations"]["b9fb_frame_matcher"],
                         "complete_frame_matcher_only")
        self.assertEqual(result["vin_accepted_by_client"], "unknown")
        self.assertEqual(result["cross_source_transaction_attribution"], "not_established")

    def test_02_independent_reports_never_auto_join(self):
        result = tool.audit(j2534(transaction("B9FB", "delivered")), sectorv())
        self.assertEqual(result["provenance"], "independent_reports_no_same_run_claim")
        self.assertEqual(result["first_investigation_priority"],
                         "review_same_run_provenance_first")
        self.assertFalse(result["replay_approved"])

    def test_03_client_match_missing_or_partial_transport(self):
        result = tool.audit(j2534(), sectorv(), same_run_reviewed=True)
        self.assertEqual(result["first_investigation_priority"],
                         "obtain_same_run_j2534_b9fb_tx")
        result = tool.audit(j2534(transaction("B9FB", "partial_rx")),
                            sectorv(), same_run_reviewed=True)
        self.assertEqual(result["first_investigation_priority"],
                         "investigate_b9fb_transport")

    def test_04_a3_no_reply_no_e3_or_authorization(self):
        result = tool.audit(j2534(transaction("B9FB", "delivered"),
                                   transaction("A3", "timeout")),
                            sectorv(), same_run_reviewed=True)
        self.assertEqual(result["stage_evidence"]["A3_50"]["statuses"], {"timeout": 1})
        self.assertEqual(result["a3_security_access_authorized"], "unknown")
        self.assertEqual(result["first_investigation_priority"],
                         "investigate_hardware_a3_no_reply_without_emulating_security")
        self.assertNotIn("E3 02", json.dumps(result))

    def test_05_a6_b9f0_p3_transport_does_not_identify_ecu(self):
        result = tool.audit(j2534(transaction("B9FB", "delivered"),
                                   transaction("A6", "delivered"),
                                   transaction("B9F0", "delivered"),
                                   transaction("22F190", "delivered", route="P3")),
                            sectorv(hardware=False, warning=False),
                            same_run_reviewed=True)
        self.assertEqual([result["stage_evidence"][s]["requests"]
                          for s in ("A6", "B9F0", "P3")], [1, 1, 1])
        self.assertEqual(result["ecu_identification_accepted"], "unknown")
        self.assertEqual(result["first_investigation_priority"],
                         "obtain_verified_vehicle_and_ecu_acceptance")

    def test_06_route_target_baud_11_29_bit_separation(self):
        result = tool.audit(j2534(
            transaction("A3", "timeout", target="0x40", baud=125000, channel=3),
            transaction("A3", "unsupported", target="0x50", baud=500000, channel=7),
            transaction("A3", "unverified", target=None, baud=None,
                        channel=None, id_format="unknown")), sectorv(),
            same_run_reviewed=True)
        self.assertEqual(result["stage_evidence"]["A3_40"]["baud_categories"], {"125k": 1})
        self.assertEqual(result["stage_evidence"]["A3_50"]["baud_categories"], {"500k": 1})
        self.assertEqual(result["stage_evidence"]["A3_unknown_target"]["requests"], 1)
        self.assertNotIn('"channel": 7', json.dumps(result))

    def test_07_reject_extra_private_or_fake_positive_fields(self):
        base = j2534(transaction("B9FB", "delivered"))
        gate = sectorv()
        cases = [(dict(base, vin="TEST-PRIVATE"), gate),
                 (dict(base, counts={"timeout": 1}), gate),
                 (j2534(transaction("B9FB", "delivered", baud=True)), gate),
                 (j2534(transaction("A3", "delivered", target="C:/private.ini")), gate),
                 (base, dict(gate, normal_mode_predicate="E3 02")),
                 (base, dict(gate, replay_approved=True)),
                 (base, dict(gate, b9fb_client_matcher={
                     "observed": 13, "matched": 13, "ignored": 0,
                     "frame_matcher_complete": False}))]
        for left, right in cases:
            with self.subTest(kind="malformed"), self.assertRaises(ValueError):
                tool.audit(left, right, same_run_reviewed=True)
        with self.assertRaises(ValueError):
            tool.audit(base, gate, same_run_reviewed=1)

    def test_08_cli_redaction_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as temp:
            left = Path(temp) / "TEST-PRIVATE-VIN.log.json"
            right = Path(temp) / "TEST-PRIVATE-SectorV.ini.json"
            output = Path(temp) / "new-report.json"
            left.write_text(json.dumps(j2534(transaction("B9FB", "delivered"))),
                            encoding="utf-8")
            right.write_text(json.dumps(sectorv()), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                tool.main([str(left), str(right), "--same-run-reviewed",
                           "--output", str(output)])
            text = output.read_text(encoding="utf-8")
            for forbidden in ("TEST-PRIVATE", str(left), str(right), "E3 02"):
                self.assertNotIn(forbidden, text)
            self.assertEqual(json.loads(text)["vin_accepted_by_client"], "unknown")
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                tool.main([str(left), str(right), "--output", str(output)])

    def test_09_late_p2_40_delivery_does_not_substitute_for_50(self):
        report = tool.audit(j2534(transaction(
            "B9FB", "delivered", target="0x40", baud=125000)),
            sectorv(), same_run_reviewed=True)
        self.assertEqual(report["stage_evidence"]["B9FB_40"]["statuses"],
                         {"delivered": 1})
        self.assertEqual(report["stage_evidence"]["B9FB_50"]["requests"], 0)
        self.assertEqual(report["first_investigation_priority"],
                         "verify_b9fb_target_50_transport")
        self.assertEqual(report["vin_accepted_by_client"], "unknown")

    def test_10_target_40_delivered_and_50_partial_does_not_advance(self):
        report = tool.audit(j2534(
            transaction("B9FB", "delivered", target="0x40", baud=125000),
            transaction("B9FB", "partial_rx", target="0x50", baud=500000)),
            sectorv(), same_run_reviewed=True)
        self.assertEqual(report["stage_evidence"]["B9FB"]["statuses"],
                         {"delivered": 1, "partial_rx": 1})
        self.assertEqual(report["stage_evidence"]["B9FB_50"]["statuses"],
                         {"partial_rx": 1})
        self.assertEqual(report["first_investigation_priority"],
                         "investigate_b9fb_target_50_transport")

    def test_11_target_50_delivery_allows_next_investigation_not_identity(self):
        report = tool.audit(j2534(
            transaction("B9FB", "delivered", target="0x40", baud=125000),
            transaction("B9FB", "delivered", target="0x50", baud=500000)),
            sectorv(), same_run_reviewed=True)
        self.assertEqual(report["first_investigation_priority"],
                         "investigate_hardware_a3_no_reply_without_emulating_security")
        self.assertTrue(report["b9fb_target_evidence_boundary"]["j2534_target_50_delivered"])
        self.assertEqual(report["b9fb_target_evidence_boundary"]["client_matcher_target"],
                         "not_reported_by_gate_schema")
        self.assertEqual(report["cross_source_transaction_attribution"], "not_established")
        self.assertEqual(report["a3_security_access_authorized"], "unknown")

    def test_12_unknown_target_b9fb_delivery_is_not_50_evidence(self):
        report = tool.audit(j2534(
            transaction("B9FB", "delivered", target=None, baud=None,
                        channel=None, id_format="unknown")),
            sectorv(), same_run_reviewed=True)
        self.assertEqual(report["stage_evidence"]["B9FB_unknown_target"]["requests"], 1)
        self.assertEqual(report["stage_evidence"]["B9FB_50"]["requests"], 0)
        self.assertEqual(report["first_investigation_priority"],
                         "verify_b9fb_target_50_transport")
        self.assertFalse(report["b9fb_target_evidence_boundary"]["j2534_target_50_delivered"])

    def test_13_target_level_speed_id_and_channel_metadata_separate(self):
        report = tool.audit(j2534(
            transaction("B9FB", "unverified", target="0x40", baud=125000,
                        id_format="11bit", channel=2),
            transaction("B9FB", "delivered", target="0x50", baud=500000,
                        id_format="29bit", channel=7),
            transaction("B9FB", "timeout", target=None, baud=None,
                        id_format="unknown", channel=None)),
            sectorv(), same_run_reviewed=True)
        t = report["stage_evidence"]
        self.assertEqual(t["B9FB_40"]["baud_categories"], {"125k": 1})
        self.assertEqual(t["B9FB_40"]["id_formats"], {"11bit": 1})
        self.assertEqual(t["B9FB_50"]["baud_categories"], {"500k": 1})
        self.assertEqual(t["B9FB_50"]["id_formats"], {"29bit": 1})
        self.assertEqual(t["B9FB_unknown_target"]["missing_channel_metadata"], 1)
        self.assertEqual(t["B9FB"]["requests"], 3)

    def test_14_unknown_lab_does_not_invent_target_50_requirement(self):
        unknown = sectorv()
        unknown["scenario"] = "unknown_lab"
        report = tool.audit(j2534(transaction(
            "B9FB", "delivered", target="0x40", baud=125000)),
            unknown, same_run_reviewed=True)
        self.assertEqual(report["first_investigation_priority"],
                         "investigate_hardware_a3_no_reply_without_emulating_security")
        self.assertEqual(report["b9fb_target_evidence_boundary"]["target_50_model_context"],
                         "unknown_lab_no_target_assumption")

    def test_15_no_delivery_and_missing_b9fb_keep_original_priority(self):
        no_request = tool.audit(j2534(), sectorv(), same_run_reviewed=True)
        self.assertEqual(no_request["first_investigation_priority"],
                         "obtain_same_run_j2534_b9fb_tx")
        bad = tool.audit(j2534(
            transaction("B9FB", "no_fixture", target="0x40"),
            transaction("B9FB", "timeout", target="0x50")),
            sectorv(), same_run_reviewed=True)
        self.assertEqual(bad["first_investigation_priority"],
                         "investigate_b9fb_transport")

    def test_16_no_private_identifiers_or_false_cross_source_link(self):
        secret = "PRIVATE-VIN-DO-NOT-EXPORT"
        tx = transaction("B9FB", "delivered", target="0x40")
        tx["private_source_label"] = secret
        report = tool.audit(j2534(tx), sectorv(), same_run_reviewed=True)
        text = json.dumps(report)
        self.assertNotIn(secret, text)
        self.assertNotIn('"channel": 1', text)
        self.assertEqual(report["b9fb_target_evidence_boundary"]["target_cross_source_match"],
                         "not_established")
        self.assertEqual(report["normal_mode_predicate"], "unknown")
        self.assertFalse(report["replay_approved"])


if __name__ == "__main__":
    unittest.main()
