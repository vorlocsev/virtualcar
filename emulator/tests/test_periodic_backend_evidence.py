"""Eight synthetic regressions for distinct J2534 periodic and app-write origins.

These fixtures contain only allowlisted backend metadata. They are not
captured VDASH traffic and cannot establish ECU acceptance or identity.
"""
import json
import unittest

from test_audit_backend_evidence import audit, evt


class PeriodicBackendEvidenceTests(unittest.TestCase):
    def test_01_periodic_no_fixture_has_explicit_origin(self):
        r = audit(evt("periodic_fired"),
                  evt("probe_classified", probe="D2_40_B9FB"),
                  evt("route_selected", route="CEM"),
                  evt("request_completed", route="CEM",
                      reason="missing_profile", outcome="no_response"))
        t = r["transactions"][0]
        self.assertEqual(t["request_origin"], "periodic")
        self.assertEqual((t["status"], t["reason"]),
                         ("no_fixture", "explicit_missing_profile"))
        self.assertEqual(t["service"], "B9FB")
        self.assertFalse(r["identity_verified"])

    def test_02_app_write_origin_remains_separate(self):
        r = audit(evt("tx_received"),
                  evt("request_completed", route="ECU_OTHER",
                      reason="no_response", outcome="no_response"))
        t = r["transactions"][0]
        self.assertEqual(t["request_origin"], "app_write")
        self.assertEqual(t["status"], "unverified")

    def test_03_repeated_periodic_firings_are_distinct_requests(self):
        r = audit(evt("periodic_fired", rid=1),
                  evt("request_completed", rid=1, route="ECU_OTHER",
                      reason="no_response", outcome="no_response"),
                  evt("periodic_fired", rid=2, tick=2000000),
                  evt("request_completed", rid=2, tick=2000000,
                      route="ECU_OTHER", reason="no_response",
                      outcome="no_response"))
        self.assertEqual(r["summary"]["requests"], 2)
        self.assertEqual([t["request_origin"] for t in r["transactions"]],
                         ["periodic", "periodic"])
        self.assertFalse(r["client_acceptance_verified"])

    def test_04_periodic_then_write_with_same_rid_is_conflict(self):
        r = audit(evt("periodic_fired"),
                  evt("tx_received"),
                  evt("request_completed", route="ECM",
                      reason="no_response", outcome="no_response"))
        t = r["transactions"][0]
        self.assertEqual(t["request_origin"], "unknown")
        self.assertEqual((t["status"], t["reason"]),
                         ("unverified", "inconsistent_event_lifecycle"))

    def test_05_periodic_rx_delivery_is_not_ecu_acceptance(self):
        r = audit(evt("periodic_fired"),
                  evt("route_selected", route="ECM"),
                  evt("response_generated", route="ECM"),
                  evt("rx_queued", route="ECM"),
                  evt("rx_dequeued", route="ECM", tick=1020000),
                  evt("request_completed", route="ECM",
                      outcome="responded", tick=1020000))
        t = r["transactions"][0]
        self.assertEqual(t["request_origin"], "periodic")
        self.assertEqual(t["status"], "delivered")
        self.assertEqual(t["elapsed_ms"], 20)
        self.assertFalse(r["client_acceptance_verified"])

    def test_06_private_payload_is_ignored_for_periodic(self):
        private = "FAKE_VIN_12345678901234567_DO_NOT_EXPORT"
        r = audit(evt("periodic_fired", raw_can=private, vin=private),
                  evt("request_completed", route="ECU_OTHER",
                      reason="no_response", outcome="no_response",
                      account_token=private))
        self.assertNotIn(private, json.dumps(r))
        self.assertFalse(r["contains_payload_data"])

    def test_07_periodic_terminal_without_root_is_unverified(self):
        r = audit(evt("request_completed", route="CEM",
                      reason="missing_profile", outcome="no_response"))
        self.assertEqual(r["transactions"][0]["request_origin"], "unknown")
        self.assertEqual(r["transactions"][0]["status"], "unverified")
        self.assertEqual(r["transactions"][0]["reason"],
                         "inconsistent_event_lifecycle")

    def test_08_periodic_context_conflict_does_not_verify_route(self):
        r = audit(evt("periodic_fired", channel=1, protocol=5,
                      baud=500000),
                  evt("route_selected", route="CEM", channel=2,
                      protocol=5, baud=500000),
                  evt("request_completed", route="CEM", channel=1,
                      protocol=5, baud=500000,
                      reason="missing_profile", outcome="no_response"))
        t = r["transactions"][0]
        self.assertEqual(t["request_origin"], "periodic")
        self.assertEqual(t["status"], "unverified")
        self.assertEqual(t["reason"], "inconsistent_route_or_channel")
        self.assertEqual(t["evidence_conflicts"], ["channel"])


    @staticmethod
    def _suppressed(origin, rid):
        return (
            evt(origin, rid=rid),
            evt("probe_classified", rid=rid, probe="FUNC29_TP_SUPPRESSED"),
            evt("route_selected", rid=rid, route="ECU_OTHER"),
            evt("request_completed", rid=rid, route="ECU_OTHER",
                reason="no_response", outcome="no_response"),
        )

    def test_09_mixed_known_keepalive_by_origin(self):
        r = audit(*self._suppressed("periodic_fired", 1),
                  *self._suppressed("tx_received", 2))
        self.assertEqual(r["summary"]["request_origins"],
                         {"app_write": 1, "periodic": 1})
        p = next(p for p in r["coverage"]["probes"]
                 if p["probe"] == "FUNC29_TP_SUPPRESSED")
        self.assertEqual(p["observed_requests"], 2)
        self.assertEqual(p["status_counts"], {"suppressed": 2})
        self.assertEqual(p["by_origin"], {
            "app_write": {"suppressed": 1},
            "periodic": {"suppressed": 1},
        })
        self.assertFalse(r["identity_verified"])

    def test_10_same_cem_probe_two_different_sources(self):
        def cem(source, rid):
            return (
                evt(source, rid=rid),
                evt("probe_classified", rid=rid, probe="D2_40_B9FB"),
                evt("route_selected", rid=rid, route="CEM"),
                evt("request_completed", rid=rid, route="CEM",
                    reason="missing_profile", outcome="no_response"),
            )
        r = audit(*cem("tx_received", 1), *cem("periodic_fired", 2))
        p = next(x for x in r["coverage"]["probes"] if x["probe"] == "D2_40_B9FB")
        self.assertEqual(p["by_origin"], {
            "app_write": {"no_fixture": 1},
            "periodic": {"no_fixture": 1},
        })
        self.assertEqual(p["status_counts"], {"no_fixture": 2})
        self.assertFalse(r["client_acceptance_verified"])

    def test_11_status_counts_remain_distinct_within_origin(self):
        r = audit(
            evt("tx_received", rid=1),
            evt("probe_classified", rid=1, probe="D2_40_B9FB"),
            evt("route_selected", rid=1, route="CEM"),
            evt("request_completed", rid=1, route="CEM",
                reason="missing_profile", outcome="no_response"),
            evt("periodic_fired", rid=2),
            evt("probe_classified", rid=2, probe="D2_40_B9FB"),
            evt("route_selected", rid=2, route="CEM"),
            evt("request_completed", rid=2, route="CEM",
                reason="no_response", outcome="no_response"))
        p = next(x for x in r["coverage"]["probes"] if x["probe"] == "D2_40_B9FB")
        self.assertEqual(p["status_counts"], {"no_fixture": 1, "unverified": 1})
        self.assertEqual(p["by_origin"], {
            "app_write": {"no_fixture": 1},
            "periodic": {"unverified": 1},
        })

    def test_12_unattributed_sources_count_only_in_summary(self):
        r = audit(evt("tx_received", rid=1),
                  evt("request_completed", rid=1, route="ECU_OTHER",
                      reason="no_response", outcome="no_response"),
                  evt("periodic_fired", rid=2),
                  evt("request_completed", rid=2, route="ECU_OTHER",
                      reason="no_response", outcome="no_response"))
        self.assertEqual(r["coverage"]["attributed_requests"], 0)
        self.assertEqual(r["coverage"]["unattributed_requests"], 2)
        self.assertEqual(r["summary"]["request_origins"],
                         {"app_write": 1, "periodic": 1})
        self.assertTrue(all(not p["by_origin"] for p in r["coverage"]["probes"]))

    def test_13_conflicting_origin_cannot_claim_probe_coverage(self):
        r = audit(evt("periodic_fired"),
                  evt("tx_received"),
                  evt("probe_classified", probe="FUNC29_TP_SUPPRESSED"),
                  evt("route_selected", route="ECU_OTHER"),
                  evt("request_completed", route="ECU_OTHER",
                      reason="no_response", outcome="no_response"))
        self.assertEqual(r["summary"]["request_origins"], {"unknown": 1})
        self.assertEqual(r["coverage"]["attributed_requests"], 0)
        self.assertEqual(r["coverage"]["unattributed_requests"], 1)
        self.assertEqual(r["summary"]["statuses"], {"unverified": 1})

    def test_14_duplicate_request_id_from_two_sessions_is_separate(self):
        second_session = "fedcba9876543210"
        r = audit(*self._suppressed("tx_received", 1),
                  evt("periodic_fired", sid=second_session, rid=1),
                  evt("probe_classified", sid=second_session, rid=1,
                      probe="FUNC29_TP_SUPPRESSED"),
                  evt("route_selected", sid=second_session, rid=1,
                      route="ECU_OTHER"),
                  evt("request_completed", sid=second_session, rid=1,
                      route="ECU_OTHER", reason="no_response",
                      outcome="no_response"))
        self.assertEqual(r["summary"]["sessions"], 2)
        self.assertEqual(r["summary"]["request_origins"],
                         {"app_write": 1, "periodic": 1})
        self.assertNotIn(second_session, json.dumps(r))

    def test_15_private_untrusted_fields_cannot_inflate_origins(self):
        marker = "SYNTHETIC_VIN_DO_NOT_EMIT_ABCDEFG"
        r = audit(evt("periodic_fired", rid=1, origin=marker, vin=marker),
                  evt("request_completed", rid=1, route="ECU_OTHER",
                      reason="no_response", outcome="no_response",
                      source=marker))
        self.assertEqual(r["summary"]["request_origins"], {"periodic": 1})
        self.assertNotIn(marker, json.dumps(r))
        self.assertFalse(r["contains_payload_data"])

    def test_16_empty_input_has_no_fake_origin_or_discovery(self):
        r = audit()
        self.assertEqual(r["summary"]["requests"], 0)
        self.assertEqual(r["summary"]["request_origins"], {})
        self.assertEqual(r["coverage"]["attributed_requests"], 0)
        self.assertTrue(all(not p["by_origin"] for p in r["coverage"]["probes"]))
        self.assertFalse(r["identity_verified"])


if __name__ == "__main__":
    unittest.main()
