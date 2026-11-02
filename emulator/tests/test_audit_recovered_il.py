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
        {"method_token": token, "decoded_instructions": { 
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


if __name__ == "__main__":
    unittest.main()
