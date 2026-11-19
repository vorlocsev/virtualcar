"""Fully synthetic PE/CIL: no original VIDA assemblies or profile data."""
from contextlib import redirect_stderr
from io import StringIO
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_2015a_inithw_il_calls as tool
from audit_vida_2015a_inithw_metadata import MetadataError
from test_vida_2015a_inithw_metadata import _synthetic_cli

TARGET_MEMBERREF = 0x0A000001
TARGET_METHODDEF = 0x06000001


def with_first_method_body(code: bytes) -> bytes:
    binary = bytearray(_synthetic_cli())
    # Synthetic MethodDef #1: table RVA=0, flags=0, impl=0, name
    # string index of GetInitHwSettings and a dummy signature index.
    name_index = 1 + len("CarComRepository") + 1
    marker = struct.pack("<IHHHHH", 0, 0, 0, name_index, 0, 1)
    pos = binary.find(marker, 0x300)
    if pos < 0 or binary.find(marker, pos + 1) != -1:
        raise AssertionError("unique synthetic MethodDef row expected")
    struct.pack_into("<I", binary, pos, 0x2200)
    if len(code) > 63:
        raise AssertionError("tiny header fixture limited to 63 IL bytes")
    binary[0x400] = (len(code) << 2) | 2
    binary[0x401:0x401 + len(code)] = code
    return bytes(binary)


class VidaOriginalStaticCilCallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_01_synthetic_direct_memberref_call_detected(self):
        il = b"\x28" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A"
        r = tool.inspect_module(with_first_method_body(il))
        self.assertEqual(r["target_name_memberref_rows"], 1)
        self.assertEqual(r["direct_call_memberref_sites"], 1)
        self.assertEqual(r["direct_call_local_methoddef_sites"], 0)
        self.assertEqual(r["direct_call_to_repository_memberref_sites"], 1)
        self.assertEqual(r["distinct_methods_with_target_calls"], 1)
        self.assertTrue(r["all_present_cil_method_bodies_decoded"])

    def test_02_inline_integer_matching_token_is_not_call(self):
        il = b"\x20" + struct.pack("<I", TARGET_MEMBERREF) + b"\x26\x2A"
        r = tool.inspect_module(with_first_method_body(il))
        self.assertEqual(r["direct_call_memberref_sites"], 0)
        self.assertEqual(r["distinct_methods_with_target_calls"], 0)

    def test_03_ldstr_matching_token_is_not_call(self):
        il = b"\x72" + struct.pack("<I", TARGET_MEMBERREF) + b"\x26\x2A"
        self.assertEqual(tool.inspect_module(with_first_method_body(il))[
            "direct_call_memberref_sites"], 0)

    def test_04_callvirt_and_local_methoddef_are_distinguished(self):
        il = b"\x6F" + struct.pack("<I", TARGET_METHODDEF) + b"\x2A"
        r = tool.inspect_module(with_first_method_body(il))
        self.assertEqual(r["direct_call_local_methoddef_sites"], 1)
        self.assertEqual(r["direct_call_to_repository_local_methoddef_sites"], 1)
        self.assertEqual(r["direct_call_memberref_sites"], 0)

    def test_05_ldftn_is_reference_not_callsite(self):
        il = b"\xFE\x06" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A"
        r = tool.inspect_module(with_first_method_body(il))
        self.assertEqual(r["ldftn_reference_sites_not_calls"], 1)
        self.assertEqual(r["direct_call_memberref_sites"], 0)

    def test_06_switch_operands_cannot_be_misread_as_call(self):
        il = (b"\x45" + struct.pack("<I", 1) +
              struct.pack("<I", TARGET_MEMBERREF) + b"\x2A")
        r = tool.inspect_module(with_first_method_body(il))
        self.assertEqual(r["direct_call_memberref_sites"], 0)

    def test_07_unsupported_opcode_is_not_misreported_as_full_scan(self):
        binary = with_first_method_body(b"\xFF\x2A")
        r = tool.inspect_module(binary)
        self.assertEqual(r["method_bodies_present"], 1)
        self.assertEqual(r["method_bodies_unsupported"], 1)
        self.assertEqual(r["method_bodies_decoded"], 0)
        self.assertFalse(r["all_present_cil_method_bodies_decoded"])

    def test_08_truncated_call_operand_fails_closed_for_body(self):
        r = tool.inspect_module(with_first_method_body(b"\x28\x00\x00"))
        self.assertEqual(r["method_bodies_unsupported"], 1)
        self.assertEqual(r["direct_call_memberref_sites"], 0)

    def test_09_assembly_was_not_loaded_or_executed(self):
        pe = with_first_method_body(b"\x28" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A")
        pins = self._sources(pe)
        with patch.object(tool, "EXPECTED", pins):
            result = tool.audit(self.folder)
        self.assertEqual(len(result["results"]), 3)
        for key in ("source_writes_performed", "original_assemblies_loaded_or_executed",
                    "source_il_bytes_method_names_profiles_or_paths_exported",
                    "static_calls_prove_execution",
                    "memberref_owner_name_proves_runtime_target_binding",
                    "callsite_arguments_or_profile_list_proven",
                    "original_vida_2015a_generic_profile_inheritance_verified",
                    "d2_baudrate_verified", "original_vida_readvin_accepted"):
            self.assertIs(result[key], False)

    def _sources(self, binary: bytes) -> dict:
        sha = hashlib.sha256(binary).hexdigest()
        names = ("BizServices.CarCom.DB.DLL", "BizServices.VehicleCommProvider.DLL",
                 "Workflow.DLL")
        for name in names:
            (self.folder / name).write_bytes(binary)
        return {n.casefold(): (n, sha) for n in names}

    def test_10_wrong_original_sha_pin_stops(self):
        binary = with_first_method_body(b"\x2A")
        pins = self._sources(binary)
        pins["workflow.dll"] = ("Workflow.DLL", "0" * 64)
        with patch.object(tool, "EXPECTED", pins):
            with self.assertRaises(MetadataError):
                tool.audit(self.folder)

    def test_11_no_source_paths_or_private_binary_contents_in_json(self):
        binary = with_first_method_body(b"\x28" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A")
        pins = self._sources(binary)
        with patch.object(tool, "EXPECTED", pins):
            text = json.dumps(tool.audit(self.folder))
        self.assertNotIn(str(self.folder), text)
        self.assertNotIn("BSJB", text)
        self.assertNotIn('"OriginalVINSecret"', text)
        self.assertNotIn('"source_il_bytes"', text)

    def test_12_missing_original_file_fails_closed(self):
        binary = with_first_method_body(b"\x2A")
        pins = self._sources(binary)
        (self.folder / "Workflow.DLL").unlink()
        with patch.object(tool, "EXPECTED", pins):
            with self.assertRaises(MetadataError):
                tool.audit(self.folder)

    def test_13_cli_error_only_exposes_error_class(self):
        output = StringIO()
        with redirect_stderr(output):
            code = tool.main(["--folder", str(self.folder / "missing")])
        self.assertEqual(code, 2)
        self.assertEqual(set(json.loads(output.getvalue())), {"status", "error_class"})
        self.assertNotIn(str(self.folder), output.getvalue())

    def test_14_duplicate_original_filename_rejected(self):
        binary = with_first_method_body(b"\x2A")
        pins = self._sources(binary)
        (self.folder / "subdir").mkdir()
        (self.folder / "subdir" / "Workflow.DLL").write_bytes(binary)
        with patch.object(tool, "EXPECTED", pins):
            with self.assertRaises(MetadataError):
                tool.audit(self.folder)

    def test_15_inline_switch_out_of_bounds_fail_closed(self):
        with self.assertRaises(MetadataError):
            tool._calls(b"\x45" + struct.pack("<I", 0xFFFF) + b"\x2A")

    def test_16_first_layer_stored_scope_not_runtime_profile_list(self):
        result = tool.inspect_module(with_first_method_body(b"\x2A"))
        self.assertEqual(result["method_bodies_present"], 1)
        self.assertEqual(result["direct_call_memberref_sites"], 0)
        self.assertTrue(result["all_present_cil_method_bodies_decoded"])


if __name__ == "__main__":
    unittest.main()
