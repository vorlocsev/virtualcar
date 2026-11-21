"""B3A65: tests of opt-in, disposable synthetic D2_40 B9FB profile builder."""
from contextlib import redirect_stdout, redirect_stderr
import io
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import build_cem40_b9fb_isolated_lab_ini as build
from audit_vida_b3a53_b9fb_loader import audit_text
sys.path.pop(0)

SOURCE = build.SOURCE.read_text(encoding="utf-8-sig")


class CEM40LabTests(unittest.TestCase):
    def test_01_output_is_synthetic_both_routes_and_no_b9f0(self):
        out = build.build_lab_ini(SOURCE)
        cfg = build._cfg(out)
        self.assertIn("NOT OEM DATA", out)
        self.assertEqual(cfg.get("P2", "FixtureAuthority"), build.AUTHORITY)
        self.assertEqual(cfg.get("P2", "FixtureProvenance"), build.PROVENANCE)
        self.assertEqual(cfg.get("D2_40", "B9FBFrameCount"), "13")
        self.assertEqual(cfg.get("D2_50", "B9FBFrameCount"), "13")
        self.assertEqual(cfg.get("P2", "StrictRouting"), "1")
        for key in ("D2_40_B9F0", "D2_50_B9F0", "D2_40_B9FC",
                    "D2_50_B9FC"):
            self.assertEqual(cfg.get(key, "FrameCount"), "0")

    def test_02_only_first_frame_target_changes(self):
        orig = build._cfg(SOURCE)
        out = build._cfg(build.build_lab_ini(SOURCE))
        src = build._frames(orig, "D2_50", 0x50)
        dst = build._frames(out, "D2_40", 0x40)
        self.assertEqual(dst[0][0], src[0][0])
        self.assertEqual(dst[0][1], 0x40)
        self.assertEqual(dst[0][2:], src[0][2:])
        self.assertEqual(dst[1:], src[1:])
        self.assertEqual(build._frames(out, "D2_50", 0x50), src)
        self.assertEqual(len(dst), 13)

    def test_03_carcom230_prefix_stays_86_plus_crlf(self):
        out = build._cfg(build.build_lab_ini(SOURCE))
        s = b"".join(f[1:] for f in build._frames(out, "D2_40", 0x40))
        self.assertEqual(s[:3], bytes.fromhex("40 F9 FB"))
        payload = s[3:]
        self.assertEqual(len(payload), 88)
        self.assertEqual(len(payload[:86]), 86)
        self.assertEqual(payload[86:], b"\r\n")
        self.assertEqual(payload[11:28].decode("ascii"), out.get("Vehicle", "VIN"))
        self.assertEqual(payload[0], 0x57)

    def test_04_static_native_loader_finds_both_synthetic_routes(self):
        r = audit_text(build.build_lab_ini(SOURCE))["b9fb"]
        self.assertEqual(r["CEM_40"]["declared_frame_count"], 13)
        self.assertEqual(r["CEM_50"]["declared_frame_count"], 13)
        self.assertEqual(r["CEM_40"]["native_base_route_baud_bps"], 125000)
        self.assertEqual(r["CEM_50"]["native_base_route_baud_bps"], 500000)
        self.assertTrue(all(x["static_loader_class"] ==
                            "locally_structural_reply_not_oem_verified"
                            for x in r.values()))
        self.assertFalse(r["CEM_40"]["actual_j2534_d2_filter_and_29bit_flags_verified"])

    def test_05_unapproved_source_or_wrong_routing_rejected(self):
        for old, new in (("StrictRouting = 1", "StrictRouting = 0"),
                         ("Enabled = 1", "Enabled = 0"),
                         ("synthetic_lab_not_oem_attested", "real_oem_proven"),
                         ("B9FBFrameCount = 13", "B9FBFrameCount = 12")):
            with self.subTest(field=old), self.assertRaises(ValueError):
                build.build_lab_ini(SOURCE.replace(old, new))

    def test_06_wrong_donor_vin_or_data_fails_closed(self):
        self.assertIn("B9FBFrame0 = 8F 50", SOURCE)
        for candidate in (
            SOURCE.replace("B9FBFrame0 = 8F 50", "B9FBFrame0 = 8F 40"),
            SOURCE.replace("B9FBFrameC = 4F 30 36 39 33 31 0D 0A",
                           "B9FBFrameC = 4F 30 36 39 33 31 41 42"),
            SOURCE.replace("B9FBFrame0 = 8F", "B9FBFrame0 = XX"),
        ):
            with self.assertRaises(ValueError):
                build.build_lab_ini(candidate)

    def test_07_b9f0_and_b9fc_must_stay_disabled(self):
        for section in ("D2_40_B9F0", "D2_50_B9F0",
                        "D2_40_B9FC", "D2_50_B9FC"):
            cfg = build._cfg(SOURCE)
            cfg.set(section, "FrameCount", "1")
            out = io.StringIO()
            cfg.write(out)
            with self.subTest(section=section), self.assertRaises(ValueError):
                build.build_lab_ini(out.getvalue())

    def test_08_no_framecount_precedence_ambiguity(self):
        self.assertIn("B9FBFrameCount = 13", SOURCE)
        source = SOURCE.replace("B9FBFrameCount = 13",
                                "FrameCount = 0\nB9FBFrameCount = 13")
        with self.assertRaises(ValueError):
            build.build_lab_ini(source)

    def test_09_nonexistent_output_dir_exclusive_new_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "B3A65-isolated"
            path = build.create_exclusive(dest, build.build_lab_ini(SOURCE))
            self.assertEqual(path.name, "virtualcar.ini")
            self.assertTrue(path.is_file())
            self.assertEqual(path.read_text(encoding="utf-8"),
                             build.build_lab_ini(SOURCE))
            with self.assertRaises(ValueError):
                build.create_exclusive(dest, "OVERWRITE")
            self.assertEqual(path.read_text(encoding="utf-8"),
                             build.build_lab_ini(SOURCE))

    def test_10_output_inside_checkout_and_source_file_rejected(self):
        with self.assertRaises(ValueError):
            build._safe_new_directory(ROOT / "new-lab-dir")
        with self.assertRaises(ValueError):
            build._safe_new_directory(build.SOURCE)
        with self.assertRaises(ValueError):
            build._safe_new_directory(Path("relative-lab-dir"))

    def test_11_cli_explicit_optin_and_no_stdout_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "lab"
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                with self.assertRaises(SystemExit):
                    build.main(["--output-dir", str(dest)])
            self.assertFalse(dest.exists())
            with redirect_stdout(stdout), redirect_stderr(stderr):
                status = build.main(["--output-dir", str(dest),
                                     "--accept-synthetic-lab-only"])
            self.assertEqual(status, 0, stderr.getvalue())
            self.assertIn("CREATED_NEW_ISOLATED_SYNTHETIC_INI", stdout.getvalue())
            self.assertNotIn(str(dest), stdout.getvalue())
            self.assertNotIn(build._cfg(SOURCE).get("Vehicle", "VIN"), stdout.getvalue())
            self.assertEqual((dest / "virtualcar.ini").is_file(), True)

    def test_12_repeated_cli_cannot_overwrite_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "lab"
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(build.main(["--output-dir", str(dest),
                                              "--accept-synthetic-lab-only"]), 0)
            before = (dest / "virtualcar.ini").read_bytes()
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(build.main(["--output-dir", str(dest),
                                              "--accept-synthetic-lab-only"]), 2)
            self.assertEqual(before, (dest / "virtualcar.ini").read_bytes())


if __name__ == "__main__":
    unittest.main()
