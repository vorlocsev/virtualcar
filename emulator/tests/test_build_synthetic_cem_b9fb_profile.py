"""Eight offline gates for opt-in synthetic CEM B9FB profile construction.

No vehicle connection, real VIN, proprietary trace, or OEM claims.
"""
from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE / "tools"))
import build_synthetic_cem_b9fb_profile as build
from audit_vida_b3a54_private_b9fb_vin import _ini, _read_b9fb
from audit_p2_b9fb_shape import audit_frames
sys.path.pop(0)

PRIVATE_TEST_VIN = "YV1CZ0003A0000002"
TEMPLATE = build.PUBLIC_TEMPLATE.read_text(encoding="utf-8")
IDENTITY = json.dumps({"Vehicle": {"VIN": PRIVATE_TEST_VIN, "ModelYear": 2009}})


def parsed_frames(ini_text):
    status, count, frames = _read_b9fb(_ini(ini_text))
    assert status == "declared_frame_values_loaded_locally", status
    assert count == 13, count
    return frames


class CanonicalSyntheticCemProfileTests(unittest.TestCase):
    def test_01_build_13_frame_reference_and_private_vin(self):
        result = build.build_profile(TEMPLATE, IDENTITY)
        cfg = _ini(result)
        self.assertEqual(cfg.get("Vehicle", "VIN"), PRIVATE_TEST_VIN)
        self.assertEqual(cfg.get("Vehicle", "ModelYear"), "2009")
        self.assertEqual(cfg.get("P2", "StrictRouting"), "1")
        self.assertEqual(cfg.get("P2", "FixtureProvenance"),
                         build.CANONICAL_PROVENANCE)
        self.assertEqual(cfg.get("P2", "FixtureAuthority"),
                         "virtual_cem_reference_not_oem_capture")
        frames = parsed_frames(result)
        self.assertEqual(audit_frames(frames, target=0x50)["transport"], "complete")
        self.assertEqual(len(frames), 13)
        stream = b"".join(data[1:] for _, data in frames)
        self.assertEqual(stream[14:31], PRIVATE_TEST_VIN.encode("ascii"))
        self.assertEqual(stream[:3], bytes.fromhex("50 F9 FB"))

    def test_02_only_seventeen_identity_bytes_change(self):
        original = b"".join(frame[1:] for _, frame in parsed_frames(TEMPLATE))
        patched = b"".join(frame[1:] for _, frame in
                           parsed_frames(build.build_profile(TEMPLATE, IDENTITY)))
        self.assertEqual(original[:14], patched[:14])
        self.assertEqual(original[31:], patched[31:])
        self.assertNotEqual(original[14:31], patched[14:31])
        self.assertEqual(len(original), len(patched))
        # The other six-digit field must not be guessed from the VIN suffix.
        self.assertEqual(original[31:], patched[31:])

    def test_03_missing_or_wrong_owner_identity_rejected(self):
        for candidate in (
            {"VIN": "INVALID", "ModelYear": 2009},
            {"VIN": PRIVATE_TEST_VIN, "ModelYear": 2010},
            {"VIN": PRIVATE_TEST_VIN},
            {"Unrelated": {"VIN": PRIVATE_TEST_VIN}},
        ):
            with self.subTest(candidate=list(candidate)), self.assertRaises(ValueError):
                build.build_profile(TEMPLATE, json.dumps(candidate))

    def test_04_modified_or_malformed_template_rejected(self):
        variants = (
            TEMPLATE.replace("B9FBFrameCount = 13", "B9FBFrameCount = 12"),
            TEMPLATE.replace("B9FBFrame0 = 8F", "B9FBFrame0 = ZZ"),
            TEMPLATE.replace("B9FBFrame0 = 8F 50", "B9FBFrame0 = 8F 40"),
            TEMPLATE.replace("VIN = YV1CZ0002A0000001",
                             "VIN = YV1CZ0002A0000002"),
        )
        for candidate in variants:
            with self.subTest(kind=len(candidate)), self.assertRaises(ValueError):
                build.build_profile(candidate, IDENTITY)

    def test_05_no_ambiguous_framecount_or_unverified_positive_diagnostics(self):
        cases = (
            TEMPLATE.replace("B9FBFrameCount = 13",
                             "FrameCount = 0\nB9FBFrameCount = 13"),
            TEMPLATE.replace("[D2_40]\nResponseId = 00800003\nB9FBFrameCount = 0",
                             "[D2_40]\nResponseId = 00800003\nB9FBFrameCount = 1"),
            TEMPLATE.replace("[D2_50_B9F0]\nResponseId = 01000003\nFrameCount = 0",
                             "[D2_50_B9F0]\nResponseId = 01000003\nFrameCount = 1"),
            TEMPLATE.replace("StrictRouting = 1", "StrictRouting = 0"),
        )
        for candidate in cases:
            with self.assertRaises(ValueError):
                build.build_profile(candidate, IDENTITY)

    def test_06_explicit_output_never_overwrites_existing_private_profile(self):
        content = build.build_profile(TEMPLATE, IDENTITY)
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "virtualcar.ini"
            build.write_exclusive(target, content)
            self.assertEqual(target.read_text(encoding="utf-8"), content)
            with self.assertRaises(FileExistsError):
                build.write_exclusive(target, "OVERWRITE")
            self.assertEqual(target.read_text(encoding="utf-8"), content)
            with self.assertRaises(ValueError):
                build.write_exclusive(Path(tmp) / "not-ini.txt", content)

    def test_07_ambiguous_identity_json_is_not_selected(self):
        for case in (
            '{"VIN":"YV1CZ0003A0000002","VIN":"YV1CZ0002A0000001","ModelYear":2009}',
            json.dumps({"VIN": PRIVATE_TEST_VIN, "ModelYear": 2009,
                        "Vehicle": {"VIN": PRIVATE_TEST_VIN, "ModelYear": 2009}}),
            json.dumps({"Vehicle": {"VIN": PRIVATE_TEST_VIN, "ModelYear": 2009},
                        "Identity": {"VIN": PRIVATE_TEST_VIN, "ModelYear": 2009}}),
        ):
            with self.assertRaises(ValueError):
                build.build_profile(TEMPLATE, case)

    def test_08_cli_private_output_no_leak_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            identity = root / "vehicle-identity.json"
            target = root / "virtualcar.ini"
            identity.write_text(IDENTITY, encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = build.main(["--identity-json", str(identity),
                                     "--output", str(target)])
            self.assertEqual(result, 0, stderr.getvalue())
            self.assertTrue(target.is_file())
            self.assertNotIn(PRIVATE_TEST_VIN, stdout.getvalue())
            self.assertNotIn(PRIVATE_TEST_VIN, stderr.getvalue())
            self.assertNotIn(str(target), stdout.getvalue())
            self.assertIn("CREATED_NEW_PRIVATE_SYNTHETIC_CEM_INI", stdout.getvalue())
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = build.main(["--identity-json", str(identity),
                                     "--output", str(target)])
            self.assertEqual(result, 2)
            self.assertIn("REJECTED", stderr.getvalue())
            self.assertEqual(_ini(target.read_text()).get("Vehicle", "VIN"),
                             PRIVATE_TEST_VIN)


if __name__ == "__main__":
    unittest.main()
