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


def with_typeref_parent(binary: bytes) -> bytes:
    """Rebuild the fully synthetic BSJB streams to add one TypeRef row."""
    image = bytearray(binary)
    streams = tool._cli_metadata(binary)
    old = streams["#~"]
    old_strings = streams["#Strings"]
    new_name = len(old_strings)
    new_strings = old_strings + b"ICarComRepository\x00"
    old_rows = old[24 + 16:]
    selfmodule = old_rows[:10]
    typedef = old_rows[10:24]
    methods = bytearray(old_rows[24:66])
    # Reserve extra synthetic RVA room for the larger TypeRef metadata blob.
    struct.pack_into("<I", methods, 0, 0x2400)
    memberrefs = bytearray(old_rows[66:78])
    struct.pack_into("<H", memberrefs, 0, (1 << 3) | 1)  # TypeRef row 1, tag 1
    new_valid = struct.unpack_from("<Q", old, 8)[0] | (1 << 1)
    new_tables = (
        old[:8] + struct.pack("<Q", new_valid) + old[16:24] +
        struct.pack("<IIIII", 1, 1, 1, 3, 2) +
        selfmodule + struct.pack("<HHH", (1 << 2) | 0, new_name, 0) +
        typedef + methods + memberrefs
    )
    version = b"v4.0.30319\x00"
    version += b"\x00" * (-len(version) % 4)
    root = bytearray(
        b"BSJB" + struct.pack("<HHII", 1, 1, 0, len(version)) +
        version + struct.pack("<HH", 0, 2)
    )
    headers = []
    for name in (b"#~", b"#Strings"):
        padded = name + b"\x00"
        padded += b"\x00" * (-len(padded) % 4)
        headers.append(padded)
    start = len(root) + sum(8 + len(x) for x in headers)
    for off, blob, name in (
        (start, new_tables, headers[0]),
        (start + len(new_tables), new_strings, headers[1]),
    ):
        root.extend(struct.pack("<II", off, len(blob)) + name)
    root.extend(new_tables)
    root.extend(new_strings)
    assert len(root) < 0x300, "synthetic metadata must not overlap relocated test IL"
    image[0x600:0x640] = image[0x400:0x440]
    image[0x300:0x300 + len(root)] = root
    struct.pack_into("<I", image, 0x200 + 12, len(root))
    return bytes(image)


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

    def test_17_hwsettings_memberref_parent_and_caller_are_separate(self):
        il = b"\x28" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A"
        data = with_first_method_body(il)
        before = b"CarComRepository\x00"
        after = b"HwSettings\x00" + b"\x00" * (len(before) - len(b"HwSettings\x00"))
        self.assertEqual(len(before), len(after))
        self.assertIn(before, data)
        edited = data.replace(before, after, 1)
        r = tool.inspect_module(edited)
        self.assertEqual(r["target_memberref_parent_hwsettings_rows"], 1)
        self.assertEqual(r["target_memberref_parent_carcom_repository_rows"], 0)
        self.assertEqual(r["target_methoddef_owner_hwsettings_rows"], 1)
        self.assertEqual(r["distinct_target_caller_methods_in_hwsettings"], 1)
        self.assertEqual(r["direct_target_calls_to_hwsettings_memberref"], 1)
        self.assertEqual(r["direct_call_to_repository_memberref_sites"], 0)

    def test_18_supported_no_prefix_remains_instruction_aligned(self):
        il = b"\xFE\x19\x01\x28" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A"
        self.assertEqual(tool._calls(il), [("call", TARGET_MEMBERREF)])

    def test_19_multiple_calls_one_method_are_not_multiple_callers(self):
        il = (b"\x28" + struct.pack("<I", TARGET_MEMBERREF)) * 2 + b"\x2A"
        r = tool.inspect_module(with_first_method_body(il))
        self.assertEqual(r["direct_call_memberref_sites"], 2)
        self.assertEqual(r["distinct_methods_with_target_calls"], 1)
        self.assertEqual(r["distinct_target_caller_methods_in_carcom_repository"], 1)
        self.assertEqual(r["direct_call_to_repository_memberref_sites"], 2)

    def test_20_skipped_method_reason_count_reconciles(self):
        r = tool.inspect_module(with_first_method_body(b"\xFF\x2A"))
        self.assertEqual(r["method_bodies_unsupported"], 1)
        self.assertEqual(r["method_bodies_unsupported_unknown_opcode"], 1)
        self.assertEqual(r["method_bodies_unsupported_truncated_or_invalid_operand"], 0)
        self.assertEqual(r["method_bodies_unsupported_other"], 0)

    def test_21_memberref_parent_tag_typedef_and_fixed_type_family(self):
        il = b"\x28" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A"
        r = tool.inspect_module(with_first_method_body(il))
        self.assertEqual(r["target_memberref_parent_kind_counts"]["typedef"], 1)
        self.assertEqual(r["target_memberref_parent_type_family_counts"]["carcom_repository"], 1)
        self.assertEqual(r["target_memberref_typeref_scope_counts"]["not_typeref"], 1)

    def test_22_pinned_type_ref_can_classify_interface_name_not_bind(self):
        il = b"\x28" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A"
        pe = with_typeref_parent(with_first_method_body(il))
        r = tool.inspect_module(pe)
        self.assertEqual(r["target_memberref_parent_kind_counts"]["typeref"], 1)
        self.assertEqual(r["target_memberref_parent_type_family_counts"]["icarcom_repository"], 1)
        self.assertEqual(r["target_memberref_typeref_scope_counts"]["module"], 1)
        self.assertEqual(r["direct_target_calls_to_other_or_unresolved_memberref"], 1)
        self.assertEqual(r["direct_call_to_repository_memberref_sites"], 0)

    def test_23_one_byte_unknown_opcodes_histogram_is_aggregate_only(self):
        r = tool.inspect_module(with_first_method_body(b"\xFF\x2A"))
        self.assertEqual(r["unsupported_unknown_opcode_histogram"], {"cil_opcode_FF": 1})
        self.assertEqual(r["method_bodies_unsupported_unknown_opcode"], 1)

    def test_24_two_byte_unknown_opcodes_histogram_is_aggregate_only(self):
        r = tool.inspect_module(with_first_method_body(b"\xFE\xFF\x2A"))
        self.assertEqual(r["unsupported_unknown_opcode_histogram"], {"cil_opcode_FE_FF": 1})

    def test_25_token_in_wrong_memberref_row_not_counted(self):
        il = b"\x28" + struct.pack("<I", 0x0A0000FF) + b"\x2A"
        r = tool.inspect_module(with_first_method_body(il))
        self.assertEqual(r["direct_call_memberref_sites"], 0)
        self.assertEqual(r["distinct_methods_with_target_calls"], 0)

    def test_26_zero_memberref_parent_index_fails_closed(self):
        il = b"\x28" + struct.pack("<I", TARGET_MEMBERREF) + b"\x2A"
        pe = bytearray(with_first_method_body(il))
        # Synthetic MemberRef table starts after the synthetic table rows.
        marker = struct.pack("<HHH", 8, 1 + len("CarComRepository") + 1, 0)
        i = pe.find(marker, 0x300, 0x400)
        self.assertGreater(i, 0)
        struct.pack_into("<H", pe, i, 0)
        with self.assertRaises(MetadataError):
            tool.inspect_module(bytes(pe))

    def test_16_first_layer_stored_scope_not_runtime_profile_list(self):
        result = tool.inspect_module(with_first_method_body(b"\x2A"))
        self.assertEqual(result["method_bodies_present"], 1)
        self.assertEqual(result["direct_call_memberref_sites"], 0)
        self.assertTrue(result["all_present_cil_method_bodies_decoded"])


if __name__ == "__main__":
    unittest.main()
