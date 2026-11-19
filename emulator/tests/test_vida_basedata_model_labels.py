"""Synthetic, private-data-free BaseData vehicle-model label category tests."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from inspect_vida_basedata_model_labels import SchemaError, audit, main, _summarize_descriptions
from test_vida_profile_fk_counts import make_database


class BaseDataModelLabelsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = make_database(self.folder, "BaseData")
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute('ALTER TABLE "dbo_VehicleModel" ADD COLUMN "Description" TEXT')
            db.execute(
                'INSERT INTO "_vida_columns" VALUES (?,?,?)',
                ("dbo", "VehicleModel", "Description"),
            )
            db.execute(
                'UPDATE "dbo_VehicleModel" SET "Description"="XC90 (2002-)" WHERE "Id"=10'
            )
            db.execute(
                'UPDATE "dbo_VehicleModel" SET "Description"="Volvo XC90" WHERE "Id"=20'
            )
            db.executemany(
                'INSERT INTO "dbo_VehicleModel" VALUES (?,?)',
                [(30, "XC900"), (40, "XC 90"),
                 (50, "XC-90"), (60, " XC90 (2003-)"), (70, None)],
            )
            db.execute(
                'UPDATE "_vida_tables" SET "rows_exported"=7 '
                'WHERE "table_name"="VehicleModel"'
            )

    def test_01_owner_zero_exact_case_yields_shape_only(self):
        r = audit(self.folder)
        self.assertEqual(r["status"], "original_model_description_categories_only")
        self.assertEqual(r["vehicle_model_table_rows_checked"], 7)
        self.assertEqual(r["description_counts"], {
            "exact_xc90": 0,
            "prefix_xc90_token": 2,
            "anywhere_xc90_token": 3,
            "anywhere_xc90_substring": 4,
            "anywhere_xc_space_90_token": 1,
            "anywhere_xc_hyphen_90_token": 1,
            "null_or_empty_description_rows": 1,
        })
        self.assertTrue(r["source_rows_read"])
        self.assertFalse(r["original_model_labels_or_ids_exported"])
        self.assertFalse(r["model_identity_resolved"])
        self.assertFalse(r["original_selection_of_43_reconstructed"])

    def test_02_boundary_rejects_xc900_token(self):
        counts = _summarize_descriptions([
            ("XC900",), ("XC90X",), ("XC90",),
        ])
        self.assertEqual(counts["anywhere_xc90_substring"], 3)
        self.assertEqual(counts["anywhere_xc90_token"], 1)
        self.assertEqual(counts["exact_xc90"], 1)

    def test_03_unknown_labels_not_reported(self):
        output = json.dumps(audit(self.folder))
        for forbidden in ("XC90", "XC900", "Volvo", "XC-90", "XC 90", "2003-", str(self.folder)):
            self.assertNotIn(forbidden, output)
        # No original Model/Profile ID values, VIN, or absolute source paths.
        self.assertFalse(audit(self.folder)["cross_database_profile_mapping_verified"])

    def test_04_ambiguous_two_model_tokens_not_selected(self):
        r = audit(self.folder)
        self.assertEqual(r["description_counts"]["prefix_xc90_token"], 2)
        self.assertFalse(r["model_identity_resolved"])

    def test_05_reject_missing_description_metadata(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute(
                'DELETE FROM "_vida_columns" WHERE "table_name"="VehicleModel" '
                'AND "column_name"="Description"'
            )
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_06_reject_wrong_export_database_identity(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute(
                'UPDATE "_vida_meta" SET "value"="wrong" WHERE "key"="source_database"'
            )
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_07_reject_export_sidecars(self):
        Path(str(self.source) + "-shm").write_text("unsafe")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_08_reject_unbounded_source_row_declaration(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute(
                'UPDATE "_vida_tables" SET "rows_exported"=10001 '
                'WHERE "table_name"="VehicleModel"'
            )
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_09_reject_oversized_description_in_memory(self):
        with self.assertRaises(SchemaError):
            _summarize_descriptions([("X" * 513,)])

    def test_10_cli_failure_is_redacted(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            result = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(result, 2)
        response = json.loads(stderr.getvalue())
        self.assertEqual(set(response), {"status", "error_class"})
        self.assertNotIn(str(self.folder), stderr.getvalue())

    def test_11_reject_missing_original_physical_description(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute('ALTER TABLE "dbo_VehicleModel" DROP COLUMN "Description"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_12_reject_non_string_description(self):
        with self.assertRaises(SchemaError):
            _summarize_descriptions([(1234,)])


if __name__ == "__main__":
    unittest.main()
