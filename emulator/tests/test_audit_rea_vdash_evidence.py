"""Eight synthetic security/meaning checks for offline REA VDASH evidence audit.

No proprietary DLL, method body, CIL text or real VIN is used in this module.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_rea_vdash_evidence.py"
spec = importlib.util.spec_from_file_location("audit_rea_vdash_evidence", SOURCE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

SHA = "a" * 64
MVID = "01234567-89ab-cdef-0123-456789abcdef"
PRIVATE = "VENDOR_PRIVATE_METHOD_DO_NOT_PUBLISH"


def edge(target, offset, kind, name=PRIVATE):
    return {
        "caller_token": "0x0600132b",
        "il_offset": offset, "target_token": target,
        "opcode": "call", "target_kind": kind,
        "target_name": name,
        "target_declaring_type": "Private.Obfuscated",
        "private_can_payload": "SECRET_FAKE_VIN",
    }


def fixture():
    return {
        "normalized_result": {
            "artifact": {"path": "C:/PRIVATE/VDASH/Frontend.Client.Core.dll",
                         "sha256": SHA, "byte_length": 123456, "format": "pe"},
            "module": {"name": "Frontend.Client.Core.dll", "mvid": MVID},
            "identity_scope": {
                "token_identity": "build-local",
                "requires_artifact_sha256": SHA,
                "requires_mvid": MVID,
            },
            "coverage": {"state": "complete", "issues": []},
            "methods": [
                {"token": "0x0600132b", "body": {"status": "present",
                                               "raw_il": "PRIVATE_IL"}},
                {"token": "0x06001359", "body": {"status": "present"}},
                {"token": "0x06001160", "body": {"status": "partial"}},
            ],
            "call_edges": [
                edge("0x2b000002", 0x0124, "method-spec"),
                edge("0x06001359", 0x0129, "method-def"),
                edge("0x2b000002", 0x0423, "method-spec"),
                edge("0x06001359", 0x0428, "method-def"),
            ],
            "user_strings": {"literals": [{"value": "PRIVATE_VIN"}]},
        },
    }


class ReaStaticEvidenceTests(unittest.TestCase):
    def test_01_both_sites_and_partial_method_observed(self):
        output = tool.audit(fixture())
        self.assertEqual(output["format"], tool.FORMAT)
        for result in output["call_sites"].values():
            self.assertEqual(result, {
                "observed_call_count": 2,
                "exact_expected_sites": True,
                "target_identity_resolved": True,
            })
        self.assertEqual(output["method_bodies"]["predicate"],
                         {"inspected": True, "status": "present"})
        self.assertEqual(output["method_bodies"]["parse_data"],
                         {"inspected": True, "status": "partial"})
        self.assertEqual(output["method_bodies"]["ecus_constructor"],
                         {"inspected": False, "status": "not_inspected"})

    def test_02_missing_edges_are_unknown_not_negative_evidence(self):
        source = fixture()
        result = source["normalized_result"]
        result["coverage"]["state"] = "partial"
        result["methods"] = []
        result["call_edges"] = []
        report = tool.audit(source)
        self.assertEqual(report["assembly"]["coverage"], "partial")
        self.assertEqual(report["call_sites"]["methodspec_string_candidate"][
            "observed_call_count"], 0)
        self.assertFalse(report["call_sites"]["methodspec_string_candidate"][
            "exact_expected_sites"])
        self.assertEqual(report["method_bodies"]["detect"]["status"], "not_inspected")

    def test_03_wrong_module_and_unattested_scope_rejected(self):
        source = fixture()
        source["normalized_result"]["module"]["name"] = "AnotherAssembly.dll"
        with self.assertRaisesRegex(ValueError, "wrong_module"):
            tool.audit(source)
        source = fixture()
        source["normalized_result"]["identity_scope"]["token_identity"] = "unknown"
        with self.assertRaisesRegex(ValueError, "unattested_token_scope"):
            tool.audit(source)

    def test_04_artifact_sha_and_mvid_conflicts_rejected(self):
        source = fixture()
        source["normalized_result"]["identity_scope"][
            "requires_artifact_sha256"] = "b" * 64
        with self.assertRaisesRegex(ValueError, "artifact_identity_conflict"):
            tool.audit(source)
        source = fixture()
        source["normalized_result"]["identity_scope"]["requires_mvid"] = (
            "ffffffff-ffff-ffff-ffff-ffffffffffff"
        )
        with self.assertRaisesRegex(ValueError, "module_identity_conflict"):
            tool.audit(source)

    def test_05_wrong_offsets_or_extra_call_not_exact(self):
        source = fixture()
        edges = source["normalized_result"]["call_edges"]
        edges[0]["il_offset"] = 0x0125
        report = tool.audit(source)
        self.assertFalse(report["call_sites"]["methodspec_string_candidate"][
            "exact_expected_sites"])
        self.assertTrue(report["call_sites"]["opaque_predicate"][
            "exact_expected_sites"])
        source = fixture()
        source["normalized_result"]["call_edges"].append(
            edge("0x2b000002", 0x0600, "method-spec"))
        result = tool.audit(source)["call_sites"]["methodspec_string_candidate"]
        self.assertEqual(result["observed_call_count"], 3)
        self.assertFalse(result["exact_expected_sites"])

    def test_06_unresolvable_generic_method_is_not_assumed(self):
        source = fixture()
        source["normalized_result"]["call_edges"][0]["target_name"] = None
        result = tool.audit(source)
        self.assertFalse(result["call_sites"]["methodspec_string_candidate"][
            "target_identity_resolved"])
        self.assertTrue(result["call_sites"]["opaque_predicate"][
            "target_identity_resolved"])

    def test_07_no_raw_names_paths_or_il_are_emitted(self):
        source = fixture()
        source["normalized_result"]["artifact"]["path"] = "C:/SECRET/VIN/FILE"
        report = tool.audit(source)
        dumped = json.dumps(report)
        for secret in ("VENDOR_PRIVATE", "Private.Obfuscated", "PRIVATE_IL",
                       "PRIVATE_VIN", "SECRET_FAKE_VIN", "C:/SECRET", SHA, MVID):
            self.assertNotIn(secret, dumped)
        self.assertFalse(report["contains_private_metadata"])
        self.assertFalse(report["client_acceptance_verified"])
        self.assertFalse(report["ecu_identity_verified"])

    def test_08_cli_refuses_overwrite_and_corrupt_input(self):
        with tempfile.TemporaryDirectory() as work:
            private = Path(work) / "rea-private.json"
            out = Path(work) / "safe.json"
            source = json.dumps(fixture())
            private.write_text(source, encoding="utf-8")
            self.assertEqual(tool.main([str(private), "--output", str(out)]), 0)
            saved = out.read_bytes()
            self.assertEqual(tool.main([str(private), "--output", str(out)]), 2)
            self.assertEqual(out.read_bytes(), saved)
            self.assertEqual(private.read_text(encoding="utf-8"), source)
            private.write_text('{"normalized_result":', encoding="utf-8")
            broken = Path(work) / "broken.json"
            self.assertEqual(tool.main([str(private), "--output", str(broken)]), 2)
            self.assertFalse(broken.exists())


if __name__ == "__main__":
    unittest.main()
