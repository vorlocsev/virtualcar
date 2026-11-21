"""CEM50 B9FB published owner-approved reference, separate x86 J2534 adapter.

Eight synthetic/offline regression groups. NOT original VIDA acceptance.
"""
import configparser
from pathlib import Path
import re
import sys
import unittest

EMULATOR = Path(__file__).resolve().parents[1]
ADAPTER = EMULATOR / "adapters" / "cem50"
VIN = "YV1CR855691511566"
NAME = "J2534 Diagnostic Interface CEM50"
sys.path.insert(0, str(EMULATOR / "tools"))
from audit_p2_b9fb_shape import audit_frames
from import_p2_trace import validate_response
sys.path.pop(0)


def profile():
    ini = configparser.ConfigParser(interpolation=None, strict=True)
    ini.optionxform = str
    ini.read_string((ADAPTER / "virtualcar.ini").read_text(encoding="utf-8"))
    return ini


def frames(ini):
    response_id = int(ini.get("D2_50", "ResponseId"), 16)
    return [
        (response_id, bytes.fromhex(ini.get("D2_50", "B9FBFrame" + format(i, "X"))))
        for i in range(int(ini.get("D2_50", "B9FBFrameCount")))
    ]


class CEM50J2534AdapterTests(unittest.TestCase):
    def test_01_owner_approved_literal_vin_and_my2009(self):
        ini = profile()
        self.assertEqual(ini.get("Vehicle", "VIN"), VIN)
        self.assertEqual(ini.get("Vehicle", "ModelYear"), "2009")

    def test_02_13_valid_cem50_d2_frames(self):
        ini = profile()
        reply = frames(ini)
        self.assertEqual(len(reply), 13)
        self.assertTrue(all(len(f) == 8 for _, f in reply))
        self.assertTrue(all(can_id == 0x01200003 for can_id, _ in reply))
        self.assertEqual(reply[0][1][:4], bytes.fromhex("8F 50 F9 FB"))
        self.assertEqual(reply[-1][1][0], 0x4F)
        self.assertIsNone(validate_response(reply, 0x50, 0xFB))

    def test_03_published_88_byte_envelope(self):
        audit = audit_frames(frames(profile()), target=0x50)
        self.assertEqual(audit["transport"], "complete")
        self.assertEqual(audit["payload_byte_count"], 88)
        self.assertEqual(audit["published_88_byte_shape"], "matches_one_observed_example")
        self.assertTrue(audit["vin_shaped_field"])

    def test_04_vin_and_chassis_suffix_are_consistent(self):
        wire = b"".join(f[1:] for _, f in frames(profile()))
        self.assertEqual(len(wire), 91)
        self.assertEqual(wire[:3], bytes.fromhex("50 F9 FB"))
        self.assertEqual(wire[14:31], VIN.encode("ascii"))
        self.assertEqual(wire[49:55], VIN[-6:].encode("ascii"))
        self.assertEqual(audit_frames(frames(profile()), 0x50)[
            "six_digit_field_compared_with_vin_suffix"], "equal")

    def test_05_other_cem_d2_responses_remain_disabled(self):
        ini = profile()
        self.assertEqual(ini.get("P2", "StrictRouting"), "1")
        self.assertEqual(ini.get("Vehicle", "ECUCount"), "1")
        self.assertNotIn("ECU1", ini)  # No short F114 responder at 0x726.
        for section, field in (
            ("D2_40", "B9FBFrameCount"),
            ("D2_40_B9F0", "FrameCount"),
            ("D2_50_B9F0", "FrameCount"),
            ("D2_40_B9FC", "FrameCount"),
            ("D2_50_B9FC", "FrameCount"),
        ):
            self.assertEqual(ini.get(section, field), "0")
        self.assertEqual(ini.get("PassiveCAN", "Enabled"), "0")

    def test_06_provenance_is_explicitly_synthetic(self):
        ini = profile()
        self.assertEqual(ini.get("P2", "FixtureAuthority"),
                         "synthetic_lab_not_oem_attested")
        self.assertIn("synthetic", ini.get("P2", "FixtureProvenance"))
        self.assertIn("intentionally PUBLIC", (ADAPTER / "virtualcar.ini").read_text())

    def test_07_new_provider_name_and_fail_closed_installer(self):
        ps = (ADAPTER / "Install-J2534CEM50.ps1").read_text(encoding="utf-8")
        self.assertIn("$name = '" + NAME + "'", ps)
        self.assertNotIn("Virtual", NAME)
        self.assertIn("Registry32", ps)
        self.assertIn("J2534CEM50.dll", ps)
        self.assertIn("if (-not $Apply)", ps)
        self.assertIn("registration already exists; never overwrite", ps)
        self.assertIn("Source DLL SHA256 mismatch", ps)
        self.assertIn("Get-FileHash", ps)
        self.assertIn("Duplicate INI section", ps)
        self.assertIn("Duplicate INI setting", ps)
        self.assertIn("Wrong number of CEM50 B9FB frame keys", ps)
        self.assertIn("Invalid D2 frame sequence", ps)
        self.assertIn("CEM50 B9FB VIN/chassis/payload mismatch", ps)
        self.assertIn("Registered J2534 values failed readback verification", ps)
        self.assertLess(ps.index("PROFILE_OK: CEM50 13 frames"), ps.index("$reg ="))

    def test_08_matches_existing_native_cem50_route(self):
        source = (EMULATOR / "src" / "virtualcar.c").read_text(encoding="utf-8")
        self.assertIn("d->baud=(d->target==0x40?125000u:500000u);", source)
        self.assertIn("d->frame_count=valid", source)
        self.assertIn("str_append(g_profile_path,\"virtualcar.ini\"", source)
        self.assertIn("0x01200003u", source)


    def test_09_native_x86_smoke_matches_all_published_frames(self):
        ps = (ADAPTER / "Verify-J2534CEM50.ps1").read_text(encoding="utf-8")
        self.assertIn("SysWOW64", ps)
        self.assertIn("PassThruOpen", ps)
        self.assertIn("PassThruConnect", ps)
        self.assertIn("PassThruWriteMsgs", ps)
        self.assertIn("PassThruReadMsgs", ps)
        self.assertIn("CEM50_NATIVE_PASS", ps)
        self.assertNotIn("CreateSubKey", ps)
        self.assertIn("ExpectedSha256", ps)
        match = re.search(
            r"static readonly byte\[,\] Frames = new byte\[13,8\] \{(.*?)\n    \};",
            ps, re.S)
        self.assertIsNotNone(match, "native frame matrix must be explicit")
        native = [
            bytes(int(value.strip(), 16) for value in row.split(","))
            for row in re.findall(r"\{([^{}]+)\}", match.group(1))
        ]
        self.assertEqual(len(native), 13)
        self.assertEqual(native, [frame for _, frame in frames(profile())])


if __name__ == "__main__":
    unittest.main()
