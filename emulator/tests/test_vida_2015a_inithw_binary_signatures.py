"""Synthetic fixed-token census; never needs a genuine VIDA assembly."""
from contextlib import redirect_stderr
import hashlib
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_2015a_inithw_binary_signatures import (
    EvidenceError, SOURCE_TOKENS, _scan, audit, main,
)


class OriginalBinaryTokenCensusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.folder.joinpath("Bin").mkdir()
        self.example = self.folder / "Bin" / "CarCom.Test.DLL"
        self.blob = (b"MZ" + b"\x00" * 32 + b"GetInitHwSettings" +
                     b"\x00" * 8 + "folderLevel".encode("utf-16le"))
        self.example.write_bytes(self.blob)

    def test_01_fixed_ascii_and_utf16_only(self):
        r = audit(self.folder)
        self.assertEqual(r["matching_binaries"], 1)
        self.assertEqual(r["binary_files_scanned"], 1)
        match = r["matches"][0]
        self.assertEqual(match["module_basename"], "CarCom.Test.DLL")
        self.assertEqual(match["sha256"], hashlib.sha256(self.blob).hexdigest())
        self.assertTrue(match["fixed_token_present"]["GetInitHwSettings"])
        self.assertTrue(match["fixed_token_present"]["folderLevel"])
        self.assertFalse(match["fixed_token_present"]["vadis_GetHwSettings"])

    def test_02_no_original_binary_data_or_absolute_paths(self):
        result = json.dumps(audit(self.folder))
        self.assertNotIn(str(self.folder), result)
        self.assertNotIn("MZ", result)
        self.assertNotIn("GetInitHwSettings", result.split("fixed_token_present")[0])
        self.assertFalse(audit(self.folder)["original_binary_contents_or_install_paths_emitted"])

    def test_03_no_logic_or_runtime_claims(self):
        result = audit(self.folder)
        for key in ("assemblies_loaded_or_executed", "sql_or_vida_routines_called",
                    "source_writes_performed", "token_match_proves_methoddef_or_il",
                    "vida_2015a_procedure_callers_verified",
                    "runtime_selected_profile_set_verified",
                    "inherited_hardware_settings_verified", "d2_baudrate_verified",
                    "original_vida_readvin_accepted"):
            self.assertIs(result[key], False)

    def test_04_non_executable_not_scanned(self):
        (self.folder / "Bin" / "VIDA.log").write_text("GetInitHwSettings")
        r = audit(self.folder)
        self.assertEqual(r["binary_files_scanned"], 1)
        self.assertEqual(r["matching_binaries"], 1)

    def test_05_unmatched_executable_still_counted(self):
        (self.folder / "Bin" / "Unrelated.exe").write_bytes(b"MZ" + b"unrelated")
        r = audit(self.folder)
        self.assertEqual(r["binary_files_scanned"], 2)
        self.assertEqual(r["matching_binaries"], 1)

    def test_06_utf16_token_split_across_chunk_boundary(self):
        from unittest.mock import patch
        import audit_vida_2015a_inithw_binary_signatures as module
        x = self.folder / "Bin" / "Unicode.dll"
        x.write_bytes(b"12345678" + "CarComRepository".encode("utf-16le"))
        with patch.object(module, "CHUNK", 11):
            flags, _, size = _scan(x)
        self.assertEqual(size, x.stat().st_size)
        self.assertTrue(flags["CarComRepository"])

    def test_07_sha256_matches_entire_file(self):
        _, digest, n = _scan(self.example)
        self.assertEqual(n, len(self.blob))
        self.assertEqual(digest, hashlib.sha256(self.blob).hexdigest())

    def test_08_uppercase_only_token_not_guessed_as_equal(self):
        self.example.write_bytes(b"MZcarcomrepository")
        r = audit(self.folder)
        self.assertEqual(r["matching_binaries"], 0)

    def test_09_exact_fixed_token_set(self):
        result = audit(self.folder)["matches"][0]["fixed_token_present"]
        self.assertEqual(set(result), set(SOURCE_TOKENS))

    def test_10_file_limit_returns_none_without_read(self):
        self.assertIsNone(_scan(self.example, max_binary_size=10))

    def test_11_symlink_executable_is_skipped_when_supported(self):
        link = self.folder / "Bin" / "Linked.dll"
        try:
            link.symlink_to(self.example)
        except (OSError, NotImplementedError):
            self.skipTest("OS does not allow creating symlinks")
        r = audit(self.folder)
        self.assertEqual(r["binary_files_scanned"], 1)

    def test_12_invalid_source_folder_error_sanitized(self):
        out = StringIO()
        with redirect_stderr(out):
            rc = main(["--folder", str(self.folder / "unavailable")])
        self.assertEqual(rc, 2)
        report = json.loads(out.getvalue())
        self.assertEqual(set(report), {"status", "error_class"})
        self.assertNotIn(str(self.folder), out.getvalue())

    def test_13_special_executable_basename_suppressed_but_scanned(self):
        odd = self.folder / "Bin" / "Private Name.dll"
        odd.write_bytes(b"GetInitHwSettings")
        result = audit(self.folder)
        self.assertEqual(result["binary_files_scanned"], 2)
        self.assertEqual(result["matching_binaries"], 2)
        basenames = [item["module_basename"] for item in result["matches"]]
        self.assertIn("special_filename_suppressed", basenames)
        self.assertNotIn("Private Name.dll", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
