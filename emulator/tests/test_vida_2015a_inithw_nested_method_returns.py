"""Synthetic-only original VIDA local MethodDef return/receiver count tests."""
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
import audit_vida_2015a_inithw_nested_method_returns as tool
from audit_vida_2015a_inithw_metadata import MetadataError
from test_vida_2015a_inithw_il_calls import with_first_method_body
from test_vida_2015a_inithw_precursor_types import (
    instructions, layout_with_nested,
)

TARGET = 0x0A000001
METHOD = 0x06000003
FIELD = 0x04000001


def fake_layout(writer_sig=b"\x20\x01\x01\x12\x05",
                nested_sig=b"\x20\x00\x12\x05"):
    return layout_with_nested(b"\x20\x01\x01\x12\x05",
                              nested_sig, writer_sig)


def inspect(*, caller_pre=b"\x02", method_body=None,
            method_rva=0x2300, writer_sig=b"\x20\x01\x01\x12\x05",
            nested_sig=b"\x20\x00\x12\x05"):
    callsite = instructions(caller_pre, precursor_op=0x6F, nested=METHOD)
    pe = with_first_method_body(callsite)
    md = tool._metadata_tables(pe)
    md["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
    md["target_reference_signature_contracts"][TARGET] = {
        "parameters": 1, "has_this": True,
    }
    md["methods"][3] = {"rva": method_rva, "name": "private_dummy"}
    original_body = tool._body
    returns = method_body if method_body is not None else (
        b"\x7B" + struct.pack("<I", FIELD) + b"\x2A"
    )
    def body(blob, rva, sections):
        return returns if rva == method_rva and method_rva else original_body(blob, rva, sections)
    with patch.object(tool, "_metadata_tables", return_value=md), patch.object(
        tool, "_table_layout", return_value=fake_layout(writer_sig, nested_sig)
    ), patch.object(tool, "_body", side_effect=body), patch.object(
        tool, "_moresects", return_value=False
    ):
        return tool.inspect_module(pe, require_interface_memberref=True)


class NestedLocalReturnSyntheticTests(unittest.TestCase):
    def test_01_instance_caller_slot0_classifies_this_only_statically(self):
        self.assertEqual(tool._caller_arg_role(fake_layout(), 0x06000001, "slot0"),
                         "instance_this")

    def test_02_instance_caller_slot1_is_first_explicit(self):
        self.assertEqual(tool._caller_arg_role(fake_layout(), 0x06000001, "slot1"),
                         "instance_first_explicit")

    def test_03_static_caller_slot0_is_first_explicit(self):
        layout = fake_layout(writer_sig=b"\x00\x01\x01\x12\x05")
        self.assertEqual(tool._caller_arg_role(layout, 0x06000001, "slot0"),
                         "static_first_explicit")

    def test_04_no_declared_slot_returns_unclassified(self):
        layout = fake_layout(writer_sig=b"\x20\x00\x01")
        self.assertEqual(tool._caller_arg_role(layout, 0x06000001, "slot1"),
                         "out_of_signature_or_unclassified")

    def test_05_address_is_not_treated_as_receiver_value(self):
        self.assertEqual(tool._caller_arg_role(fake_layout(), 0x06000001,
                                               "address_slot0"),
                         "out_of_signature_or_unclassified")

    def test_06_return_predecessor_ldfld_classified(self):
        body = b"\x7B" + struct.pack("<I", FIELD) + b"\x2A"
        rets, categories, targeted = tool._local_return_census(body)
        self.assertEqual(rets, 1)
        self.assertEqual(categories["load_field_or_address"], 1)
        self.assertEqual(targeted, 0)

    def test_07_branch_target_to_ret_is_counted(self):
        body = b"\x2B\x05\x7B" + struct.pack("<I", FIELD) + b"\x2A"
        rets, _, targeted = tool._local_return_census(body)
        self.assertEqual(rets, 1)
        self.assertEqual(targeted, 1)

    def test_08_multiple_return_sites_are_counted_without_flow_claim(self):
        body = b"\x02\x2A\x06\x2A"
        rets, hist, _ = tool._local_return_census(body)
        self.assertEqual(rets, 2)
        self.assertEqual(hist["load_arg_or_address"], 1)
        self.assertEqual(hist["load_local_or_address"], 1)

    def test_09_realistic_synthetic_local_methoddef_census(self):
        counts = inspect()
        self.assertEqual(counts["target_getinithw_calls"], 1)
        self.assertEqual(counts["nested_local_callvirt_before_newobj_sites"], 1)
        self.assertEqual(counts["distinct_nested_local_methoddefs"], 1)
        self.assertEqual(counts["nested_call_input_slot_counts"]["slot0"], 1)
        self.assertEqual(counts["nested_call_caller_arg_role_counts"]["instance_this"], 1)
        self.assertEqual(counts["nested_method_signature_counts"][
            "instance_zero_explicit_class_return"], 1)
        self.assertEqual(counts["nested_method_with_il_body"], 1)
        self.assertEqual(counts["nested_method_return_sites"], 1)
        self.assertEqual(counts["nested_method_return_preceding_opcode_families"][
            "load_field_or_address"], 1)

    def test_10_local_nested_method_without_rva_is_unresolved(self):
        c = inspect(method_rva=0)
        self.assertEqual(c["nested_method_without_il_body"], 1)
        self.assertEqual(c["nested_method_return_sites"], 0)

    def test_11_wrong_nested_method_signature_preserves_unclassified(self):
        c = inspect(nested_sig=b"\x00\x01\x08\x08")
        self.assertEqual(c["nested_method_signature_counts"][
            "other_or_unclassified"], 1)

    def test_12_nested_caller_ldarg_s_slot1_classified(self):
        c = inspect(caller_pre=b"\x0E\x01")
        self.assertEqual(c["nested_call_input_slot_counts"]["slot1"], 1)
        self.assertEqual(c["nested_call_caller_arg_role_counts"][
            "instance_first_explicit"], 1)

    def test_13_invalid_branch_target_fails_closed(self):
        body = b"\x2B\x01\x7B" + struct.pack("<I", FIELD) + b"\x2A"
        with self.assertRaises(MetadataError):
            tool._local_return_census(body)

    def test_14_original_sha_guard_blocks_mismatch(self):
        binary = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pins = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / name).write_bytes(binary)
                pins[name.casefold()] = (name, "0" * 64)
            with patch.object(tool, "EXPECTED", pins):
                with self.assertRaisesRegex(MetadataError, "SHA256"):
                    tool.audit(root)

    def test_15_successful_synthetic_pins_do_not_execute_assemblies(self):
        binary = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            pins = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / name).write_bytes(binary)
                pins[name.casefold()] = (name, hashlib.sha256(binary).hexdigest())
            with patch.object(tool, "EXPECTED", pins), patch.object(
                tool, "inspect_module", return_value={"target_getinithw_calls": 0}
            ):
                result = tool.audit(root)
            self.assertEqual(len(result["results"]), 3)
            self.assertFalse(result["original_assemblies_loaded_or_executed"])
            self.assertFalse(result["nested_method_return_adjacency_proves_return_value_source"])
            self.assertFalse(result["nested_call_input_slot_proves_runtime_receiver"])
            self.assertNotIn(d, json.dumps(result))

    def test_16_sanitized_error_class_only(self):
        with tempfile.TemporaryDirectory() as d:
            errors = StringIO()
            with redirect_stderr(errors):
                rc = tool.main(["--folder", str(Path(d) / "missing")])
            self.assertEqual(rc, 2)
            self.assertEqual(set(json.loads(errors.getvalue())), {"status", "error_class"})
            self.assertNotIn(d, errors.getvalue())


if __name__ == "__main__":
    unittest.main()
