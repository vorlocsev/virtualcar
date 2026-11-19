"""Synthetic-only, read-only IL branch-entry and MemberRef arity tests."""
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
import audit_vida_2015a_inithw_stack_boundaries as tool
from audit_vida_2015a_inithw_metadata import MetadataError
from test_vida_2015a_inithw_il_calls import with_first_method_body
from test_vida_2015a_inithw_writer_memberrefs import fake_layout, source_il

WRITER = 0x0A000002
TARGET = 0x0A000001
FIELD = 0x04000001


def check(code=None, *, sig=b"\x20\x00\x01", more=False):
    pe = with_first_method_body(source_il() if code is None else code)
    meta = tool._metadata_tables(pe)
    meta["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
    meta["target_reference_signature_contracts"][TARGET] = {
        "parameters": 1, "has_this": True,
    }
    with patch.object(tool, "_metadata_tables", return_value=meta), patch.object(
        tool, "_table_layout", return_value=fake_layout(method_sig=sig)
    ), patch.object(tool, "_moresects", return_value=more):
        return tool.inspect_module(pe, require_interface_memberref=True)


class StackBoundarySyntheticTests(unittest.TestCase):
    def test_01_memberref_arity_zero(self):
        self.assertEqual(tool._arity(fake_layout(), WRITER), "zero")

    def test_02_memberref_arity_one(self):
        self.assertEqual(tool._arity(fake_layout(
            method_sig=b"\x20\x01\x01\x08"), WRITER), "one")

    def test_03_memberref_arity_multiple(self):
        self.assertEqual(tool._arity(fake_layout(
            method_sig=b"\x20\x02\x01\x08\x08"), WRITER), "two_or_more")

    def test_04_complex_memberref_signature_is_unclassified(self):
        self.assertEqual(tool._arity(fake_layout(
            method_sig=b"\x20\x01\x14\x08"), WRITER), "unclassified")

    def test_05_non_memberref_token_does_not_invent_arity(self):
        self.assertEqual(tool._arity(fake_layout(), 0x06000002), "unclassified")

    def test_06_default_visitor_counts_one_reader_and_one_writer(self):
        r = check()
        self.assertEqual(r["target_getinithw_calls"], 1)
        self.assertEqual(r["target_stfld_writes"], 1)
        self.assertEqual(r["writer_predecessor_arity"]["newobj"]["zero"], 1)
        self.assertEqual(r["sink_without_static_direct_branch_entry"]["reader"], 1)
        self.assertEqual(r["sink_without_static_direct_branch_entry"]["writer"], 1)

    def test_07_callvirt_producer_arity_one(self):
        r = check(source_il(0x6F), sig=b"\x20\x01\x12\x05\x08")
        self.assertEqual(r["writer_predecessor_arity"]["callvirt"]["one"], 1)

    def test_08_branch_directly_to_stfld_is_detected(self):
        # br.s +5 skips newobj and lands on stfld at offset 7.
        r = check(b"\x2B\x05" + source_il())
        self.assertEqual(r["sink_with_static_direct_branch_entry"]["writer"], 1)
        self.assertEqual(r["sink_with_static_direct_branch_entry"]["reader"], 0)

    def test_09_branch_directly_to_getinithw_is_detected(self):
        # br.s +15 lands on target callvirt at offset 17.
        r = check(b"\x2B\x0F" + source_il())
        self.assertEqual(r["sink_with_static_direct_branch_entry"]["reader"], 1)
        self.assertEqual(r["sink_with_static_direct_branch_entry"]["writer"], 0)

    def test_10_direct_branch_to_newobj_not_consumer(self):
        # br.s +0 falls through to newobj at offset 2, not stfld.
        r = check(b"\x2B\x00" + source_il())
        self.assertEqual(r["sink_with_static_direct_branch_entry"]["writer"], 0)

    def test_11_more_sections_are_marked_as_unresolved_hazard(self):
        r = check(more=True)
        self.assertEqual(r["sink_in_method_with_more_sections"]["reader"], 1)
        self.assertEqual(r["sink_in_method_with_more_sections"]["writer"], 1)

    def test_12_short_branch_target_not_instruction_aligned_rejected(self):
        code = b"\x2B\x01" + source_il()
        with self.assertRaises(MetadataError):
            tool._branch_targets(code, tool._instructions(code))

    def test_13_switch_target_to_sink_is_detected(self):
        # switch targets use the end of its own instruction.
        # switch at 0: 9 bytes, newobj at 9..14, stfld at 14.
        switch = b"\x45" + struct.pack("<I", 1) + struct.pack("<i", 5)
        r = check(switch + source_il())
        self.assertEqual(r["sink_with_static_direct_branch_entry"]["writer"], 1)

    def test_14_fake_token_inside_ldc_operand_not_a_target_call(self):
        code = b"\x20" + struct.pack("<I", TARGET) + source_il()
        r = check(code)
        self.assertEqual(r["target_getinithw_calls"], 1)

    def test_15_unrelated_stfld_is_ignored(self):
        # First stfld writes a non-target FieldDef and must not count.
        code = (b"\x7D" + struct.pack("<I", 0x04000002) + source_il())
        r = check(code)
        self.assertEqual(r["target_stfld_writes"], 1)

    def test_16_negative_sha_fails_before_original_analysis(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pins = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (folder / name).write_bytes(pe)
                pins[name.casefold()] = (name, "0" * 64)
            with patch.object(tool, "EXPECTED", pins):
                with self.assertRaisesRegex(MetadataError, "SHA256"):
                    tool.audit(folder)

    def test_17_clean_synthetic_pins_never_execute_original_assemblies(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            pins = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (folder / name).write_bytes(pe)
                pins[name.casefold()] = (name, hashlib.sha256(pe).hexdigest())
            with patch.object(tool, "EXPECTED", pins), patch.object(
                tool, "inspect_module", return_value={"target_stfld_writes": 0}
            ):
                result = tool.audit(folder)
            self.assertFalse(result["original_assemblies_loaded_or_executed"])
            self.assertFalse(result["no_direct_branch_proves_stack_producer_consumer"])
            self.assertFalse(result["original_profile_identifiers_proven"])
            self.assertNotIn(tmp, json.dumps(result))

    def test_18_cli_failure_sanitizes_original_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = StringIO()
            with redirect_stderr(err):
                status = tool.main(["--folder", str(Path(tmp) / "missing")])
            self.assertEqual(status, 2)
            self.assertEqual(set(json.loads(err.getvalue())), {"status", "error_class"})
            self.assertNotIn(tmp, err.getvalue())


if __name__ == "__main__":
    unittest.main()
