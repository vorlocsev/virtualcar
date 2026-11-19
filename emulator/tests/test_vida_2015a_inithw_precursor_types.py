"""Synthetic-only source-private constructor input / receiver signature tests."""
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
import audit_vida_2015a_inithw_precursor_types as tool
from audit_vida_2015a_inithw_metadata import MetadataError
from audit_vida_2015a_inithw_signature_shapes import _SigReader
from test_vida_2015a_inithw_il_calls import with_first_method_body
from test_vida_2015a_inithw_writer_memberrefs import fake_layout

TARGET = 0x0A000001
CTOR = 0x0A000002
NESTED = 0x0A000003
FIELD = 0x04000001
USER_STRING = 0x70000001


def instructions(pre, *, producer_op=0x73, precursor_op=None, nested=NESTED):
    if precursor_op is None:
        first = pre
    else:
        first = pre + bytes([precursor_op]) + struct.pack("<I", nested)
    return (first + bytes([producer_op]) + struct.pack("<I", CTOR) +
            b"\x7D" + struct.pack("<I", FIELD) +
            b"\x7B" + struct.pack("<I", FIELD) +
            b"\x6F" + struct.pack("<I", TARGET) + b"\x2A")


def layout_with_nested(ctor_sig, nested_sig, writer_sig=b"\x20\x01\x01\x12\x05"):
    base = fake_layout(method_sig=ctor_sig)
    old_row, old_u, old_blob = base["row"], base["u"], base["blob"]
    base["row"] = lambda t, i: (
        16 if (t, i) == (10, 3) else
        24 if (t, i) == (6, 1) else
        40 if (t, i) == (6, 3) else old_row(t, i)
    )
    base["u"] = lambda p, n: (
        4 if (p, n) == (20, 2) else
        5 if (p, n) == (34, 2) else
        6 if (p, n) == (50, 2) else old_u(p, n)
    )
    base["blob"] = lambda i: (
        nested_sig if i in (4, 6) else
        writer_sig if i == 5 else old_blob(i)
    )
    return base


def inspect(code, *, ctor_sig=b"\x20\x01\x01\x0E",
            nested_sig=b"\x20\x00\x0E", writer_sig=b"\x20\x01\x01\x12\x05",
            more_layout=None):
    pe = with_first_method_body(code)
    m = tool._metadata_tables(pe)
    m["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
    m["target_reference_signature_contracts"][TARGET] = {
        "parameters": 1, "has_this": True,
    }
    layout = more_layout if more_layout is not None else layout_with_nested(
        ctor_sig, nested_sig, writer_sig,
    )
    with patch.object(tool, "_metadata_tables", return_value=m), patch.object(
        tool, "_table_layout", return_value=layout
    ):
        return tool.inspect_module(pe, require_interface_memberref=True)


class OriginalVidaPrecursorSyntheticTests(unittest.TestCase):
    def test_01_class_type_retains_local_token_privately(self):
        self.assertEqual(tool._simple_type(_SigReader(b"\x12\x05")), ("class", 5))

    def test_02_ldstr_constructor_parameter_string_equal(self):
        code = instructions(b"\x72" + struct.pack("<I", USER_STRING))
        c = inspect(code)
        self.assertEqual(c["producer_input_source_counts"]["ldstr"], 1)
        self.assertEqual(c["newobj_constructor_one_param_kind"]["string"], 1)
        self.assertEqual(c["newobj_ldstr_constructor_parameter_relation"][
            "exact_same_module_type"], 1)

    def test_03_ldstr_class_parameter_different(self):
        code = instructions(b"\x72" + struct.pack("<I", USER_STRING))
        c = inspect(code, ctor_sig=b"\x20\x01\x01\x12\x05")
        self.assertEqual(c["newobj_constructor_one_param_kind"]["class"], 1)
        self.assertEqual(c["newobj_ldstr_constructor_parameter_relation"][
            "different_type"], 1)

    def test_04_invalid_ldstr_token_fail_closed(self):
        code = instructions(b"\x72" + struct.pack("<I", 0x06000001))
        with self.assertRaises(MetadataError):
            inspect(code)

    def test_05_nested_call_memberref_simple_class_return_matches(self):
        code = instructions(b"", precursor_op=0x28)
        c = inspect(code, ctor_sig=b"\x20\x01\x01\x12\x05",
                    nested_sig=b"\x20\x00\x12\x05")
        self.assertEqual(c["newobj_nested_call_opcode_counts"]["call"], 1)
        self.assertEqual(c["newobj_nested_call_token_kind_counts"]["memberref"], 1)
        self.assertEqual(c["newobj_nested_call_return_to_constructor_parameter_relation"][
            "exact_same_module_type"], 1)

    def test_06_nested_call_same_class_shape_different_index(self):
        code = instructions(b"", precursor_op=0x28)
        c = inspect(code, ctor_sig=b"\x20\x01\x01\x12\x05",
                    nested_sig=b"\x20\x00\x12\x09")
        self.assertEqual(c["newobj_nested_call_return_to_constructor_parameter_relation"][
            "different_type"], 1)

    def test_07_nested_callvirt_memberref_return_string_matches(self):
        code = instructions(b"", precursor_op=0x6F)
        c = inspect(code)
        self.assertEqual(c["newobj_nested_call_opcode_counts"]["callvirt"], 1)
        self.assertEqual(c["newobj_nested_call_return_to_constructor_parameter_relation"][
            "exact_same_module_type"], 1)

    def test_08_nested_calli_unclassified_not_derived(self):
        code = instructions(b"", precursor_op=0x29, nested=0x11000001)
        c = inspect(code)
        self.assertEqual(c["newobj_nested_call_opcode_counts"]["calli"], 1)
        self.assertEqual(c["newobj_nested_call_return_to_constructor_parameter_relation"][
            "unclassified"], 1)

    def test_09_nested_call_void_return_does_not_match_constructor_param(self):
        code = instructions(b"", precursor_op=0x28)
        c = inspect(code, nested_sig=b"\x20\x00\x01")
        self.assertEqual(c["newobj_nested_call_return_to_constructor_parameter_relation"][
            "different_type"], 1)

    def test_10_callvirt_receiver_ldarg_0_value_slot(self):
        code = instructions(b"\x02", producer_op=0x6F)
        c = inspect(code)
        self.assertEqual(c["callvirt_receiver_arg_slot_counts"]["slot0"], 1)
        self.assertEqual(c["callvirt_receiver_is_value"], 1)

    def test_11_callvirt_receiver_ldarg_s_slot1(self):
        code = instructions(b"\x0E\x01", producer_op=0x6F)
        c = inspect(code)
        self.assertEqual(c["callvirt_receiver_arg_slot_counts"]["slot1"], 1)

    def test_12_callvirt_receiver_ldarga_s_slot1(self):
        code = instructions(b"\x0F\x01", producer_op=0x6F)
        c = inspect(code)
        self.assertEqual(c["callvirt_receiver_arg_slot_counts"]["address_slot1"], 1)
        self.assertEqual(c["callvirt_receiver_is_address"], 1)

    def test_13_callvirt_receiver_ldarg_long_slot2(self):
        code = instructions(b"\xFE\x09\x02\x00", producer_op=0x6F)
        c = inspect(code)
        self.assertEqual(c["callvirt_receiver_arg_slot_counts"]["slot2plus"], 1)

    def test_14_callvirt_receiver_unclassified_when_non_arg_opcode(self):
        code = instructions(b"\x06", producer_op=0x6F)
        c = inspect(code)
        self.assertEqual(c["producer_input_source_counts"]["other_or_unclassified"], 1)
        self.assertEqual(c["callvirt_receiver_other_or_unclassified"], 1)

    def test_15_two_stfld_sources_reconcile(self):
        left = instructions(b"\x72" + struct.pack("<I", USER_STRING))[:-1]
        right = instructions(b"\x02", producer_op=0x6F)
        c = inspect(left + right)
        self.assertEqual(c["target_field_stfld_sites"], 2)
        self.assertEqual(c["producer_input_source_counts"]["ldstr"], 1)
        self.assertEqual(c["producer_input_source_counts"]["receiver_ldarg"], 1)

    def test_19_nested_local_callvirt_methoddef_instance_zero_args(self):
        code = instructions(b"\x02", precursor_op=0x6F, nested=0x06000003)
        c = inspect(code, ctor_sig=b"\x20\x01\x01\x12\x05",
                    nested_sig=b"\x20\x00\x12\x05")
        self.assertEqual(c["nested_local_callvirt_methoddef_sites"], 1)
        self.assertEqual(c["nested_local_callvirt_methoddef_signature_counts"][
            "instance_zero_explicit"], 1)
        self.assertEqual(c["nested_local_callvirt_immediate_input_family"][
            "load_arg_or_address"], 1)
        self.assertEqual(c["newobj_nested_call_return_to_constructor_parameter_relation"][
            "exact_same_module_type"], 1)

    def test_20_nested_local_callvirt_methoddef_static_one_arg(self):
        code = instructions(b"\x06", precursor_op=0x6F, nested=0x06000003)
        c = inspect(code, ctor_sig=b"\x20\x01\x01\x12\x05",
                    nested_sig=b"\x00\x01\x12\x05\x08")
        self.assertEqual(c["nested_local_callvirt_methoddef_signature_counts"][
            "static_one_explicit"], 1)
        self.assertEqual(c["nested_local_callvirt_immediate_input_family"][
            "load_local_or_address"], 1)

    def test_21_writer_slot1_is_instance_first_explicit_class(self):
        code = instructions(b"\x03", producer_op=0x6F)
        c = inspect(code)
        self.assertEqual(c["callvirt_writer_slot1_method_signature_counts"][
            "instance_first_explicit"], 1)
        self.assertEqual(c["callvirt_writer_receiver_parent_token_kind_counts"][
            "typeref"], 1)
        self.assertEqual(c["callvirt_writer_slot1_type_vs_receiver_parent"][
            "exact_same_module_type"], 1)

    def test_22_writer_slot1_class_different_from_memberref_owner(self):
        code = instructions(b"\x03", producer_op=0x6F)
        c = inspect(code, writer_sig=b"\x20\x01\x01\x12\x09")
        self.assertEqual(c["callvirt_writer_slot1_type_vs_receiver_parent"][
            "different_type"], 1)

    def test_23_writer_static_slot1_second_explicit_parameter(self):
        code = instructions(b"\x03", producer_op=0x6F)
        c = inspect(code, writer_sig=b"\x00\x02\x01\x08\x12\x05")
        self.assertEqual(c["callvirt_writer_slot1_method_signature_counts"][
            "static_second_explicit"], 1)
        self.assertEqual(c["callvirt_writer_slot1_type_vs_receiver_parent"][
            "exact_same_module_type"], 1)

    def test_24_writer_slot1_without_declared_parameter_not_invented(self):
        code = instructions(b"\x03", producer_op=0x6F)
        c = inspect(code, writer_sig=b"\x20\x00\x01")
        self.assertEqual(c["callvirt_writer_slot1_method_signature_counts"][
            "out_of_signature_or_unclassified"], 1)
        self.assertEqual(c["callvirt_writer_slot1_type_vs_receiver_parent"][
            "unclassified"], 1)

    def test_25_writer_slot1_non_class_parameter_unclassified(self):
        code = instructions(b"\x03", producer_op=0x6F)
        c = inspect(code, writer_sig=b"\x20\x01\x01\x08")
        self.assertEqual(c["callvirt_writer_slot1_type_vs_receiver_parent"][
            "different_type"], 1)

    def test_16_sha_pin_mismatch_fails_closed(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pins = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / name).write_bytes(pe)
                pins[name.casefold()] = (name, "0" * 64)
            with patch.object(tool, "EXPECTED", pins):
                with self.assertRaisesRegex(MetadataError, "SHA256"):
                    tool.audit(root)

    def test_17_successful_synthetic_three_pin_only_private_output(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pins = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / name).write_bytes(pe)
                pins[name.casefold()] = (name, hashlib.sha256(pe).hexdigest())
            with patch.object(tool, "EXPECTED", pins), patch.object(
                tool, "inspect_module", return_value={"target_field_stfld_sites": 0}
            ):
                report = tool.audit(root)
            self.assertEqual(len(report["results"]), 3)
            self.assertIs(report["original_assemblies_loaded_or_executed"], False)
            self.assertIs(report["immediate_precursor_proves_constructor_input_or_receiver"], False)
            self.assertIs(report["original_profile_identifiers_proven"], False)
            self.assertNotIn(d, json.dumps(report))

    def test_18_sanitized_errors_never_emit_original_folder(self):
        with tempfile.TemporaryDirectory() as d:
            log = StringIO()
            with redirect_stderr(log):
                status = tool.main(["--folder", str(Path(d) / "missing")])
            self.assertEqual(status, 2)
            self.assertEqual(set(json.loads(log.getvalue())), {"status", "error_class"})
            self.assertNotIn(d, log.getvalue())


if __name__ == "__main__":
    unittest.main()
