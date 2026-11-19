"""Synthetic local FieldDef typed-token and stfld write-site regressions only."""
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
import audit_vida_2015a_inithw_field_writes as tool
from audit_vida_2015a_inithw_metadata import MetadataError
from test_vida_2015a_inithw_field_shapes import synthetic_layout
from test_vida_2015a_inithw_il_calls import with_first_method_body

TARGET = 0x0A000001
FIELD = 0x04000001
OTHER_FIELD = 0x04000002
CLASS_1 = b"\x05"   # TypeRef row 1
CLASS_2 = b"\x09"   # TypeRef row 2


def _call(op=0x6F):
    return bytes([op]) + struct.pack("<I", TARGET)


def _load(field=FIELD):
    return b"\x7B" + struct.pack("<I", field)


def _write(field=FIELD, op=0x7D):
    return bytes([op]) + struct.pack("<I", field)


def inspect(code, *, field_sig=b"\x06\x12\x05",
            target_sig=b"\x20\x01\x01\x12\x05",
            caller_name="CallerMethod", require=True):
    pe = with_first_method_body(code)
    meta = tool._metadata_tables(pe)
    meta["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
    meta["target_reference_signature_contracts"][TARGET] = {
        "parameters": 1, "has_this": True,
    }
    meta["target_reference_signature_bytes_private"][TARGET] = target_sig
    meta["methods"][1]["name"] = caller_name
    with patch.object(tool, "_metadata_tables", return_value=meta), patch.object(
        tool, "_table_layout", return_value=synthetic_layout(field_sig)
    ):
        return tool.inspect_module(pe, require_interface_memberref=require)


class FieldDefProvenanceSyntheticTests(unittest.TestCase):
    def test_01_matching_exact_same_module_coded_token(self):
        r = inspect(_load() + _call() + b"\x2A")
        self.assertEqual(r["target_calls_preceded_by_ldfld_fielddef"], 1)
        self.assertEqual(r["exact_same_module_typedeforref_token_equal_sites"], 1)
        self.assertEqual(r["exact_same_module_typedeforref_token_different_sites"], 0)

    def test_02_class_shape_equal_but_different_local_token(self):
        r = inspect(_load() + _call() + b"\x2A",
                    field_sig=b"\x06\x12\x09")
        self.assertEqual(r["exact_same_module_typedeforref_token_equal_sites"], 0)
        self.assertEqual(r["exact_same_module_typedeforref_token_different_sites"], 1)

    def test_03_identical_field_used_twice_is_one_distinct_field(self):
        r = inspect(_load() + _call() + _load() + _call() + b"\x2A")
        self.assertEqual(r["target_callvirt_sites"], 2)
        self.assertEqual(r["distinct_target_fielddefs_in_module"], 1)
        self.assertEqual(r["exact_same_module_typedeforref_token_equal_sites"], 2)

    def test_04_one_local_writer_stfld_found(self):
        r = inspect(_write() + _load() + _call() + b"\x2A")
        self.assertEqual(r["target_fielddef_stfld_write_sites"], 1)
        self.assertEqual(r["distinct_target_fielddefs_with_any_stfld"], 1)
        self.assertEqual(r["distinct_methods_writing_target_fielddefs"], 1)
        self.assertEqual(r["writer_method_family_counts"]["other_named_method"], 1)

    def test_05_constructor_writer_counted_separately(self):
        r = inspect(_write() + _load() + _call() + b"\x2A", caller_name=".ctor")
        self.assertEqual(r["writer_method_family_counts"]["instance_constructor"], 1)
        self.assertEqual(r["writer_method_family_counts"]["other_named_method"], 0)

    def test_06_type_initializer_writer_counted_separately(self):
        r = inspect(_write(op=0x80) + _load() + _call() + b"\x2A",
                    caller_name=".cctor")
        self.assertEqual(r["target_fielddef_stsfld_write_sites"], 1)
        self.assertEqual(r["writer_method_family_counts"]["type_initializer"], 1)

    def test_07_write_to_other_field_not_target(self):
        r = inspect(_write(OTHER_FIELD) + _load() + _call() + b"\x2A")
        self.assertEqual(r["target_fielddef_stfld_write_sites"], 0)
        self.assertEqual(r["distinct_target_fielddefs_without_local_stfld"], 1)

    def test_08_other_instruction_before_call_is_not_field(self):
        r = inspect(b"\x02" + _call() + b"\x2A")
        self.assertEqual(r["target_calls_preceded_by_other_instruction"], 1)
        self.assertEqual(r["distinct_target_fielddefs_in_module"], 0)

    def test_09_bad_field_token_table_rejected(self):
        with self.assertRaises(MetadataError):
            inspect(_load(0x06000001) + _call() + b"\x2A")

    def test_10_zero_field_row_rejected(self):
        with self.assertRaises(MetadataError):
            inspect(_load(0x04000000) + _call() + b"\x2A")

    def test_11_unhandled_complex_field_sig_is_unclassified(self):
        r = inspect(_load() + _call() + b"\x2A",
                    field_sig=b"\x06\x15\x12\x05\x01\x08")
        self.assertEqual(r["exact_type_token_unclassified_sites"], 1)

    def test_12_unsupported_return_type_leaves_unknown_parameter(self):
        r = inspect(_load() + _call() + b"\x2A",
                    target_sig=b"\x20\x01\x14\x08\x12\x05")
        self.assertEqual(r["exact_type_token_unclassified_sites"], 1)

    def test_13_malformed_field_signature_rejected(self):
        with self.assertRaises(MetadataError):
            inspect(_load() + _call() + b"\x2A", field_sig=b"\x20\x01\x01")

    def test_14_false_call_token_in_ldc_operand_ignored(self):
        il = b"\x20" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il)
        self.assertEqual(r["target_callvirt_sites"], 0)

    def test_15_false_stfld_token_in_ldc_operand_ignored(self):
        il = b"\x20" + struct.pack("<I", FIELD) + _load() + _call() + b"\x2A"
        r = inspect(il)
        self.assertEqual(r["target_fielddef_stfld_write_sites"], 0)

    def test_16_interface_signature_contract_not_one_param_rejected(self):
        pe = with_first_method_body(_load() + _call() + b"\x2A")
        meta = tool._metadata_tables(pe)
        meta["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
        meta["target_reference_signature_contracts"][TARGET] = {
            "parameters": 2, "has_this": True,
        }
        with patch.object(tool, "_metadata_tables", return_value=meta):
            with self.assertRaises(MetadataError):
                tool.inspect_module(pe, require_interface_memberref=True)

    def test_17_exact_sha_mismatch_fails_closed(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            expected = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (base / name).write_bytes(pe)
                expected[name.casefold()] = (name, "0" * 64)
            with patch.object(tool, "EXPECTED", expected):
                with self.assertRaisesRegex(MetadataError, "SHA256"):
                    tool.audit(base)

    def test_18_synthetic_end_to_end_no_raw_type_or_path_leak(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            expected = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (base / name).write_bytes(pe)
                expected[name.casefold()] = (name, hashlib.sha256(pe).hexdigest())
            with patch.object(tool, "EXPECTED", expected), patch.object(
                tool, "inspect_module", return_value={
                    "target_callvirt_sites": 0,
                    "distinct_target_fielddefs_in_module": 0,
                }
            ):
                result = tool.audit(base)
            self.assertEqual(len(result["results"]), 3)
            self.assertFalse(result["exact_local_type_token_match_proves_argument_value_source"])
            self.assertFalse(result["field_assignments_or_runtime_values_verified"])
            self.assertFalse(result["profile_identifiers_argument_proven"])
            self.assertNotIn(str(base), json.dumps(result))

    def test_20_first_instruction_stfld_has_no_preceding_value_proof(self):
        r = inspect(_write() + _load() + _call() + b"\x2A")
        self.assertEqual(
            r["immediately_preceding_stfld_opcode_family_counts"]["none"], 1
        )
        self.assertEqual(r["distinct_target_call_methods_with_local_field_write"], 1)

    def test_21_ldarg_before_stfld_is_category_not_stack_source(self):
        r = inspect(b"\x02" + _write() + _load() + _call() + b"\x2A")
        self.assertEqual(
            r["immediately_preceding_stfld_opcode_family_counts"]["load_arg_or_address"], 1
        )
        self.assertEqual(r["target_field_write_sites_in_target_call_methods"], 1)
        self.assertEqual(r["target_field_write_sites_outside_target_call_methods"], 0)

    def test_22_ldloc_preceding_stfld_classified_separately(self):
        r = inspect(b"\x06" + _write() + _load() + _call() + b"\x2A")
        self.assertEqual(
            r["immediately_preceding_stfld_opcode_family_counts"]["load_local_or_address"], 1
        )

    def test_23_nested_call_before_stfld_is_unknown_return_value(self):
        nested = b"\x28" + struct.pack("<I", 0x0A000002)
        r = inspect(nested + _write() + _load() + _call() + b"\x2A")
        self.assertEqual(
            r["immediately_preceding_stfld_opcode_family_counts"][
                "nested_call_or_calli_unresolved_return"], 1
        )
        self.assertEqual(r["distinct_target_call_methods_with_local_field_write"], 1)

    def test_24_target_caller_without_local_stfld_is_counted(self):
        r = inspect(_load() + _call() + b"\x2A")
        self.assertEqual(r["distinct_target_call_methods_in_module"], 1)
        self.assertEqual(r["distinct_target_call_methods_with_local_field_write"], 0)
        self.assertEqual(r["distinct_target_call_methods_without_local_field_write"], 1)
        self.assertEqual(r["target_field_write_sites_outside_target_call_methods"], 0)

    def test_25_two_stfld_predecessors_have_reconciled_totals(self):
        r = inspect(b"\x02" + _write() + b"\x06" + _write() +
                    _load() + _call() + b"\x2A")
        histogram = r["immediately_preceding_stfld_opcode_family_counts"]
        self.assertEqual(sum(histogram.values()), 2)
        self.assertEqual(histogram["load_arg_or_address"], 1)
        self.assertEqual(histogram["load_local_or_address"], 1)
        self.assertEqual(r["target_field_write_sites_in_target_call_methods"], 2)

    def test_26_newobj_preceding_stfld_classified_in_constructor(self):
        maker = b"\x73" + struct.pack("<I", 0x0A000002)
        r = inspect(maker + _write() + _load() + _call() + b"\x2A",
                    caller_name=".ctor")
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["newobj"], 1)
        self.assertEqual(r["preceding_stfld_operand_token_kind_counts"]["memberref"], 1)
        self.assertEqual(r["preceding_stfld_opcode_by_writer_method_family"][
            "instance_constructor"]["newobj"], 1)

    def test_27_newarr_not_mislabeled_newobj(self):
        maker = b"\x8D" + struct.pack("<I", 0x01000001)
        r = inspect(maker + _write() + _load() + _call() + b"\x2A")
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["newarr"], 1)
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["newobj"], 0)
        self.assertEqual(r["preceding_stfld_operand_token_kind_counts"]["typeref"], 1)

    def test_28_nested_call_methoddef_in_other_method(self):
        maker = b"\x28" + struct.pack("<I", 0x06000001)
        r = inspect(maker + _write() + _load() + _call() + b"\x2A",
                    caller_name="OtherMethod")
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["call"], 1)
        self.assertEqual(r["preceding_stfld_operand_token_kind_counts"]["methoddef"], 1)
        self.assertEqual(r["preceding_stfld_opcode_by_writer_method_family"][
            "other_named_method"]["call"], 1)

    def test_29_nested_callvirt_memberref_classified(self):
        maker = b"\x6F" + struct.pack("<I", 0x0A000002)
        r = inspect(maker + _write() + _load() + _call() + b"\x2A")
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["callvirt"], 1)
        self.assertEqual(r["preceding_stfld_operand_token_kind_counts"]["memberref"], 1)

    def test_30_calli_standalone_signature_not_methodref(self):
        maker = b"\x29" + struct.pack("<I", 0x11000001)
        r = inspect(maker + _write() + _load() + _call() + b"\x2A")
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["calli"], 1)
        self.assertEqual(r["preceding_stfld_operand_token_kind_counts"]["standalonesig"], 1)

    def test_31_invalid_newobj_token_kind_fails_closed(self):
        maker = b"\x73" + struct.pack("<I", 0x01000001)
        with self.assertRaises(MetadataError):
            inspect(maker + _write() + _load() + _call() + b"\x2A")

    def test_32_ldarg_predecessor_has_no_metadata_operand(self):
        r = inspect(b"\x02" + _write() + _load() + _call() + b"\x2A")
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["other_or_none"], 1)
        self.assertEqual(r["preceding_stfld_operand_token_kind_counts"]["not_applicable"], 1)

    def test_33_writer_cross_tab_reconciles_two_different_opcodes(self):
        maker1 = b"\x73" + struct.pack("<I", 0x0A000002)
        maker2 = b"\x28" + struct.pack("<I", 0x0A000003)
        r = inspect(maker1 + _write() + maker2 + _write() +
                    _load() + _call() + b"\x2A", caller_name=".ctor")
        by_family = r["preceding_stfld_opcode_by_writer_method_family"]
        self.assertEqual(r["writer_write_sites_by_method_family"]["instance_constructor"], 2)
        self.assertEqual(by_family["instance_constructor"]["newobj"], 1)
        self.assertEqual(by_family["instance_constructor"]["call"], 1)
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["newobj"], 1)
        self.assertEqual(r["preceding_stfld_exact_opcode_counts"]["call"], 1)

    def test_19_cli_errors_only_class_no_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = StringIO()
            with redirect_stderr(out):
                rc = tool.main(["--folder", str(Path(tmp) / "not-found")])
            self.assertEqual(rc, 2)
            self.assertEqual(set(json.loads(out.getvalue())), {"status", "error_class"})
            self.assertNotIn(tmp, out.getvalue())


if __name__ == "__main__":
    unittest.main()
