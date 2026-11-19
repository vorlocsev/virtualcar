"""Synthetic, owner-private GetInitHwSettings writer MemberRef type relations."""
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
import audit_vida_2015a_inithw_writer_memberrefs as tool
from audit_vida_2015a_inithw_metadata import MetadataError, _u
from test_vida_2015a_inithw_il_calls import with_first_method_body

TARGET = 0x0A000001
WRITER = 0x0A000002
FIELD = 0x04000001
CLASS_1 = (1 << 2) | 1


def fake_layout(*, method_sig=b"\x20\x00\x01", method_name=".ctor",
                parent_tag=1, parent_row=1, field_sig=b"\x06\x12\x05"):
    raw = bytearray(32)
    struct.pack_into("<HHH", raw, 0, (parent_row << 3) | parent_tag, 7, 3)
    struct.pack_into("<HHH", raw, 8, 0, 5, 2)
    def row(tid, index):
        if tid == 10 and index == 2:
            return 0
        if tid == 4 and index == 1:
            return 8
        raise MetadataError("invalid synthetic CLR row")
    return {
        "row": row,
        "u": lambda offset, width: _u(raw, offset, width),
        "strsize": 2, "blobsize": 2,
        "memberref_parent_size": 2,
        "typename": lambda index: method_name if index == 7 else "",
        "blob": lambda index: (
            method_sig if index == 3 else
            field_sig if index == 2 else
            (_ for _ in ()).throw(MetadataError("invalid synthetic CLR Blob index"))
        ),
    }


def source_il(opcode=0x73, writer_token=WRITER):
    return (bytes([opcode]) + struct.pack("<I", writer_token) +
            b"\x7D" + struct.pack("<I", FIELD) +
            b"\x7B" + struct.pack("<I", FIELD) +
            b"\x6F" + struct.pack("<I", TARGET) + b"\x2A")


def synthetic_inspect(code=None, *, layout=None, writer="CallerMethod"):
    pe = with_first_method_body(code if code is not None else source_il())
    metadata = tool._metadata_tables(pe)
    metadata["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
    metadata["target_reference_signature_contracts"][TARGET] = {
        "parameters": 1, "has_this": True,
    }
    metadata["methods"][1]["name"] = writer
    with patch.object(tool, "_metadata_tables", return_value=metadata), patch.object(
        tool, "_table_layout", return_value=layout or fake_layout(),
    ):
        return tool.inspect_module(pe, require_interface_memberref=True)


class MemberRefWriterRelationsTests(unittest.TestCase):
    def test_01_ctor_typeref_owner_equals_field_class_token(self):
        counts = synthetic_inspect(writer=".ctor")
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "newobj_owner_exact_field_type"], 1)
        self.assertEqual(counts["writer_producer_relation_by_method_family"][
            "instance_constructor"]["newobj_owner_exact_field_type"], 1)

    def test_02_ctor_owner_different_local_typeref(self):
        counts = synthetic_inspect(layout=fake_layout(parent_row=2), writer=".ctor")
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "newobj_owner_different_field_type"], 1)

    def test_03_ctor_parent_typedef_still_classified(self):
        counts = synthetic_inspect(layout=fake_layout(parent_tag=0), writer=".ctor")
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "newobj_owner_different_field_type"], 1)

    def test_04_ctor_name_does_not_match_unclassified(self):
        counts = synthetic_inspect(layout=fake_layout(method_name="Factory"),
                                   writer=".ctor")
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "newobj_owner_unclassified"], 1)

    def test_05_callvirt_simple_return_exact_field_type(self):
        layout = fake_layout(method_sig=b"\x20\x00\x12\x05", method_name="Factory")
        counts = synthetic_inspect(source_il(0x6F), layout=layout,
                                   writer="NonCtor")
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "callvirt_return_exact_field_type"], 1)

    def test_06_callvirt_simple_return_different_field_type(self):
        layout = fake_layout(method_sig=b"\x20\x00\x12\x09", method_name="Factory")
        counts = synthetic_inspect(source_il(0x6F), layout=layout)
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "callvirt_return_different_field_type"], 1)

    def test_07_callvirt_nonclass_return_is_unclassified(self):
        layout = fake_layout(method_sig=b"\x20\x00\x08", method_name="Factory")
        counts = synthetic_inspect(source_il(0x6F), layout=layout)
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "callvirt_return_unclassified"], 1)

    def test_08_callvirt_void_return_is_unclassified(self):
        layout = fake_layout(method_sig=b"\x20\x00\x01", method_name="Factory")
        counts = synthetic_inspect(source_il(0x6F), layout=layout)
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "callvirt_return_unclassified"], 1)

    def test_09_unknown_predecessor_separately_counted(self):
        code = (b"\x02\x7D" + struct.pack("<I", FIELD) +
                b"\x7B" + struct.pack("<I", FIELD) +
                b"\x6F" + struct.pack("<I", TARGET) + b"\x2A")
        counts = synthetic_inspect(code)
        self.assertEqual(counts["other_writer_predecessor_sites"], 1)
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "other_or_unclassified"], 1)

    def test_10_valid_kind_but_wrong_operand_table_is_unclassified(self):
        counts = synthetic_inspect(source_il(writer_token=0x06000002))
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "other_or_unclassified"], 1)

    def test_11_invalid_memberrefparent_row_fails_closed(self):
        with self.assertRaises(MetadataError):
            synthetic_inspect(layout=fake_layout(parent_row=0))

    def test_12_truncated_memberref_sig_fails_closed(self):
        with self.assertRaises(MetadataError):
            synthetic_inspect(layout=fake_layout(method_sig=b"\x20\x00"))

    def test_13_unsupported_complex_return_unclassified(self):
        layout = fake_layout(method_sig=b"\x20\x00\x14\x08",
                             method_name="Factory")
        counts = synthetic_inspect(source_il(0x6F), layout=layout)
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "callvirt_return_unclassified"], 1)

    def test_19_unsupported_newobj_signature_uses_declared_category(self):
        layout = fake_layout(method_sig=b"\x20\x00\x14\x08")
        counts = synthetic_inspect(layout=layout, writer=".ctor")
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "newobj_owner_unclassified"], 1)

    def test_20_newobj_with_nonclass_field_uses_declared_category(self):
        layout = fake_layout(field_sig=b"\x06\x08")
        counts = synthetic_inspect(layout=layout, writer=".ctor")
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "newobj_owner_unclassified"], 1)

    def test_21_callvirt_with_nonclass_field_uses_declared_category(self):
        layout = fake_layout(method_sig=b"\x20\x00\x12\x05",
                             method_name="Factory", field_sig=b"\x06\x08")
        counts = synthetic_inspect(source_il(0x6F), layout=layout)
        self.assertEqual(counts["writer_producer_type_relation_counts"][
            "callvirt_return_unclassified"], 1)
        self.assertEqual(sum(counts["writer_producer_type_relation_counts"].values()), 1)

    def test_14_no_raw_original_values_emitted(self):
        counts = synthetic_inspect()
        output = json.dumps(counts)
        for term in ("0A000002", "04000001", "GetInitHwSettings",
                     "MemberRefParent", ".ctor", "FieldSig"):
            self.assertNotIn(term, output)

    def test_15_two_writes_reconcile_categories(self):
        code = (source_il()[:-1] + source_il(0x6F))
        counts = synthetic_inspect(code, layout=fake_layout(
            method_sig=b"\x20\x00\x01",
        ))
        self.assertEqual(counts["target_field_stfld_sites"], 2)
        self.assertEqual(sum(counts["writer_producer_type_relation_counts"].values()), 2)

    def test_16_wrong_sha_rejected_before_original_pe_analysis(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as folder:
            names = ("BizServices.CarCom.DB.DLL",
                     "BizServices.VehicleCommProvider.DLL", "Workflow.DLL")
            expected = {}
            for name in names:
                (Path(folder) / name).write_bytes(pe)
                expected[name.casefold()] = (name, "0" * 64)
            with patch.object(tool, "EXPECTED", expected):
                with self.assertRaisesRegex(MetadataError, "SHA256 mismatch"):
                    tool.audit(Path(folder))

    def test_17_cli_failures_do_not_leak_source_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            stderr = StringIO()
            with redirect_stderr(stderr):
                rc = tool.main(["--folder", str(Path(folder) / "missing")])
            self.assertEqual(rc, 2)
            self.assertEqual(set(json.loads(stderr.getvalue())), {"status", "error_class"})
            self.assertNotIn(folder, stderr.getvalue())

    def test_18_end_to_end_synthetic_sources_flags_honest(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as folder:
            expected = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (Path(folder) / name).write_bytes(pe)
                expected[name.casefold()] = (name, hashlib.sha256(pe).hexdigest())
            with patch.object(tool, "EXPECTED", expected), patch.object(
                tool, "inspect_module", return_value={
                    "target_field_stfld_sites": 0,
                    "writer_producer_type_relation_counts": {},
                },
            ):
                output = tool.audit(Path(folder))
            self.assertEqual(len(output["results"]), 3)
            self.assertFalse(output["memberref_type_token_equality_proves_stack_value_source"])
            self.assertFalse(output["memberref_type_token_equality_proves_runtime_write"])
            self.assertFalse(output["original_getinithw_argument_profile_identifiers_proven"])
            self.assertFalse(output["original_vida_readvin_accepted"])
            self.assertNotIn(folder, json.dumps(output))


if __name__ == "__main__":
    unittest.main()
