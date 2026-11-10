"""Synthetic-only gates for privacy-safe VIDA Analyzer evidence aggregation."""
from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import vida_evidence_summary as mod


def catalog():
    return {
        "schema_version": "virtualcar-vida-unified-catalog-v1",
        "backend": "sqlite-export", "status": "metadata_only",
        **{name: False for name in mod.CATALOG_NEGATIVE},
        "databases": {name: {"table_count": 1, "column_count": 2,
                              "declared_fk_column_count": 0, "known_tables": {}}
                      for name in mod.DATABASES},
        "edges": [], "hidden_private_vin": "PRIVATE_VIN_SHOULD_NEVER_LEAK",
    }


def comparison():
    return {
        "schema_version": "virtualcar-vida-catalog-compare-v1",
        "status": "metadata_shape_comparison_only",
        **{name: False for name in mod.COMPARE_NEGATIVE},
        "table_disagreements": [], "column_disagreements": [],
        "candidate_edge_disagreements": [],
    }


def readvin():
    return {
        "schema_version": "virtualcar-vida-redacted-readvin-crosscheck-v1",
        "input_kind": "two_redacted_static_vida_reports",
        "structural_counters_consistent": True,
        **{name: False for name in mod.READVIN_NEGATIVE},
        "crosschecked_fields": 7, "nodes": 14, "readvin_nodes": 7,
        "identity_output_nodes": 1,
        "identity_methods": {"add_vin_declarations": 2, "x40_declarations": 1},
    }


class VidaEvidenceSummaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_01_catalog_only_never_promotes_selected_profile(self):
        report = mod.assemble(catalog=catalog())
        gates = {v["id"]: v["status"] for v in report["stages"]}
        self.assertEqual(gates["catalog_metadata"], "passed")
        self.assertEqual(gates["getscript_runtime_selection"], "not_tested")
        self.assertFalse(report["same_installation_provenance_verified"])
        self.assertFalse(report["replay_approved"])

    def test_02_readvin_only_static_not_runtime(self):
        report = mod.assemble(readvin=readvin())
        self.assertEqual(report["readvin_graph"]["readvin_reader_nodes"], 7)
        self.assertFalse(report["client_vin_accepted"])
        self.assertIn("profile_to_readvin_join", report["open_blockers"])

    def test_03_comparison_pass_only_for_zero_shape_disagreements(self):
        report = mod.assemble(comparison=comparison())
        self.assertEqual(report["stages"][1]["status"], "passed")
        changed = comparison()
        changed["column_disagreements"].append({"PRIVATE_VIN": "SECRET"})
        report = mod.assemble(comparison=changed)
        self.assertEqual(report["stages"][1]["status"], "failed")
        self.assertIn("catalog_shape_comparison", report["open_blockers"])
        self.assertNotIn("PRIVATE", json.dumps(report))

    def test_04_all_inputs_still_no_runtime_and_private_data_leak(self):
        original = catalog(), comparison(), readvin()
        result = mod.assemble(*original)
        serialized = json.dumps(result)
        self.assertNotIn("PRIVATE_VIN_SHOULD_NEVER_LEAK", serialized)
        for key in ("client_vin_accepted", "profile_script_link_verified",
                    "actual_getscript_selected", "physical_j2534_verified"):
            self.assertIs(result[key], False)
        self.assertEqual(len(result["stages"]), 7)

    def test_05_reject_forged_runtime_flags_in_each_source(self):
        for index, flag in ((0, "record_joins_verified"),
                            (1, "client_vin_accepted"),
                            (2, "runtime_readvin_selected")):
            reports = [catalog(), comparison(), readvin()]
            reports[index][flag] = True
            with self.subTest(source=index), self.assertRaises(mod.EvidenceError):
                mod.assemble(*reports)

    def test_06_reject_empty_graph_and_bogus_count_types(self):
        for field, val in (("readvin_nodes", 0), ("identity_output_nodes", 0),
                           ("nodes", True), ("crosschecked_fields", 6)):
            bad = readvin()
            bad[field] = val
            with self.subTest(field=field), self.assertRaises(mod.EvidenceError):
                mod.assemble(readvin=bad)

    def test_07_reject_missing_catalog_scope_bad_comparison_shape(self):
        cat = catalog()
        del cat["databases"]["CarCom"]
        with self.assertRaises(mod.EvidenceError):
            mod.assemble(catalog=cat)
        cmp = comparison()
        cmp["table_disagreements"] = "not-a-list"
        with self.assertRaises(mod.EvidenceError):
            mod.assemble(comparison=cmp)

    def test_08_reject_duplicate_keys_nonfinite_symlink_and_large_input(self):
        path = self.folder / "source.json"
        for txt in ('{"x":1,"x":2}', '{"x":NaN}'):
            path.write_text(txt, encoding="utf-8")
            with self.assertRaises(mod.EvidenceError):
                mod.read_report(path)
        path.write_bytes(b"X" * (mod.MAX_REPORT_BYTES + 1))
        with self.assertRaises(mod.EvidenceError):
            mod.read_report(path)
        path.write_text("{}", encoding="utf-8")
        link = self.folder / "link.json"
        try:
            link.symlink_to(path)
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation unavailable")
        with self.assertRaises(mod.EvidenceError):
            mod.read_report(link)

    def test_09_cli_output_exclusive_and_no_private_content_echo(self):
        src = self.folder / "readvin-private.json"
        src.write_text(json.dumps(readvin()), encoding="utf-8")
        out = self.folder / "summary.json"
        args = ["--readvin-report", str(src), "--output", str(out)]
        out_stdout, out_stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out_stdout), contextlib.redirect_stderr(out_stderr):
            self.assertEqual(mod.main(args), 0)
            self.assertEqual(mod.main(args), 2)
        self.assertEqual(json.loads(out.read_text())["readvin_graph"]["identity_call_declarations"], 3)
        self.assertNotIn(str(src), out_stderr.getvalue())
        self.assertNotIn(str(out), out_stderr.getvalue())

    def test_10_no_inputs_or_same_input_output_rejected(self):
        out = self.folder / "out.json"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(["--output", str(out)]), 2)
        self.assertFalse(out.exists())
        src = self.folder / "input.json"
        src.write_text(json.dumps(readvin()), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(["--readvin-report", str(src), "--output", str(src)]), 2)
        self.assertEqual(json.loads(src.read_text())["schema_version"], readvin()["schema_version"])


if __name__ == "__main__":
    unittest.main()
