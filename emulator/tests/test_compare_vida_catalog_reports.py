"""Offline privacy and evidence-boundary checks for two redacted catalog reports."""
from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import vida_unified_analyzer as unified

SPEC = importlib.util.spec_from_file_location("vida_catalog_compare", TOOLS / "compare_vida_catalog_reports.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def sample(backend):
    inventories = {db: {"tables": {("dbo", name.casefold()): {c.casefold() for c in (cols or ("SECRET_INTERNAL_COLUMN",))}
                                  for name, cols in fixed.items()}, "keys": []}
                   for db, fixed in unified.TABLES.items()}
    return unified.render(inventories, backend)


class CompareVidaReportsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.sqlite = sample("sqlite-export")
        self.sqlserver = sample("sqlserver")

    def test_01_matching_shape_no_unverified_claim(self):
        result = mod.compare(self.sqlite, self.sqlserver)
        self.assertEqual(result["status"], "metadata_shape_comparison_only")
        self.assertEqual(result["table_disagreements"], [])
        self.assertEqual(result["column_disagreements"], [])
        self.assertEqual(result["candidate_edge_disagreements"], [])
        self.assertFalse(result["client_vin_accepted"])
        self.assertFalse(result["record_joins_verified"])

    def test_02_known_table_column_and_candidate_edge_diff(self):
        entry = self.sqlserver["databases"]["CarCom"]["known_tables"]["T122_Protocol"]
        entry["present"] = False
        entry["column_count"] = 0
        self.sqlserver["databases"]["CarCom"]["column_count"] -= 2
        entry["known_columns_present"] = []
        entry["known_columns_missing"] = list(unified.TABLES["CarCom"]["T122_Protocol"])
        for edge in self.sqlserver["edges"]:
            if edge["target"] == "T122_Protocol":
                edge["column_shape_present"] = False
        result = mod.compare(self.sqlite, self.sqlserver)
        self.assertEqual(len(result["table_disagreements"]), 1)
        self.assertGreaterEqual(len(result["column_disagreements"]), 2)
        self.assertGreaterEqual(len(result["candidate_edge_disagreements"]), 1)
        self.assertTrue(all(item["database"] == "CarCom"
                            for item in result["candidate_edge_disagreements"]))

    def test_03_unknown_private_identifiers_never_emitted(self):
        self.sqlserver["databases"]["CarCom"]["PRIVATE_VIN_FROM_CUSTOMER"] = "SENSITIVE_DATA"
        self.sqlserver["edges"].append({"evidence": "sqlserver_declared_fk",
                                        "referential_rows_verified": False,
                                        "source": "PRIVATE_USER_FK",
                                        "PRIVATE_KEY": "PRIVATE_VIN_123456789"})
        result = json.dumps(mod.compare(self.sqlite, self.sqlserver))
        self.assertNotIn("PRIVATE", result)
        self.assertNotIn("SENSITIVE", result)

    def test_04_reject_forged_acceptance_or_wrong_backend(self):
        self.sqlite["client_vin_accepted"] = True
        with self.assertRaisesRegex(mod.CompareError, "unsupported verified claim"):
            mod.compare(self.sqlite, self.sqlserver)
        self.sqlite["client_vin_accepted"] = False
        self.sqlserver["backend"] = "sqlite-export"
        with self.assertRaisesRegex(mod.CompareError, "unexpected backend"):
            mod.compare(self.sqlite, self.sqlserver)
        self.sqlserver["backend"] = "sqlserver"
        self.sqlserver["edges"].append({"evidence": "sqlserver_declared_fk",
                                        "referential_rows_verified": True})
        with self.assertRaisesRegex(mod.CompareError, "unexpected declared FK"):
            mod.compare(self.sqlite, self.sqlserver)

    def test_05_reject_duplicate_missing_and_bogus_shape(self):
        self.sqlite["edges"].append(copy.deepcopy(self.sqlite["edges"][0]))
        with self.assertRaisesRegex(mod.CompareError, "duplicate shape edge"):
            mod.compare(self.sqlite, self.sqlserver)
        self.sqlite["edges"].pop()
        self.sqlite["edges"][0]["database"] = ["unhashable"]
        with self.assertRaisesRegex(mod.CompareError, "invalid report edge identity"):
            mod.compare(self.sqlite, self.sqlserver)
        self.sqlite["edges"][0]["database"] = "CarCom"
        self.sqlite["edges"].pop()
        with self.assertRaisesRegex(mod.CompareError, "missing known shape edges"):
            mod.compare(self.sqlite, self.sqlserver)

    def test_06_reject_ambiguous_columns_and_unknown_fixed_table(self):
        entry = self.sqlite["databases"]["CarCom"]["known_tables"]["T111_Service"]
        entry["known_columns_present"].append("PRIVATE_CUSTOMER_VIN")
        with self.assertRaisesRegex(mod.CompareError, "ambiguous column shapes"):
            mod.compare(self.sqlite, self.sqlserver)
        entry["known_columns_present"].pop()
        self.sqlite["databases"]["CarCom"]["known_tables"]["EXTRA"] = {"present": True}
        with self.assertRaisesRegex(mod.CompareError, "unexpected table inventory"):
            mod.compare(self.sqlite, self.sqlserver)

    def test_07_reject_candidate_edge_shape_inconsistent_with_tables(self):
        edge = self.sqlite["edges"][0]
        edge["column_shape_present"] = False
        with self.assertRaisesRegex(mod.CompareError, "inconsistent candidate edge shape"):
            mod.compare(self.sqlite, self.sqlserver)

    def test_08_fail_closed_on_duplicate_json_keys(self):
        path = self.folder / "bad.json"
        path.write_text('{"backend":"sqlserver", "backend":"sqlite-export"}', encoding="utf-8")
        with self.assertRaisesRegex(mod.CompareError, "duplicate JSON key"):
            mod.read_redacted_report(path)

    def test_10_reject_absent_table_with_positive_columns(self):
        entry = self.sqlserver["databases"]["CarCom"]["known_tables"]["T122_Protocol"]
        entry["present"] = False
        entry["known_columns_present"] = []
        entry["known_columns_missing"] = list(unified.TABLES["CarCom"]["T122_Protocol"])
        with self.assertRaisesRegex(mod.CompareError, "inconsistent known-table column count"):
            mod.compare(self.sqlite, self.sqlserver)

    def test_11_reject_known_columns_exceeding_declared_count(self):
        entry = self.sqlite["databases"]["CarCom"]["known_tables"]["T111_Service"]
        entry["column_count"] = 1
        with self.assertRaisesRegex(mod.CompareError, "inconsistent known-table column count"):
            mod.compare(self.sqlite, self.sqlserver)

    def test_12_reject_invalid_aggregate_and_metadata_count_types(self):
        self.sqlite["databases"]["CarCom"]["table_count"] = False
        with self.assertRaisesRegex(mod.CompareError, "invalid catalog count"):
            mod.compare(self.sqlite, self.sqlserver)
        self.sqlite["databases"]["CarCom"]["table_count"] = 1
        with self.assertRaisesRegex(mod.CompareError, "inconsistent aggregate catalog count"):
            mod.compare(self.sqlite, self.sqlserver)

    def test_13_reject_zero_column_present_table_and_fake_sqlite_fks(self):
        entry = self.sqlite["databases"]["DiagSwdlRepository"]["known_tables"]["ScriptContent"]
        entry["column_count"] = 0
        with self.assertRaisesRegex(mod.CompareError, "inconsistent known-table column count"):
            mod.compare(self.sqlite, self.sqlserver)
        entry["column_count"] = 1
        self.sqlite["databases"]["CarCom"]["declared_fk_column_count"] = 2
        with self.assertRaisesRegex(mod.CompareError, "unexpected SQLite declared FK count"):
            mod.compare(self.sqlite, self.sqlserver)

    def test_09_cli_exclusive_output_and_no_secret_echo(self):
        s = self.folder / "s.json"
        t = self.folder / "t.json"
        out = self.folder / "result.json"
        s.write_text(json.dumps(self.sqlite), encoding="utf-8")
        t.write_text(json.dumps(self.sqlserver), encoding="utf-8")
        args = ["--sqlite-report", str(s), "--sqlserver-report", str(t),
                "--output", str(out)]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(args), 0)
            self.assertEqual(mod.main(args), 2)
        self.assertEqual(json.loads(out.read_text(encoding="utf-8"))["table_disagreements"], [])
        self.assertEqual(json.loads(s.read_text(encoding="utf-8"))["backend"], "sqlite-export")


if __name__ == "__main__":
    unittest.main()
