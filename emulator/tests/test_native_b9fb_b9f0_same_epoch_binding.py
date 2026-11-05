"""Eight native B9FB -> B9F0 positive-binding regressions.

A fully formed D2 B9F0 RX in a log is not enough: the native channel
chronology and independent first-next-TX audit must agree it directly
followed one completed B9FB in the same closed source epoch.
Everything is synthetic; no proprietary diagnostic client is executed.
"""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tests"))

import prepare_p2_capture as capture
import prepare_p2_client_run as client
from test_prepare_p2_client_run import session, GOOD_CONNECT
from test_audit_d2_followup_window import D2FB, A3, marker, tx, response, rx
from test_native_b9f0_response import F0, NEG, POS, f0_response
from test_native_p2_p3_single_run_gate import parts

CLOSE = [marker("PassThruClose")]


def evaluated(lines):
    return capture.prepare("\n".join(lines))["capture-summary.json"][
        "b9fb_to_b9f0_same_epoch_positive_binding"]


def full():
    return parts()[0] + parts()[1] + parts()[2] + CLOSE


class NativeB9FBB9F0CrossBindingTests(unittest.TestCase):
    def test_01_positive_single_epoch_is_transport_only(self):
        report = evaluated(full())
        self.assertEqual(report["status"],
                         "direct_positive_b9f0_transport_same_native_epoch")
        self.assertTrue(report["direct_b9fb_to_b9f0_request_cross_audit_verified"])
        self.assertTrue(report["positive_b9f0_transport_bound_to_direct_first_read"])
        self.assertFalse(report["genuine_cem_identity_verified"])
        self.assertFalse(report["application_checksum_verified"])
        self.assertFalse(report["client_b9f0_acceptance_verified"])

    def test_02_direct_negative_service_reply_is_not_positive(self):
        lines = parts()[0] + tx(F0, at=1_132_000) + rx(NEG, at=1_142_000) + CLOSE
        summary = evaluated(lines)
        self.assertEqual(summary["status"], "direct_negative_b9f0_service_reply")
        self.assertTrue(summary["direct_b9fb_to_b9f0_request_cross_audit_verified"])
        self.assertFalse(summary["positive_b9f0_transport_bound_to_direct_first_read"])

    def test_03_partial_b9f0_does_not_complete_pair(self):
        lines = (parts()[0] + tx(F0, at=1_132_000)
                 + f0_response(start=1_142_000, payloads=POS[:2]) + CLOSE)
        summary = evaluated(lines)
        self.assertEqual(summary["status"],
                         "direct_b9f0_transport_incomplete_or_unverified")
        self.assertFalse(summary["positive_b9f0_transport_bound_to_direct_first_read"])

    def test_04_positive_later_b9f0_after_a3_is_not_direct_handoff(self):
        lines = (parts()[0] + tx(A3, at=1_100_000)
                 + parts()[1] + parts()[2] + CLOSE)
        summary = evaluated(lines)
        self.assertEqual(summary["status"],
                         "no_independent_direct_first_b9f0_request_pair")
        self.assertFalse(summary["positive_b9f0_transport_bound_to_direct_first_read"])
        with_ui = "\n".join(GOOD_CONNECT + lines)
        note = client.prepare(with_ui)["client-boundary.json"]
        self.assertEqual(note["b9f0_positive_transport_count"], 1)
        self.assertFalse(note["direct_b9fb_b9f0_positive_transport_bound"])
        self.assertEqual(note["diagnostic_focus"],
                         "b9fb_b9f0_positive_transport_not_directly_bound")

    def test_05_two_b9f0_requests_make_positive_attribution_ambiguous(self):
        lines = (parts()[0] + parts()[1]
                 + tx(F0, at=1_190_000)
                 + f0_response(start=1_192_000) + CLOSE)
        result = evaluated(lines)
        self.assertTrue(result["direct_b9fb_to_b9f0_request_cross_audit_verified"])
        self.assertEqual(result["status"], "multiple_or_unmatched_b9f0_requests")
        self.assertFalse(result["positive_b9f0_transport_bound_to_direct_first_read"])

    def test_06_two_completed_b9fb_reads_cannot_claim_one_predecessor(self):
        lines = (parts()[0]
                 + tx(D2FB, at=1_050_000)
                 + response(first=1_070_000)
                 + tx(F0, at=1_232_000)
                 + f0_response(start=1_242_000) + CLOSE)
        result = evaluated(lines)
        self.assertEqual(result["status"], "not_exactly_one_completed_b9fb")
        self.assertFalse(result["positive_b9f0_transport_bound_to_direct_first_read"])

    def test_07_separate_epochs_or_unclosed_source_not_one_handoff(self):
        separately = (parts()[0] + CLOSE + parts()[1] + CLOSE)
        report = evaluated(separately)
        self.assertEqual(report["status"], "multiple_or_missing_native_epochs")
        self.assertFalse(report["positive_b9f0_transport_bound_to_direct_first_read"])
        unclosed = evaluated(parts()[0] + parts()[1])
        self.assertEqual(unclosed["status"], "native_epoch_not_closed")

    def test_08_independent_target_mismatch_private_and_unverified(self):
        source = "\n".join(full())
        original = capture.audit_b9f0(source)
        altered = copy.deepcopy(original)
        altered["observations"][0]["target"] = "0x40"
        with patch.object(capture, "audit_b9f0", return_value=altered):
            summary = capture.prepare(source)["capture-summary.json"]
        binding = summary["b9fb_to_b9f0_same_epoch_positive_binding"]
        self.assertEqual(binding["status"],
                         "b9f0_response_target_disagrees_with_direct_request")
        self.assertFalse(binding["positive_b9f0_transport_bound_to_direct_first_read"])
        public = json.dumps(summary)
        for hidden in ("ABCDEF12", "VCARLAB0000000000", "PRIVATE_CLIENT",
                       "62 F1 14", "F9 F0", "0x01000003"):
            self.assertNotIn(hidden, public)
        self.assertFalse(summary["same_run_with_sectorv_client_verified"])
        self.assertFalse(summary["xc90_v8_my2009_verified"])


if __name__ == "__main__":
    unittest.main()
