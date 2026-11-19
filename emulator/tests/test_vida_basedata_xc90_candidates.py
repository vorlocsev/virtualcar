"""Synthetic XC90 candidate count tests: never open owner-private sources."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_basedata_xc90_candidates import (
    SchemaError, _candidate_keys, _counts_for_model, audit, main,
)
from test_vida_profile_fk_counts import make_database


class BasedataXc90CandidatesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.base = make_database(self.folder, "BaseData")
        with closing(sqlite3.connect(self.base)) as db, db:
            for table in ("VehicleModel", "ModelYear", "Engine"):
                db.execute('ALTER TABLE "dbo_' + table + '" ADD COLUMN "Description" TEXT')
                db.execute('INSERT INTO "_vida_columns" VALUES (?,?,?)',
                           ("dbo", table, "Description"))
            db.execute(
                'UPDATE "dbo_VehicleModel" SET "Description"="XC90 LEGACY" WHERE Id=10'
            )
            db.execute(
                'UPDATE "dbo_VehicleModel" SET "Description"="XC90 RESTYLING" WHERE Id=20'
            )
            db.execute(
                'UPDATE "dbo_ModelYear" SET "Description"="2009" WHERE Id=2009'
            )
            db.execute(
                'UPDATE "dbo_Engine" SET "Description"="B8444S" WHERE Id=80'
            )
            db.executemany('INSERT INTO "dbo_VehicleProfile" VALUES (?,?,?,?)', [
                (4, 10, 2009, None), (5, 20, 2009, None),
                (6, 20, None, 80), (7, 20, None, None),
            ])
            db.execute('UPDATE "_vida_tables" SET "rows_exported"=7 WHERE "table_name"="VehicleProfile"')

    def test_01_two_candidate_vectors_not_cross_db_mapping(self):
        r = audit(self.folder)
        self.assertEqual(r["status"], "candidate_profile_aggregate_only")
        self.assertEqual(r["xc90_prefix_model_candidate_count"], 2)
        self.assertEqual(r["year_description_lookup"], "one")
        self.assertEqual(r["engine_description_lookup"], "one")
        self.assertEqual([x["model_profiles_all_years"] for x in
                          r["candidate_count_vectors_sorted_numerically"]], [4, 2])
        self.assertEqual([x["model_profiles_year_2009_engine_b8444s"] for x in
                          r["candidate_count_vectors_sorted_numerically"]], [1, 1])
        self.assertEqual([x["model_profiles_year_2009_engine_null"] for x in
                          r["candidate_count_vectors_sorted_numerically"]], [1, 1])
        self.assertFalse(r["model_identity_resolved"])
        self.assertFalse(r["original_selection_of_43_reconstructed"])
        self.assertFalse(r["cross_database_profile_mapping_verified"])
        self.assertFalse(r["original_vida_readvin_accepted"])
        self.assertTrue(r["source_rows_read"])
        self.assertFalse(r["source_writes_performed"])

    def test_02_private_model_names_do_not_escape_report(self):
        output = json.dumps(audit(self.folder))
        self.assertNotIn("XC90 LEGACY", output)
        self.assertNotIn("XC90 RESTYLING", output)
        self.assertNotIn(str(self.folder), output)
        self.assertNotIn("model_key", output)
        self.assertNotIn("model_id", output)

    def test_03_broad_xc900_substring_is_not_a_candidate(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_VehicleModel" SET Description="XC900" WHERE Id=20')
        r = audit(self.folder)
        self.assertEqual(r["xc90_prefix_model_candidate_count"], 1)
        self.assertEqual(len(r["candidate_count_vectors_sorted_numerically"]), 1)

    def test_04_missing_year_label_emits_no_profiles(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_ModelYear" SET Description="MY09"')
        r = audit(self.folder)
        self.assertEqual(r["year_description_lookup"], "zero")
        self.assertIsNone(r["candidate_count_vectors_sorted_numerically"])

    def test_05_ambiguous_engine_label_emits_no_profiles(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('INSERT INTO "dbo_Engine" VALUES (?,?)', (90, "B8444S"))
            db.execute('UPDATE "_vida_tables" SET rows_exported=2 WHERE table_name="Engine"')
        r = audit(self.folder)
        self.assertEqual(r["engine_description_lookup"], "multiple_or_invalid")
        self.assertIsNone(r["candidate_count_vectors_sorted_numerically"])

    def test_06_missing_model_description_column_fails_closed(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('DELETE FROM "_vida_columns" WHERE table_name="VehicleModel" AND column_name="Description"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_07_mismatched_exporter_count_fails_closed(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "_vida_tables" SET rows_exported=999 WHERE table_name="VehicleModel"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_08_duplicate_candidate_id_fails_closed(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('INSERT INTO "dbo_VehicleModel" VALUES (?,?)', (10, "XC90 DUPLICATE"))
            db.execute('UPDATE "_vida_tables" SET rows_exported=3 WHERE table_name="VehicleModel"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_09_null_matched_model_id_fails_closed(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_VehicleModel" SET Id=NULL WHERE Id=20')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_10_uncheckpointed_sqlite_sidecar_fails(self):
        Path(str(self.base) + "-wal").write_text("pending")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_11_malformed_or_oversized_model_name_fails(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_VehicleModel" SET Description=? WHERE Id=20',
                       ("X" * 513,))
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_12_sanitized_cli_failure(self):
        stream = StringIO()
        with redirect_stderr(stream):
            code = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(code, 2)
        result = json.loads(stream.getvalue())
        self.assertEqual(set(result), {"status", "error_class"})
        self.assertNotIn(str(self.folder), stream.getvalue())

    def test_13_no_model_prefix_produces_zero_candidate_vectors(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_VehicleModel" SET Description="XC70"')
        r = audit(self.folder)
        self.assertEqual(r["xc90_prefix_model_candidate_count"], 0)
        self.assertIsNone(r["candidate_count_vectors_sorted_numerically"])


if __name__ == "__main__":
    unittest.main()
