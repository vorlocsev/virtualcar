"""Synthetic instruction-boundary and owner-private adjacency regressions."""
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
import audit_vida_2015a_inithw_callsite_adjacent as tool
from audit_vida_2015a_inithw_metadata import MetadataError
from test_vida_2015a_inithw_il_calls import with_first_method_body

MEMBERREF = 0x0A000001


def fixture(body):
    """One synthetic method body; its MemberRef family is set by test seam."""
    return with_first_method_body(body)


def inspect_interface(body):
    pe = fixture(body)
    meta = tool._metadata_tables(pe)
    meta["target_reference_parent_type_families"][MEMBERREF] = "icarcom_repository"
    meta["target_reference_signature_contracts"][MEMBERREF] = {
        "parameters": 1, "has_this": True,
    }
    with patch.object(tool, "_metadata_tables", return_value=meta):
        return tool.inspect_module(pe, require_interface_memberref=True)


class OriginalVidaAdjacencySyntheticTests(unittest.TestCase):
    def test_01_ldloc_direct_predecessor(self):
        il = b"\x06\x28" + struct.pack("<I", MEMBERREF) + b"\x2A"
        counts = inspect_interface(il)
        self.assertEqual(counts["aligned_interface_getinithw_sites"], 1)
        self.assertEqual(counts["static_call_instruction_count"], 1)
        self.assertEqual(
            counts["immediately_preceding_opcode_family_counts"]["load_local_or_address"], 1
        )

    def test_02_ldarg_direct_predecessor(self):
        il = b"\x02\x6F" + struct.pack("<I", MEMBERREF) + b"\x2A"
        counts = inspect_interface(il)
        self.assertEqual(counts["static_callvirt_instruction_count"], 1)
        self.assertEqual(
            counts["immediately_preceding_opcode_family_counts"]["load_arg_or_address"], 1
        )

    def test_03_ldfld_direct_predecessor(self):
        il = (b"\x7B" + struct.pack("<I", 0x04000001) +
              b"\x28" + struct.pack("<I", MEMBERREF) + b"\x2A")
        counts = inspect_interface(il)
        self.assertEqual(
            counts["immediately_preceding_opcode_family_counts"]["load_field_or_address"], 1
        )

    def test_04_previous_nested_call_not_assumed_argument(self):
        il = (b"\x28" + struct.pack("<I", 0x0A000002) +
              b"\x28" + struct.pack("<I", MEMBERREF) + b"\x2A")
        result = inspect_interface(il)
        self.assertEqual(result["immediately_preceding_opcode_family_counts"][
            "nested_call_or_calli_unresolved_return"], 1)
        self.assertIs(result["adjacency_proves_operand_stack_provenance"], False)

    def test_05_adjacent_nop_is_not_a_producer(self):
        il = b"\x06\x00\x28" + struct.pack("<I", MEMBERREF) + b"\x2A"
        result = inspect_interface(il)
        self.assertEqual(result["immediately_preceding_opcode_family_counts"]["nop"], 1)

    def test_06_first_opcode_is_target_call_no_producer(self):
        il = b"\x28" + struct.pack("<I", MEMBERREF) + b"\x2A"
        self.assertEqual(inspect_interface(il)[
            "immediately_preceding_opcode_family_counts"]["none"], 1)

    def test_07_ldc_embedded_token_does_not_make_fake_call(self):
        il = b"\x20" + struct.pack("<I", MEMBERREF) + b"\x2A"
        result = inspect_interface(il)
        self.assertEqual(result["aligned_interface_getinithw_sites"], 0)
        self.assertEqual(sum(result["immediately_preceding_opcode_family_counts"].values()), 0)

    def test_08_switch_bytes_cannot_be_taken_for_calls(self):
        il = (b"\x45" + struct.pack("<I", 1) +
              struct.pack("<I", MEMBERREF) + b"\x2A")
        self.assertEqual(inspect_interface(il)["aligned_interface_getinithw_sites"], 0)

    def test_09_non_target_call_does_not_count(self):
        il = b"\x28" + struct.pack("<I", 0x0A000002) + b"\x2A"
        self.assertEqual(inspect_interface(il)["aligned_interface_getinithw_sites"], 0)

    def test_10_two_static_sites_are_two_categories(self):
        il = (b"\x06\x28" + struct.pack("<I", MEMBERREF) +
              b"\x02\x6F" + struct.pack("<I", MEMBERREF) + b"\x2A")
        result = inspect_interface(il)
        self.assertEqual(result["aligned_interface_getinithw_sites"], 2)
        self.assertEqual(result["immediately_preceding_opcode_family_counts"][
            "load_local_or_address"], 1)
        self.assertEqual(result["immediately_preceding_opcode_family_counts"][
            "load_arg_or_address"], 1)

    def test_11_truncated_instruction_rejected(self):
        with self.assertRaises(MetadataError):
            tool._instructions(b"\x28\x00\x00")

    def test_12_unknown_instruction_rejected(self):
        with self.assertRaises(MetadataError):
            tool._instructions(b"\xFF\x2A")

    def test_13_wrong_interface_method_contract_rejected(self):
        pe = fixture(b"\x28" + struct.pack("<I", MEMBERREF) + b"\x2A")
        meta = tool._metadata_tables(pe)
        meta["target_reference_parent_type_families"][MEMBERREF] = "icarcom_repository"
        meta["target_reference_signature_contracts"][MEMBERREF] = {
            "parameters": 0, "has_this": True,
        }
        with patch.object(tool, "_metadata_tables", return_value=meta):
            with self.assertRaises(MetadataError):
                tool.inspect_module(pe, require_interface_memberref=True)

    def test_14_repository_module_must_not_have_target_interface_memberref(self):
        pe = fixture(b"\x2A")
        meta = tool._metadata_tables(pe)
        meta["target_reference_parent_type_families"][MEMBERREF] = "icarcom_repository"
        with patch.object(tool, "_metadata_tables", return_value=meta):
            with self.assertRaises(MetadataError):
                tool.inspect_module(pe, require_interface_memberref=False)

    def test_15_end_to_end_three_pinned_synthetic_dlls_no_source_export(self):
        pe = fixture(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            expected = {}
            for filename in ("BizServices.CarCom.DB.DLL",
                             "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / filename).write_bytes(pe)
                expected[filename.casefold()] = (filename, hashlib.sha256(pe).hexdigest())
            with patch.object(tool, "EXPECTED", expected), patch.object(
                tool, "inspect_module",
                return_value={"aligned_interface_getinithw_sites": 0,
                              "immediately_preceding_opcode_family_counts": {"none": 0}}
            ):
                result = tool.audit(root)
            self.assertEqual(len(result["results"]), 3)
            for key in ("source_writes_performed", "original_assemblies_loaded_or_executed",
                        "original_il_bytecode_tokens_private_type_names_or_paths_exported",
                        "adjacent_opcode_proves_actual_argument_source",
                        "profile_identifiers_argument_proven",
                        "d2_baudrate_verified", "original_vida_readvin_accepted"):
                self.assertFalse(result[key])
            self.assertNotIn(str(root), json.dumps(result))

    def test_16_original_pin_mismatch_rejected(self):
        pe = fixture(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            expected = {}
            for filename in ("BizServices.CarCom.DB.DLL",
                             "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / filename).write_bytes(pe)
                expected[filename.casefold()] = (filename, "0" * 64)
            with patch.object(tool, "EXPECTED", expected):
                with self.assertRaisesRegex(MetadataError, "SHA256"):
                    tool.audit(root)

    def test_17_cli_error_has_only_error_class(self):
        with tempfile.TemporaryDirectory() as d:
            log = StringIO()
            with redirect_stderr(log):
                result = tool.main(["--folder", str(Path(d) / "nonexistent")])
            self.assertEqual(result, 2)
            self.assertEqual(set(json.loads(log.getvalue())), {"status", "error_class"})
            self.assertNotIn(d, log.getvalue())


if __name__ == "__main__":
    unittest.main()
