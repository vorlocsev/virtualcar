"""Eight offline checks for B3A51 source-backed config/VIN isolation."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_b3a51_vin_d2_readiness as audit
sys.path.pop(0)


class B3A51Tests(unittest.TestCase):
    def test_01_default_vin_cannot_create_b9fb(self):
        out = audit.inspect_ini("[P2]\nStrictRouting=1\n")
        self.assertEqual(out["vin_origin"], "native_fallback")
        self.assertEqual(out["d2_b9fb"]["CEM_40"]["static_fixture_status"], "none_declared")
        self.assertFalse(out["readvin_via_d2_verified"])

    def test_02_explicit_ascii_vin_not_d2_reply(self):
        out = audit.inspect_ini("[Vehicle]\nVIN=YV1CZ0002A0000001\n")
        self.assertEqual(out["vin_origin"], "explicit_ini")
        self.assertEqual(out["vin_shape"], "ascii_17_character_only")
        self.assertFalse(out["original_vida_vin_acceptance_verified"])

    def test_03_invalid_vin_and_zero_declared(self):
        out = audit.inspect_ini("[Vehicle]\nVIN=abc\n[D2_50]\nB9FBFrameCount=0\n")
        self.assertEqual(out["vin_shape"], "not_ascii_17")
        self.assertEqual(out["d2_b9fb"]["CEM_50"]["declared_frame_count"], 0)

    def test_04_partial_frame_list_is_not_ready(self):
        out = audit.inspect_ini("[D2_40]\nB9FBFrameCount=2\nB9FBFrame0=AA BB CC DD EE FF 11 22\n")
        d2 = out["d2_b9fb"]["CEM_40"]
        self.assertEqual(d2["declared_frame_count"], 2)
        self.assertEqual(d2["missing_declared_frame_entries"], 1)
        self.assertEqual(d2["static_fixture_status"], "missing_frame_entries")

    def test_05_declared_complete_is_unverified_not_usable(self):
        out = audit.inspect_ini("[D2_50]\nFrameCount=2\nFrame0=PRIVATE_FRAME\nB9FBFrame1=NOT_A_REAL_D2_FRAME\n")
        d2 = out["d2_b9fb"]["CEM_50"]
        self.assertEqual(d2["static_fixture_status"], "declared_frames_not_validated")
        self.assertFalse(d2["frames_usable_by_native_verified"])
        self.assertFalse(d2["oem_origin_verified"])

    def test_06_strict_250k_is_route_mismatch_even_if_50_declared(self):
        data = audit.inspect_ini("[P2]\nStrictRouting=1\n[D2_50]\nFrameCount=1\nFrame0=FAKE\n")
        rows = [{"target": "CEM_50", "command": "B9FB", "baud_bps": "250000", "count": 3},
                {"target": "CEM_50", "command": "B9FB", "baud_bps": "500000", "count": 1}]
        got = audit.evaluate_requests(data, rows)
        self.assertEqual(got[0]["static_classification"], "strict_route_mismatch_under_current_ini")
        self.assertEqual(got[1]["static_classification"], "candidate_unverified_not_oem_rx")

    def test_07_strict_off_cannot_make_missing_fixture(self):
        data = audit.inspect_ini("[P2]\nStrictRouting=0\n")
        got = audit.evaluate_requests(data, [{"target": "CEM_50", "command": "B9FB",
                                               "baud_bps": "250000", "count": 3}])
        self.assertEqual(got[0]["static_classification"], "no_declared_b9fb_fixture")
        with self.assertRaises(ValueError):
            audit.evaluate_requests(data, [{"target": "CEM_50", "command": "B9FC",
                                               "baud_bps": "500000", "count": 1}])

    def test_08_fail_closed_invalid_number_dup_and_no_privacy_leak(self):
        config = ("[Vehicle]\nVIN=PRIVATE_VIN_12345\n[D2_40]\n"
                  "B9FBFrameCount=0x40\nB9FBFrame0=PRIVATE_RAW_DATA\n")
        result = audit.inspect_ini(config)
        self.assertEqual(result["d2_b9fb"]["CEM_40"]["declared_frame_count"], 64)
        encoded = json.dumps(result)
        self.assertNotIn("PRIVATE_VIN", encoded)
        self.assertNotIn("PRIVATE_RAW_DATA", encoded)
        self.assertNotIn("YV1CZ", encoded)
        self.assertNotIn("C:\\", encoded)
        with self.assertRaises(Exception):
            audit.inspect_ini("[D2_40]\nFrameCount=1\n[D2_40]\nFrameCount=0\n")
        self.assertEqual(audit._native_num("garbage", 0), 0)


if __name__ == "__main__":
    unittest.main()
