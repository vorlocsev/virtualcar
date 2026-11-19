"""Owner-safe synthetic CLR manifest AssemblyDef vs external AssemblyRef gates."""
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
import audit_vida_2015a_inithw_assemblydef as tool
from test_vida_2015a_inithw_assembly_identity import synthetic_pe

FULL_KEY = b"SyntheticPublicKeyForUnitTestsOnly"
TOKEN = hashlib.sha1(FULL_KEY).digest()[-8:][::-1]
NAMES = {
    "bizservices.carcom.db.dll": "BizServices.CarCom.DB.DLL",
    "bizservices.vehiclecommprovider.dll": "BizServices.VehicleCommProvider.DLL",
    "workflow.dll": "Workflow.DLL",
}


def _fixture(*, caller_names=("Demo.Contracts", "Demo.Contracts"),
             caller_versions=((1, 2, 3, 4), (1, 2, 3, 4)),
             second_token=TOKEN, repo_name="Demo.Contracts",
             first_full_key=False):
    originals = {
        "bizservices.carcom.db.dll": synthetic_pe(
            repo=True, with_manifest=True, local_interface=True,
            assembly_name=repo_name, key=FULL_KEY,
        ),
        "bizservices.vehiclecommprovider.dll": synthetic_pe(
            assembly_name=caller_names[0], version=caller_versions[0],
            key=FULL_KEY if first_full_key else TOKEN,
            reference_full_key=first_full_key,
        ),
        "workflow.dll": synthetic_pe(
            assembly_name=caller_names[1], version=caller_versions[1],
            key=second_token,
        ),
    }
    return {k: tool._table_layout(v) for k, v in originals.items()}, originals


class OriginalAssemblyDefComparisonTests(unittest.TestCase):
    def test_01_local_typedef_vs_two_external_assemblyrefs_match(self):
        metadata, _ = _fixture()
        counts = tool._compare_private(metadata)
        self.assertEqual(counts["original_repository_local_interface_typedef"], 1)
        self.assertEqual(counts["original_repository_assemblydef_count"], 1)
        self.assertEqual(counts["caller_typeref_assemblyref_candidates"], 2)
        self.assertEqual(counts["stored_canonical_name_version_culture_token_equal"], 2)
        self.assertEqual(counts["stored_canonical_name_version_culture_token_different"], 0)
        self.assertEqual(counts["normalized_publickeytoken_equal"], 2)
        self.assertEqual(counts["full_interface_typename_equal"], 2)

    def test_02_one_external_assembly_name_mismatch_counted(self):
        metadata, _ = _fixture(caller_names=("Demo.Contracts", "Other.Contracts"))
        counts = tool._compare_private(metadata)
        self.assertEqual(counts["assembly_simple_name_equal"], 1)
        self.assertEqual(counts["assembly_simple_name_different"], 1)
        self.assertEqual(counts["stored_canonical_name_version_culture_token_different"], 1)

    def test_03_one_external_version_mismatch_counted(self):
        metadata, _ = _fixture(
            caller_versions=((1, 2, 3, 4), (1, 2, 3, 5))
        )
        counts = tool._compare_private(metadata)
        self.assertEqual(counts["assembly_version_equal"], 1)
        self.assertEqual(counts["assembly_version_different"], 1)

    def test_04_one_public_key_token_mismatch_counted(self):
        metadata, _ = _fixture(second_token=b"\x00" * 8)
        counts = tool._compare_private(metadata)
        self.assertEqual(counts["normalized_publickeytoken_equal"], 1)
        self.assertEqual(counts["normalized_publickeytoken_different"], 1)

    def test_05_reference_using_full_key_normalized_to_token(self):
        metadata, _ = _fixture(first_full_key=True)
        counts = tool._compare_private(metadata)
        self.assertEqual(counts["caller_assemblyref_keys_are_full"], 1)
        self.assertEqual(counts["caller_assemblyref_keys_are_token"], 1)
        self.assertEqual(counts["normalized_publickeytoken_equal"], 2)

    def test_06_missing_manifest_assemblydef_refuses_comparison(self):
        metadata, _ = _fixture()
        metadata["bizservices.carcom.db.dll"]["counts"][32] = 0
        with self.assertRaises(tool.MetadataError):
            tool._compare_private(metadata)

    def test_07_repository_typeref_not_local_typedef_refuses_comparison(self):
        metadata, _ = _fixture()
        metadata["bizservices.carcom.db.dll"] = tool._table_layout(
            synthetic_pe(repo=True, with_manifest=True,
                         local_interface=False, key=FULL_KEY)
        )
        with self.assertRaises(tool.MetadataError):
            tool._compare_private(metadata)

    def test_08_invalid_external_token_length_refuses_comparison(self):
        metadata, _ = _fixture()
        metadata["workflow.dll"] = tool._table_layout(
            synthetic_pe(key=b"\xAA\xBB")
        )
        with self.assertRaises(tool.MetadataError):
            tool._compare_private(metadata)

    def test_09_full_key_to_token_derivation_is_deterministic(self):
        self.assertEqual(tool._public_key_token(FULL_KEY), TOKEN)
        with self.assertRaises(tool.MetadataError):
            tool._public_key_token(b"")

    def test_10_output_does_not_contain_private_assembly_identifiers(self):
        metadata, _ = _fixture()
        output = json.dumps(tool._compare_private(metadata))
        for private in ("Demo.Contracts", "ICarComRepository", "SyntheticPublicKey",
                        "BizServices", "1.2.3.4"):
            self.assertNotIn(private, output)

    def test_11_sha_pinned_synthetic_end_to_end_without_execution(self):
        _, original = _fixture()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            expected = {}
            for canonical, binary in original.items():
                filename = NAMES[canonical]
                (root / filename).write_bytes(binary)
                expected[canonical] = (filename, hashlib.sha256(binary).hexdigest())
            with patch.object(tool, "EXPECTED", expected):
                result = tool.audit(root)
            self.assertEqual(result["counts"][
                "stored_canonical_name_version_culture_token_equal"], 2)
            self.assertFalse(result["stored_assembly_identity_proves_runtime_binding"])
            self.assertFalse(result["stored_interface_typename_proves_methodimpl_dispatch"])
            self.assertFalse(result["caller_profile_identifiers_argument_verified"])
            self.assertFalse(result["d2_baudrate_verified"])
            self.assertFalse(result["original_vida_readvin_accepted"])
            self.assertNotIn(str(root), json.dumps(result))

    def test_12_sha_mismatch_rejected_before_metadata_parse(self):
        _, original = _fixture()
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            expected = {}
            for canonical, binary in original.items():
                filename = NAMES[canonical]
                (root / filename).write_bytes(binary)
                expected[canonical] = (filename, "0" * 64)
            with patch.object(tool, "EXPECTED", expected):
                with self.assertRaisesRegex(tool.MetadataError, "SHA256 mismatch"):
                    tool.audit(root)

    def test_13_cli_error_exposes_only_class(self):
        with tempfile.TemporaryDirectory() as d:
            stderr = StringIO()
            with redirect_stderr(stderr):
                status = tool.main(["--folder", str(Path(d) / "not-present")])
            self.assertEqual(status, 2)
            self.assertEqual(set(json.loads(stderr.getvalue())), {"status", "error_class"})
            self.assertNotIn(d, stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
