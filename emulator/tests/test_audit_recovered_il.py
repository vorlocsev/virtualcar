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
            f"VddModel.Detect; {len(lines)} decoded opcodes\\n"
            + "".join(f"IL_{i:04X} {instruction}\\n"
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
        self.assertEqual(report["format"], "recovered-il-evidence-audit-v2")


def inventory_for_detect_shape(source):
    import re
    m = re.search(r"VddModel.Detect; (\\d+) decoded opcodes", source)
    if m is None:
        raise ValueError("missing synthetic fixture")
    return {"selected_methods": [{
        "module": "Frontend.Client.Core.dll",
        "method_token": "0x0600132B",
        "decoded_instructions": int(m.group(1)),
    }]}



if __name__ == "__main__":
    unittest.main()
