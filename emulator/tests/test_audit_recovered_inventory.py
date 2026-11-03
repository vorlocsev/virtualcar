"""Eight synthetic checks for recovered ParseData inventory and REA SHA binding.

No proprietary IL, DLL, encrypted symbol names, or real VINs are in fixtures.
"""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_recovered_inventory.py"
spec = importlib.util.spec_from_file_location("audit_recovered_inventory", SOURCE)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)
ZIP = "a" * 64
ORIGINAL = "b" * 64
RECOVERED = "c" * 64
PRIVATE = "PRIVATE_DO_NOT_PUBLISH"


def method(token, index, il_bytes, decoded, calls):
    return {
        "module": "Frontend.Client.Core.dll",
        "method_token": token,
        "method_index": index,
        "il_bytes": il_bytes,
        "decoded_instructions": decoded,
        "decoder_issues": 0,
        "metadata_name": PRIVATE,
        "calls": [{"token": t, "count": n, "symbol": PRIVATE}
                  for t, n in calls.items()],
    }


def inventory():
    return {
        "format": tool.INPUT_FORMAT,
        "source_zip_sha256": ZIP,
        "recovered_modules": {
            tool.MODULE: {
                "source_sha256": ORIGINAL,
                "recovered_sha256": RECOVERED,
                "metadata_row_alignment_normalized": True,
                "duplicate_heap_names_normalized": True,
                "private_path": "C:/VDASH/PRIVATE_VIN",
            }
        },
        "selected_methods": [
            method("0x0600132B", 4907, 1746, 511, {
                "0x2B000002": 2, "0x06001359": 2,
                "0x06001142": 1, "0x060011BB": 1,
                "0x0600126D": 1,
            }),
            method("0x0600115D", 4445, 1073, 311, {
                "0x06001160": 1,
            }),
            method("0x06001160", 4448, 550, 171, {
                "0x06001142": 4, "0x06001161": 2,
                "0x0600113D": 1, "0x06001195": 1,
                "0x06001198": 1,
            }),
        ],
        "user_strings": [PRIVATE],
    }


def rea(sha):
    return {
        "normalized_result": {
            "artifact": {"sha256": sha, "path": PRIVATE},
            "module": {"name": tool.MODULE,
                       "mvid": "01234567-89ab-cdef-0123-456789abcdef"},
            "identity_scope": {
                "token_identity": "build-local",
                "requires_artifact_sha256": sha,
                "requires_mvid": "01234567-89ab-cdef-0123-456789abcdef",
            },
        },
    }


class RecoveredInventoryEvidenceTests(unittest.TestCase):
    def test_01_parse_data_observed_static_summary(self):
        result = tool.audit(inventory())
        self.assertEqual(result["methods"]["parse_data"], {
            "inventory_record": "reported",
            "il_bytes": 550, "decoded_instructions": 171, "decoder_issues": 0,
            "call_counts": {
                "get_result_data_call": 4, "raise_event_call": 2,
                "set_data_hash_call": 1, "parse_data_callback_88": 1,
                "parse_data_callback_1": 1,
            },
        })
        self.assertEqual(result["methods"]["execute"]["call_counts"],
                         {"parse_data_call": 1})
        self.assertFalse(result["client_ecu_acceptance_verified"])

    def test_02_rea_recovered_material_match_is_distinct_from_source(self):
        result = tool.audit(inventory(), rea(RECOVERED))
        self.assertEqual(result["rea_material_binding"],
                         "matched_recovered_material")
        self.assertFalse(result["original_binary_verified_by_runtime"])

    def test_03_rea_original_source_match_does_not_prove_token_alignment(self):
        result = tool.audit(inventory(), rea(ORIGINAL))
        self.assertEqual(result["rea_material_binding"],
                         "matched_original_material")
        self.assertTrue(any("source hash match alone" in x.lower()
                            for x in result["limitations"]))

    def test_04_mismatched_rea_build_and_broken_scope_rejected(self):
        with self.assertRaisesRegex(ValueError, "different_build"):
            tool.audit(inventory(), rea("d" * 64))
        bad = rea(RECOVERED)
        bad["normalized_result"]["identity_scope"]["requires_artifact_sha256"] = ORIGINAL
        with self.assertRaisesRegex(ValueError, "invalid_rea_identity_scope"):
            tool.audit(inventory(), bad)
        bad = rea(RECOVERED)
        bad["normalized_result"]["identity_scope"]["requires_mvid"] = PRIVATE
        with self.assertRaisesRegex(ValueError, "invalid_rea_mvid"):
            tool.audit(inventory(), bad)

    def test_05_missing_inventory_method_does_not_prove_absence(self):
        data = inventory()
        data["selected_methods"] = [
            m for m in data["selected_methods"]
            if m["method_token"] != "0x06001160"
        ]
        result = tool.audit(data)
        self.assertEqual(result["methods"]["parse_data"],
                         {"inventory_record": "not_reported", "call_counts": {}})
        self.assertEqual(result["methods"]["execute"]["call_counts"],
                         {"parse_data_call": 1})

    def test_06_duplicate_tokens_and_malformed_counts_fail_closed(self):
        data = inventory()
        data["selected_methods"].append(dict(data["selected_methods"][2]))
        with self.assertRaisesRegex(ValueError, "duplicate_focus_method"):
            tool.audit(data)
        data = inventory()
        data["selected_methods"][2]["calls"].append(
            {"token": "0x06001142", "count": 3})
        with self.assertRaisesRegex(ValueError, "duplicate_call_token"):
            tool.audit(data)
        data = inventory()
        data["selected_methods"][2]["decoded_instructions"] = 551
        with self.assertRaisesRegex(ValueError, "invalid_recovered_method_counts"):
            tool.audit(data)

    def test_07_private_symbols_vin_hashes_and_paths_suppressed(self):
        result = tool.audit(inventory())
        txt = json.dumps(result, ensure_ascii=False)
        for secret in (PRIVATE, "C:/VDASH", ZIP, ORIGINAL, RECOVERED,
                       "PRIVATE_VIN"):
            self.assertNotIn(secret, txt)
        self.assertFalse(result["contains_binary_digests_or_private_symbols"])
        self.assertFalse(result["exact_original_il_body_available_here"])

    def test_08_cli_refuses_overwrite_and_malformed_file(self):
        with tempfile.TemporaryDirectory() as temp:
            original = Path(temp) / "private.json"
            sanitized = Path(temp) / "sanitized.json"
            original_text = json.dumps(inventory())
            original.write_text(original_text, encoding="utf-8")
            self.assertEqual(tool.main([str(original), "--output",
                                        str(sanitized)]), 0)
            previous = sanitized.read_bytes()
            self.assertEqual(tool.main([str(original), "--output",
                                        str(sanitized)]), 2)
            self.assertEqual(sanitized.read_bytes(), previous)
            self.assertEqual(original.read_text(encoding="utf-8"),
                             original_text)
            original.write_text("{broken_json", encoding="utf-8")
            invalid_out = Path(temp) / "invalid.json"
            self.assertEqual(tool.main([str(original), "--output",
                                        str(invalid_out)]), 2)
            self.assertFalse(invalid_out.exists())


if __name__ == "__main__":
    unittest.main()
