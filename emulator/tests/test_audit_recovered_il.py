"""Eight synthetic checks for the allowlisted recovered-IL evidence reader."""
import importlib.util
import json
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "tools" / "audit_recovered_il.py"
spec = importlib.util.spec_from_file_location("audit_recovered_il", path)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

HEADER = "Frontend.Client.Core.dll: MethodDef"
D = """Frontend.Client.Core.dll: MethodDef 0x0600132B VddModel.Detect; 4 decoded opcodes
IL_0000 call 0x06001329 CreateCommand
IL_0005 call 0x0600132C Enqueue
IL_000A call 0x0600115B Wait
IL_000F call 0x060012DF set_Ecus
"""
E = """Frontend.Client.Core.dll: MethodDef 0x0600115D VddCommand.Execute; 12 decoded opcodes
IL_0000 ldftn 0x0600115F OnCheckResult
IL_0005 newobj 0x0A0000CD System.Threading.TimerCallback..ctor
IL_000A ldc.r8 1.0
IL_0013 call 0x0A0000CE System.TimeSpan.FromSeconds
IL_0018 ldsfld 0x0A0000CF System.Threading.Timeout.InfiniteTimeSpan
IL_001D call 0x0600117C <obfuscated Unicode name>
IL_0022 stfld 0x04000334 timer
IL_0027 call 0x06001178 <obfuscated Unicode name>
IL_002C ldc.i4.3
IL_002D call 0x06001160 ParseData
IL_0032 call 0x06001178 <obfuscated Unicode name>
IL_0037 ldc.i4.4
"""


def inventory(*tokens):
    return {"selected_methods": [
        {"module": "Frontend.Client.Core.dll", "method_token": token,
         "decoded_instructions": { 
            "0x0600132B": 4, "0x0600115D": 12, "0x06001160": 1
        }.get(token, 1)}
        for token in tokens
    ]}


class RecoveredIlTests(unittest.TestCase):
    def test_01_exact_opcode_counts(self):
        self.assertEqual(len(tool.parse_excerpts(D)), 1)

    def test_02_direct_call_signals_not_execution(self):
        x = tool.audit(inventory("0x0600132B"), D)["evidence"]
        self.assertTrue(x["detect_calls_create_command"])
        self.assertTrue(x["detect_calls_enqueue"])
        self.assertTrue(x["detect_calls_wait"])
        self.assertTrue(x["detect_assigns_ecus_model"])
        self.assertFalse(x["execute_calls_parse_data"])

    def test_03_status_numbers_uninterpreted(self):
        x = tool.audit(inventory("0x0600115D"), E)["evidence"]
        self.assertEqual(x["execute_observed_status_numeric_comparisons"], [3, 4])
        self.assertTrue(x["execute_calls_parse_data"])

    def test_04_one_second_shape_only(self):
        x = tool.audit(inventory("0x0600115D"), E)["evidence"]
        self.assertTrue(x["execute_one_second_timer_shape"])
        self.assertFalse(tool._one_shot_timer_shape([("ldc.r8", "1.0")]))

    def test_05_truncated_body_rejected(self):
        with self.assertRaisesRegex(ValueError, "truncated"):
            tool.parse_excerpts(D.replace("4 decoded opcodes", "5 decoded opcodes"))

    def test_06_unknown_and_duplicate_tokens_rejected(self):
        with self.assertRaisesRegex(ValueError, "not_in_inventory"):
            tool.audit(inventory("0x0600115D"), D)
        with self.assertRaisesRegex(ValueError, "duplicate_inventory"):
            tool.audit(inventory("0x0600132B", "0x0600132B"), D)

    def test_07_unexpanded_method_not_treated_as_body(self):
        x = tool.audit(inventory("0x0600132B", "0x06001160"), D)
        self.assertEqual(x["fully_extracted_excerpt_methods"], 1)
        self.assertEqual(x["missing_priority_bodies"], ["parse_data"])

    def test_08_private_data_does_not_escape(self):
        secret = "SYNTHETIC-VIN-PRIVATE-MARKER"
        report = tool.audit(inventory("0x0600132B"), D + "# " + secret)
        self.assertNotIn(secret, json.dumps(report))
        self.assertNotIn("Frontend.Client.Core.dll", json.dumps(report))


    def test_09_methoddef_tokens_are_scoped_to_assembly(self):
        # The same token may legitimately identify two unrelated assemblies.
        other = """Frontend.exe: MethodDef 0x0600132B Other.Detect; 1 decoded opcodes
IL_0000 ret
"""
        inv = inventory("0x0600132B")
        inv["selected_methods"].append({
            "module": "Frontend.exe", "method_token": "0x0600132B",
            "decoded_instructions": 1,
        })
        result = tool.audit(inv, D + other)
        self.assertEqual(result["fully_extracted_excerpt_methods"], 2)
        self.assertTrue(result["evidence"]["detect_assigns_ecus_model"])

    def test_10_wrong_module_not_equivalent_to_matching_token(self):
        with self.assertRaisesRegex(ValueError, "excerpt_method_not_in_inventory"):
            tool.audit({"selected_methods": [{
                "module": "Frontend.exe", "method_token": "0x0600132B",
                "decoded_instructions": 4,
            }]}, D)

    def test_11_missing_inventory_assembly_is_rejected(self):
        inv = inventory("0x0600132B")
        del inv["selected_methods"][0]["module"]
        with self.assertRaisesRegex(ValueError, "invalid_inventory_module"):
            tool.audit(inv, D)

    @staticmethod
    def _shaped_detect(*, ecus_ctor="0x0600126D", result_ctor="0x060011BB",
                       hash_field="0x040003A9"):
        lines = [
            "ldloc.1",
            "callvirt 0x06001142 get_ResultData",
            "dup", "brtrue.s 2", "pop", "ldnull", "stloc.2",
            "ldarg.0", "ldarg.0", "call 0x060012E2 get_Volvo", "ldloc.2",
            "newobj " + result_ctor, "call 0x060012E9 set_DetectResult",
            "ldarg.0", "ldarg.0", "call 0x060012E8 get_DetectResult",
            "newobj " + ecus_ctor, "call 0x060012DF set_Ecus",
            "ldarg.0", "ldloc.1", "callvirt 0x0600113C get_DataHash",
            "stfld " + hash_field,
            "call 0x060012E8 get_DetectResult",
            "callvirt 0x06001B99 get_Units",
            "callvirt 0x0A00011A GetEnumerator",
            "ldc.i4.0", "ret", "ldc.i4.1", "ret",
        ]
        return (
            "Frontend.Client.Core.dll: MethodDef 0x0600132B "
            f"VddModel.Detect; {len(lines)} decoded opcodes\n"
            + "".join(f"IL_{i:04X} {instruction}\n"
                      for i, instruction in enumerate(lines))
        )

    def test_12_resultdata_to_detectresult_model_neighborhood(self):
        report = tool.audit(inventory_for_detect_shape(self._shaped_detect()),
                            self._shaped_detect())
        evidence = report["evidence"]
        self.assertTrue(evidence["detect_resultdata_near_local2_store"])
        self.assertTrue(evidence["detect_result_constructor_from_volvo_and_local2"])
        self.assertTrue(evidence["detect_ecus_constructor_from_detect_result"])

    def test_13_result_constructor_token_mismatch_rejected(self):
        source = self._shaped_detect(result_ctor="0x060011BC")
        report = tool.audit(inventory_for_detect_shape(source), source)
        self.assertFalse(report["evidence"][
            "detect_result_constructor_from_volvo_and_local2"])
        self.assertTrue(report["evidence"][
            "detect_ecus_constructor_from_detect_result"])

    def test_14_ecus_constructor_token_mismatch_rejected(self):
        source = self._shaped_detect(ecus_ctor="0x0600126E")
        report = tool.audit(inventory_for_detect_shape(source), source)
        self.assertFalse(report["evidence"][
            "detect_ecus_constructor_from_detect_result"])
        self.assertTrue(report["evidence"][
            "detect_result_constructor_from_volvo_and_local2"])

    def test_15_hash_field_mismatch_and_units_independent(self):
        source = self._shaped_detect(hash_field="0x040003A8")
        report = tool.audit(inventory_for_detect_shape(source), source)
        evidence = report["evidence"]
        self.assertFalse(evidence["detect_model_stores_command_datahash"])
        self.assertTrue(evidence["detect_has_result_units_enumeration"])
        self.assertTrue(evidence["detect_has_both_boolean_return_sites"])

    def test_16_source_data_neighborhood_is_not_proof_of_execution(self):
        # A flattened method can contain a syntactically intact but unreachable
        # motif; detection is not execution, parsing, nor accepted ECU evidence.
        source = self._shaped_detect()
        report = tool.audit(inventory_for_detect_shape(source), source)
        self.assertIn("Constructor/data-flow motifs do not establish runtime reachability",
                      report["limitations"])
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v5")


    @staticmethod
    def _get_vin_fixture():
        return """Frontend.Client.Core.dll: MethodDef 0x0600133A VddModel.GetVin; 7 decoded opcodes
IL_0000 ldarg.0
IL_0001 call 0x060012F2 get_PreDetectResult
IL_0006 brfalse.s 108
IL_0008 ldc.i4.0
IL_0009 ret
IL_0074 ldarg.0
IL_0075 call 0x060012E2 get_Volvo
"""

    @staticmethod
    def _get_config_fixture():
        return """Frontend.Client.Core.dll: MethodDef 0x06001339 VddModel.GetConfig; 9 decoded opcodes
IL_0000 ldarg.0
IL_0001 call 0x060012E8 get_DetectResult
IL_0006 dup
IL_0007 brtrue.s 3
IL_0009 pop
IL_000A ldnull
IL_000B ret
IL_000C callvirt 0x06001B7E get_Config
IL_0011 ret
"""

    @staticmethod
    def _get_result_gate_fixture():
        return """Frontend.Client.Core.dll: MethodDef 0x0600132B VddModel.Detect; 11 decoded opcodes
IL_0000 ldloc.1
IL_0001 callvirt 0x0600113E get_Result
IL_0006 ldc.i4 123
IL_000B br.s 0
IL_000D call 0x2B000002 opaque_generic
IL_0012 call 0x06001359 opaque_predicate
IL_0017 brfalse 3
IL_001C ldc.i4.1
IL_001D ret
IL_001F ldc.i4.0
IL_0020 ret
"""

    def test_17_get_vin_missing_predetect_falls_back_to_volvo(self):
        src = self._get_vin_fixture()
        out = tool.audit(inventory_for_single(src, "0x0600133A", 7), src)
        self.assertTrue(out["evidence"][
            "get_vin_missing_predetect_direct_volvo_fallback"])

    def test_18_get_vin_wrong_relative_target_not_accepted(self):
        src = self._get_vin_fixture().replace("brfalse.s 108", "brfalse.s 107")
        out = tool.audit(inventory_for_single(src, "0x0600133A", 7), src)
        self.assertFalse(out["evidence"][
            "get_vin_missing_predetect_direct_volvo_fallback"])

    def test_19_get_config_guard_targets_accessor(self):
        src = self._get_config_fixture()
        out = tool.audit(inventory_for_single(src, "0x06001339", 9), src)
        self.assertTrue(out["evidence"][
            "get_config_null_guard_direct_get_config"])

    def test_20_get_config_bad_null_arm_rejected(self):
        src = self._get_config_fixture().replace("IL_000A ldnull", "IL_000A ldc.i4.0")
        out = tool.audit(inventory_for_single(src, "0x06001339", 9), src)
        self.assertFalse(out["evidence"][
            "get_config_null_guard_direct_get_config"])

    def test_21_detect_result_predicate_false_return(self):
        src = self._get_result_gate_fixture()
        out = tool.audit(inventory_for_single(src, "0x0600132B", 11), src)
        self.assertTrue(out["evidence"][
            "detect_result_predicate_direct_false_return"])

    def test_22_detect_result_wrong_target_rejected(self):
        src = self._get_result_gate_fixture().replace("brfalse 3", "brfalse 4")
        out = tool.audit(inventory_for_single(src, "0x0600132B", 11), src)
        self.assertFalse(out["evidence"][
            "detect_result_predicate_direct_false_return"])

    def test_23_duplicate_il_offset_rejected(self):
        src = D.replace("IL_0005 call", "IL_0000 call")
        with self.assertRaisesRegex(ValueError, "nonmonotonic_il_offsets"):
            tool.audit(inventory("0x0600132B"), src)

    def test_24_branch_source_without_valid_edge_not_overinterpreted(self):
        src = self._get_result_gate_fixture().replace("IL_0017 brfalse", "IL_0017 brtrue")
        out = tool.audit(inventory_for_single(src, "0x0600132B", 11), src)
        self.assertFalse(out["evidence"][
            "detect_result_predicate_direct_false_return"])
        self.assertIn(
            "Direct branch targets do not prove that source blocks are reachable",
            out["limitations"])




    @staticmethod
    def _shared_predicate_fixture():
        # Both snippets are SYNTHETIC; copied names/tokens only, not VDASH IL.
        lines = [
            "ldloc.1", "callvirt 0x0600113E get_Result",
            "ldc.i4 123", "br.s 0",
            "call 0x2B000002 generic_helper",
            "call 0x06001359 opaque_predicate", "brfalse 0",
            "ldloc.s 6", "callvirt 0x06001F95 get_HardwareNumber",
            "ldc.i4 456", "br.s 0",
            "call 0x2B000002 generic_helper",
            "call 0x06001359 opaque_predicate", "brtrue.s 0",
        ]
        return (
            "Frontend.Client.Core.dll: MethodDef 0x0600132B "
            f"VddModel.Detect; {len(lines)} decoded opcodes\n"
            + "".join(f"IL_{i:04X} {instruction}\n"
                      for i, instruction in enumerate(lines))
        )

    def test_25_shared_predicate_both_source_getters(self):
        src = self._shared_predicate_fixture()
        out = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertTrue(out[
            "detect_shared_predicate_for_result_and_hardware_number"])
        self.assertEqual(out["detect_shared_predicate_call_count"], 2)

    def test_26_result_getter_mismatch_rejected(self):
        src = self._shared_predicate_fixture().replace(
            "0x0600113E get_Result", "0x0600113F set_Result")
        out = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertFalse(out[
            "detect_shared_predicate_for_result_and_hardware_number"])
        self.assertEqual(out["detect_shared_predicate_call_count"], 2)

    def test_27_hardware_getter_mismatch_rejected(self):
        src = self._shared_predicate_fixture().replace(
            "0x06001F95 get_HardwareNumber", "0x06001F96 get_Value")
        out = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertFalse(out[
            "detect_shared_predicate_for_result_and_hardware_number"])

    def test_28_second_helper_mismatch_rejected(self):
        src = self._shared_predicate_fixture().replace(
            "call 0x2B000002 generic_helper\nIL_000C",
            "call 0x2B000003 generic_helper\nIL_000C")
        out = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertFalse(out[
            "detect_shared_predicate_for_result_and_hardware_number"])

    def test_29_second_predicate_mismatch_rejected(self):
        src = self._shared_predicate_fixture().replace(
            "IL_000C call 0x06001359", "IL_000C call 0x0600135A")
        out = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertFalse(out[
            "detect_shared_predicate_for_result_and_hardware_number"])
        self.assertEqual(out["detect_shared_predicate_call_count"], 1)

    def test_30_inverted_second_branch_rejected(self):
        src = self._shared_predicate_fixture().replace(
            "IL_000D brtrue.s", "IL_000D brfalse.s")
        out = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertFalse(out[
            "detect_shared_predicate_for_result_and_hardware_number"])

    def test_31_hardware_operand_mismatch_rejected(self):
        src = self._shared_predicate_fixture().replace(
            "IL_0007 ldloc.s 6", "IL_0007 ldloc.s 7")
        out = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertFalse(out[
            "detect_shared_predicate_for_result_and_hardware_number"])

    def test_32_no_semantic_comparator_claim_in_output(self):
        src = self._shared_predicate_fixture()
        report = tool.audit(inventory_for_detect_shape(src), src)
        self.assertIn("Shared opaque predicate usage does not reveal equality or acceptance semantics",
                      report["limitations"])
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v5")
        self.assertNotIn("hardware=real", json.dumps(report))



    @staticmethod
    def _string_methodspec_fixture():
        # Synthetic; the signature bytes are a three-byte ECMA-335 example.
        return RecoveredIlTests._shared_predicate_fixture().replace(
            "0x2B000002 generic_helper", r"0x2B000002 [12, b'\n\x01\x0e']"
        )

    def test_33_realistic_string_methodspec_on_both_calls(self):
        src = self._string_methodspec_fixture()
        proof = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertTrue(proof["detect_shared_string_methodspec_at_both_calls"])
        self.assertEqual(
            proof["detect_shared_string_methodspec_predicate_call_count"], 2)

    def test_34_equivalent_escape_encoding_accepted(self):
        src = self._string_methodspec_fixture().replace(
            r"b'\n\x01\x0e'", r"b'\x0a\x01\x0e'")
        proof = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertTrue(proof["detect_shared_string_methodspec_at_both_calls"])

    def test_35_different_generic_arity_rejected(self):
        src = self._string_methodspec_fixture().replace(
            r"b'\n\x01\x0e'", r"b'\n\x02\x0e'")
        proof = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertEqual(
            proof["detect_shared_string_methodspec_predicate_call_count"], 0)

    def test_36_integer_type_argument_not_string(self):
        src = self._string_methodspec_fixture().replace(
            r"b'\n\x01\x0e'", r"b'\n\x01\x08'")
        proof = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertFalse(proof["detect_shared_string_methodspec_at_both_calls"])

    def test_37_wrong_genericinst_prefix_rejected(self):
        src = self._string_methodspec_fixture().replace(
            r"b'\n\x01\x0e'", r"b'\x09\x01\x0e'")
        proof = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertEqual(
            proof["detect_shared_string_methodspec_predicate_call_count"], 0)

    def test_38_one_methodspec_missing_detected(self):
        src = self._string_methodspec_fixture().replace(
            "IL_000B call 0x2B000002", "IL_000B call 0x2B000003")
        proof = tool.audit(inventory_for_detect_shape(src), src)["evidence"]
        self.assertEqual(
            proof["detect_shared_string_methodspec_predicate_call_count"], 1)
        self.assertFalse(proof["detect_shared_string_methodspec_at_both_calls"])

    def test_39_malformed_or_too_long_bytes_rejected(self):
        self.assertFalse(tool._string_methodspec_instantiation(
            r"0x2B000002 [12, b'\xZZ\x01\x0e']"))
        self.assertFalse(tool._string_methodspec_instantiation(
            r"0x2B000002 [12, b'\n\x01\x0e']" + (" " * 256)))

    def test_40_summary_is_allowlisted_no_raw_bytes(self):
        src = self._string_methodspec_fixture()
        report = tool.audit(inventory_for_detect_shape(src), src)
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v5")
        self.assertNotIn("0x2B000002", json.dumps(report))
        self.assertNotIn(r"\x01\x0e", json.dumps(report))
        self.assertIn("MethodSpec<string> does not establish generic method return type or semantics",
                      report["limitations"])




    @staticmethod
    def _execute_preparse_fixture(*, with_inventory=True):
        # Synthetic isolated CIL, with offsets copied from the already
        # independently recovered *structure*, not the proprietary body.
        rows = [
            "IL_0247 ldarg.0",
            "IL_0248 ldarg.0",
            "IL_0249 ldfld 0x04000333 result",
            "IL_024E call 0x0600117A opaque_helper_a",
            "IL_0253 ldarg.0",
            "IL_0254 ldfld 0x04000333 result",
            "IL_0259 call 0x0600117B opaque_helper_b",
            "IL_025E call 0x06001160 ParseData",
        ]
        source = ("Frontend.Client.Core.dll: MethodDef 0x0600115D "
                  "VddCommand.Execute; 8 decoded opcodes\n"
                  + "\n".join(rows) + "\n")
        inventory = inventory_for_single(source, "0x0600115D", 8)
        if with_inventory:
            inventory["selected_methods"][0]["calls"] = [
                {"token": tok, "count": 1, "symbol": "PRIVATE_DONOR"}
                for tok in ("0x0600117A", "0x0600117B", "0x06001160")
            ]
        return source, inventory

    def test_41_exact_execute_result_field_staging_and_counts(self):
        source, inventory = self._execute_preparse_fixture()
        result = tool.audit(inventory, source)
        self.assertTrue(result["evidence"][
            "execute_parse_data_two_result_wrappers_exact_static_site"])
        self.assertEqual(result["evidence"]["execute_parse_data_wrappers_inventory"],
                         "three_single_calls_observed")
        self.assertTrue(result["evidence"]["execute_calls_parse_data"])
        self.assertFalse(result["evidence"]["detect_calls_create_command"])

    def test_42_second_wrapper_token_substitution_rejected(self):
        source, inventory = self._execute_preparse_fixture()
        source = source.replace("0x0600117B", "0x0600117C")
        result = tool.audit(inventory, source)["evidence"]
        self.assertFalse(result[
            "execute_parse_data_two_result_wrappers_exact_static_site"])
        self.assertEqual(result["execute_parse_data_wrappers_inventory"],
                         "three_single_calls_observed")

    def test_43_wrappers_reversed_rejected(self):
        source, inventory = self._execute_preparse_fixture()
        source = source.replace("0x0600117A", "0x0600117Z")
        source = source.replace("0x0600117B", "0x0600117A")
        source = source.replace("0x0600117Z", "0x0600117B")
        self.assertFalse(tool.audit(inventory, source)["evidence"][
            "execute_parse_data_two_result_wrappers_exact_static_site"])

    def test_44_different_result_field_rejected(self):
        source, inventory = self._execute_preparse_fixture()
        source = source.replace("IL_0254 ldfld 0x04000333",
                                "IL_0254 ldfld 0x04000335")
        self.assertFalse(tool.audit(inventory, source)["evidence"][
            "execute_parse_data_two_result_wrappers_exact_static_site"])

    def test_45_changed_il_offset_is_not_same_static_callsite(self):
        source, inventory = self._execute_preparse_fixture()
        source = source.replace("IL_0249", "IL_024A")
        self.assertFalse(tool.audit(inventory, source)["evidence"][
            "execute_parse_data_two_result_wrappers_exact_static_site"])

    def test_46_missing_caller_this_staging_rejected(self):
        source, inventory = self._execute_preparse_fixture()
        source = source.replace("IL_0253 ldarg.0", "IL_0253 ldarg.1")
        self.assertFalse(tool.audit(inventory, source)["evidence"][
            "execute_parse_data_two_result_wrappers_exact_static_site"])

    def test_47_missing_inventory_does_not_negate_source_shape(self):
        source, inventory = self._execute_preparse_fixture(with_inventory=False)
        report = tool.audit(inventory, source)["evidence"]
        self.assertTrue(report[
            "execute_parse_data_two_result_wrappers_exact_static_site"])
        self.assertEqual(report["execute_parse_data_wrappers_inventory"],
                         "unreported")
        inventory["selected_methods"][0]["calls"] = [
            {"token": "0x0600117A", "count": 1},
            {"token": "0x0600117B", "count": 1},
            {"token": "0x06001160", "count": 2},
        ]
        self.assertEqual(tool.audit(inventory, source)["evidence"][
            "execute_parse_data_wrappers_inventory"], "counts_differ")

    def test_48_malformed_counts_and_private_symbols_not_exported(self):
        source, inventory = self._execute_preparse_fixture()
        inventory["selected_methods"][0]["calls"][0]["count"] = "private"
        result = tool.audit(inventory, source)
        self.assertEqual(result["evidence"][
            "execute_parse_data_wrappers_inventory"], "invalid_inventory")
        inventory["selected_methods"][0]["calls"][0]["count"] = 1
        report = tool.audit(inventory, source)
        dumped = json.dumps(report)
        self.assertNotIn("PRIVATE_DONOR", dumped)
        self.assertNotIn("0x04000333", dumped)
        self.assertNotIn("opaque_helper_a", dumped)
        self.assertIn("Two unknown result-field wrappers before ParseData",
                      " ".join(report["limitations"]))


def inventory_for_single(source, token, count):
    # All fixtures are explicitly synthetic and isolated from real IL text.
    return {"selected_methods": [{
        "module": "Frontend.Client.Core.dll",
        "method_token": token,
        "decoded_instructions": count,
    }]}




def inventory_for_detect_shape(source):
    import re
    m = re.search(r"VddModel.Detect; (\d+) decoded opcodes", source)
    if m is None:
        raise ValueError("missing synthetic fixture")
    return {"selected_methods": [{
        "module": "Frontend.Client.Core.dll",
        "method_token": "0x0600132B",
        "decoded_instructions": int(m.group(1)),
    }]}



if __name__ == "__main__":
    unittest.main()
