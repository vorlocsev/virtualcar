"""Synthetic bounded CLR token-neutral signatures. No original VIDA binaries."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_2015a_inithw_signature_shapes as tool

# HasThis + 1 explicit param + void return + class TypeRef encoded index
SIG_A = b"\x20\x01\x01\x12\x05"   # TypeRef row 1 (1<<2 | 1)
SIG_B = b"\x20\x01\x01\x12\x11"   # TypeRef row 4 (4<<2 | 1)
SIG_C = b"\x20\x01\x01\x11\x05"   # valuetype TypeRef row 1
SIG_D = b"\x20\x01\x08\x12\x05"   # int32 return, class TypeRef param


def synthetic_meta(repo_sig=SIG_A, ref_one=SIG_B, ref_two=SIG_B):
    return {
        "bizservices.carcom.db.dll": {
            "methods": {1: {
                "name": "GetInitHwSettings",
                "repository_owner": True,
                "signature_bytes_private": repo_sig,
            }},
            "carcom_repository_direct_icarcomrepository_interfaceimpl_rows": 1,
        },
        "bizservices.vehiclecommprovider.dll": {
            "target_reference_parent_type_families": {0x0A000001: "icarcom_repository"},
            "target_reference_signature_bytes_private": {0x0A000001: ref_one},
        },
        "workflow.dll": {
            "target_reference_parent_type_families": {0x0A000001: "icarcom_repository"},
            "target_reference_signature_bytes_private": {0x0A000001: ref_two},
        },
    }


class SignatureShapesTests(unittest.TestCase):
    def test_01_local_type_tokens_differ_but_same_shape(self):
        self.assertNotEqual(SIG_A, SIG_B)
        self.assertEqual(tool.decode_shape(SIG_A), tool.decode_shape(SIG_B))

    def test_02_reference_and_value_type_shapes_different(self):
        self.assertNotEqual(tool.decode_shape(SIG_A), tool.decode_shape(SIG_C))

    def test_03_return_type_structure_difference(self):
        self.assertNotEqual(tool.decode_shape(SIG_A)[1], tool.decode_shape(SIG_D)[1])

    def test_04_generic_instance_arguments_shape(self):
        a = b"\x20\x01\x01\x15\x12\x05\x01\x08"  # void return, List<int> param
        b = b"\x20\x01\x01\x15\x12\x11\x01\x08"  # different local coded index
        self.assertEqual(tool.decode_shape(a), tool.decode_shape(b))

    def test_05_signature_has_this_difference_detected(self):
        self.assertNotEqual(tool.decode_shape(SIG_A),
                            tool.decode_shape(b"\x00" + SIG_A[1:]))

    def test_06_invalid_compressed_type_token_rejected(self):
        with self.assertRaises(tool.MetadataError):
            tool.decode_shape(b"\x20\x01\x01\x12\x00")

    def test_07_unsupported_array_is_not_guessed(self):
        with self.assertRaises(tool.UnsupportedSignature):
            tool.decode_shape(b"\x20\x01\x01\x14\x08\x01")

    def test_08_trailing_bytes_are_not_ignored(self):
        with self.assertRaises(tool.UnsupportedSignature):
            tool.decode_shape(SIG_A + b"\xFF")

    def test_09_two_token_neutral_equal_counts(self):
        counts = tool._compare_private(synthetic_meta())
        self.assertEqual(counts["signatures_shape_compared"], 2)
        self.assertEqual(counts["signatures_structurally_equal_ignoring_type_tokens"], 2)
        self.assertEqual(counts["signatures_structurally_different"], 0)
        self.assertNotIn("0A000001", json.dumps(counts))

    def test_10_exact_shape_difference_only_in_one_reference(self):
        counts = tool._compare_private(synthetic_meta(ref_two=SIG_C))
        self.assertEqual(counts["signatures_structurally_equal_ignoring_type_tokens"], 1)
        self.assertEqual(counts["signatures_structurally_different"], 1)
        self.assertEqual(counts["parameters_structurally_different"], 1)

    def test_11_one_unclassified_signature_is_separately_counted(self):
        counts = tool._compare_private(synthetic_meta(ref_two=b"\x20\x01\x01\x14"))
        self.assertEqual(counts["signatures_shape_compared"], 1)
        self.assertEqual(counts["signatures_unclassified"], 1)
        self.assertEqual(counts["signatures_structurally_equal_ignoring_type_tokens"], 1)

    def test_12_missing_repo_target_refuses_any_inference(self):
        meta = synthetic_meta()
        meta["bizservices.carcom.db.dll"]["methods"].clear()
        with self.assertRaises(tool.MetadataError):
            tool._compare_private(meta)

    def test_13_missing_interface_reference_refuses_selection(self):
        meta = synthetic_meta()
        meta["workflow.dll"]["target_reference_parent_type_families"].clear()
        with self.assertRaises(tool.MetadataError):
            tool._compare_private(meta)

    def test_14_private_signature_bytes_not_exposed_by_comparator(self):
        counts = json.dumps(tool._compare_private(synthetic_meta()))
        self.assertNotIn("signature_bytes_private", counts)
        self.assertNotIn("target_reference", counts)
        self.assertNotIn("GetInitHwSettings", counts)

    def test_15_bad_folder_cli_error_sanitized(self):
        with tempfile.TemporaryDirectory() as d:
            err = StringIO()
            with contextlib.redirect_stderr(err):
                status = tool.main(["--folder", str(Path(d) / "missing")])
            self.assertEqual(status, 2)
            self.assertEqual(set(json.loads(err.getvalue())), {"status", "error_class"})
            self.assertNotIn(d, err.getvalue())

    def test_16_sha_mismatch_rejected_before_metadata_parsing(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            pins = {}
            for filename in ("BizServices.CarCom.DB.DLL",
                             "BizServices.VehicleCommProvider.DLL", "Workflow.DLL"):
                (folder / filename).write_bytes(b"synthetic-invalid-PE" * 10)
                pins[filename.casefold()] = (filename, "0" * 64)
            with patch.object(tool, "EXPECTED", pins):
                with self.assertRaisesRegex(tool.MetadataError, "hash mismatch"):
                    tool.audit(folder)

    def test_17_bounded_generic_depth_rejected(self):
        sig = b"\x20\x01\x01" + b"\x1D" * 30 + b"\x08"
        with self.assertRaises(tool.UnsupportedSignature):
            tool.decode_shape(sig)


if __name__ == "__main__":
    unittest.main()
