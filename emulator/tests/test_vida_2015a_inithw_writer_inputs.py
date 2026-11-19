"""Synthetic-only GetInitHwSettings writer input-adjacency tests."""
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
import audit_vida_2015a_inithw_writer_inputs as tool
from audit_vida_2015a_inithw_metadata import MetadataError
from test_vida_2015a_inithw_il_calls import with_first_method_body
from test_vida_2015a_inithw_writer_memberrefs import fake_layout

TARGET = 0x0A000001
PRODUCER = 0x0A000002
FIELD = 0x04000001


def il(pre=b"\x02", opcode=0x73, producer=PRODUCER):
    return (pre + bytes([opcode]) + struct.pack("<I", producer) +
            b"\x7D" + struct.pack("<I", FIELD) +
            b"\x7B" + struct.pack("<I", FIELD) +
            b"\x6F" + struct.pack("<I", TARGET) + b"\x2A")


def inspect(code=None, *, sig=b"\x20\x01\x01\x08", name=".ctor",
            more=False):
    pe = with_first_method_body(il() if code is None else code)
    md = tool._metadata_tables(pe)
    md["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
    md["target_reference_signature_contracts"][TARGET] = {
        "parameters": 1, "has_this": True,
    }
    with patch.object(tool, "_metadata_tables", return_value=md), patch.object(
        tool, "_table_layout", return_value=fake_layout(
            method_sig=sig, method_name=name,
        )
    ), patch.object(tool, "_moresects", return_value=more):
        return tool.inspect_module(pe, require_interface_memberref=True)


class WriterInputSyntheticTests(unittest.TestCase):
    def test_01_ctor_arg_ldarg_preceding_opcode(self):
        c = inspect()
        self.assertEqual(c["target_field_stfld_sites"], 1)
        self.assertEqual(c["writer_predecessor_kind_counts"]["newobj"], 1)
        self.assertEqual(c["writer_memberref_arity_by_kind"]["newobj"]["one"], 1)
        self.assertEqual(c["writer_type_relation_by_kind"]["newobj"]["equal"], 1)
        self.assertEqual(c["immediately_before_writer_producer_opcode_family"][
            "newobj"]["load_arg_or_address"], 1)

    def test_02_ctor_arg_ldloc_preceding_opcode(self):
        c = inspect(il(pre=b"\x06"))
        self.assertEqual(c["immediately_before_writer_producer_opcode_family"][
            "newobj"]["load_local_or_address"], 1)

    def test_03_ctor_arg_ldfld_preceding_opcode(self):
        pre = b"\x7B" + struct.pack("<I", 0x04000002)
        c = inspect(il(pre=pre))
        self.assertEqual(c["immediately_before_writer_producer_opcode_family"][
            "newobj"]["load_field_or_address"], 1)

    def test_04_ctor_arg_ldc_preceding_opcode(self):
        c = inspect(il(pre=b"\x17"))
        self.assertEqual(c["immediately_before_writer_producer_opcode_family"][
            "newobj"]["load_numeric"], 1)

    def test_05_ctor_arg_nested_call_unresolved_return(self):
        pre = b"\x28" + struct.pack("<I", 0x0A000003)
        c = inspect(il(pre=pre))
        self.assertEqual(c["immediately_before_writer_producer_opcode_family"][
            "newobj"]["nested_call_or_calli_unresolved_return"], 1)

    def test_06_callvirt_zero_args_receiver_ldarg(self):
        c = inspect(il(opcode=0x6F), sig=b"\x20\x00\x12\x05",
                    name="Factory")
        self.assertEqual(c["writer_predecessor_kind_counts"]["callvirt"], 1)
        self.assertEqual(c["writer_memberref_arity_by_kind"]["callvirt"]["zero"], 1)
        self.assertEqual(c["writer_type_relation_by_kind"]["callvirt"]["equal"], 1)
        self.assertEqual(c["immediately_before_writer_producer_opcode_family"][
            "callvirt"]["load_arg_or_address"], 1)

    def test_07_callvirt_zero_args_receiver_ldloc(self):
        c = inspect(il(pre=b"\x06", opcode=0x6F),
                    sig=b"\x20\x00\x12\x05", name="Factory")
        self.assertEqual(c["immediately_before_writer_producer_opcode_family"][
            "callvirt"]["load_local_or_address"], 1)

    def test_08_producer_direct_branch_entry_counted(self):
        c = inspect(b"\x2B\x01" + il())
        self.assertEqual(c["producer_has_direct_branch_entry"], 1)
        self.assertEqual(c["producer_input_has_no_direct_branch_entry"], 1)

    def test_09_producer_input_direct_branch_entry_counted(self):
        c = inspect(b"\x2B\x00" + il())
        self.assertEqual(c["producer_input_has_direct_branch_entry"], 1)
        self.assertEqual(c["producer_has_no_direct_branch_entry"], 1)

    def test_10_no_direct_branch_not_a_provenance_claim(self):
        c = inspect()
        self.assertEqual(c["producer_has_no_direct_branch_entry"], 1)
        self.assertEqual(c["producer_input_has_no_direct_branch_entry"], 1)

    def test_11_moresects_flagged_not_interpreted_as_eh(self):
        c = inspect(more=True)
        self.assertEqual(c["writer_method_has_more_sections"], 1)
        self.assertEqual(c["writer_method_has_no_more_sections"], 0)

    def test_12_missing_immediate_producer_is_unclassified(self):
        c = inspect(b"\x02\x7D" + struct.pack("<I", FIELD) +
                    b"\x7B" + struct.pack("<I", FIELD) +
                    b"\x6F" + struct.pack("<I", TARGET) + b"\x2A")
        self.assertEqual(c["writer_predecessor_kind_counts"]["other_or_unclassified"], 1)
        self.assertEqual(c["writer_source_arity_not_as_expected_or_unclassified"], 1)

    def test_13_constructor_arity_zero_not_considered_one(self):
        c = inspect(sig=b"\x20\x00\x01")
        self.assertEqual(c["writer_memberref_arity_by_kind"]["newobj"]["zero"], 1)
        self.assertEqual(c["writer_source_arity_not_as_expected_or_unclassified"], 1)

    def test_14_two_writer_sites_reconcile_per_category(self):
        code = il()[:-1] + il(pre=b"\x06")
        c = inspect(code)
        self.assertEqual(c["target_field_stfld_sites"], 2)
        self.assertEqual(c["writer_predecessor_kind_counts"]["newobj"], 2)
        self.assertEqual(c["writer_source_arity_as_expected"], 2)

    def test_15_bad_field_token_rejected(self):
        code = (b"\x02\x73" + struct.pack("<I", PRODUCER) +
                b"\x7D" + struct.pack("<I", 0x04000000) +
                b"\x7B" + struct.pack("<I", FIELD) +
                b"\x6F" + struct.pack("<I", TARGET) + b"\x2A")
        # Unrelated malformed field writes are ignored as in the older scanner.
        c = inspect(code)
        self.assertEqual(c["target_field_stfld_sites"], 0)

    def test_16_hash_mismatch_fails_closed(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            expected = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / name).write_bytes(pe)
                expected[name.casefold()] = (name, "0" * 64)
            with patch.object(tool, "EXPECTED", expected):
                with self.assertRaisesRegex(MetadataError, "SHA256"):
                    tool.audit(root)

    def test_17_only_aggregate_counts_not_paths_or_tokens(self):
        c = inspect()
        report = json.dumps(c)
        for secret in ("0A000002", "04000001", "original IL", "GetInitHwSettings"):
            self.assertNotIn(secret, report)

    def test_18_error_json_hides_source_path(self):
        with tempfile.TemporaryDirectory() as d:
            stderr = StringIO()
            with redirect_stderr(stderr):
                rc = tool.main(["--folder", str(Path(d) / "missing")])
            self.assertEqual(rc, 2)
            self.assertEqual(set(json.loads(stderr.getvalue())), {"status", "error_class"})
            self.assertNotIn(d, stderr.getvalue())

    def test_19_valid_synthetic_sha_files_read_without_execution(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            expected = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / name).write_bytes(pe)
                expected[name.casefold()] = (name, hashlib.sha256(pe).hexdigest())
            with patch.object(tool, "EXPECTED", expected), patch.object(
                tool, "inspect_module", return_value={"target_field_stfld_sites": 0}
            ):
                out = tool.audit(root)
            self.assertEqual(len(out["results"]), 3)
            self.assertFalse(out["original_assemblies_loaded_or_executed"])
            self.assertFalse(out["adjacent_writer_input_proves_operand_stack_value_source"])
            self.assertFalse(out["original_profile_identifiers_argument_proven"])
            self.assertNotIn(d, json.dumps(out))


if __name__ == "__main__":
    unittest.main()
