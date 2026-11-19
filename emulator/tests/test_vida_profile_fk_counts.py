"""Synthetic, count-only profile FK tests. Never access owner-private data."""
from contextlib import closing, redirect_stderr
from io import StringIO
from pathlib import Path
import json
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_profile_fk_counts import SchemaError, audit, main, NEEDED


def make_database(folder: Path, database_name: str):
    path = folder / (database_name + ".sqlite")
    specs = NEEDED[database_name]
    with closing(sqlite3.connect(path)) as db, db:
        db.execute('CREATE TABLE "_vida_meta"("key" TEXT,"value" TEXT)')
        db.execute('CREATE TABLE "_vida_tables"("schema_name" TEXT,"table_name" TEXT,"rows_exported" INTEGER)')
        db.execute('CREATE TABLE "_vida_columns"("schema_name" TEXT,"table_name" TEXT,"column_name" TEXT)')
        db.executemany('INSERT INTO "_vida_meta" VALUES (?,?)', [
            ("schema_version", "virtualcar-vida-offline-sqlite-v1"),
            ("source_database", database_name),
            ("scope", "all_user_tables"),
        ])
        for table, cols in specs.items():
            column_sql = ','.join('"' + col + '" INTEGER' for col in cols)
            db.execute('CREATE TABLE "dbo_' + table + '" (' + column_sql + ')')
            db.executemany('INSERT INTO "_vida_columns" VALUES (?,?,?)',
                           [("dbo", table, col) for col in cols])
        if database_name == "BaseData":
            db.executemany('INSERT INTO "dbo_VehicleModel" VALUES (?)', [(10,), (20,)])
            db.executemany('INSERT INTO "dbo_ModelYear" VALUES (?)', [(2009,)])
            db.executemany('INSERT INTO "dbo_Engine" VALUES (?)', [(80,)])
            db.executemany('INSERT INTO "dbo_VehicleProfile" VALUES (?,?,?,?)',
                           [(1, 10, 2009, 80), (2, 20, 2009, 80), (3, None, 2009, 80)])
        else:
            db.executemany('INSERT INTO "dbo_T162_ProfileValue" VALUES (?)',
                           [(100,), (200,)])
            db.executemany('INSERT INTO "dbo_T161_Profile" VALUES (?,?,?,?)',
                           [(1, 100, 200, 100), (2, 200, 200, 100), (3, None, 200, 100)])
        for table in specs:
            rows = db.execute('SELECT COUNT(*) FROM "dbo_' + table + '"').fetchone()[0]
            db.execute('INSERT INTO "_vida_tables" VALUES (?,?,?)', ("dbo", table, rows))
    return path


class ProfileFkCountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.base = make_database(self.folder, "BaseData")
        self.carcom = make_database(self.folder, "CarCom")

    def test_01_six_scoped_edges_and_explicit_unverified_flags(self):
        report = audit(self.folder)
        self.assertEqual(report["status"], "offline_sqlite_aggregate_only")
        self.assertFalse(report["cross_database_profile_mapping_verified"])
        self.assertFalse(report["original_selection_of_43_reconstructed"])
        self.assertFalse(report["runtime_vida_readvin_accepted"])
        self.assertEqual([len(x["candidate_fk_edges"]) for x in report["databases"].values()], [3, 3])
        for db in report["databases"].values():
            self.assertEqual(db["profile_table_rows"], 3)
            for edge in db["candidate_fk_edges"]:
                self.assertEqual(edge["source_rows"], 3)
                self.assertEqual(edge["missing_target_rows"], 0)
                self.assertEqual(edge["ambiguous_target_rows"], 0)

    def test_02_no_keys_values_or_private_strings_in_output(self):
        text = json.dumps(audit(self.folder))
        self.assertNotIn("B8444S", text)
        self.assertNotIn("XC90", text)
        self.assertNotIn('"identifier":', text)
        self.assertNotIn(str(self.folder), text)

    def test_03_missing_target_is_only_a_count(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T161_Profile" SET "fkT162_ProfileValue_Model"=999 WHERE id=1')
        row = audit(self.folder)["databases"]["CarCom"]["candidate_fk_edges"][0]
        self.assertEqual(row["missing_target_rows"], 1)
        self.assertEqual(row["unique_target_rows"], 1)
        self.assertFalse(row["all_source_keys_unambiguous"])

    def test_04_duplicate_target_key_is_ambiguous(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T162_ProfileValue" VALUES (100)')
            db.execute('UPDATE "_vida_tables" SET "rows_exported"=3 WHERE "table_name"="T162_ProfileValue"')
        row = audit(self.folder)["databases"]["CarCom"]["candidate_fk_edges"][0]
        self.assertEqual(row["ambiguous_target_rows"], 1)
        self.assertFalse(row["all_source_keys_unambiguous"])

    def test_05_catalog_count_mismatch_fails_closed(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "_vida_tables" SET "rows_exported"=4 WHERE "table_name"="VehicleProfile"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_06_bad_source_database_identity_fails(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('UPDATE "_vida_meta" SET "value"="wrong" WHERE "key"="source_database"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_07_sidecars_fail_closed(self):
        Path(str(self.carcom) + "-wal").write_text("pending")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_08_missing_required_physical_column_fails(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('ALTER TABLE "dbo_VehicleProfile" DROP COLUMN "fkEngine"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_09_virtual_or_view_replacement_fails(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('DROP TABLE "dbo_Engine"')
            db.execute('CREATE VIEW "dbo_Engine" AS SELECT 80 AS Id')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_10_cli_failure_has_no_paths(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            code = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(code, 2)
        result = json.loads(stderr.getvalue())
        self.assertEqual(set(result), {"status", "error_class"})
        self.assertNotIn(str(self.folder), stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
