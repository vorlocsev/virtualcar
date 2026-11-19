"""Synthetic EH small/fat section and GetInitHwSettings membership gates."""
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
import audit_vida_2015a_inithw_eh_regions as tool
from audit_vida_2015a_inithw_metadata import MetadataError
from test_vida_2015a_inithw_il_calls import with_first_method_body

TARGET = 0x0A000001
FIELD = 0x04000001
IL = b"\x7B" + struct.pack("<I", FIELD) + b"\x6F" + struct.pack("<I", TARGET) + b"\x2A"


def fixture(*, flags=0, try_offset=0, try_length=10,
            handler_offset=10, handler_length=1, extra=0,
            fat_section=False, other_section=False,
            method_more=True, chained=False):
    """Build an original-independent fat CIL header and synthetic EH section."""
    pe = bytearray(with_first_method_body(IL))
    hdr_flags = 0x3003 | (0x0008 if method_more else 0)
    struct.pack_into("<HHII", pe, 0x400, hdr_flags, 8, len(IL), 0)
    pe[0x40C:0x40C + len(IL)] = IL
    at = (0x40C + len(IL) + 3) & ~3
    if fat_section:
        kind = 0x41
        size = 28
        clause = struct.pack("<IIIIII", flags, try_offset, try_length,
                             handler_offset, handler_length, extra)
    else:
        kind = 0x01
        size = 16
        clause = struct.pack("<HHBHBI", flags, try_offset, try_length,
                             handler_offset, handler_length, extra)
    if other_section:
        kind, size, clause = 0x02, 4, b""
    if chained:
        kind |= 0x80
    pe[at] = kind
    pe[at + 1:at + 4] = size.to_bytes(3, "little") if fat_section else bytes([size, 0, 0])
    pe[at + 4:at + 4 + len(clause)] = clause
    if chained:
        next_at = (at + size + 3) & ~3
        pe[next_at:next_at + 4] = b"\x01\x10\x00\x00"
        pe[next_at + 4:next_at + 16] = struct.pack(
            "<HHBHBI", 0, 0, 10, 10, 1, 0
        )
    return bytes(pe)


def inspect(pe):
    md = tool._metadata_tables(pe)
    md["target_reference_parent_type_families"][TARGET] = "icarcom_repository"
    md["target_reference_signature_contracts"][TARGET] = {
        "parameters": 1, "has_this": True,
    }
    with patch.object(tool, "_metadata_tables", return_value=md):
        return tool.inspect_module(pe, require_interface_memberref=True)


class OriginalVidaEhRegionSyntheticTests(unittest.TestCase):
    def test_01_small_catch_reader_in_try(self):
        c = inspect(fixture())
        self.assertEqual(c["target_getinithw_calls"], 1)
        self.assertEqual(c["small_eh_sections"], 1)
        self.assertEqual(c["eh_clause_kind_counts"]["catch"], 1)
        self.assertEqual(c["reader_in_try"], 1)

    def test_02_small_finally_reader_in_handler(self):
        c = inspect(fixture(flags=2, try_length=5,
                            handler_offset=5, handler_length=5))
        self.assertEqual(c["eh_clause_kind_counts"]["finally"], 1)
        self.assertEqual(c["reader_in_handler"], 1)
        self.assertEqual(c["reader_ldfld_and_call_cross_eh_membership"], 1)

    def test_03_small_fault_reader_in_handler(self):
        c = inspect(fixture(flags=4, try_length=5,
                            handler_offset=5, handler_length=5))
        self.assertEqual(c["eh_clause_kind_counts"]["fault"], 1)
        self.assertEqual(c["reader_in_handler"], 1)

    def test_04_filter_region_reader_at_filter_offset(self):
        c = inspect(fixture(flags=1, try_length=5, extra=5))
        self.assertEqual(c["eh_clause_kind_counts"]["filter"], 1)
        self.assertEqual(c["reader_in_filter"], 1)

    def test_05_fat_catch_eh_section_parsed(self):
        c = inspect(fixture(fat_section=True))
        self.assertEqual(c["fat_eh_sections"], 1)
        self.assertEqual(c["reader_in_try"], 1)
        self.assertEqual(c["small_eh_sections"], 0)

    def test_06_fat_method_without_moresects_has_no_eh(self):
        c = inspect(fixture(method_more=False))
        self.assertEqual(c["target_calling_methods_without_extra_sections"], 1)
        self.assertEqual(c["reader_outside_eh_regions"], 1)

    def test_07_other_extra_section_is_not_eh(self):
        c = inspect(fixture(other_section=True))
        self.assertEqual(c["target_calling_methods_with_extra_sections"], 1)
        self.assertEqual(c["other_extra_sections"], 1)
        self.assertEqual(c["reader_outside_eh_regions"], 1)
        self.assertEqual(sum(c["eh_clause_kind_counts"].values()), 0)

    def test_08_chained_eh_sections_counted(self):
        c = inspect(fixture(chained=True))
        self.assertEqual(c["small_eh_sections"], 2)
        self.assertEqual(c["eh_clause_kind_counts"]["catch"], 2)

    def test_09_reader_outside_try_and_handler(self):
        c = inspect(fixture(try_length=5, handler_offset=10, handler_length=1))
        self.assertEqual(c["reader_outside_eh_regions"], 1)
        self.assertEqual(c["reader_in_try"], 0)

    def test_10_invalid_clause_kind_rejected(self):
        with self.assertRaises(MetadataError):
            inspect(fixture(flags=8))

    def test_11_out_of_bounds_eh_region_rejected(self):
        with self.assertRaises(MetadataError):
            inspect(fixture(try_length=20))

    def test_12_non_instruction_aligned_clause_offset_rejected(self):
        with self.assertRaises(MetadataError):
            inspect(fixture(try_offset=1))

    def test_13_invalid_filter_offset_rejected(self):
        with self.assertRaises(MetadataError):
            inspect(fixture(flags=1, extra=10))

    def test_14_original_eh_byte_offsets_not_exported(self):
        c = inspect(fixture())
        report = json.dumps(c)
        for item in ("GetInitHwSettings", "0x0A000001", "catch_type_name",
                     "FieldDef", "0x04000001"):
            self.assertNotIn(item, report)

    def test_15_sha_pinned_synthetic_sources_only(self):
        data = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / name).write_bytes(data)
                expected[name.casefold()] = (name, hashlib.sha256(data).hexdigest())
            with patch.object(tool, "EXPECTED", expected), patch.object(
                tool, "inspect_module", return_value={
                    "cil_method_bodies_examined": 0, "target_getinithw_calls": 0,
                }
            ):
                result = tool.audit(root)
            self.assertEqual(len(result["results"]), 3)
            self.assertFalse(result["original_assemblies_loaded_or_executed"])
            self.assertFalse(result["eh_regions_prove_runtime_execution_or_stack_provenance"])
            self.assertFalse(result["original_profile_identifiers_argument_verified"])
            self.assertNotIn(tmp, json.dumps(result))

    def test_16_wrong_source_sha_rejected(self):
        data = with_first_method_body(b"\x2A")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = {}
            for name in ("BizServices.CarCom.DB.DLL",
                         "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (root / name).write_bytes(data)
                expected[name.casefold()] = (name, "0" * 64)
            with patch.object(tool, "EXPECTED", expected):
                with self.assertRaisesRegex(MetadataError, "SHA256"):
                    tool.audit(root)

    def test_17_sanitized_error_class_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = StringIO()
            with redirect_stderr(err):
                rc = tool.main(["--folder", str(Path(tmp) / "missing")])
            self.assertEqual(rc, 2)
            self.assertEqual(set(json.loads(err.getvalue())), {"status", "error_class"})
            self.assertNotIn(tmp, err.getvalue())


if __name__ == "__main__":
    unittest.main()
