"""Synthetic original-VIDA CLR interface/MethodImpl metadata tests only."""
from contextlib import redirect_stderr
from io import StringIO
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_vida_2015a_inithw_methodimpl as tool
from test_vida_2015a_inithw_assembly_identity import synthetic_pe

NAMES = (
    "BizServices.CarCom.DB.DLL",
    "BizServices.VehicleCommProvider.DLL",
    "Workflow.DLL",
)


def _synthetic_repo(*, explicit=False, methods=True, local=True):
    return tool._table_layout(synthetic_pe(
        repo=True, local_interface=local, with_manifest=True,
        with_methods=methods, explicit_method_impl=explicit,
        key=b"SyntheticOnlyKey",
    ))


class OriginalVidaMethodImplSyntheticTests(unittest.TestCase):
    def test_01_local_repository_and_interface_typedef_present(self):
        self.assertEqual(tool._types(_synthetic_repo()), (1, 2))

    def test_02_both_methoddef_declarations_found(self):
        meta = _synthetic_repo()
        self.assertEqual(len(tool._method_rows(meta, 1)), 1)
        self.assertEqual(len(tool._method_rows(meta, 2)), 1)

    def test_03_same_module_signatures_equal_and_stored_as_counts(self):
        result = tool.inspect_metadata(_synthetic_repo())
        self.assertEqual(result["same_module_raw_method_signature_equal"], 1)
        self.assertEqual(result["same_module_raw_method_signature_different"], 0)
        self.assertNotIn("SyntheticOnlyKey", json.dumps(result))

    def test_04_repo_method_public_virtual_instance(self):
        result = tool.inspect_metadata(_synthetic_repo())
        self.assertEqual(result["repository_method_public"], 1)
        self.assertEqual(result["repository_method_virtual"], 1)
        self.assertEqual(result["repository_method_instance"], 1)
        self.assertEqual(result["repository_method_abstract"], 0)

    def test_05_interface_method_public_virtual_abstract(self):
        result = tool.inspect_metadata(_synthetic_repo())
        self.assertEqual(result["interface_method_public"], 1)
        self.assertEqual(result["interface_method_virtual"], 1)
        self.assertEqual(result["interface_method_abstract"], 1)

    def test_06_no_methodimpl_record_is_not_failure(self):
        result = tool.inspect_metadata(_synthetic_repo())
        self.assertEqual(result["repository_methodimpl_rows_total"], 0)
        self.assertEqual(result["repository_methodimpl_exact_target_pair"], 0)

    def test_07_explicit_methodimpl_exact_pair_detected(self):
        result = tool.inspect_metadata(_synthetic_repo(explicit=True))
        self.assertEqual(result["repository_methodimpl_rows_total"], 1)
        self.assertEqual(result["repository_methodimpl_body_repository_target"], 1)
        self.assertEqual(result["repository_methodimpl_declaration_interface_target"], 1)
        self.assertEqual(result["repository_methodimpl_exact_target_pair"], 1)

    def test_08_missing_local_interface_refuses_inference(self):
        with self.assertRaises(tool.MetadataError):
            tool.inspect_metadata(_synthetic_repo(local=False, methods=False))

    def test_09_missing_target_methoddef_refuses_inference(self):
        with self.assertRaises(tool.MetadataError):
            tool.inspect_metadata(_synthetic_repo(methods=False))

    def test_10_disallowed_target_method_owner_not_guessed(self):
        meta = _synthetic_repo()
        meta["counts"][6] = 1
        with self.assertRaises(tool.MetadataError):
            tool.inspect_metadata(meta)

    def test_11_owner_private_no_export_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            pinned = {}
            for filename in NAMES:
                data = synthetic_pe(
                    repo=filename == NAMES[0],
                    local_interface=filename == NAMES[0],
                    with_methods=filename == NAMES[0],
                    with_manifest=True,
                    key=b"SyntheticOnlyKey",
                )
                (folder / filename).write_bytes(data)
                pinned[filename.casefold()] = (filename, hashlib.sha256(data).hexdigest())
            with patch.object(tool, "EXPECTED", pinned):
                result = tool.audit(folder)
            self.assertEqual(result["counts"]["repository_getinithw_methoddef_candidates"], 1)
            for flag in ("original_assemblies_loaded_or_executed",
                         "original_methods_signatures_tokens_types_or_paths_exported",
                         "implicit_interface_dispatch_verified",
                         "explicit_methodimpl_proves_runtime_execution",
                         "memberref_dispatch_from_caller_verified",
                         "caller_profile_identifiers_argument_verified",
                         "d2_baudrate_verified", "original_vida_readvin_accepted"):
                self.assertIs(result[flag], False)
            report = json.dumps(result)
            self.assertNotIn(str(folder), report)
            self.assertNotIn("SyntheticOnlyKey", report)

    def test_12_wrong_sha_pin_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            pinned = {}
            for filename in NAMES:
                (folder / filename).write_bytes(b"NotAnOriginalDll" * 20)
                pinned[filename.casefold()] = (filename, "0" * 64)
            with patch.object(tool, "EXPECTED", pinned):
                with self.assertRaisesRegex(tool.MetadataError, "SHA256"):
                    tool.audit(folder)

    def test_13_sanitized_cli_error(self):
        with tempfile.TemporaryDirectory() as d:
            stderr = StringIO()
            with redirect_stderr(stderr):
                rc = tool.main(["--folder", str(Path(d) / "not-existing")])
            self.assertEqual(rc, 2)
            obj = json.loads(stderr.getvalue())
            self.assertEqual(set(obj), {"status", "error_class"})
            self.assertNotIn(d, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
