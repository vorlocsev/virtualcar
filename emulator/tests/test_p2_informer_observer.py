"""Eight bounded, synthetic evidence checks for upstream P2 Informer probes."""
import json
import unittest
from test_audit_backend_evidence import audit, evt, tool

INFO = (
    ("P2INF_LS_VIN_F190", "22F190", 125000),
    ("P2INF_LS_REM_A6", "A6", 125000),
    ("P2INF_LS_CCM_A6", "A6", 125000),
    ("P2INF_HS_ECM_A6", "A6", 500000),
    ("P2INF_HS_TCM_A5", "A5", 500000),
    ("P2INF_HS_DEM_A6", "A6", 500000),
)


def probe_event(probe, *, rid=1, kind="probe_classified", **extra):
    baud = 125000 if "_LS_" in probe else 500000
    return evt(kind, rid=rid, probe=probe, baud=baud, **extra)


class P2InformerObserverTests(unittest.TestCase):
    def test_01_six_allowlisted_source_shapes_have_no_invented_target(self):
        for token, service, baud in INFO:
            with self.subTest(token=token):
                info = tool.PROBES[token]
                self.assertEqual(info, {
                    "service": service, "can_id": "0x000FFFFE",
                    "id_format": "29bit", "target": None,
                })
                self.assertEqual(baud, 125000 if "_LS_" in token else 500000)

    def test_02_all_six_silent_unhandled_requests_keep_precise_coverage(self):
        rows = []
        for index, (token, service, baud) in enumerate(INFO, 1):
            rows.extend((
                evt("tx_received", rid=index, baud=baud),
                probe_event(token, rid=index),
                evt("request_completed", rid=index, baud=baud,
                    route="UNHANDLED", reason="unhandled_request",
                    outcome="no_response"),
            ))
        result = audit(*rows)
        self.assertEqual(result["summary"]["requests"], 6)
        self.assertEqual(result["summary"]["statuses"], {"unsupported": 6})
        self.assertEqual(result["coverage"]["attributed_requests"], 6)
        self.assertEqual(result["coverage"]["unattributed_requests"], 0)
        by_token = {x["probe"]: x for x in result["coverage"]["probes"]}
        for token, service, baud in INFO:
            self.assertEqual(by_token[token]["status_counts"], {"unsupported": 1})
            self.assertEqual(by_token[token]["observed_requests"], 1)
        self.assertTrue(all(x["rx_queued"] == x["rx_dequeued"] == 0
                            for x in result["transactions"]))

    def test_03_no_claim_that_vin_or_ecu_was_accepted(self):
        token = INFO[0][0]
        result = audit(evt("tx_received", rid=4, baud=125000),
                       probe_event(token, rid=4),
                       evt("request_completed", rid=4, baud=125000,
                           reason="no_response", outcome="no_response"))
        tx = result["transactions"][0]
        self.assertEqual(tx["status"], "unverified")
        self.assertEqual(tx["service"], "22F190")
        self.assertIsNone(tx["target"])
        self.assertFalse(result["client_acceptance_verified"])
        self.assertFalse(result["identity_verified"])

    def test_04_malformed_tokens_and_raw_payload_are_never_reflected(self):
        secret = "USER_PRIVATE_VIN_SHOULD_NOT_ESCAPE"
        result = audit(evt("tx_received", rid=8, baud=125000,
                           raw_payload=secret, vin=secret),
                       probe_event("P2INF_LS_VIN_F190", rid=8, vin=secret),
                       evt("probe_classified", rid=9, probe=secret,
                           baud=125000, raw_payload=secret),
                       evt("request_completed", rid=8, baud=125000,
                           route="UNHANDLED", reason="unhandled_request",
                           outcome="no_response"))
        self.assertEqual(result["summary"]["invalid_lines"], 1)
        self.assertNotIn(secret, json.dumps(result))
        self.assertEqual(result["coverage"]["attributed_requests"], 1)

    def test_05_wrong_protocol_and_wrong_baud_tokens_fail_closed(self):
        for token, _, baud in INFO:
            with self.subTest(token=token):
                wrong = 500000 if baud == 125000 else 125000
                for changed in ({"protocol": 6}, {"baud": wrong}):
                    obj = json.loads(probe_event(token))
                    obj.update(changed)
                    self.assertIsNone(tool._decode(json.dumps(obj)))

    def test_06_conflicting_probe_evidence_cannot_claim_coverage(self):
        result = audit(evt("tx_received", rid=11, baud=125000),
                       probe_event("P2INF_LS_VIN_F190", rid=11),
                       probe_event("P2INF_LS_REM_A6", rid=11),
                       evt("request_completed", rid=11, baud=125000,
                           reason="unhandled_request", outcome="no_response"))
        self.assertEqual(result["transactions"][0]["status"], "unverified")
        self.assertEqual(result["transactions"][0]["reason"], "conflicting_probe_evidence")
        self.assertEqual(result["coverage"]["attributed_requests"], 0)

    def test_07_no_tx_or_terminal_never_becomes_delivered(self):
        result = audit(probe_event("P2INF_LS_VIN_F190", rid=1),
                       evt("tx_received", rid=2, baud=500000),
                       probe_event("P2INF_HS_ECM_A6", rid=2))
        self.assertEqual(result["summary"]["requests"], 2)
        self.assertEqual([x["status"] for x in result["transactions"]],
                         ["unverified", "unverified"])
        self.assertNotIn("delivered", result["summary"]["statuses"])
        self.assertFalse(result["identity_verified"])

    def test_08_legacy_d2_p3_matrix_is_not_replaced(self):
        self.assertEqual(len(tool.PROBES), 27)
        self.assertEqual(tool.PROBES["FUNC29_TP_SUPPRESSED"], {
            "service": "3E80", "can_id": "0x18DB33F1",
            "id_format": "29bit", "target": None,
        })
        for token in ("D2_40_B9FB", "D2_50_A3", "P3_726_F114",
                      "P3_29_F190"):
            self.assertIn(token, tool.PROBES)
        result = audit(evt("tx_received", rid=1, baud=500000),
                       evt("probe_classified", rid=1, probe="D2_50_B9FB"),
                       evt("request_completed", rid=1, route="CEM",
                           reason="missing_profile", outcome="no_response"))
        self.assertEqual(result["summary"]["statuses"], {"no_fixture": 1})
        self.assertEqual(result["transactions"][0]["service"], "B9FB")
        self.assertEqual(len(result["coverage"]["probes"]), 27)


if __name__ == "__main__":
    unittest.main()
