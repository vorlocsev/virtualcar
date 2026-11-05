"""Eight synthetic checks for OBD VIN request -> CEM probe TX ordering.

No VIN bytes, original ECU replies, or client session predicates are used.
Order is first appearance of *trusted allowlisted request shapes* in JSONL.
"""
import json
import unittest

from test_audit_backend_evidence import audit, evt


def tx(probe, rid, *, sid="0123456789abcdef", root="tx_received",
       protocol=5, baud=500000, route="CEM", reason="missing_profile"):
    parts = [
        evt(root, rid=rid, sid=sid, protocol=protocol, baud=baud),
        evt("probe_classified", rid=rid, sid=sid, protocol=protocol,
            baud=baud, probe=probe),
        evt("route_selected", rid=rid, sid=sid, protocol=protocol,
            baud=baud, route=route),
        evt("request_completed", rid=rid, sid=sid, protocol=protocol,
            baud=baud, route=route, reason=reason, outcome="no_response"),
    ]
    return tuple(parts)


def vin(rid, *, sid="0123456789abcdef", root="tx_received"):
    return tx("OBD_FUNC_VIN_0902", rid, sid=sid, root=root,
              protocol=6, route="ECU_OTHER", reason="no_response")


def cem(rid, *, sid="0123456789abcdef", root="tx_received"):
    return tx("D2_50_B9FB", rid, sid=sid, root=root)


class VinCemOrderingTests(unittest.TestCase):
    def test_01_same_session_vin_then_cem(self):
        r = audit(*vin(1), *cem(2))
        flow = r["vin_cem_observation"]["sessions"][0]
        self.assertEqual(flow["observation"], "vin_tx_then_cem_probe_tx")
        self.assertEqual((flow["vin_request_count"], flow["cem_probe_count"],
                          flow["cem_before_first_vin"], flow["cem_after_first_vin"]),
                         (1, 1, 0, 1))
        self.assertFalse(r["client_acceptance_verified"])

    def test_02_cem_before_vin_does_not_count_as_after(self):
        r = audit(*cem(1), *vin(2))
        flow = r["vin_cem_observation"]["sessions"][0]
        self.assertEqual(flow["observation"], "vin_tx_no_later_cem_probe_observed")
        self.assertEqual((flow["cem_before_first_vin"], flow["cem_after_first_vin"]),
                         (1, 0))

    def test_03_vin_alone_is_not_accepted_vin(self):
        r = audit(*vin(1))
        flow = r["vin_cem_observation"]["sessions"][0]
        self.assertEqual((flow["vin_request_count"], flow["cem_probe_count"]),
                         (1, 0))
        self.assertEqual(flow["observation"], "vin_tx_no_later_cem_probe_observed")
        self.assertFalse(r["identity_verified"])

    def test_04_cem_alone_is_not_missing_vin_or_ecu(self):
        r = audit(*cem(1))
        flow = r["vin_cem_observation"]["sessions"][0]
        self.assertEqual(flow["observation"], "cem_probe_without_observed_obd_vin")
        self.assertIsNone(flow["cem_after_first_vin"])
        self.assertEqual(flow["cem_probe_count"], 1)

    def test_05_session_boundary_never_creates_vin_then_cem(self):
        second = "fedcba9876543210"
        r = audit(*vin(1), *cem(1, sid=second))
        flows = r["vin_cem_observation"]["sessions"]
        self.assertEqual(len(flows), 2)
        self.assertEqual([x["observation"] for x in flows], [
            "vin_tx_no_later_cem_probe_observed",
            "cem_probe_without_observed_obd_vin",
        ])
        self.assertNotIn(second, json.dumps(r))

    def test_06_first_vin_is_anchoring_request(self):
        r = audit(*cem(1), *vin(2), *cem(3), *vin(4), *cem(5))
        flow = r["vin_cem_observation"]["sessions"][0]
        self.assertEqual((flow["vin_request_count"], flow["cem_probe_count"]),
                         (2, 3))
        self.assertEqual((flow["cem_before_first_vin"], flow["cem_after_first_vin"]),
                         (1, 2))
        self.assertEqual(flow["observation"], "vin_tx_then_cem_probe_tx")

    def test_07_conflicting_probe_not_used_for_sequence(self):
        events = [evt("tx_received", rid=1),
                  evt("probe_classified", rid=1, probe="OBD_FUNC_VIN_0902"),
                  evt("route_selected", rid=1, route="ECU_OTHER"),
                  evt("route_selected", rid=1, route="CEM"),
                  evt("request_completed", rid=1, route="CEM",
                      reason="missing_profile", outcome="no_response")]
        r = audit(*events, *cem(2))
        flow = r["vin_cem_observation"]["sessions"][0]
        self.assertEqual(flow["observation"], "cem_probe_without_observed_obd_vin")
        self.assertEqual(flow["vin_request_count"], 0)
        self.assertEqual(r["transactions"][0]["status"], "unverified")

    def test_08_wrong_transport_privacy_and_empty_input(self):
        for bad_protocol, bad_baud in ((6, 125000), (5, 250000), (4, 500000)):
            with self.subTest(protocol=bad_protocol, baud=bad_baud):
                values = [evt("tx_received", rid=1, protocol=bad_protocol,
                              baud=bad_baud, vin="SYNTHETIC_PRIVATE_VIN"),
                          evt("probe_classified", rid=1,
                              protocol=bad_protocol, baud=bad_baud,
                              probe="OBD_FUNC_VIN_0902"),
                          evt("request_completed", rid=1, protocol=bad_protocol,
                              baud=bad_baud, route="ECU_OTHER",
                              reason="no_response", outcome="no_response")]
                result = audit(*values)
                self.assertEqual(result["summary"]["invalid_lines"], 1)
                self.assertEqual(result["vin_cem_observation"]["sessions"][0][
                    "vin_request_count"], 0)
                self.assertNotIn("SYNTHETIC_PRIVATE_VIN", json.dumps(result))
        empty = audit()
        self.assertEqual(empty["vin_cem_observation"]["sessions"], [])
        self.assertFalse(empty["identity_verified"])


if __name__ == "__main__":
    unittest.main()
