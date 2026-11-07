"""Eight synthetic regression groups for VIDA script-profile metadata joins."""
import contextlib
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_script_profile_links import audit, main, FIELDS


def table(path, name, rows):
    with (path / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDS[name])
        w.writerows(rows)


def fixture(path):
    table(path, "Script.csv", [("s1",), ("s2",), ("s3",)])
    table(path, "ScriptProfileMap.csv", [("private_PROFILE_A", "s1"), ("private_PROFILE_A", "s2"), ("profile_B", "s3")])
    table(path, "ScriptContent.csv", [("s1", "15"), ("s1", "1"), ("s3", "15")])


class VidaScriptProfileLinksTests(unittest.TestCase):
    def test_01_normal_selected_profile_counts_not_id(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); fixture(p)
            r = audit(p, "private_PROFILE_A")
            self.assertEqual(r["selected_profile"]["mapped_script_count"], 2)
            self.assertEqual(r["selected_profile"]["mapped_scripts_with_any_content"], 1)
            self.assertEqual(r["selected_profile"]["mapped_scripts_without_content"], 1)
            self.assertEqual(r["selected_profile"]["distinct_content_languages"], 2)
            self.assertFalse(r["runtime_selected_identity_script_verified"])

    def test_02_aggregate_without_profile_is_not_runtime_selection(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); fixture(p)
            r = audit(p)
            self.assertIsNone(r["selected_profile"])
            self.assertEqual(r["profile_count_from_mappings"], 2)
            self.assertFalse(r["b9fb_to_vin_mapping_verified"])

    def test_03_duplicate_rows_are_counted(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); fixture(p)
            table(p, "Script.csv", [("s1",), ("s1",)])
            table(p, "ScriptProfileMap.csv", [("p1", "s1"), ("p1", "s1")])
            table(p, "ScriptContent.csv", [("s1", "15"), ("s1", "15")])
            r = audit(p, "p1")
            self.assertEqual(list(r["duplicate_rows"].values()), [1, 1, 1])
            self.assertEqual(r["selected_profile"]["mapped_script_count"], 1)

    def test_04_orphan_references_distinct_from_acceptance(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); fixture(p)
            table(p, "ScriptProfileMap.csv", [("p1", "missing")])
            table(p, "ScriptContent.csv", [("missing", "15")])
            r = audit(p, "p1")
            self.assertEqual(r["orphan_foreign_key_rows"]["profile_map_script_missing"], 1)
            self.assertEqual(r["orphan_foreign_key_rows"]["script_content_script_missing"], 1)
            self.assertEqual(r["selected_profile"]["mapped_script_rows_missing_from_script_table"], 1)
            self.assertFalse(r["replay_approved"])

    def test_05_strict_headers_and_csv_values(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); fixture(p)
            table(p, "Script.csv", [("s1",), ("s2",)])
            (p / "Script.csv").write_text("id,secret\ns1,private\n", encoding="utf8")
            with self.assertRaises(ValueError): audit(p)
            table(p, "Script.csv", [("a",), ("bad value",)])
            with self.assertRaises(ValueError): audit(p)

    def test_06_missing_file_and_bad_selector_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); fixture(p)
            with self.assertRaises(ValueError): audit(p, "bad SELECT *")
            (p / "ScriptContent.csv").unlink()
            with self.assertRaises(ValueError): audit(p)

    def test_07_unknown_profile_reports_absence_without_guess(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); fixture(p)
            r = audit(p, "not_in_table")
            self.assertFalse(r["selected_profile"]["selector_has_profile_mapping"])
            self.assertEqual(r["selected_profile"]["mapped_script_count"], 0)
            self.assertFalse(r["source_sql_schema_verified_for_vida_2015a"])

    def test_08_cli_exclusive_and_redacted(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            private = base / "PRIVATE-VIN-DO-NOT-SHARE"
            private.mkdir()
            fixture(private)
            out = base / "SAFE.json"
            with contextlib.redirect_stdout(io.StringIO()):
                main([str(private), "--profile-key", "private_PROFILE_A", "--output", str(out)])
            contents = out.read_text()
            for forbidden in ("private_PROFILE_A", "PRIVATE-VIN", str(private), "s1", "profile_B"):
                self.assertNotIn(forbidden, contents)
            self.assertEqual(json.loads(contents)["selected_profile"]["mapped_script_count"], 2)
            with contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    main([str(private), "--output", str(out)])


if __name__ == "__main__":
    unittest.main()
