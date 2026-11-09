"""Read-only canonical J2534 provider provenance regression: synthetic files only."""
import contextlib
import io
import json
from unittest import mock
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vmware_provider_provenance as audit


def fake_pe(path, *, x86=True, tail=b"synthetic"):
    buf = bytearray(512)
    buf[:2] = b"MZ"
    struct.pack_into("<I", buf, 0x3C, 64)
    buf[64:68] = b"PE\x00\x00"
    struct.pack_into("<H", buf, 68, 0x14C if x86 else 0x8664)
    struct.pack_into("<H", buf, 88, 0x10B if x86 else 0x20B)
    path.write_bytes(bytes(buf) + tail)
    return path


def executable_pe(path, *, code=b"AAA", metadata=b"metadata"):
    """Synthetic bounded PE32 with one executable section, no valid J2534 exports."""
    image = bytearray(1024)
    image[:2] = b"MZ"
    struct.pack_into("<I", image, 0x3C, 0x80)
    image[0x80:0x84] = b"PE\x00\x00"
    struct.pack_into("<HH", image, 0x84, 0x14C, 1)
    struct.pack_into("<H", image, 0x94, 0xE0)
    struct.pack_into("<H", image, 0x98, 0x10B)
    section = 0x80 + 24 + 0xE0
    image[section:section + 8] = b".text\x00\x00\x00"
    struct.pack_into("<II", image, section + 16, 256, 512)
    struct.pack_into("<I", image, section + 36, 0x60000020)
    image[512:512 + len(code)] = code
    image[800:800 + len(metadata)] = metadata
    path.write_bytes(image)
    return path


class ProviderProvenanceTests(unittest.TestCase):
    def test_01_missing_key_is_not_client_failure(self):
        result = audit.assess(False, None, Path("/unused"))
        self.assertEqual(result["provider_status"], "canonical_provider_absent")
        self.assertEqual(result["vin_or_ecu_accepted"], "not_verified")

    def test_02_missing_registry_value(self):
        result = audit.assess(True, None, Path("/unused"))
        self.assertEqual(result["provider_status"], "library_value_missing")

    def test_03_missing_local_dll(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "not-a-dll.dll"
            result = audit.assess(True, str(path), path)
            self.assertEqual(result["provider_status"], "installed_library_missing")

    def test_04_invalid_pe_is_not_safely_classified_as_x86(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "private-invalid.dll"
            path.write_bytes(b"not a valid file" * 32)
            result = audit.assess(True, str(path), path)
            self.assertEqual(result["provider_status"], "installed_library_unverifiable")

    def test_05_x64_cannot_be_loaded_by_32bit_client(self):
        with tempfile.TemporaryDirectory() as td:
            path = fake_pe(Path(td) / "test.dll", x86=False)
            result = audit.assess(True, str(path), path)
            self.assertEqual(result["provider_status"], "installed_library_not_x86")

    def test_06_exact_byte_match_not_vehicle_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            installed = fake_pe(root / "private-installed.dll")
            tested = root / "current.dll"
            tested.write_bytes(installed.read_bytes())
            result = audit.assess(True, str(installed), tested)
            self.assertEqual(result["binary_comparison"], "exact_bytes")
            self.assertEqual(result["sectorv_client_execution"], "not_performed")
            self.assertEqual(result["vin_or_ecu_accepted"], "not_verified")

    def test_07_different_valid_pe_is_not_categorized_as_old_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            installed = fake_pe(root / "private-installed.dll", tail=b"A")
            tested = fake_pe(root / "current.dll", tail=b"B")
            result = audit.assess(True, str(installed), tested)
            self.assertEqual(result["binary_comparison"], "different_bytes")

    def test_08_local_paths_and_hashes_are_never_emitted(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            installed = fake_pe(root / "PRIVATE-VIN-YV1-CEM.dll")
            tested = fake_pe(root / "tested.dll")
            output = json.dumps(audit.assess(True, str(installed), tested))
            self.assertNotIn(str(root), output)
            self.assertNotIn("PRIVATE-VIN", output)
            self.assertNotIn("FunctionLibrary", output)
            self.assertNotIn("sha256", output)

    def test_09_reject_relative_and_remote_paths_without_reading(self):
        for value in ("../relative.dll", r"\\server\private\client.dll", ""):
            result = audit.assess(True, value, Path("/unused"))
            self.assertIn(result["provider_status"],
                          ("nonlocal_or_relative_path", "library_value_missing"))

    def test_10_tested_binary_missing_does_not_claim_comparison(self):
        with tempfile.TemporaryDirectory() as td:
            installed = fake_pe(Path(td) / "installed.dll")
            missing = Path(td) / "missing-current.dll"
            result = audit.assess(True, str(installed), missing)
            self.assertEqual(result["provider_status"], "installed_library_x86")
            self.assertEqual(result["binary_comparison"], "tested_build_unverifiable")

    def test_11_empty_and_oversized_files_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            f = Path(td) / "short.dll"
            f.write_bytes(b"MZ")
            self.assertEqual(audit._pe_machine(f), "invalid_pe")
            prior = audit.MAX_DLL
            try:
                audit.MAX_DLL = 100
                fake_pe(f)
                self.assertEqual(audit._pe_machine(f), "invalid_pe")
            finally:
                audit.MAX_DLL = prior


    def test_12_image_difference_can_be_non_executable_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            installed = executable_pe(root / "installed.dll",
                                      code=b"same-code", metadata=b"older-stamp")
            built = executable_pe(root / "built.dll",
                                  code=b"same-code", metadata=b"newer-stamp")
            result = audit.assess(True, str(installed), built)
            self.assertEqual(result["binary_comparison"], "different_bytes")
            self.assertEqual(result["executable_sections"], "same_bytes")
            self.assertEqual(result["vin_or_ecu_accepted"], "not_verified")

    def test_13_executable_difference_is_separately_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            installed = executable_pe(root / "installed.dll", code=b"code-old")
            built = executable_pe(root / "built.dll", code=b"code-new")
            result = audit.assess(True, str(installed), built)
            self.assertEqual(result["executable_sections"], "different_bytes")
            self.assertEqual(result["binary_comparison"], "different_bytes")

    def test_14_missing_pe_section_evidence_cannot_claim_same_code(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            installed = fake_pe(root / "minimal.dll")
            built = fake_pe(root / "built.dll")
            result = audit.assess(True, str(installed), built)
            self.assertEqual(result["executable_sections"], "unverifiable")
            self.assertEqual(result["installed_export_contract"],
                             "not_exact_or_unverifiable")

    def test_15_exact_export_probe_suppresses_verifier_prints(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            installed = executable_pe(root / "private.dll")
            built = executable_pe(root / "built.dll")
            import verify_pe_exports
            capture = io.StringIO()
            with mock.patch.object(verify_pe_exports, "verify",
                                   side_effect=lambda *a: print("PRIVATE VERSION PATH")):
                with contextlib.redirect_stdout(capture):
                    result = audit.assess(True, str(installed), built)
            self.assertEqual(result["installed_export_contract"],
                             "exact_14_named_j2534")
            self.assertNotIn("PRIVATE", capture.getvalue())

    def test_16_report_cannot_promote_binary_identity_to_client_acceptance(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            installed = executable_pe(root / "private.dll")
            built = executable_pe(root / "current.dll")
            result = audit.assess(True, str(installed), built)
            self.assertEqual(result["binary_comparison"], "exact_bytes")
            self.assertEqual(result["executable_sections"], "same_bytes")
            self.assertEqual(result["sectorv_client_execution"], "not_performed")
            self.assertEqual(result["vin_or_ecu_accepted"], "not_verified")
            self.assertNotIn(str(root), json.dumps(result))


if __name__ == "__main__":
    unittest.main()
