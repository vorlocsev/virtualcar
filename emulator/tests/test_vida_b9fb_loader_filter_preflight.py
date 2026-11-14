"""Eight offline preflight groups for documented VIDA D2 RX-ID eligibility.

Synthetic INI fragments only. No real VIN, ECU dump, active INI, or VIDA call.
"""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_b3a53_b9fb_loader import audit_text


def result(section="D2_40", response_id=None, frame=None, count="1"):
    if frame is None:
        frame = ("CB 40 F9 FB 00 00 00 00" if section == "D2_40"
                 else "CB 50 F9 FB 00 00 00 00")
    lines = [f"[{section}]", f"B9FBFrameCount={count}"]
    if response_id is not None:
        lines.append(f"ResponseId={response_id}")
    lines.append(f"B9FBFrame0={frame}")
    label = "CEM_40" if section == "D2_40" else "CEM_50"
    return audit_text("\n".join(lines) + "\n")["b9fb"][label]


class VidaB9FBLoaderFilterPreflightTests(unittest.TestCase):
    def test_01_native_default_40_is_odd_but_not_vida_verified(self):
        row = result()
        self.assertEqual(row["response_id_source"],
                         "native_default_response_id")
        self.assertEqual(row["vida2014d_d2_rx_filter_candidate"],
                         "odd_extended_id_candidate")
        self.assertFalse(row["actual_j2534_d2_filter_and_29bit_flags_verified"])

    def test_02_native_default_50_is_also_only_a_candidate(self):
        row = result("D2_50")
        self.assertEqual(row["static_loader_class"],
                         "locally_structural_reply_not_oem_verified")
        self.assertEqual(row["vida2014d_d2_rx_filter_candidate"],
                         "odd_extended_id_candidate")
        self.assertFalse(row["actual_j2534_d2_filter_and_29bit_flags_verified"])

    def test_03_explicit_even_extended_id_is_mask_mismatch_not_invalid_d2(self):
        row = result("D2_50", response_id="01200002")
        self.assertEqual(row["response_id_source"],
                         "explicit_hex_ini_response_id")
        self.assertEqual(row["static_loader_class"],
                         "locally_structural_reply_not_oem_verified")
        self.assertEqual(row["vida2014d_d2_rx_filter_candidate"],
                         "even_extended_id_mask_mismatch")

    def test_04_small_id_requires_actual_frame_width_flag(self):
        for numeric in ("701", "700"):
            with self.subTest(can_id=numeric):
                row = result(response_id=numeric)
                self.assertEqual(row["vida2014d_d2_rx_filter_candidate"],
                                 "width_unknown_without_j2534_flags")
                self.assertFalse(
                    row["actual_j2534_d2_filter_and_29bit_flags_verified"])

    def test_05_bad_response_id_uses_native_fallback_not_explicit_evidence(self):
        row = result(response_id="nothex")
        self.assertEqual(row["response_id_source"],
                         "malformed_ini_falls_back_to_native_default")
        self.assertEqual(row["vida2014d_d2_rx_filter_candidate"],
                         "odd_extended_id_candidate")
        self.assertEqual(row["static_loader_class"],
                         "locally_structural_reply_not_oem_verified")

    def test_06_out_of_range_extended_id_is_not_evaluated(self):
        row = result(response_id="20000000")
        self.assertEqual(row["static_loader_class"],
                         "response_id_outside_29bit_range")
        self.assertEqual(row["vida2014d_d2_rx_filter_candidate"],
                         "not_evaluated")

    def test_07_missing_or_invalid_b9fb_does_not_claim_filter_gate(self):
        empty = result(count="0")
        broken = result(frame="CB 50 F9 FB 00 00 00 00")
        self.assertEqual(empty["static_loader_class"], "zero_frame_count")
        self.assertEqual(broken["static_loader_class"],
                         "invalid_d2_frame_sequence")
        for row in (empty, broken):
            self.assertEqual(row["vida2014d_d2_rx_filter_candidate"],
                             "not_evaluated")

    def test_08_no_identity_or_response_id_bytes_in_report(self):
        text = ("[Vehicle]\nVIN=PRIVATE_VALUE_SHOULD_STAY_LOCAL\n"
                "[D2_50]\nB9FBFrameCount=1\n"
                "ResponseId=01200003\n"
                "B9FBFrame0=CB 50 F9 FB 00 00 00 00\n")
        output = audit_text(text)
        report = json.dumps(output)
        for prohibited in ("PRIVATE_VALUE", "01200003", "C8 50 F9",
                           "B9FBFrame0", "VIN="):
            self.assertNotIn(prohibited, report)
        self.assertFalse(output["vida_vin_accepted"])
        self.assertFalse(output["authentic_oem_cem_response"])
        for item in output["b9fb"].values():
            self.assertFalse(
                item["actual_j2534_d2_filter_and_29bit_flags_verified"])


if __name__ == "__main__":
    unittest.main()
