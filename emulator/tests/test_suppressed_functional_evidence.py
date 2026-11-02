"""Eight synthetic checks for exact 29-bit suppressed functional TesterPresent.

These events are not actual VDASH traffic. Silence under 3E 80 indicates
suppressed positive response, never proven ECU identification or VIN.
"""
import json
import unittest

from test_audit_backend_evidence import audit, evt


def suppressed_events(origin="periodic_fired", *, protocol=6, baud=500000):
    kw = {"protocol": protocol, "baud": baud}
    return (
        evt(origin, **kw),
        evt("probe_classified", probe="FUNC29_TP_SUPPRESSED", **kw),
        evt("route_selected", route="ECU_OTHER", **kw),
        evt("request_completed", route="ECU_OTHER", reason="no_response",
            outcome="no_response", **kw),
    )


class FunctionalSuppressedEvidenceTests(unittest.TestCase):
    def test_01_periodic_iso_expected_silence(self):
        result = audit(*suppressed_events())
        item = result["transactions"][0]
        self.assertEqual((item["status"], item["reason"]),
                         ("suppressed", "functional_tester_present_no_rx_expected"))
        self.assertEqual(item["request_origin"], "periodic")
        self.assertEqual((item["service"], item["can_id"], item["id_format"]),
                         ("3E80", "0x18DB33F1", "29bit"))
        self.assertIsNone(item["target"])
        self.assertEqual(item["rx_dequeued"], 0)
        self.assertFalse(result["identity_verified"])

    def test_02_app_write_same_expected_silence(self):
        result = audit(*suppressed_events(origin="tx_received"))
        item = result["transactions"][0]
        self.assertEqual(item["request_origin"], "app_write")
        self.assertEqual(item["status"], "suppressed")
        self.assertFalse(result["client_acceptance_verified"])

    def test_03_raw_can_is_same_provenance_class(self):
        result = audit(*suppressed_events(origin="tx_received", protocol=5))
        item = result["transactions"][0]
        self.assertEqual(item["protocol"], "CAN")
        self.assertEqual(item["status"], "suppressed")
        self.assertEqual(item["route"], "ECU_OTHER")
        coverage = next(p for p in result["coverage"]["probes"]
                        if p["probe"] == "FUNC29_TP_SUPPRESSED")
        self.assertEqual(coverage["status_counts"], {"suppressed": 1})

    def test_04_wrong_ecu_route_cannot_be_suppressed(self):
        events = [evt("periodic_fired"),
                  evt("probe_classified", probe="FUNC29_TP_SUPPRESSED"),
                  evt("route_selected", route="CEM"),
                  evt("request_completed", route="CEM",
                      reason="no_response", outcome="no_response")]
        item = audit(*events)["transactions"][0]
        self.assertEqual((item["status"], item["reason"]),
                         ("unverified", "explicit_no_response"))

    def test_05_unexpected_rx_contradicts_expected_silence(self):
        events = [evt("periodic_fired"),
                  evt("probe_classified", probe="FUNC29_TP_SUPPRESSED"),
                  evt("route_selected", route="ECU_OTHER"),
                  evt("rx_queued", route="ECU_OTHER"),
                  evt("rx_dequeued", route="ECU_OTHER"),
                  evt("request_completed", route="ECU_OTHER",
                      reason="no_response", outcome="no_response")]
        item = audit(*events)["transactions"][0]
        self.assertEqual((item["status"], item["reason"]),
                         ("unverified", "rx_evidence_with_no_response"))

    def test_06_missing_terminal_is_not_expected_silence(self):
        item = audit(*suppressed_events()[:3])["transactions"][0]
        self.assertEqual((item["status"], item["reason"]),
                         ("unverified", "no_terminal_evidence"))
        self.assertFalse(item["terminal_seen"])

    def test_07_wrong_bus_or_protocol_fails_allowlist(self):
        for protocol, baud in ((6, 125000), (5, 250000), (4, 500000)):
            with self.subTest(protocol=protocol, baud=baud):
                result = audit(*suppressed_events(protocol=protocol, baud=baud))
                self.assertEqual(result["summary"]["invalid_lines"], 1)
                self.assertEqual(result["transactions"][0]["status"], "unverified")
                self.assertIsNone(result["transactions"][0]["service"])
                self.assertFalse(result["identity_verified"])

    def test_08_duplicate_terminal_and_private_data_not_accepted(self):
        private = "FAKE_VIN_NOT_REAL_12345678901234567"
        events = [evt("periodic_fired", vin=private),
                  evt("probe_classified", probe="FUNC29_TP_SUPPRESSED"),
                  evt("route_selected", route="ECU_OTHER"),
                  evt("request_completed", route="ECU_OTHER",
                      reason="no_response", outcome="no_response"),
                  evt("request_completed", route="ECU_OTHER",
                      reason="no_response", outcome="no_response")]
        result = audit(*events)
        self.assertEqual((result["transactions"][0]["status"],
                          result["transactions"][0]["reason"]),
                         ("unverified", "inconsistent_event_lifecycle"))
        self.assertNotIn(private, json.dumps(result))


if __name__ == "__main__":
    unittest.main()
