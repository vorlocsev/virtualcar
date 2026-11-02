"""Eight synthetic gates for route metadata; no raw VMware log or ECU identity."""
import json
import os
from pathlib import Path
import unittest

from test_audit_backend_evidence import audit, evt, tool


class VMwareRouteEvidenceTests(unittest.TestCase):
    def test_01_legacy_route_conflict_stays_unverified(self):
        result = audit(evt("tx_received"), evt("route_selected", route="ECM"),
                       evt("request_completed", route="ECU_OTHER",
                           reason="no_response", outcome="no_response"))
        one = result["transactions"][0]
        self.assertEqual((one["status"], one["reason"]),
                         ("unverified", "inconsistent_route_or_channel"))
        self.assertEqual(one["observed_routes"], ["ECM", "ECU_OTHER"])
        self.assertEqual(one["evidence_conflicts"], ["route"])
        self.assertEqual(one["route"], "UNKNOWN")

    def test_02_channel_conflict_is_distinct(self):
        one = audit(evt("tx_received"), evt("request_completed", channel=2,
                    route="CEM", outcome="no_response"))["transactions"][0]
        self.assertEqual(one["evidence_conflicts"], ["channel"])
        self.assertEqual(one["observed_routes"], ["CEM"])
        self.assertEqual(one["status"], "unverified")

    def test_03_protocol_and_baud_conflicts_are_distinct(self):
        for changes, expected in [({"protocol": 6}, ["protocol"]),
                                  ({"baud": 125000}, ["baud"]),
                                  ({"channel": 2, "protocol": 6, "baud": 125000},
                                   ["baud", "channel", "protocol"])]:
            with self.subTest(changes=changes):
                one = audit(evt("tx_received"), evt("request_completed",
                            outcome="responded", **changes))["transactions"][0]
                self.assertEqual(one["evidence_conflicts"], expected)
                self.assertEqual(one["status"], "unverified")

    def test_04_fixed_silent_routes_do_not_infer_probe_or_success(self):
        for route in ("CEM", "ECM", "ECU_OTHER"):
            one = audit(evt("tx_received"), evt("route_selected", route=route),
                        evt("request_completed", route=route, reason="no_response",
                            outcome="no_response"))["transactions"][0]
            self.assertEqual(one["evidence_conflicts"], [])
            self.assertEqual((one["status"], one["reason"]),
                             ("unverified", "explicit_no_response"))
            self.assertIsNone(one["service"])

    def test_05_interleaved_channels_stay_independent(self):
        one = audit(evt("tx_received", rid=1),
                    evt("tx_received", rid=2, channel=2, baud=125000),
                    evt("request_completed", rid=1, route="ECM",
                        reason="no_response", outcome="no_response"),
                    evt("request_completed", rid=2, channel=2, baud=125000,
                        route="CEM", reason="missing_profile", outcome="no_response"))
        self.assertEqual([t["evidence_conflicts"] for t in one["transactions"]], [[], []])
        self.assertEqual([t["status"] for t in one["transactions"]], ["unverified", "no_fixture"])

    def test_06_privacy_fields_cannot_spoof_conflict_details(self):
        marker = "SYNTHETIC_PRIVATE_NOT_FROM_VEHICLE"
        result = audit(evt("tx_received", observed_routes=[marker],
                           evidence_conflicts=[marker], raw_payload=marker),
                       evt("route_selected", route="CEM"),
                       evt("request_completed", route="ECU_OTHER", outcome="responded"))
        self.assertNotIn(marker, json.dumps(result))
        self.assertEqual(result["transactions"][0]["evidence_conflicts"], ["route"])
        self.assertFalse(result["identity_verified"])

    def test_07_conflicts_do_not_hide_other_lifecycle_failures(self):
        result = audit(evt("tx_received"), evt("rx_dequeued", route="CEM"),
                       evt("request_completed", route="CEM", outcome="responded"))
        one = result["transactions"][0]
        self.assertEqual(one["evidence_conflicts"], [])
        self.assertEqual(one["reason"], "dequeue_without_queue")

    def test_08_real_c_emitter_to_python_auditor(self):
        path = os.environ.get("VIRTUALCAR_ROUTE_EVIDENCE")
        if not path:
            self.skipTest("Set VIRTUALCAR_ROUTE_EVIDENCE when running the C harness first")
        with Path(path).open(encoding="utf-8") as source:
            result = tool.audit(source)
        self.assertEqual(result["summary"]["invalid_lines"], 0)
        self.assertEqual(result["summary"]["requests"], 21)
        # Frozen C-emitter fixture precedes periodic tests and contains only
        # direct application writes. Counts do not prove an ECU exists.
        self.assertEqual(result["summary"]["request_origins"], {"app_write": 21})
        self.assertEqual(result["summary"]["statuses"],
                         {"unverified": 11, "suppressed": 2, "no_fixture": 3,
                          "unsupported": 3, "delivered": 2})
        for one in result["transactions"]:
            self.assertEqual(one["evidence_conflicts"], [])
            self.assertTrue(one["terminal_seen"])
        self.assertEqual(result["coverage"]["attributed_requests"], 5)
        keepalive = next(p for p in result["coverage"]["probes"]
                         if p["probe"] == "FUNC29_TP_SUPPRESSED")
        self.assertEqual(keepalive["status_counts"], {"suppressed": 2})
        self.assertEqual(keepalive["by_origin"], {"app_write": {"suppressed": 2}})
        self.assertEqual(keepalive["observed_requests"], 2)
        self.assertFalse(result["identity_verified"])
        self.assertFalse(result["client_acceptance_verified"])


if __name__ == "__main__":
    unittest.main()
