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
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v9")


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
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v9")
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
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v9")
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



    @staticmethod
    def _phase_predetect_fixture():
        # Synthetic shape with source-grounded offsets, no vendor IL or payload.
        rows = [
            (0x0186, "ldarg.0"), (0x0187, "ldarg.0"),
            (0x0188, "call 0x060012E2 get_Volvo"),
            (0x018D, "ldarg.0"), (0x018E, "ldfld 0x040003A6 dongleId"),
            (0x0193, "ldloc.2"), (0x0194, "ldloc.3"),
            (0x0195, "newobj 0x0600139D .ctor"),
            (0x019A, "call 0x060012F3 set_PreDetectResult"),
            (0x019F, "ldarg.0"), (0x01A0, "ldfld 0x040003CC PreDetectDone"),
            (0x01A5, "dup"), (0x01A6, "brtrue.s 6"),
            (0x01A8, "pop"), (0x01A9, "br -186"),
            (0x01AE, "ldarg.0"),
            (0x01AF, "ldsfld 0x0A0000DE System.EventArgs.Empty"),
            (0x01B4, "callvirt 0x0A0000DF System.EventHandler.Invoke"),
        ]
        return ("Frontend.Client.Core.dll: MethodDef 0x0600133D VddModel.PreDetect; "
                + str(len(rows)) + " decoded opcodes\n"
                + "".join(f"IL_{offset:04X} {line}\n" for offset, line in rows))

    @staticmethod
    def _phase_detect_fixture():
        # Offsets and method identities are fixture motifs; the source body is
        # control-flow-flattened. No ordering/reachability is asserted.
        rows = [
            (0x0261, "ldarg.0"), (0x0262, "ldarg.0"),
            (0x0263, "call 0x060012E8 get_DetectResult"),
            (0x0268, "newobj 0x0600126D .ctor"),
            (0x026D, "call 0x060012DF set_Ecus"),
            (0x05CD, "ldarg.0"), (0x05CE, "call 0x060012EC get_Dim"),
            (0x05D3, "callvirt 0x06001BB2 RefreshAvailability"),
            (0x0617, "ldarg.0"), (0x0618, "call 0x060012F0 get_Ecm"),
            (0x061D, "callvirt 0x06001BBA RefreshAvailability"),
            (0x0632, "ldarg.0"), (0x0633, "call 0x06001343 OnDetectDone"),
            (0x0648, "ldarg.0"), (0x0649, "call 0x060012EE get_Icm"),
            (0x064E, "callvirt 0x06001BCC RefreshAvailability"),
            (0x0683, "ldarg.0"), (0x0684, "ldc.i4.1"),
            (0x0685, "call 0x060012F7 set_DeviceAvailable"),
            (0x069D, "ldarg.0"), (0x069E, "call 0x060012EA get_Phm"),
            (0x06A3, "callvirt 0x06001BE9 RefreshAvailability"),
        ]
        return ("Frontend.Client.Core.dll: MethodDef 0x0600132B VddModel.Detect; "
                + str(len(rows)) + " decoded opcodes\n"
                + "".join(f"IL_{offset:04X} {line}\n" for offset, line in rows))

    @staticmethod
    def _phase_inv(source, token):
        import re
        count = int(re.search(r"; (\d+) decoded opcodes", source).group(1))
        return {"selected_methods": [{
            "module": "Frontend.Client.Core.dll",
            "method_token": token, "decoded_instructions": count,
        }]}

    def test_49_predetect_constructor_and_completion_event_sites(self):
        src = self._phase_predetect_fixture()
        e = tool.audit(self._phase_inv(src, "0x0600133D"), src)["evidence"]
        self.assertTrue(e["pre_detect_result_constructor_exact_static_site"])
        self.assertTrue(e["pre_detect_done_guarded_event_exact_static_site"])
        self.assertTrue(e["pre_detect_has_distinct_result_and_event_sites"])
        self.assertFalse(e["detect_ecus_ctor_and_ui_sites_observed"])

    def test_50_wrong_predetect_result_constructor_does_not_negate_event(self):
        src = self._phase_predetect_fixture().replace(
            "IL_0195 newobj 0x0600139D", "IL_0195 newobj 0x0600139E")
        e = tool.audit(self._phase_inv(src, "0x0600133D"), src)["evidence"]
        self.assertFalse(e["pre_detect_result_constructor_exact_static_site"])
        self.assertTrue(e["pre_detect_done_guarded_event_exact_static_site"])
        self.assertFalse(e["pre_detect_has_distinct_result_and_event_sites"])

    def test_51_wrong_event_guard_branch_target_rejected(self):
        src = self._phase_predetect_fixture().replace(
            "IL_01A6 brtrue.s 6", "IL_01A6 brtrue.s 7")
        e = tool.audit(self._phase_inv(src, "0x0600133D"), src)["evidence"]
        self.assertFalse(e["pre_detect_done_guarded_event_exact_static_site"])
        self.assertTrue(e["pre_detect_result_constructor_exact_static_site"])

    def test_52_wrong_event_invocation_token_rejected(self):
        src = self._phase_predetect_fixture().replace(
            "IL_01B4 callvirt 0x0A0000DF", "IL_01B4 callvirt 0x0A0000DE")
        e = tool.audit(self._phase_inv(src, "0x0600133D"), src)["evidence"]
        self.assertFalse(e["pre_detect_done_guarded_event_exact_static_site"])

    def test_53_four_refreshes_and_distinct_detect_completion_sites(self):
        src = self._phase_detect_fixture()
        e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
        self.assertEqual(e["detect_availability_refresh_static_site_count"], 4)
        self.assertTrue(e["detect_on_detect_done_exact_static_site"])
        self.assertTrue(e["detect_device_available_true_exact_static_site"])
        self.assertTrue(e["detect_ecus_ctor_and_ui_sites_observed"])
        self.assertFalse(e["pre_detect_has_distinct_result_and_event_sites"])

    def test_54_each_refresh_token_checked_independently(self):
        good = self._phase_detect_fixture()
        for token in ("0x06001BB2", "0x06001BBA", "0x06001BCC", "0x06001BE9"):
            with self.subTest(refresh=token):
                src = good.replace(token, "0x06001BAD")
                e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
                self.assertEqual(e["detect_availability_refresh_static_site_count"], 3)
                self.assertFalse(e["detect_ecus_ctor_and_ui_sites_observed"])

    def test_55_result_ui_and_available_markers_are_not_interchangeable(self):
        good = self._phase_detect_fixture()
        for target, expected_key in (
            ("0x0600126D", "detect_ecus_ctor_and_ui_sites_observed"),
            ("0x06001343", "detect_on_detect_done_exact_static_site"),
            ("0x060012F7", "detect_device_available_true_exact_static_site"),
        ):
            with self.subTest(target=target):
                src = good.replace(target, "0x06000000")
                e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
                self.assertFalse(e[expected_key])
                self.assertFalse(e["detect_ecus_ctor_and_ui_sites_observed"])
                self.assertEqual(e["detect_availability_refresh_static_site_count"], 4)

    def test_56_allowlist_and_incomplete_evidence_never_claim_client_acceptance(self):
        src = self._phase_detect_fixture() + "# PRIVATE-VIN-AND-CUSTOMER-PATH"
        report = tool.audit(self._phase_inv(src, "0x0600132B"), src)
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v9")
        self.assertNotIn("PRIVATE-VIN", json.dumps(report))
        self.assertIn("not proof of successful user-facing detection",
                      " ".join(report["limitations"]))
        self.assertIn("do not establish runtime ECU list contents",
                      " ".join(report["limitations"]))
        self.assertFalse(report["evidence"]["pre_detect_has_distinct_result_and_event_sites"])



    @staticmethod
    def _unit_projection_fixture():
        # Synthetic isolated opcode/offset anchors, not a copied VDASH method.
        rows = [
            (0x01E2, "ldarg.0"), (0x01E3, "ldloc.1"),
            (0x01E4, "callvirt 0x06001140 get_Session"),
            (0x01E9, "stfld 0x040003AA session"),
            (0x02A4, "ldarg.0"),
            (0x02A5, "call 0x060012E8 get_DetectResult"),
            (0x02AA, "callvirt 0x06001B99 get_Units"),
            (0x02AF, "callvirt 0x0A00011A GetEnumerator"),
            (0x02B4, "stloc.s 5"),
            (0x030C, "ldloc.s 6"),
            (0x030E, "callvirt 0x06001F8F get_Ecu"),
            (0x0415, "ldloc.s 6"),
            (0x0417, "callvirt 0x06001F95 get_HardwareNumber"),
            (0x04DF, "ldarg.0"),
            (0x04E0, "call 0x060012E8 get_DetectResult"),
            (0x04E5, "callvirt 0x06001B99 get_Units"),
            (0x04EA, "callvirt 0x0A00011A GetEnumerator"),
            (0x04EF, "stloc.s 5"),
            (0x0530, "ldloc.s 10"), (0x0532, "ldloca.s 5"),
            (0x0534, "call 0x0A00011C get_Current"),
            (0x0539, "stfld 0x040003D3 u"),
            (0x0568, "ldloc.s 10"),
            (0x056A, "ldfld 0x040003D3 u"),
            (0x056F, "ldloc.s 9"), (0x0571, "ldloc.s 10"),
            (0x0573, "ldftn 0x06001387 <Detect>b__0"),
            (0x0579, "newobj 0x0A00011D .ctor"),
            (0x057E, "call 0x2B000023 generic_call"),
            (0x0583, "callvirt 0x06001F8E set_LoaderResult"),
        ]
        return ("Frontend.Client.Core.dll: MethodDef 0x0600132B VddModel.Detect; "
                + str(len(rows)) + " decoded opcodes\n"
                + "".join(f"IL_{offset:04X} {instruction}\n"
                          for offset, instruction in rows))

    def test_57_units_twice_and_loader_static_sites_present(self):
        src = self._unit_projection_fixture()
        e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
        self.assertEqual(e["detect_result_units_enumerator_static_site_count"], 2)
        for field in (
            "detect_unit_ecu_getter_exact_static_site",
            "detect_unit_hardware_number_exact_static_site",
            "detect_units_current_local_capture_exact_static_site",
            "detect_unit_loader_result_exact_static_site",
            "detect_stores_command_session_exact_static_site",
            "detect_units_and_loader_static_shapes_complete",
        ):
            self.assertTrue(e[field], field)

    def test_58_first_units_enumerator_corruption_independent(self):
        src = self._unit_projection_fixture().replace(
            "IL_02AA callvirt 0x06001B99", "IL_02AA callvirt 0x06001B98")
        e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
        self.assertEqual(e["detect_result_units_enumerator_static_site_count"], 1)
        self.assertFalse(e["detect_units_and_loader_static_shapes_complete"])
        self.assertTrue(e["detect_unit_loader_result_exact_static_site"])

    def test_59_second_units_enumerator_offset_corruption_independent(self):
        src = self._unit_projection_fixture().replace(
            "IL_04EA callvirt", "IL_04EB callvirt")
        e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
        self.assertEqual(e["detect_result_units_enumerator_static_site_count"], 1)
        self.assertFalse(e["detect_units_and_loader_static_shapes_complete"])

    def test_60_ecu_and_hardware_getter_targets_are_distinct(self):
        src = self._unit_projection_fixture()
        e = tool.audit(self._phase_inv(
            src.replace("0x06001F8F get_Ecu", "0x06001F90 get_Ecu"),
            "0x0600132B"),
            src.replace("0x06001F8F get_Ecu", "0x06001F90 get_Ecu"))["evidence"]
        self.assertFalse(e["detect_unit_ecu_getter_exact_static_site"])
        self.assertTrue(e["detect_unit_hardware_number_exact_static_site"])
        swapped = src.replace(
            "0x06001F95 get_HardwareNumber", "0x06001F94 get_HardwareNumber")
        e = tool.audit(self._phase_inv(swapped, "0x0600132B"), swapped)["evidence"]
        self.assertTrue(e["detect_unit_ecu_getter_exact_static_site"])
        self.assertFalse(e["detect_unit_hardware_number_exact_static_site"])

    def test_61_current_capture_requires_correct_storage_field(self):
        src = self._unit_projection_fixture().replace(
            "IL_0539 stfld 0x040003D3", "IL_0539 stfld 0x040003D4")
        e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
        self.assertFalse(e["detect_units_current_local_capture_exact_static_site"])
        self.assertTrue(e["detect_unit_loader_result_exact_static_site"])
        self.assertFalse(e["detect_units_and_loader_static_shapes_complete"])

    def test_62_loader_callback_and_setter_not_inferred_by_name(self):
        original = self._unit_projection_fixture()
        for before, after in (
            ("IL_0573 ldftn 0x06001387", "IL_0573 ldftn 0x06001388"),
            ("IL_0583 callvirt 0x06001F8E", "IL_0583 callvirt 0x06001F8F"),
        ):
            with self.subTest(before=before):
                src = original.replace(before, after)
                e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
                self.assertFalse(e["detect_unit_loader_result_exact_static_site"])
                self.assertFalse(e["detect_units_and_loader_static_shapes_complete"])

    def test_63_session_store_is_not_a_requirement_for_units_sites(self):
        src = self._unit_projection_fixture().replace(
            "IL_01E9 stfld 0x040003AA", "IL_01E9 stfld 0x040003AB")
        e = tool.audit(self._phase_inv(src, "0x0600132B"), src)["evidence"]
        self.assertFalse(e["detect_stores_command_session_exact_static_site"])
        self.assertTrue(e["detect_units_and_loader_static_shapes_complete"])

    def test_64_absent_source_and_privacy_preserve_unknown_acceptance(self):
        original = self._unit_projection_fixture()
        src = original + "# PRIVATE_VIN_AND_CREDENTIALS_SHOULD_STAY_PRIVATE\n"
        report = tool.audit(self._phase_inv(src, "0x0600132B"), src)
        dumped = json.dumps(report)
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v9")
        self.assertNotIn("PRIVATE_VIN", dumped)
        self.assertIn("not proof of two executed loops", " ".join(report["limitations"]))
        self.assertIn("without authenticated identity or acceptance evidence",
                      " ".join(report["limitations"]))
        # Another selected method without an extracted Detect body yields
        # unknown static sites, not a negative client or ECU result.
        other = ("Frontend.Client.Core.dll: MethodDef 0x06001160 "
                 "VddCommand.ParseData; 1 decoded opcodes\nIL_0000 ret\n")
        r = tool.audit(self._phase_inv(other, "0x06001160"), other)
        self.assertEqual(r["evidence"]["detect_result_units_enumerator_static_site_count"], 0)
        self.assertFalse(r["evidence"]["detect_units_and_loader_static_shapes_complete"])



    @staticmethod
    def _ui_done_fixture(*, omit=(), extra=(), decoder_issues=0):
        tokens = (
            ("model_id", "0x0600695B"),
            ("header", "0x0600695D"),
            ("initialize_units", "0x06002469"),
            ("dtcs_row_height", "0x060023C9"),
            ("dtcs_visibility", "0x060023D5"),
            ("cem_command_getter", "0x060023DC"),
            ("tuning_getter", "0x060023F1"),
        )
        return {"selected_methods": [{
            "module": "Frontend.exe", "method_token": "0x06002472",
            "decoded_instructions": 379, "decoder_issues": decoder_issues,
            "calls": [
                {"token": token, "count": 1, "symbol": "PRIVATE_UI_MARKER"}
                for name, token in tokens if name not in omit
            ] + list(extra),
        }]}

    @staticmethod
    def _ui_report(inv):
        # No vendor method body is added: a one-instruction mock Detect
        # exists only to exercise the audit's required parsed input.
        return tool.audit(inv, D + "Frontend.Client.Core.dll: MethodDef "
                          "0x06001160 VddCommand.ParseData; 1 decoded opcodes\n"
                          "IL_0000 ret\n")

    def test_65_ui_inventory_all_seven_methods_without_body(self):
        inv = self._ui_done_fixture()
        inv["selected_methods"].append({
            "module": "Frontend.Client.Core.dll",
            "method_token": "0x0600132B", "decoded_instructions": 4,
        })
        report = tool.audit(inv, D)
        ev = report["evidence"]
        self.assertEqual(ev["ui_done_inventory_state"], "seven_single_calls_indexed")
        self.assertEqual(ev["ui_done_covered_call_tokens"], 7)
        self.assertTrue(ev["ui_done_initialize_units_call_indexed"])
        self.assertTrue(ev["ui_done_cem_command_getter_indexed"])
        self.assertEqual(ev["ui_done_ui_projection_call_token_count"], 4)
        self.assertEqual(ev["ui_done_reported_decoded_instructions"], 379)
        self.assertEqual(ev["ui_done_reported_decoder_issues"], 0)
        self.assertFalse(ev["ui_done_full_body_in_excerpt"])
        self.assertEqual(ev["ui_done_availability_bodies_in_excerpt"], 0)

    def test_66_missing_ui_method_means_not_selected(self):
        report = tool.audit(inventory("0x0600132B"), D)
        ev = report["evidence"]
        self.assertEqual(ev["ui_done_inventory_state"], "not_selected")
        self.assertEqual(ev["ui_done_covered_call_tokens"], 0)
        self.assertIsNone(ev["ui_done_reported_decoded_instructions"])
        self.assertFalse(ev["ui_done_full_body_in_excerpt"])

    def test_67_partial_ui_call_inventory_is_not_a_full_ui_contract(self):
        inv = self._ui_done_fixture(omit=("initialize_units", "tuning_getter"))
        inv["selected_methods"].append({
            "module": "Frontend.Client.Core.dll",
            "method_token": "0x0600132B", "decoded_instructions": 4,
        })
        ev = tool.audit(inv, D)["evidence"]
        self.assertEqual(ev["ui_done_inventory_state"],
                         "partial_or_duplicate_named_calls")
        self.assertEqual(ev["ui_done_covered_call_tokens"], 5)
        self.assertFalse(ev["ui_done_initialize_units_call_indexed"])
        self.assertTrue(ev["ui_done_cem_command_getter_indexed"])

    def test_68_bad_ui_call_counts_and_tokens_fail_closed(self):
        for invalid in (
            {"token": "PRIVATE_VIN", "count": 1},
            {"token": "0x06002469", "count": "1"},
            {"token": "0x06002469", "count": True},
            {"token": "0x06002469", "count": -1},
        ):
            with self.subTest(invalid=invalid):
                inv = self._ui_done_fixture(extra=(invalid,))
                inv["selected_methods"].append({
                    "module": "Frontend.Client.Core.dll",
                    "method_token": "0x0600132B", "decoded_instructions": 4,
                })
                ev = tool.audit(inv, D)["evidence"]
                self.assertEqual(ev["ui_done_inventory_state"],
                                 "invalid_call_inventory")

    def test_69_duplicate_ui_call_does_not_count_as_single(self):
        inv = self._ui_done_fixture(extra=(
            {"token": "0x06002469", "count": 1, "symbol": "PRIVATE"},))
        inv["selected_methods"].append({
            "module": "Frontend.Client.Core.dll",
            "method_token": "0x0600132B", "decoded_instructions": 4,
        })
        ev = tool.audit(inv, D)["evidence"]
        self.assertEqual(ev["ui_done_covered_call_tokens"], 6)
        self.assertFalse(ev["ui_done_initialize_units_call_indexed"])
        self.assertEqual(ev["ui_done_inventory_state"],
                         "partial_or_duplicate_named_calls")

    def test_70_frontend_ui_token_is_module_scoped(self):
        inv = self._ui_done_fixture()
        inv["selected_methods"][0]["module"] = "Frontend.Client.Core.dll"
        inv["selected_methods"][0]["decoded_instructions"] = 4
        src = """Frontend.Client.Core.dll: MethodDef 0x06002472 Other.Name; 4 decoded opcodes
IL_0000 nop
IL_0001 nop
IL_0002 nop
IL_0003 ret
"""
        ev = tool.audit(inv, src)["evidence"]
        self.assertEqual(ev["ui_done_inventory_state"], "not_selected")
        self.assertFalse(ev["ui_done_full_body_in_excerpt"])

    def test_71_method_body_flag_tracks_only_actual_excerpt(self):
        inv = self._ui_done_fixture()
        inv["selected_methods"][0]["decoded_instructions"] = 1
        src = ("Frontend.exe: MethodDef 0x06002472 "
               "DetectViewModel.Model_DetectDone; 1 decoded opcodes\n"
               "IL_0000 ret\n")
        report = tool.audit(inv, src)
        ev = report["evidence"]
        self.assertTrue(ev["ui_done_full_body_in_excerpt"])
        self.assertEqual(ev["ui_done_inventory_state"], "seven_single_calls_indexed")
        self.assertNotIn("ECU accepted", json.dumps(report))

    def test_72_ui_audit_allowlisted_redacts_raw_symbols_and_unknowns(self):
        inv = self._ui_done_fixture(extra=(
            {"token": "0x0600ABCD", "count": 1, "symbol": "CUSTOMER-PRIVATE-VIN"},
        ))
        inv["selected_methods"].append({
            "module": "Frontend.Client.Core.dll",
            "method_token": "0x0600132B", "decoded_instructions": 4,
        })
        out = tool.audit(inv, D)
        dumped = json.dumps(out)
        self.assertEqual(out["format"], "recovered-il-evidence-audit-v9")
        self.assertNotIn("CUSTOMER-PRIVATE-VIN", dumped)
        self.assertNotIn("PRIVATE_UI_MARKER", dumped)
        self.assertNotIn("0x06002472", dumped)
        self.assertIn("not a recovered method body", " ".join(out["limitations"]))
        self.assertEqual(out["evidence"]["ui_done_inventory_state"],
                         "seven_single_calls_indexed")



    @staticmethod
    def _g4_fixture(*, include_ui=True):
        # Construct a synthetic Detect method from small independently
        # recognizable shapes. It is NOT the protected vendor method.
        import re
        original = RecoveredIlTests._phase_detect_fixture().splitlines()
        extra = [
            "IL_0177 ldarg.0",
            "IL_0178 ldarg.0",
            "IL_0179 call 0x060012E2 get_Volvo",
            "IL_017E ldloc.2",
            "IL_017F newobj 0x060011BB .ctor",
            "IL_0184 call 0x060012E9 set_DetectResult",
        ]
        original[0] = re.sub(
            r"; \d+ decoded opcodes$",
            f"; {len(original) - 1 + len(extra)} decoded opcodes",
            original[0],
        )
        source = "\n".join([original[0]] + extra + original[1:]) + "\n"
        methods = [{
            "module": "Frontend.Client.Core.dll",
            "method_token": "0x0600132B",
            "decoded_instructions": len(original) - 1 + len(extra),
        }]
        if include_ui:
            methods += RecoveredIlTests._ui_done_fixture()["selected_methods"]
        return source, {"selected_methods": methods}

    @staticmethod
    def _g4_map(report):
        return {x["target"]: x for x in report["g4_dependency_coverage"]["targets"]}

    def test_73_eight_targets_split_callsite_and_body_coverage(self):
        source, inv = self._g4_fixture()
        result = tool.audit(inv, source)["g4_dependency_coverage"]
        by_name = {x["target"]: x for x in result["targets"]}
        self.assertEqual(result["total_targets"], 8)
        self.assertEqual(result["source_referenced"], 8)
        self.assertEqual(result["full_excerpt_bodies"], 0)
        self.assertEqual(len(result["prioritized_missing_bodies"]), 8)
        self.assertEqual(by_name["model_detect_done"]["reference"], "indexed_method")
        self.assertEqual(by_name["model_detect_done"]["body_coverage"],
                         "selected_without_excerpt")
        self.assertEqual(by_name["initialize_units"]["reference"], "indexed_call")
        self.assertEqual(by_name["ecus_ctor"]["reference"], "direct_il")
        self.assertFalse(result["runtime_execution_verified"])
        self.assertFalse(result["ecu_list_acceptance_verified"])

    def test_74_constructor_source_motif_mutation_is_localized(self):
        source, inv = self._g4_fixture()
        changed = source.replace("IL_017F newobj 0x060011BB",
                                 "IL_017F newobj 0x060011BC")
        evidence = self._g4_map(tool.audit(inv, changed))
        self.assertEqual(evidence["detect_result_ctor"]["reference"], "not_observed")
        self.assertEqual(evidence["ecus_ctor"]["reference"], "direct_il")
        self.assertEqual(evidence["initialize_units"]["reference"], "indexed_call")

    def test_75_missing_ui_inventory_preserves_detect_cil_references(self):
        source, inv = self._g4_fixture(include_ui=False)
        result = tool.audit(inv, source)["g4_dependency_coverage"]
        evidence = {x["target"]: x for x in result["targets"]}
        self.assertEqual(result["source_referenced"], 6)
        self.assertEqual(evidence["model_detect_done"]["reference"], "not_observed")
        self.assertEqual(evidence["initialize_units"]["reference"], "not_observed")
        self.assertEqual(evidence["ecm_refresh"]["reference"], "direct_il")

    def test_76_missing_ui_call_list_is_not_initialize_units_negative(self):
        source, inv = self._g4_fixture()
        inv["selected_methods"][1].pop("calls")
        evidence = self._g4_map(tool.audit(inv, source))
        self.assertEqual(evidence["model_detect_done"]["reference"], "indexed_method")
        self.assertEqual(evidence["initialize_units"]["reference"], "not_observed")
        self.assertEqual(evidence["initialize_units"]["body_coverage"],
                         "not_selected")

    def test_77_module_scoped_target_requires_exact_assembly(self):
        source, inv = self._g4_fixture()
        inv["selected_methods"].append({
            "module": "Frontend.Client.Core.dll",
            "method_token": "0x06002469",
            "decoded_instructions": 1,
        })
        wrong = self._g4_map(tool.audit(inv, source))
        self.assertEqual(wrong["initialize_units"]["body_coverage"], "not_selected")
        inv["selected_methods"][-1]["module"] = "Frontend.exe"
        correct = self._g4_map(tool.audit(inv, source))
        self.assertEqual(correct["initialize_units"]["body_coverage"],
                         "selected_without_excerpt")

    def test_78_full_body_requires_matching_selected_method_and_excerpt(self):
        source, inv = self._g4_fixture()
        inv["selected_methods"].append({
            "module": "Frontend.exe",
            "method_token": "0x06002469",
            "decoded_instructions": 1,
        })
        other = ("Frontend.exe: MethodDef 0x06002469 "
                 "DetectViewModel.InitializeUnits; 1 decoded opcodes\n"
                 "IL_0000 ret\n")
        report = tool.audit(inv, source + other)["g4_dependency_coverage"]
        self.assertEqual(report["full_excerpt_bodies"], 1)
        self.assertEqual(
            {x["target"]: x for x in report["targets"]}
            ["initialize_units"]["body_coverage"], "excerpt_present")
        self.assertFalse(report["ecu_list_acceptance_verified"])

    def test_79_each_refresh_reference_requires_its_own_cil_callsite(self):
        source, inv = self._g4_fixture()
        damaged = source.replace("IL_05D3 callvirt 0x06001BB2",
                                 "IL_05D3 callvirt 0x06001BB3")
        refs = self._g4_map(tool.audit(inv, damaged))
        self.assertEqual(refs["dim_refresh"]["reference"], "not_observed")
        for label in ("ecm_refresh", "icm_refresh", "phm_refresh"):
            self.assertEqual(refs[label]["reference"], "direct_il")

    def test_80_dependency_summary_is_fixed_schema_and_private_safe(self):
        source, inv = self._g4_fixture()
        inv["selected_methods"][1]["calls"].append({
            "token": "0x0600ABCD", "count": 1,
            "symbol": "PERSONAL_VIN_PRIVATE_PATH",
        })
        report = tool.audit(inv, source)
        data = json.dumps(report)
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v9")
        self.assertNotIn("PERSONAL_VIN_PRIVATE_PATH", data)
        self.assertNotIn("0x0600ABCD", data)
        self.assertNotIn("0x06002469", data)
        self.assertIn("not execution or ECU acceptance",
                      " ".join(report["limitations"]))
        self.assertEqual(report["g4_dependency_coverage"]["total_targets"], 8)


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
