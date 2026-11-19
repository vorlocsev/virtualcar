"""Synthetic PE/CLR preceding field signature shape checks; no original DLL."""
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
import audit_vida_2015a_inithw_field_shapes as tool
from audit_vida_2015a_inithw_metadata import MetadataError, _u
from test_vida_2015a_inithw_il_calls import with_first_method_body

TARGET = 0x0A000001
FIELDDEF = 0x04000001
FIELDREF = 0x0A000001


def synthetic_layout(field_sig=b"\x06\x08"):
    table = bytearray(24)
    struct.pack_into("<HHH", table, 0, 0, 3, 1)  # FieldDef SigIndex 1
    struct.pack_into("<HHH", table, 8, 8, 3, 1)  # MemberRef SigIndex 1
    return {
        "row": lambda tid, index: (
            0 if tid == 4 and index == 1 else
            8 if tid == 10 and index == 1 else
            (_ for _ in ()).throw(MetadataError("invalid synthetic field row"))
        ),
        "u": lambda off, n: _u(table, off, n),
        "strsize": 2,
        "blobsize": 2,
        "memberref_parent_size": 2,
        "blob": lambda i: field_sig if i == 1 else
                (_ for _ in ()).throw(MetadataError("invalid synthetic field signature")),
    }


def inspect(code, *, field_sig=b"\x06\x08", param_sig=b"\x20\x01\x01\x08"):
    pe = with_first_method_body(code)
    m = tool._metadata_tables(pe)
    m["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
    m["target_reference_signature_contracts"][TARGET] = {
        "parameters": 1, "has_this": True,
    }
    m["target_reference_signature_bytes_private"][TARGET] = param_sig
    with patch.object(tool, "_metadata_tables", return_value=m), patch.object(
        tool, "_table_layout", return_value=synthetic_layout(field_sig)
    ):
        return tool.inspect_module(pe, require_interface_memberref=True)


class OriginalVidaFieldSignatureSyntheticTests(unittest.TestCase):
    def test_01_ldfld_fielddef_same_primitive_shape(self):
        il = (b"\x02\x7B" + struct.pack("<I", FIELDDEF) +
              b"\x6F" + struct.pack("<I", TARGET) + b"\x2A")
        r = inspect(il)
        self.assertEqual(r["immediately_preceding_field_opcodes"]["ldfld"], 1)
        self.assertEqual(r["field_loads_with_fielddef_token"], 1)
        self.assertEqual(r["field_type_shapes_compared"], 1)
        self.assertEqual(r["field_shape_equal_to_target_parameter_ignoring_local_type_tokens"], 1)

    def test_02_ldflda_fielddef_is_not_relabelled_ldfld(self):
        il = b"\x7C" + struct.pack("<I", FIELDDEF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il)
        self.assertEqual(r["immediately_preceding_field_opcodes"]["ldflda"], 1)
        self.assertEqual(r["immediately_preceding_field_opcodes"]["ldfld"], 0)

    def test_03_ldsfld_fieldref_classified_separately(self):
        il = b"\x7E" + struct.pack("<I", FIELDREF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il)
        self.assertEqual(r["immediately_preceding_field_opcodes"]["ldsfld"], 1)
        self.assertEqual(r["field_loads_with_memberref_token"], 1)

    def test_04_ldsflda_fieldref_classified_separately(self):
        il = b"\x7F" + struct.pack("<I", FIELDREF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il)
        self.assertEqual(r["immediately_preceding_field_opcodes"]["ldsflda"], 1)

    def test_05_shape_difference_recorded_not_guessed_equal(self):
        il = b"\x7B" + struct.pack("<I", FIELDDEF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il, field_sig=b"\x06\x0E")
        self.assertEqual(r["field_shape_different_from_target_parameter"], 1)

    def test_06_local_type_token_renumbered_same_shape(self):
        il = b"\x7B" + struct.pack("<I", FIELDDEF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il, field_sig=b"\x06\x12\x09",
                    param_sig=b"\x20\x01\x01\x12\x05")
        self.assertEqual(r["field_shape_equal_to_target_parameter_ignoring_local_type_tokens"], 1)
        self.assertEqual(r["field_type_shape_family_counts"]["class"], 1)

    def test_07_unsupported_complex_field_becomes_unclassified(self):
        il = b"\x7B" + struct.pack("<I", FIELDDEF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il, field_sig=b"\x06\x14\x08")
        self.assertEqual(r["field_or_parameter_shape_unclassified"], 1)
        self.assertEqual(r["field_type_shape_family_counts"]["other_or_unclassified"], 1)

    def test_08_unsupported_parameter_does_not_invent_shape(self):
        il = b"\x7B" + struct.pack("<I", FIELDDEF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il, param_sig=b"\x20\x01\x01\x14\x08")
        self.assertEqual(r["field_or_parameter_shape_unclassified"], 1)

    def test_09_bad_field_token_table_rejected(self):
        il = b"\x7B" + struct.pack("<I", 0x06000001) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        with self.assertRaises(MetadataError):
            inspect(il)

    def test_10_zero_field_index_rejected(self):
        il = b"\x7B" + struct.pack("<I", 0x04000000) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        with self.assertRaises(MetadataError):
            inspect(il)

    def test_11_invalid_field_signature_convention_rejected(self):
        with self.assertRaises(MetadataError):
            tool._field_signature_shape(b"\x20\x01\x08")

    def test_12_field_signature_trailing_bytes_rejected(self):
        with self.assertRaises(MetadataError):
            tool._field_signature_shape(b"\x06\x08\xFF")

    def test_13_token_in_integer_operand_not_target_call(self):
        il = b"\x20" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il)
        self.assertEqual(r["interface_getinithw_callvirt_sites"], 0)
        self.assertEqual(sum(r["immediately_preceding_field_opcodes"].values()), 0)

    def test_14_preceding_non_field_counts_only(self):
        il = b"\x06\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        r = inspect(il)
        self.assertEqual(r["preceding_non_field_instruction_sites"], 1)

    def test_15_no_original_tokens_or_types_in_output(self):
        il = b"\x7B" + struct.pack("<I", FIELDDEF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        output = json.dumps(inspect(il))
        for forbidden in ("0A000001", "04000001", "GetInitHwSettings",
                          "carcom_repository", "signature_private"):
            self.assertNotIn(forbidden, output)

    def test_16_synthetic_three_sha_pinned_inputs_are_readonly(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            pins = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (folder / name).write_bytes(pe)
                pins[name.casefold()] = (name, hashlib.sha256(pe).hexdigest())
            with patch.object(tool, "EXPECTED", pins), patch.object(
                tool, "inspect_module", return_value={
                    "interface_getinithw_callvirt_sites": 0,
                    "immediately_preceding_field_opcodes": {"ldfld": 0},
                }
            ):
                r = tool.audit(folder)
            self.assertEqual(len(r["results"]), 3)
            self.assertFalse(r["original_assemblies_loaded_or_executed"])
            self.assertFalse(r["field_shape_match_proves_semantic_clr_type_identity"])
            self.assertFalse(r["profile_identifiers_argument_proven"])
            self.assertNotIn(str(folder), json.dumps(r))

    def test_17_wrong_sha_pin_stops_before_reading_metadata(self):
        pe = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            pins = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (folder / name).write_bytes(pe)
                pins[name.casefold()] = (name, "0" * 64)
            with patch.object(tool, "EXPECTED", pins):
                with self.assertRaisesRegex(MetadataError, "SHA256"):
                    tool.audit(folder)

    def test_19_field_address_is_not_field_value_shape(self):
        il = b"\x7C" + struct.pack("<I", FIELDDEF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        counts = inspect(il, field_sig=b"\x06\x08", param_sig=b"\x20\x01\x01\x08")
        self.assertEqual(counts["field_shape_different_from_target_parameter"], 1)
        self.assertEqual(counts["field_shape_equal_to_target_parameter_ignoring_local_type_tokens"], 0)

    def test_20_field_address_matches_byref_parameter_shape_only(self):
        il = b"\x7F" + struct.pack("<I", FIELDREF) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"
        counts = inspect(il, field_sig=b"\x06\x08", param_sig=b"\x20\x01\x01\x10\x08")
        self.assertEqual(counts["field_shape_equal_to_target_parameter_ignoring_local_type_tokens"], 1)
        self.assertEqual(counts["field_shape_different_from_target_parameter"], 0)

    def test_18_cli_errors_hide_owner_paths(self):
        with tempfile.TemporaryDirectory() as d:
            err = StringIO()
            with redirect_stderr(err):
                code = tool.main(["--folder", str(Path(d) / "missing")])
            self.assertEqual(code, 2)
            self.assertEqual(set(json.loads(err.getvalue())), {"status", "error_class"})
            self.assertNotIn(d, err.getvalue())


if __name__ == "__main__":
    unittest.main()
