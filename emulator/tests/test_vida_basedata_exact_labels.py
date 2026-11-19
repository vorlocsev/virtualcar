"""Synthetic exact lookup tests; never open the owner's VIDA exports."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_basedata_exact_labels import SchemaError, audit, main
from test_vida_profile_fk_counts import make_database


class BasedataExactLabelsTests(unittest.TestCase):
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
            db.execute('UPDATE "dbo_VehicleModel" SET "Description"="XC90" WHERE "Id"=10')
            db.execute('UPDATE "dbo_VehicleModel" SET "Description"="XC70" WHERE "Id"=20')
            db.execute('UPDATE "dbo_ModelYear" SET "Description"="2009" WHERE "Id"=2009')
            db.execute('UPDATE "dbo_Engine" SET "Description"="B8444S" WHERE "Id"=80')
            # General comparison candidate with model/year and unconstrained engine.
            db.execute('INSERT INTO "dbo_VehicleProfile" VALUES (4,10,2009,NULL)')
            db.execute('UPDATE "_vida_tables" SET "rows_exported"=4 WHERE "table_name"="VehicleProfile"')

    def test_01_exact_labels_count_base_data_not_cross_db(self):
        result = audit(self.folder)
        self.assertEqual(result["status"], "exact_label_preflight_only")
        self.assertEqual(result["lookup_match_classes"], {"model": "one", "year": "one", "engine": "one"})
        self.assertEqual(result["counts"]["exact_model_year_engine_rows"], 1)
        self.assertEqual(result["counts"]["model_year_with_null_engine_rows"], 1)
        self.assertEqual(result["counts"]["model_year_all_engine_rows"], 2)
        self.assertIs(result["source_rows_read"], True)
        self.assertIs(result["cross_database_profile_mapping_verified"], False)
        self.assertIs(result["original_selection_of_43_reconstructed"], False)
        self.assertIs(result["original_readvin_accepted"], False)

    def test_02_missing_exact_lookup_does_not_guess_alias(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_Engine" SET "Description"="B8444S_V8"')
        r = audit(self.folder)
        self.assertEqual(r["lookup_match_classes"]["engine"], "zero")
        self.assertIsNone(r["counts"])

    def test_03_duplicate_exact_lookup_fails_closed_for_selection(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_VehicleModel" SET "Description"="XC90" WHERE "Id"=20')
        r = audit(self.folder)
        self.assertEqual(r["lookup_match_classes"]["model"], "multiple_or_invalid")
        self.assertIsNone(r["counts"])

    def test_04_null_lookup_id_disallows_counts(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "dbo_Engine" SET "Id"=NULL')
        r = audit(self.folder)
        self.assertEqual(r["lookup_match_classes"]["engine"], "multiple_or_invalid")
        self.assertIsNone(r["counts"])

    def test_05_no_source_labels_or_ids_in_report(self):
        text = json.dumps(audit(self.folder))
        for forbidden in ("XC90", "B8444S", "2009", "139578", str(self.folder)):
            self.assertNotIn(forbidden, text)

    def test_06_missing_original_description_metadata_rejected(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('DELETE FROM "_vida_columns" WHERE "table_name"="Engine" AND "column_name"="Description"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_07_missing_physical_description_column_rejected(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('ALTER TABLE "dbo_Engine" DROP COLUMN "Description"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_08_wrong_source_database_identity_rejected(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "_vida_meta" SET "value"="wrong" WHERE "key"="source_database"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_09_uncheckpointed_export_sidecar_rejected(self):
        Path(str(self.base) + "-wal").write_text("pending")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_10_cli_only_sanitized_error(self):
        out = StringIO()
        with redirect_stderr(out):
            result = main(["--folder", str(self.folder / "absent")])
        self.assertEqual(result, 2)
        parsed = json.loads(out.getvalue())
        self.assertEqual(set(parsed), {"status", "error_class"})
        self.assertNotIn(str(self.folder), out.getvalue())


if __name__ == "__main__":
    unittest.main()
