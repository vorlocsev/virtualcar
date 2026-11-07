"""Eight synthetic gates carrying explicit native no-response into P0 summary.

No private J2534 payload, actual A3 challenge, VIN or OEM reply is present.
"""
import json
import unittest

from test_audit_p2_discovery_boundary import tool, transaction, j2534, sectorv


def missing(service="A3", target="0x50", *, status="unsupported", timeout=False):
    tx = transaction(service, status, target=target)
    tx["reason"] = ("cem_response_not_implemented" if status == "unsupported"
                    else "cem_unimplemented_marker_rx_conflict")
    tx["native_cem_response_unimplemented"] = True
    tx["j2534_timeout_observed"] = timeout
    return tx


def b9():
    return transaction("B9FB", "delivered", target="0x50")


class NativeMissingBoundaryTests(unittest.TestCase):
    def test_01_native_a3_50_takes_priority_over_client_timeout(self):
        out = tool.audit(j2534(b9(), missing("A3", timeout=True)),
                         sectorv(), same_run_reviewed=True)
        self.assertEqual(out["first_investigation_priority"],
                         "native_cem_a3_a6_response_not_implemented")
        a3 = out["stage_evidence"]["A3_50"]
        self.assertEqual(a3["native_unimplemented_no_rx"], 1)
        self.assertEqual(a3["native_marker_followed_by_j2534_timeout"], 1)
        self.assertEqual(out["vin_accepted_by_client"], "unknown")

    def test_02_native_a6_40_kept_separate_from_a3_50(self):
        out = tool.audit(j2534(b9(), missing("A6", target="0x40")),
                         sectorv(), same_run_reviewed=True)
        self.assertEqual(out["stage_evidence"]["A6"]["native_unimplemented_no_rx"], 1)
        self.assertEqual(out["stage_evidence"]["A3_50"]["native_unimplemented_no_rx"], 0)
        self.assertEqual(out["first_investigation_priority"],
                         "native_cem_a3_a6_response_not_implemented")

    def test_03_unsupported_bus_is_not_unimplemented_reply(self):
        tx = transaction("A3", "unsupported", target="0x50")
        tx["reason"] = "strict_route_rejected"
        tx["native_cem_response_unimplemented"] = False
        out = tool.audit(j2534(b9(), tx), sectorv(), same_run_reviewed=True)
        self.assertEqual(out["stage_evidence"]["A3_50"]["native_unimplemented_no_rx"], 0)
        self.assertEqual(out["first_investigation_priority"],
                         "investigate_hardware_a3_no_reply_without_emulating_security")

    def test_04_without_same_run_review_cannot_skip_provenance(self):
        out = tool.audit(j2534(b9(), missing("A3")), sectorv())
        self.assertEqual(out["first_investigation_priority"],
                         "review_same_run_provenance_first")
        self.assertEqual(out["cross_source_transaction_attribution"], "not_established")

    def test_05_spoofed_marker_on_b9fb_or_p3_fails_closed(self):
        for bad in (transaction("B9FB", "unsupported", target="0x50"),
                    transaction("22F190", "unsupported", route="P3")):
            bad["native_cem_response_unimplemented"] = True
            bad["reason"] = "cem_response_not_implemented"
            with self.subTest(route=bad["route"]), self.assertRaises(ValueError):
                tool.audit(j2534(bad), sectorv(), same_run_reviewed=True)

    def test_06_missing_target_or_missing_reason_does_not_claim_native_evidence(self):
        cases = [missing("A3", target=None), missing("A6")]
        cases[1]["reason"] = "missing_profile"
        for bad in cases:
            with self.subTest(service=bad["service"]), self.assertRaises(ValueError):
                tool.audit(j2534(bad), sectorv(), same_run_reviewed=True)
        bad = transaction("A3", "unsupported", target="0x50")
        bad["reason"] = "cem_response_not_implemented"
        with self.assertRaises(ValueError):
            tool.audit(j2534(bad), sectorv(), same_run_reviewed=True)

    def test_07_contradictory_rx_is_unverified_not_native_no_rx(self):
        tx = missing("A6", target="0x40", status="unverified", timeout=True)
        tx["rx_frames"] = 1
        out = tool.audit(j2534(b9(), tx), sectorv(), same_run_reviewed=True)
        a6 = out["stage_evidence"]["A6"]
        self.assertEqual(a6["native_unimplemented_no_rx"], 0)
        self.assertEqual(a6["native_marker_with_unverified_rx"], 1)
        self.assertEqual(a6["native_marker_followed_by_j2534_timeout"], 1)
        self.assertEqual(out["first_investigation_priority"],
                         "investigate_hardware_a3_no_reply_without_emulating_security")
        self.assertEqual(out["ecu_identification_accepted"], "unknown")

    def test_08_boolean_types_and_private_fields_cannot_escape(self):
        for invalid in (1, None, "true", [], {}):
            bad = missing()
            bad["native_cem_response_unimplemented"] = invalid
            with self.subTest(invalid=type(invalid).__name__), self.assertRaises(ValueError):
                tool.audit(j2534(bad), sectorv(), same_run_reviewed=True)
            bad = missing()
            bad["j2534_timeout_observed"] = invalid
            with self.assertRaises(ValueError):
                tool.audit(j2534(bad), sectorv(), same_run_reviewed=True)
        private = missing()
        private["private_vin_log_path"] = "SYNTHETIC_PRIVATE_DO_NOT_COPY"
        out = tool.audit(j2534(b9(), private), sectorv(), same_run_reviewed=True)
        self.assertNotIn("SYNTHETIC_PRIVATE_DO_NOT_COPY", json.dumps(out))
        self.assertFalse(out["replay_approved"])


if __name__ == "__main__":
    unittest.main()
