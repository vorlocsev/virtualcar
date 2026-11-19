"""Synthetic 43-profile equality boundary tests. No owner SQLite is opened."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_basedata_carcom_43_equality import SchemaError, audit, main
from test_vida_profile_fk_counts import make_database


class BaseDataCarCom43Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.base = make_database(self.folder, "BaseData")
        self.carcom = make_database(self.folder, "CarCom")
        with closing(sqlite3.connect(self.base)) as db, db:
            for table in ("VehicleModel", "ModelYear", "Engine"):
                db.execute('ALTER TABLE "dbo_' + table + '" ADD COLUMN "Description" TEXT')
                db.execute('INSERT INTO "_vida_columns" VALUES (?,?,?)', ("dbo", table, "Description"))
            db.execute('UPDATE "dbo_VehicleModel" SET Description="XC90 PERIOD ONE" WHERE Id=10')
            db.execute('UPDATE "dbo_VehicleModel" SET Description="XC90 PERIOD TWO" WHERE Id=20')
            db.execute('UPDATE "dbo_ModelYear" SET Description="2009" WHERE Id=2009')
            db.execute('UPDATE "dbo_Engine" SET Description="B8444S" WHERE Id=80')
            db.execute('DELETE FROM "dbo_VehicleProfile"')
            db.executemany('INSERT INTO "dbo_VehicleProfile" VALUES (?,?,?,?)',
                           [(1000 + i, 10, 2009, 80) for i in range(43)])
            db.execute('UPDATE "_vida_tables" SET rows_exported=43 WHERE table_name="VehicleProfile"')
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('ALTER TABLE "dbo_T161_Profile" ADD COLUMN "identifier" TEXT')
            db.execute('INSERT INTO "_vida_columns" VALUES (?,?,?)',
                       ("dbo", "T161_Profile", "identifier"))
            db.execute('DELETE FROM "dbo_T161_Profile"')
            db.executemany(
                'INSERT INTO "dbo_T161_Profile" VALUES (?,?,?,?,?)',
                [(i + 1, 100, 200, 100, str(1000 + i)) for i in range(43)]
            )
            db.execute('UPDATE "_vida_tables" SET rows_exported=43 WHERE table_name="T161_Profile"')

    def test_01_all_43_exact_identifier_equality_matches(self):
        r = audit(self.folder)
        self.assertEqual(r["cross_reference_gate"], "source_identifier_equality_classified")
        self.assertEqual(r["xc90_prefix_model_candidate_count"], 2)
        self.assertEqual(r["counts"], {
            "source_profile_count": 43,
            "carcom_exact_identifier_unique_matches": 43,
            "carcom_exact_identifier_missing": 0,
            "carcom_exact_identifier_ambiguous": 0,
            "all_43_have_unique_exact_identifier_matches": True,
        })
        self.assertFalse(r["original_profile_selection_provenance_verified"])
        self.assertFalse(r["same_as_prior_43_selection_verified"])
        self.assertFalse(r["original_vida_readvin_accepted"])
        self.assertFalse(r["private_profile_list_files_created"])

    def test_02_missing_carcom_identifier_only_counts(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T161_Profile" SET identifier="unknown" WHERE id=1')
        c = audit(self.folder)["counts"]
        self.assertEqual(c["carcom_exact_identifier_unique_matches"], 42)
        self.assertEqual(c["carcom_exact_identifier_missing"], 1)
        self.assertFalse(c["all_43_have_unique_exact_identifier_matches"])

    def test_03_duplicate_carcom_identifier_is_ambiguous(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T161_Profile" VALUES (999,100,200,100,"1000")')
            db.execute('UPDATE "_vida_tables" SET rows_exported=44 WHERE table_name="T161_Profile"')
        c = audit(self.folder)["counts"]
        self.assertEqual(c["carcom_exact_identifier_ambiguous"], 1)
        self.assertEqual(c["carcom_exact_identifier_unique_matches"], 42)

    def test_04_duplicate_base_profile_id_fails_closed(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_VehicleProfile" SET Id=1001 WHERE Id=1000')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_05_two_models_with_target_rows_do_not_select_one(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('INSERT INTO "dbo_VehicleProfile" VALUES (2000,20,2009,80)')
            db.execute('UPDATE "_vida_tables" SET rows_exported=44 WHERE table_name="VehicleProfile"')
        r = audit(self.folder)
        self.assertEqual(r["cross_reference_gate"], "no_unique_profile_bearing_model")
        self.assertIsNone(r["counts"])

    def test_06_42_profiles_do_not_get_promoted_to_original_43(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('DELETE FROM "dbo_VehicleProfile" WHERE Id=1000')
            db.execute('UPDATE "_vida_tables" SET rows_exported=42 WHERE table_name="VehicleProfile"')
        r = audit(self.folder)
        self.assertEqual(r["cross_reference_gate"], "candidate_profile_count_not_43")
        self.assertIsNone(r["counts"])

    def test_07_ambiguous_year_lookup_has_no_carcom_match(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('INSERT INTO "dbo_ModelYear" VALUES (2029,"2009")')
            db.execute('UPDATE "_vida_tables" SET rows_exported=2 WHERE table_name="ModelYear"')
        r = audit(self.folder)
        self.assertEqual(r["year_lookup"], "multiple_or_invalid")
        self.assertEqual(r["cross_reference_gate"], "lookup_unresolved")
        self.assertIsNone(r["counts"])

    def test_08_missing_carcom_identifier_column_rejected(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('DELETE FROM "_vida_columns" WHERE table_name="T161_Profile" AND column_name="identifier"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_09_exporter_carcom_table_count_mismatch_rejected(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "_vida_tables" SET rows_exported=900 WHERE table_name="T161_Profile"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_10_wal_shm_sidecar_fails_closed(self):
        Path(str(self.carcom) + "-wal").write_text("pending")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_11_original_values_and_paths_not_exposed(self):
        text = json.dumps(audit(self.folder))
        for private in (str(self.folder), "XC90 PERIOD ONE", "XC90 PERIOD TWO",
                        '"1000"', '"1001"', "OriginalVINSecret"):
            self.assertNotIn(private, text)
        self.assertFalse(audit(self.folder)["original_private_ids_or_labels_exported"])

    def test_12_zero_padded_carcom_identifier_is_not_guessed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T161_Profile" SET identifier="01000" WHERE id=1')
        c = audit(self.folder)["counts"]
        self.assertEqual(c["carcom_exact_identifier_missing"], 1)

    def test_13_null_carcom_profile_pk_is_ambiguous(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T161_Profile" SET id=NULL WHERE id=1')
        c = audit(self.folder)["counts"]
        self.assertEqual(c["carcom_exact_identifier_ambiguous"], 1)

    def test_14_sanitized_cli_error(self):
        stream = StringIO()
        with redirect_stderr(stream):
            status = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(status, 2)
        parsed = json.loads(stream.getvalue())
        self.assertEqual(set(parsed), {"status", "error_class"})
        self.assertNotIn(str(self.folder), stream.getvalue())


if __name__ == "__main__":
    unittest.main()
