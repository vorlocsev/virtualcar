"""Eight synthetic gates for private VIN vs D2 B9FB consistency audit."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import audit_vida_b3a54_private_b9fb_vin as audit
from test_audit_p2_b9fb_shape import LAB_VIN, content, frames
sys.path.pop(0)


def profile(source=None, vin=LAB_VIN.decode(), provenance="unverified_private"):
    source = frames() if source is None else source
    rows = [
        "[Vehicle]", "VIN=" + vin, "[P2]", "FixtureProvenance=" + provenance,
        "[D2_50]", "ResponseId=01200003", "B9FBFrameCount=" + str(len(source)),
    ]
    for i, (_id, data) in enumerate(source):
        rows.append(f"B9FBFrame{i:X}=" + data.hex(" ").upper())
    return "\n".join(rows) + "\n"


class PrivateB9FBVinTests(unittest.TestCase):
    def test_01_known_synthetic_vin_matches_observed_field(self):
        out = audit.inspect_profiles(profile())
        self.assertEqual(out["d2_transport"], "complete")
        self.assertEqual(out["published_88_byte_shape"], "matches_one_observed_example")
        self.assertEqual(out["vin_field_vs_private_vin"], "equal")
        self.assertEqual(out["observed_six_digit_field_vs_vin_suffix"], "equal")
        self.assertFalse(out["replay_approved"])

    def test_02_changing_only_private_vin_detects_mismatch(self):
        out = audit.inspect_profiles(profile(vin="YV1CZ0002A0000002"))
        self.assertEqual(out["vin_field_vs_private_vin"], "different")
        self.assertFalse(out["oem_my2009_origin_verified"])

    def test_03_malformed_vin_field_cannot_promote_identity(self):
        altered = frames(content(vin=b"AB-CDE0002A000000"))
        out = audit.inspect_profiles(profile(source=altered))
        self.assertEqual(out["d2_transport"], "complete")
        self.assertEqual(out["published_88_byte_shape"], "matches_one_observed_example")
        self.assertEqual(out["vin_field_vs_private_vin"], "not_assessable")

    def test_04_incomplete_or_malformed_frame_key(self):
        missing = profile().replace("B9FBFrameC=", "UnusedFrameC=")
        out = audit.inspect_profiles(missing)
        self.assertEqual(out["private_b9fb_loader_state"], "missing_or_invalid_frame")
        self.assertEqual(out["d2_transport"], "not_checked")
        malformed = profile().replace("B9FBFrame0=8F", "B9FBFrame0=ZZ")
        self.assertEqual(audit.inspect_profiles(malformed)["private_b9fb_loader_state"],
                         "missing_or_invalid_frame")

    def test_05_wrong_first_d2_header_fails_transport(self):
        bad = list(frames())
        rid, first = bad[0]
        bad[0] = rid, bytes([0x8F, 0x40]) + first[2:]
        out = audit.inspect_profiles(profile(source=bad))
        self.assertEqual(out["d2_transport"], "invalid")
        self.assertEqual(out["vin_field_vs_private_vin"], "not_assessable")

    def test_06_current_active_zero_and_exact_copy_remain_distinct(self):
        candidate = profile()
        active_zero = "[Vehicle]\nVIN=YV1CZ0002A0000001\n[D2_50]\nB9FBFrameCount=0\n"
        out = audit.inspect_profiles(candidate, active_zero)
        self.assertEqual(out["active_ini_b9fb"], "zero_frames_declared")
        self.assertEqual(out["active_candidate_exact_frame_match"], "candidate_not_in_active_ini")
        identical = audit.inspect_profiles(candidate, candidate)
        self.assertEqual(identical["active_candidate_exact_frame_match"],
                         "equal_current_files_only")
        self.assertFalse(identical["original_vida_vin_accepted"])

    def test_07_published_donor_and_unknown_source_not_oem(self):
        out = audit.inspect_profiles(profile(provenance=audit.LAB_SOURCE_HINT))
        self.assertEqual(out["profile_provenance"],
                         "known_published_donor_with_replaced_vin_not_oem_my2009")
        self.assertFalse(out["oem_my2009_origin_verified"])
        unknown = audit.inspect_profiles(profile(provenance="private_verified_2026"))
        self.assertEqual(unknown["profile_provenance"], "not_authenticated")
        self.assertFalse(unknown["replay_approved"])

    def test_08_privacy_failclosed_and_legacy_count_precedence(self):
        candidate = profile(vin="YV1CZ0002A0000002")
        encoded = json.dumps(audit.inspect_profiles(candidate))
        for forbidden in ("YV1CZ0002A0000002", "YV1CZ0002A0000001",
                          "01200003", "8F 50 F9 FB", "SECRET-PATH"):
            self.assertNotIn(forbidden, encoded)
        self.assertFalse(json.loads(encoded)["contains_vin_can_payload_paths_pids_or_hashes"])
        # Native FrameCount has precedence even if B9FBFrameCount exists.
        zero = candidate.replace("B9FBFrameCount=13", "FrameCount=0\nB9FBFrameCount=13")
        self.assertEqual(audit.inspect_profiles(zero)["private_b9fb_declared_count"], 0)
        with self.assertRaises(Exception):
            audit.inspect_profiles("[D2_50]\nFrameCount=0\n[D2_50]\nFrameCount=13\n")
        with self.assertRaises(ValueError):
            audit.inspect_profiles("x" * (audit.MAX_FILE + 1))

    def test_09_private_vehicle_identity_json_matches_existing_candidate(self):
        identity = json.dumps({"Vehicle": {"VIN": LAB_VIN.decode(), "ModelYear": 2009}})
        out = audit.inspect_profiles(profile(), identity_json_text=identity)
        self.assertEqual(out["identity_json_state"], "valid_17_ascii_shape_not_oem_validated")
        self.assertEqual(out["identity_json_model_year"], "declares_my2009")
        self.assertEqual(out["identity_json_vs_private_ini_vin"], "equal")
        self.assertEqual(out["b9fb_field_vs_identity_json_vin"], "equal")
        self.assertFalse(out["replay_approved"])

    def test_10_independent_private_json_mismatch_not_silently_corrected(self):
        identity = json.dumps({"Vehicle": {"VIN": "YV1CZ0002A0000002",
                                            "ModelYear": 2009}})
        out = audit.inspect_profiles(profile(), identity_json_text=identity)
        self.assertEqual(out["identity_json_vs_private_ini_vin"], "different")
        self.assertEqual(out["b9fb_field_vs_identity_json_vin"], "different")
        self.assertFalse(out["original_vida_vin_accepted"])
        self.assertNotIn("YV1CZ0002A0000002", json.dumps(out))
        self.assertNotIn(LAB_VIN.decode(), json.dumps(out))

    def test_11_identity_json_schema_duplicate_keys_and_private_bytes(self):
        out = audit.inspect_profiles(profile(), identity_json_text=json.dumps({
            "Wrong": {"VIN": "SECRET_DONOT_PRINT"}}))
        self.assertEqual(out["identity_json_state"], "unsupported_schema")
        self.assertEqual(out["b9fb_field_vs_identity_json_vin"], "not_assessable")
        self.assertNotIn("SECRET_DONOT_PRINT", json.dumps(out))
        with self.assertRaises(ValueError):
            audit.inspect_profiles(profile(), identity_json_text=(
                '{"Vehicle":{"VIN":"YV1CZ0002A0000001",'
                '"VIN":"YV1CZ0002A0000002"}}'))
        with self.assertRaises(ValueError):
            audit.inspect_profiles(profile(), identity_json_text="x" *
                                   (audit.MAX_IDENTITY_JSON + 1))


    def test_12_flat_private_json_vin_and_model_year(self):
        obj = {"vin": LAB_VIN.decode(), "model_year": 2009}
        out = audit.inspect_profiles(profile(), identity_json_text=json.dumps(obj))
        self.assertEqual(out["identity_json_schema_location"], "root_vin")
        self.assertEqual(out["identity_json_state"], "valid_17_ascii_shape_not_oem_validated")
        self.assertEqual(out["identity_json_model_year"], "declares_my2009")
        self.assertEqual(out["identity_json_vs_private_ini_vin"], "equal")
        self.assertFalse(out["oem_my2009_origin_verified"])

    def test_13_vehicle_identity_wrapped_json_aliases(self):
        obj = {"vehicle_identity": {"Vin": LAB_VIN.decode(), "ModelYear": "2009"}}
        out = audit.inspect_profiles(profile(), identity_json_text=json.dumps(obj))
        self.assertEqual(out["identity_json_schema_location"], "nested_vehicleidentity")
        self.assertEqual(out["b9fb_field_vs_identity_json_vin"], "equal")
        self.assertFalse(out["original_vida_vin_accepted"])
        case = {"vehicle": {"vin": LAB_VIN.decode(), "model_year": 2009}}
        self.assertEqual(audit.inspect_profiles(
            profile(), identity_json_text=json.dumps(case))["identity_json_schema_location"],
            "nested_vehicle")

    def test_14_ambiguous_root_and_nested_json_fail_closed(self):
        obj = {"VIN": LAB_VIN.decode(), "Vehicle": {"VIN": LAB_VIN.decode()}}
        with self.assertRaises(ValueError):
            audit.inspect_profiles(profile(), identity_json_text=json.dumps(obj))
        obj2 = {"vin": LAB_VIN.decode(), "VIN": "YV1CZ0002A0000002"}
        with self.assertRaises(ValueError):
            audit.inspect_profiles(profile(), identity_json_text=json.dumps(obj2))
        obj3 = {"VIN": LAB_VIN.decode(), "ModelYear": 2009, "model_year": 2010}
        with self.assertRaises(ValueError):
            audit.inspect_profiles(profile(), identity_json_text=json.dumps(obj3))

    def test_15_invalid_root_vin_not_exported(self):
        obj = {"VIN": "PRIVATE IDENTIFIER NOT VALID", "ModelYear": 2009}
        out = audit.inspect_profiles(profile(), identity_json_text=json.dumps(obj))
        self.assertEqual(out["identity_json_state"], "missing_or_invalid_17_ascii_vin")
        self.assertEqual(out["identity_json_schema_location"], "root_vin")
        self.assertEqual(out["identity_json_vs_private_ini_vin"], "not_assessable")
        self.assertNotIn("PRIVATE IDENTIFIER", json.dumps(out))


if __name__ == "__main__":
    unittest.main()
