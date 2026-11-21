"""Read-only synthetic B3A62 regression; no VIDA/J2534 or private INI."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
FIXTURE = Path(__file__).resolve().parents[1] / "virtualcar-p2-b9fb-lab-vin.ini"
sys.path.insert(0, str(TOOLS))
from audit_cem_b3a62_carcom230_b9fb import compare, COMMON_FIELDS, GAPS
sys.path.pop(0)


def published():
    return FIXTURE.read_text(encoding="utf-8-sig")


class B3A62Tests(unittest.TestCase):
    def test_01_public_synthetic_fixture_matches_carcom230_prefix(self):
        result = compare(published())
        self.assertEqual(result["status"], "SYNTHETIC_86_BYTE_PREFIX_PLUS_CRLF")
        self.assertEqual((result["frame_count"], result["synthetic_application_bytes"]), (13, 88))
        self.assertTrue(result["d2_framing_valid"])
        self.assertTrue(result["post_root_is_crlf"])

    def test_02_carcom_field_coverage_and_offset_no_overlap(self):
        self.assertEqual(len(COMMON_FIELDS), 10)
        self.assertEqual(sum(n for _, n in COMMON_FIELDS), 72)
        self.assertEqual(sum(n for _, n in GAPS), 14)
        occupied = [i for off, n in COMMON_FIELDS for i in range(off, off+n)]
        self.assertEqual(len(occupied), len(set(occupied)))
        self.assertEqual(max(occupied), 85)
        self.assertEqual(set(occupied) | {i for off,n in GAPS for i in range(off,off+n)}, set(range(86)))

    def test_03_vin_offset_really_is_eleven_bytes(self):
        result = compare(published())
        self.assertEqual((result["carcom_vin_offset"],result["carcom_vin_length"]), (11,17))
        self.assertEqual(result["source_vin_shape"], "17_ascii_vin_shape")
        self.assertEqual(result["source_vin_vs_ini"], "equal")
        self.assertTrue(result["first_byte_equals_remaining_count"])

    def test_04_no_d2_50_fixture(self):
        text = published().replace("B9FBFrameCount = 13", "B9FBFrameCount = 0")
        self.assertEqual(compare(text)["status"], "NO_D2_50_B9FB_FIXTURE")
        self.assertFalse(compare(text)["carcom230_prefix_structurally_consistent"])

    def test_05_wrong_route_header_fails_closed(self):
        text = published().replace("B9FBFrame0 = 8F 50", "B9FBFrame0 = 8F 40")
        self.assertEqual(compare(text)["status"], "INVALID_D2_FRAME_SEQUENCE")

    def test_06_wrong_sequence_fails_closed(self):
        text = published().replace("B9FBFrame1 = 09", "B9FBFrame1 = 0A")
        self.assertEqual(compare(text)["status"], "INVALID_D2_FRAME_SEQUENCE")

    def test_07_last_crlf_not_silently_removed(self):
        text = published().replace("B9FBFrameC = 4F 30 36 39 33 31 0D 0A",
                                   "B9FBFrameC = 4F 30 36 39 33 31 41 42")
        result = compare(text)
        self.assertTrue(result["d2_framing_valid"])
        self.assertFalse(result["post_root_is_crlf"])
        self.assertEqual(result["status"], "NOT_THE_PUBLISHED_CARCOM230_PREFIX_SHAPE")

    def test_08_private_vin_declaration_mismatch(self):
        text = published().replace("VIN = YV1CZ0002A0000001", "VIN = YV1CZ0002A0000002")
        result = compare(text)
        self.assertTrue(result["carcom230_prefix_structurally_consistent"])
        self.assertEqual(result["status"], "SYNTHETIC_VIN_DECLARATION_MISMATCH")
        self.assertEqual(result["source_vin_vs_ini"], "different")

    def test_09_no_identity_or_approval_leak(self):
        obj = compare(published())
        encoded = json.dumps(obj)
        for secret in ("YV1CZ0002A0000001", "01200003", "8F 50 F9 FB", "/tmp/", "C:\\"):
            self.assertNotIn(secret, encoded)
        self.assertFalse(obj["original_vida_readvin_verified"])
        self.assertFalse(obj["j2534_rx_delivered_verified"])
        self.assertFalse(obj["physical_ecu_or_oem_origin_verified"])

    def test_10_missing_frame_or_bad_count_fails_closed(self):
        self.assertEqual(compare(published().replace("B9FBFrameC =", "AbsentFrameC ="))["status"],
                         "MALFORMED_SOURCE_INI_OR_FRAME")
        self.assertEqual(compare(published().replace("B9FBFrameCount = 13", "B9FBFrameCount = 12"))["status"],
                         "NOT_THE_PUBLISHED_13_FRAME_SHAPE")

    def test_11_inactive_target40_not_overclaimed(self):
        obj = compare(published())
        self.assertEqual(obj["source_section"], "D2_50")
        self.assertIn("not_authenticated_as_active", obj["source_kind"])
        self.assertEqual(obj["source_vin_vs_ini"], "equal")
        self.assertFalse(obj["ecu_identification_verified"])

    def test_12_cli_categories_and_read_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            ini=Path(tmp)/"synthetic.ini"
            ini.write_text(published(),encoding="utf-8")
            before=ini.read_bytes()
            proc=subprocess.run([sys.executable,str(TOOLS/"audit_cem_b3a62_carcom230_b9fb.py"),
                                 "--ini",str(ini)],capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr)
            self.assertEqual(ini.read_bytes(),before)
            obj=json.loads(proc.stdout)
            self.assertEqual(obj["status"],"SYNTHETIC_86_BYTE_PREFIX_PLUS_CRLF")
            self.assertNotIn(str(ini),proc.stdout)
            self.assertNotIn("YV1CZ0002A0000001",proc.stdout)

    def test_13_duplicate_sections_and_invalid_data(self):
        self.assertEqual(compare(published()+"\n[D2_50]\nFrameCount=13\n")["status"],
                         "MALFORMED_SOURCE_INI_OR_FRAME")
        self.assertEqual(compare("" )["status"],"NO_D2_50_SECTION")
        self.assertEqual(compare("x" * 262145)["status"],"MALFORMED_SOURCE_INI_OR_FRAME")


if __name__ == "__main__":
    unittest.main()
