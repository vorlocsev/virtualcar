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
                "decoded_caller_corroborated": False,
            })
        self.assertEqual(output["method_bodies"]["predicate"],
                         {"inspected": True, "status": "present", "cil_decode": "unreported"})
        self.assertEqual(output["method_bodies"]["parse_data"],
                         {"inspected": True, "status": "partial", "cil_decode": "unreported"})
        self.assertEqual(output["method_bodies"]["ecus_constructor"],
                         {"inspected": False, "status": "not_inspected", "cil_decode": "not_inspected"})

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


    @staticmethod
    def _structural_fixture():
        # Synthetic graph shape, not a vendor IL body or an observed runtime path.
        value = fixture()
        edges = value["normalized_result"]["call_edges"]
        edges.extend([
            {**edge("0x060011bb", 0x017f, "method-def"),
             "opcode": "newobj"},
            {**edge("0x0600126d", 0x0268, "method-def"),
             "opcode": "newobj"},
            {**edge("0x06001160", 0x025e, "method-def"),
             "caller_token": "0x0600115d"},
            {**edge("0x0600117a", 0x024e, "method-def"),
             "caller_token": "0x0600115d"},
            {**edge("0x0600117b", 0x0259, "method-def"),
             "caller_token": "0x0600115d"},
        ])
        value["normalized_result"]["methods"].append({
            "token": "0x0600115d", "body": {"status": "present"}
        })
        return value

    def test_09_five_expected_caller_callee_anchors(self):
        report = tool.audit(self._structural_fixture())
        self.assertEqual(set(report["structural_edges"]), {
            "detect_to_detect_result_ctor",
            "detect_to_ecus_ctor",
            "execute_to_parse_data",
            "execute_to_result_helper_a",
            "execute_to_result_helper_b",
        })
        for item in report["structural_edges"].values():
            self.assertEqual(item,
                             {"observed_call_count": 1,
                              "exact_expected_site": True,
                              "decoded_caller_corroborated": False})
        self.assertEqual(report["method_bodies"]["execute"],
                         {"inspected": True, "status": "present", "cil_decode": "unreported"})
        self.assertFalse(report["client_acceptance_verified"])

    def test_10_missing_detect_result_constructor_not_accepted(self):
        value = self._structural_fixture()
        value["normalized_result"]["call_edges"] = [
            e for e in value["normalized_result"]["call_edges"]
            if e["target_token"] != "0x060011bb"]
        report = tool.audit(value)
        self.assertEqual(report["structural_edges"][
            "detect_to_detect_result_ctor"], {
                "observed_call_count": 0, "exact_expected_site": False,
                "decoded_caller_corroborated": False})
        self.assertTrue(report["structural_edges"][
            "execute_to_parse_data"]["exact_expected_site"])

    def test_11_missing_execute_to_parse_data_not_accepted(self):
        value = self._structural_fixture()
        value["normalized_result"]["call_edges"] = [
            e for e in value["normalized_result"]["call_edges"]
            if e["target_token"] != "0x06001160"]
        report = tool.audit(value)
        self.assertFalse(report["structural_edges"][
            "execute_to_parse_data"]["exact_expected_site"])

    def test_12_wrong_caller_does_not_become_a_relationship(self):
        value = self._structural_fixture()
        for edge_record in value["normalized_result"]["call_edges"]:
            if edge_record["target_token"] == "0x06001160":
                edge_record["caller_token"] = "0x0600115c"
        report = tool.audit(value)
        self.assertEqual(report["structural_edges"]["execute_to_parse_data"][
            "observed_call_count"], 0)

    def test_13_wrong_opcode_rejects_constructor(self):
        value = self._structural_fixture()
        for edge_record in value["normalized_result"]["call_edges"]:
            if edge_record["target_token"] == "0x0600126d":
                edge_record["opcode"] = "call"
        report = tool.audit(value)
        self.assertEqual(report["structural_edges"]["detect_to_ecus_ctor"][
            "observed_call_count"], 0)

    def test_14_wrong_offset_keeps_edge_but_not_exact(self):
        value = self._structural_fixture()
        for edge_record in value["normalized_result"]["call_edges"]:
            if edge_record["target_token"] == "0x060011bb":
                edge_record["il_offset"] = 0x0180
        report = tool.audit(value)
        self.assertEqual(report["structural_edges"][
            "detect_to_detect_result_ctor"], {
                "observed_call_count": 1, "exact_expected_site": False,
                "decoded_caller_corroborated": False})

    def test_15_duplicate_edge_does_not_count_as_exact(self):
        value = self._structural_fixture()
        edges = value["normalized_result"]["call_edges"]
        matching = next(e for e in edges if e["target_token"] == "0x06001160")
        edges.append(dict(matching))
        report = tool.audit(value)
        self.assertEqual(report["structural_edges"]["execute_to_parse_data"], {
            "observed_call_count": 2, "exact_expected_site": False,
                "decoded_caller_corroborated": False})

    def test_16_partial_scope_is_not_runtime_or_full_body_proof(self):
        value = self._structural_fixture()
        data = value["normalized_result"]
        data["coverage"]["state"] = "partial"
        data["methods"] = [
            m for m in data["methods"] if m["token"] != "0x0600115d"]
        data["call_edges"].append({
            **edge("0x0600126d", 0x0456, "method-def"),
            "caller_token": "0x0600115e",
            "target_name": "PRIVATE_DO_NOT_EXPORT",
        })
        report = tool.audit(value)
        self.assertEqual(report["assembly"]["coverage"], "partial")
        self.assertEqual(report["method_bodies"]["execute"]["status"],
                         "not_inspected")
        self.assertFalse(report["client_acceptance_verified"])
        self.assertFalse(report["ecu_identity_verified"])
        self.assertNotIn("PRIVATE_DO_NOT_EXPORT", json.dumps(report))
        self.assertIn("newobj and call edges do not prove",
                      " ".join(report["limitations"]))


    @staticmethod
    def _page_fixture():
        value = fixture()
        value["normalized_result"]["selection"] = None
        value["normalized_result"]["method_rows"] = {
            "offset": 0, "count": 8000, "total": 8000,
        }
        return value

    def test_17_complete_rows_and_unselected_coverage_attested(self):
        output = tool.audit(self._page_fixture())
        self.assertEqual(output["inspection_scope"], {
            "declaring_types": "all_types", "method_rows": "all_rows",
            "all_members_examined": True,
        })
        self.assertFalse(output["client_acceptance_verified"])

    def test_18_selected_type_does_not_prove_full_member_inspection(self):
        value = self._page_fixture()
        value["normalized_result"]["selection"] = {
            "type_names": ["Private.Hidden.Type"],
            "unmatched_type_names": [],
        }
        report = tool.audit(value)
        self.assertEqual(report["inspection_scope"]["declaring_types"],
                         "selected_types")
        self.assertFalse(report["inspection_scope"]["all_members_examined"])
        self.assertNotIn("Private.Hidden.Type", json.dumps(report))
        self.assertTrue(report["call_sites"]["opaque_predicate"][
            "exact_expected_sites"])

    def test_19_method_row_window_does_not_prove_missing_caller(self):
        value = self._page_fixture()
        data = value["normalized_result"]
        data["method_rows"] = {"offset": 100, "count": 200, "total": 8000}
        data["methods"] = [m for m in data["methods"]
                           if m["token"] == "0x0600132b"]
        report = tool.audit(value)
        self.assertEqual(report["inspection_scope"]["method_rows"], "page_only")
        self.assertFalse(report["inspection_scope"]["all_members_examined"])
        self.assertEqual(report["method_bodies"]["parse_data"]["status"],
                         "not_inspected")

    def test_20_historical_missing_row_scope_is_unknown(self):
        value = fixture()
        report = tool.audit(value)
        self.assertEqual(report["inspection_scope"]["method_rows"], "unreported")
        self.assertFalse(report["inspection_scope"]["all_members_examined"])
        value["normalized_result"]["coverage"]["state"] = "partial"
        value["normalized_result"]["method_rows"] = {
            "offset": 0, "count": 500, "total": 500,
        }
        self.assertFalse(tool.audit(value)["inspection_scope"][
            "all_members_examined"])

    def test_21_all_cil_decode_facts_required_for_complete_attestation(self):
        value = self._page_fixture()
        parse_method = next(m for m in value["normalized_result"]["methods"]
                            if m["token"] == "0x06001160")
        parse_method["body"] = {
            "status": "present", "instruction_count": 17,
            "decoded_instruction_count": 17, "truncated_instructions": 0,
            "normalized_il_sha256": "b" * 64, "issue": None,
            "private_cil": "PRIVATE_IL_DO_NOT_EXPORT",
        }
        result = tool.audit(value)
        self.assertEqual(result["method_bodies"]["parse_data"]["cil_decode"],
                         "complete_decode_attested")
        self.assertNotIn("PRIVATE_IL_DO_NOT_EXPORT", json.dumps(result))
        self.assertFalse(result["ecu_identity_verified"])

    def test_22_truncated_cil_and_parse_issues_are_not_complete(self):
        value = self._page_fixture()
        m = next(m for m in value["normalized_result"]["methods"]
                 if m["token"] == "0x06001359")
        m["body"] = {
            "status": "present", "instruction_count": 30,
            "decoded_instruction_count": 27, "truncated_instructions": 3,
            "normalized_il_sha256": None, "issue": "partial",
        }
        self.assertEqual(tool.audit(value)["method_bodies"]["predicate"][
            "cil_decode"], "partial_or_unavailable")
        m["body"].update({
            "decoded_instruction_count": 30,
            "truncated_instructions": 0,
            "normalized_il_sha256": "c" * 64,
        })
        self.assertEqual(tool.audit(value)["method_bodies"]["predicate"][
            "cil_decode"], "partial_or_unavailable")

    def test_23_invalid_row_and_cil_counters_rejected(self):
        for rows in (
            {"offset": 8000, "count": 1, "total": 8000},
            {"offset": -1, "count": 1, "total": 8000},
            {"offset": True, "count": 1, "total": 8000},
        ):
            with self.subTest(rows=rows):
                value = fixture()
                value["normalized_result"]["method_rows"] = rows
                with self.assertRaisesRegex(ValueError, "invalid_method_row_scope"):
                    tool.audit(value)
        value = fixture()
        value["normalized_result"]["methods"][0]["body"].update({
            "instruction_count": 2, "decoded_instruction_count": 3,
            "truncated_instructions": 0, "normalized_il_sha256": "b" * 64,
            "issue": None,
        })
        with self.assertRaisesRegex(ValueError, "invalid_cil_decode_counts"):
            tool.audit(value)

    def test_24_invalid_selection_and_digest_rejected_without_content(self):
        for selection in ({"type_names": [], "unmatched_type_names": []},
                          {"type_names": "Private.Hidden", "unmatched_type_names": []},
                          {"type_names": ["A"]},
                          False):
            with self.subTest(selection=str(type(selection))):
                value = fixture()
                value["normalized_result"]["selection"] = selection
                with self.assertRaisesRegex(ValueError, "invalid_type_selection"):
                    tool.audit(value)
        value = fixture()
        value["normalized_result"]["methods"][0]["body"].update({
            "instruction_count": 1, "decoded_instruction_count": 1,
            "truncated_instructions": 0, "normalized_il_sha256": "PRIVATE_HASH",
            "issue": None,
        })
        with self.assertRaisesRegex(ValueError, "invalid_normalized_il_digest"):
            tool.audit(value)



    @staticmethod
    def _complete_detect_body(value):
        target = next(m for m in value["normalized_result"]["methods"]
                      if m["token"] == "0x0600132b")
        target["body"] = {
            "status": "present", "instruction_count": 511,
            "decoded_instruction_count": 511, "truncated_instructions": 0,
            "normalized_il_sha256": "c" * 64, "issue": None,
        }
        return value

    def test_25_absent_selection_field_remains_unreported(self):
        value = self._page_fixture()
        del value["normalized_result"]["selection"]
        result = tool.audit(value)
        self.assertEqual(result["inspection_scope"]["declaring_types"],
                         "unreported")
        self.assertFalse(result["inspection_scope"]["all_members_examined"])
        self.assertTrue(result["call_sites"]["opaque_predicate"][
            "exact_expected_sites"])

    def test_26_explicit_null_selection_attests_all_types(self):
        value = self._page_fixture()
        result = tool.audit(value)["inspection_scope"]
        self.assertEqual(result["declaring_types"], "all_types")
        self.assertTrue(result["all_members_examined"])

    def test_27_edges_without_detect_caller_row_not_corroborated(self):
        value = fixture()
        value["normalized_result"]["methods"] = [
            m for m in value["normalized_result"]["methods"]
            if m["token"] != "0x0600132b"]
        result = tool.audit(value)
        for entry in result["call_sites"].values():
            self.assertTrue(entry["exact_expected_sites"])
            self.assertFalse(entry["decoded_caller_corroborated"])
        self.assertEqual(result["method_bodies"]["detect"]["status"],
                         "not_inspected")

    def test_28_present_detect_without_decode_attestation(self):
        result = tool.audit(fixture())
        self.assertTrue(all(not item["decoded_caller_corroborated"]
                            for item in result["call_sites"].values()))
        self.assertEqual(result["method_bodies"]["detect"]["cil_decode"],
                         "unreported")

    def test_29_complete_decoded_detect_corroborates_pair_sites(self):
        value = self._complete_detect_body(fixture())
        result = tool.audit(value)
        for item in result["call_sites"].values():
            self.assertTrue(item["decoded_caller_corroborated"])
        self.assertEqual(result["method_bodies"]["detect"]["cil_decode"],
                         "complete_decode_attested")
        self.assertFalse(result["client_acceptance_verified"])

    def test_30_partial_decode_prevents_false_corroboration(self):
        value = self._complete_detect_body(fixture())
        body = next(m for m in value["normalized_result"]["methods"]
                    if m["token"] == "0x0600132b")["body"]
        body["truncated_instructions"] = 1
        body["decoded_instruction_count"] = 510
        result = tool.audit(value)
        self.assertFalse(result["call_sites"]["opaque_predicate"][
            "decoded_caller_corroborated"])

    def test_31_decoded_execute_only_correlates_execute_edge(self):
        value = self._structural_fixture()
        execute = next(m for m in value["normalized_result"]["methods"]
                       if m["token"] == "0x0600115d")
        execute["body"] = {
            "status": "present", "instruction_count": 74,
            "decoded_instruction_count": 74, "truncated_instructions": 0,
            "normalized_il_sha256": "d" * 64, "issue": None,
        }
        report = tool.audit(value)
        self.assertTrue(report["structural_edges"]["execute_to_parse_data"][
            "decoded_caller_corroborated"])
        self.assertFalse(report["structural_edges"]["detect_to_ecus_ctor"][
            "decoded_caller_corroborated"])
        self.assertFalse(report["call_sites"]["opaque_predicate"][
            "decoded_caller_corroborated"])

    def test_32_wrong_offset_stays_uncorroborated_with_complete_cil(self):
        value = self._complete_detect_body(self._structural_fixture())
        edges = value["normalized_result"]["call_edges"]
        next(e for e in edges if e["target_token"] == "0x060011bb")[
            "il_offset"] = 0x0180
        report = tool.audit(value)
        self.assertFalse(report["structural_edges"][
            "detect_to_detect_result_ctor"]["decoded_caller_corroborated"])
        self.assertTrue(report["structural_edges"][
            "detect_to_ecus_ctor"]["decoded_caller_corroborated"])
        self.assertNotIn("Private.Obfuscated", json.dumps(report))
        self.assertFalse(report["ecu_identity_verified"])


    @staticmethod
    def _signature_fixture():
        value = ReaStaticEvidenceTests._structural_fixture()
        methods = value["normalized_result"]["methods"]
        def synthetic_method(token, parameter_types, returns):
            return {
                "token": token,
                "body": {"status": "present"},
                "name": PRIVATE,
                "signature": {
                    "kind": "method", "parse_status": "decoded",
                    "raw_length": 12, "raw_sha256": "e" * 64,
                    "calling_convention": "default",
                    "generic_parameter_count": 0,
                    "parameter_count": len(parameter_types),
                    "return_type": returns,
                    "parameter_types": parameter_types,
                    "field_type": None, "issue": None,
                    "private_binary_name": PRIVATE,
                },
            }
        methods.extend([
            synthetic_method("0x0600117a", ["VENDOR_PRIVATE_PARAMETER"],
                             "VENDOR_PRIVATE_RETURN"),
            synthetic_method("0x0600117b", ["VENDOR_PRIVATE_PARAMETER"],
                             "System.Void"),
        ])
        parse = next(m for m in methods if m["token"] == "0x06001160")
        parse["signature"] = synthetic_method(
            "0x06001160", ["PRIVATE_1", "PRIVATE_2"], "void")["signature"]
        return value

    def test_33_private_helper_signatures_are_sanitized(self):
        report = tool.audit(self._signature_fixture())
        self.assertEqual(report["method_signatures"], {
            "result_helper_a": {
                "status": "decoded", "parameter_count": 1,
                "generic_parameter_count": 0, "return_kind": "non_void",
            },
            "result_helper_b": {
                "status": "decoded", "parameter_count": 1,
                "generic_parameter_count": 0, "return_kind": "void",
            },
            "parse_data": {
                "status": "decoded", "parameter_count": 2,
                "generic_parameter_count": 0, "return_kind": "void",
            },
        })
        dump = json.dumps(report)
        for private in (PRIVATE, "VENDOR_PRIVATE_PARAMETER",
                        "VENDOR_PRIVATE_RETURN", "PRIVATE_1", "PRIVATE_2",
                        "e" * 64):
            self.assertNotIn(private, dump)
        self.assertFalse(report["client_acceptance_verified"])

    def test_34_selected_type_missing_helpers_do_not_infer_absence(self):
        value = fixture()
        value["normalized_result"]["selection"] = {
            "type_names": ["PRIVATE_DETECT_TYPE"],
            "unmatched_type_names": [],
        }
        report = tool.audit(value)
        self.assertEqual(report["method_signatures"]["result_helper_a"]["status"],
                         "not_inspected")
        self.assertEqual(report["method_signatures"]["result_helper_b"]["status"],
                         "not_inspected")
        self.assertEqual(report["method_signatures"]["parse_data"]["status"],
                         "unreported")
        self.assertFalse(report["inspection_scope"]["all_members_examined"])

    def test_35_incomplete_signature_does_not_expose_partial_types(self):
        value = self._signature_fixture()
        raw = next(m for m in value["normalized_result"]["methods"]
                   if m["token"] == "0x0600117a")["signature"]
        raw.update({"parse_status": "partial", "return_type": PRIVATE,
                    "parameter_count": None, "parameter_types": []})
        output = tool.audit(value)["method_signatures"]["result_helper_a"]
        self.assertEqual(output, {
            "status": "partial", "parameter_count": None,
            "generic_parameter_count": None, "return_kind": "unknown",
        })

    def test_36_malformed_signature_digest_fails_closed(self):
        value = self._signature_fixture()
        value["normalized_result"]["methods"][-1]["signature"][
            "raw_sha256"] = PRIVATE
        with self.assertRaisesRegex(ValueError, "invalid_signature_provenance"):
            tool.audit(value)

    def test_37_inconsistent_decoded_parameter_types_rejected(self):
        value = self._signature_fixture()
        raw = next(m for m in value["normalized_result"]["methods"]
                   if m["token"] == "0x06001160")["signature"]
        raw["parameter_count"] = 3
        with self.assertRaisesRegex(ValueError, "invalid_decoded_method_signature"):
            tool.audit(value)
        raw["parameter_count"] = True
        with self.assertRaisesRegex(ValueError, "invalid_decoded_method_signature"):
            tool.audit(value)

    def test_38_wrong_signature_kind_and_empty_return_rejected(self):
        value = self._signature_fixture()
        sig = value["normalized_result"]["methods"][-1]["signature"]
        sig["kind"] = "field"
        with self.assertRaisesRegex(ValueError, "invalid_decoded_method_signature"):
            tool.audit(value)
        sig["kind"] = "method"
        sig["return_type"] = ""
        with self.assertRaisesRegex(ValueError, "invalid_decoded_method_signature"):
            tool.audit(value)

    def test_39_helper_edge_offsets_must_match_exactly(self):
        value = self._signature_fixture()
        report = tool.audit(value)
        for kind in ("execute_to_result_helper_a", "execute_to_result_helper_b"):
            self.assertTrue(report["structural_edges"][kind]["exact_expected_site"])
        next(e for e in value["normalized_result"]["call_edges"]
             if e["target_token"] == "0x0600117b")["il_offset"] = 0x0260
        changed = tool.audit(value)
        self.assertTrue(changed["structural_edges"][
            "execute_to_result_helper_a"]["exact_expected_site"])
        self.assertFalse(changed["structural_edges"][
            "execute_to_result_helper_b"]["exact_expected_site"])
        self.assertFalse(changed["ecu_identity_verified"])

    def test_40_signature_and_edge_do_not_establish_parse_data_success(self):
        value = self._signature_fixture()
        execute = next(m for m in value["normalized_result"]["methods"]
                       if m["token"] == "0x0600115d")
        execute["body"] = {
            "status": "present", "instruction_count": 8,
            "decoded_instruction_count": 8, "truncated_instructions": 0,
            "normalized_il_sha256": "f" * 64, "issue": None,
        }
        report = tool.audit(value)
        for name in ("execute_to_result_helper_a", "execute_to_result_helper_b",
                     "execute_to_parse_data"):
            self.assertTrue(report["structural_edges"][name][
                "decoded_caller_corroborated"])
        self.assertFalse(report["client_acceptance_verified"])
        self.assertFalse(report["ecu_identity_verified"])
        self.assertNotIn("VENDOR_PRIVATE_RETURN", json.dumps(report))


    @staticmethod
    def _realistic_typed_probe_fixture():
        # Synthetic types/counts shaped after *observed* private REA export,
        # not copied proprietary code, method names or DLL.
        value = ReaStaticEvidenceTests._signature_fixture()
        m = {m["token"].lower(): m for m in value["normalized_result"]["methods"]}
        for token in ("0x0600117a", "0x0600117b", "0x06001160"):
            m[token]["signature"]["generic_parameter_count"] = None
            m[token]["body"] = {"status": "malformed",
                               "issue": "Unsupported method body header"}
        m["0x0600117a"]["signature"].update({
            "parameter_types": ["class:1349"], "return_type": "class:205[]",
        })
        m["0x0600117b"]["signature"].update({
            "parameter_types": ["class:1349"], "return_type": "u1[]",
        })
        m["0x06001160"]["signature"].update({
            "parameter_types": ["class:205[]", "u1[]"], "return_type": "void",
        })
        value["normalized_result"]["fields"] = [{
            "token": "0x04000333",
            "name": PRIVATE,
            "signature": {"kind": "field", "parse_status": "decoded",
                          "field_type": "class:1349", "issue": None},
        }]
        return value

    def test_41_probe_style_null_generic_parameter_counts_accepted(self):
        report = tool.audit(self._realistic_typed_probe_fixture())
        for name in ("result_helper_a", "result_helper_b", "parse_data"):
            self.assertEqual(report["method_signatures"][name]["status"],
                             "decoded")
            self.assertIsNone(report["method_signatures"][name][
                "generic_parameter_count"])
        self.assertFalse(report["client_acceptance_verified"])

    def test_42_decoded_helper_return_shapes_match_parse_data(self):
        report = tool.audit(self._realistic_typed_probe_fixture())
        self.assertEqual(report["typed_staging_alignment"], {
            "status": "compatible_static_signatures",
            "helper_a_return_shape": "class_array",
            "helper_b_return_shape": "byte_array",
            "parse_data_parameter_shapes": ["class_array", "byte_array"],
        })
        self.assertEqual(report["method_bodies"]["parse_data"]["status"],
                         "malformed")
        self.assertFalse(report["ecu_identity_verified"])

    def test_43_mismatched_result_field_never_attests_alignment(self):
        v = self._realistic_typed_probe_fixture()
        v["normalized_result"]["fields"][0]["signature"]["field_type"] = (
            "class:1350")
        report = tool.audit(v)
        self.assertEqual(report["typed_staging_alignment"]["status"],
                         "signature_mismatch")

    def test_44_reversed_parse_data_parameters_not_compatible(self):
        v = self._realistic_typed_probe_fixture()
        parse_sig = next(m["signature"] for m in
                         v["normalized_result"]["methods"]
                         if m["token"] == "0x06001160")
        parse_sig["parameter_types"] = ["u1[]", "class:205[]"]
        self.assertEqual(tool.audit(v)["typed_staging_alignment"]["status"],
                         "signature_mismatch")

    def test_45_missing_field_is_unknown_not_negative(self):
        v = self._realistic_typed_probe_fixture()
        v["normalized_result"]["fields"] = []
        report = tool.audit(v)
        self.assertEqual(report["typed_staging_alignment"]["status"],
                         "unreported")
        v["normalized_result"].pop("fields")
        self.assertEqual(tool.audit(v)["typed_staging_alignment"]["status"],
                         "unreported")

    def test_46_partial_helper_signature_is_unknown_not_compatible(self):
        v = self._realistic_typed_probe_fixture()
        method = next(m for m in v["normalized_result"]["methods"]
                      if m["token"] == "0x0600117b")
        method["signature"]["parse_status"] = "partial"
        report = tool.audit(v)
        self.assertEqual(report["typed_staging_alignment"]["status"],
                         "unreported")
        self.assertEqual(report["method_signatures"]["result_helper_b"][
            "status"], "partial")

    def test_47_duplicate_result_field_is_rejected(self):
        v = self._realistic_typed_probe_fixture()
        v["normalized_result"]["fields"].append(dict(
            v["normalized_result"]["fields"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate_result_field"):
            tool.audit(v)

    def test_48_private_source_type_names_and_digests_not_exported(self):
        v = self._realistic_typed_probe_fixture()
        v["normalized_result"]["fields"][0]["name"] = PRIVATE
        text = json.dumps(tool.audit(v))
        for forbidden in (PRIVATE, "class:1349", "class:205", SHA, MVID,
                          "u1[]", "0x04000333"):
            self.assertNotIn(forbidden, text)
        self.assertIn("compatible_static_signatures", text)
        self.assertNotIn("PRIVATE_VIN", text)


if __name__ == "__main__":
    unittest.main()
