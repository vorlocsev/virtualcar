"""Eight isolated checks of captured, redacted P2 B9FB layout evidence."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
spec = importlib.util.spec_from_file_location(
    "audit_p2_b9fb_layout", ROOT / "tools" / "audit_p2_b9fb_layout.py")
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def example():
    return (ROOT / "samples" / "p2_b9fb_public_redacted.txt").read_text(
        encoding="utf-8")


class B9FBLayoutTests(unittest.TestCase):
    def test_01_known_redacted_donor_has_13_frames_88_byte_body(self):
        data = tool.audit(example())
        self.assertEqual(data["format"], "virtualcar-p2-b9fb-layout-evidence-v1")
        self.assertTrue(data["transport_framing_checked"])
        self.assertEqual(data["frames"], 13)
        self.assertEqual(data["d2_payload_bytes_with_echo"], 91)
        self.assertEqual(data["positive_echo_bytes"], 3)
        self.assertEqual(data["post_echo_body_bytes"], 88)
        self.assertTrue(data["has_embedded_nul"])
        self.assertEqual(data["crlf_separator_offsets"],
                         [9, 28, 39, 44, 52, 56, 64, 86])
        self.assertEqual(data["redaction_mask_span_offset"], 11)
        self.assertTrue(data["first_byte_equals_following_byte_count"])
        self.assertTrue(data["matches_known_redacted_donor_footprint"])
        self.assertFalse(data["xc90_v8_my2009_identity_verified"])
        self.assertFalse(data["vdash_ecu_acceptance_verified"])

    def test_02_truncated_final_frame_not_a_valid_block(self):
        raw = example()
        lines = [s for s in raw.splitlines()
                 if "0x4f, 0x30, 0x36" not in s.lower()]
        with self.assertRaises(ValueError):
            tool.audit("\n".join(lines))

    def test_03_misordered_middle_continuation_rejected(self):
        lines = example().splitlines()
        i = next(i for i, s in enumerate(lines) if "0x09, 0x70, 0x28" in s)
        j = next(i for i, s in enumerate(lines) if "0x0a, 0x58, 0x58" in s)
        lines[i], lines[j] = lines[j], lines[i]
        with self.assertRaises(ValueError):
            tool.audit("\n".join(lines))

    def test_04_service_echo_and_route_not_silently_repaired(self):
        raw = example()
        changed = raw.replace("0x8f, 0x50, 0xf9, 0xfb",
                              "0x8f, 0x50, 0xf9, 0xf0", 1)
        with self.assertRaises(ValueError):
            tool.audit(changed)
        with self.assertRaises(ValueError):
            tool.audit(raw, target=0x40)

    def test_05_b9f0_excerpt_is_not_b9fb_nor_order_evidence(self):
        raw = (ROOT / "samples" / "p2_b9f0_public_excerpt.txt").read_text(
            encoding="utf-8")
        with self.assertRaises(ValueError):
            tool.audit(raw)
        self.assertIn("No requirement that B9F0 precede B9FB",
                      " ".join(tool.audit(example())["limitations"]))

    def test_06_two_distinct_capture_blocks_refuse_automatic_join(self):
        source = example()
        with self.assertRaises(ValueError):
            tool.audit(source + "\n" + source)

    def test_07_binary_prefix_mutation_changes_footprint_not_identity(self):
        src = example()
        self.assertIn("0x57, 0x00, 0x30, 0x66", src)
        changed = src.replace("0x57, 0x00, 0x30, 0x66",
                              "0x57, 0x01, 0x30, 0x66", 1)
        data = tool.audit(changed)
        self.assertFalse(data["has_embedded_nul"])
        self.assertFalse(data["matches_known_redacted_donor_footprint"])
        self.assertEqual(data["redaction_mask_span_offset"], 11)
        self.assertFalse(data["schema_semantics_verified"])
        self.assertFalse(data["checksum_verified"])

    def test_08_cli_redacts_source_and_exclusive_output(self):
        with tempfile.TemporaryDirectory() as directory:
            private = "PRIVATE_CUSTOMER_VIN_NEVER_EXPORT"
            src, dst = Path(directory) / "input.txt", Path(directory) / "audit.json"
            src.write_text(example() + "\n# " + private + "\n",
                           encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(tool.main([str(src), "--output", str(dst)]), 0)
            raw = dst.read_text(encoding="utf-8")
            self.assertNotIn(private, raw)
            self.assertNotIn(str(directory), raw)
            self.assertNotIn("0x01200003", raw)
            self.assertEqual(json.loads(raw)["post_echo_body_bytes"], 88)
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(tool.main([str(src), "--output", str(dst)]), 2)
                self.assertEqual(tool.main([str(src), "--output", str(src)]), 2)
            self.assertNotIn(private, errors.getvalue())


if __name__ == "__main__":
    unittest.main()
