"""Synthetic privacy/negative tests; never open the owner's SQLite files."""
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
import json
import sqlite3
import tempfile
import unittest
import sys

# unittest discovery uses emulator/tests, but the production module is in tools.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from inspect_vida_profile_selection_schema import SchemaError, inspect, main


def make_export(folder: Path, name: str):
    path = folder / (name + ".sqlite")
    with sqlite3.connect(path) as db:
        for sql in (
            'CREATE TABLE "_vida_meta"("key" TEXT,"value" TEXT)',
            'CREATE TABLE "_vida_tables"("schema_name" TEXT,"table_name" TEXT,"rows_exported" INTEGER)',
            'CREATE TABLE "_vida_columns"("schema_name" TEXT,"table_name" TEXT,"column_name" TEXT)',
        ):
            db.execute(sql)
        db.executemany('INSERT INTO "_vida_meta" VALUES (?,?)', [
            ("schema_version", "virtualcar-vida-offline-sqlite-v1"),
            ("source_database", name),
            ("scope", "all_user_tables"),
        ])
        table = "T161_Profile" if name == "CarCom" else "VehicleProfile"
        db.execute('INSERT INTO "_vida_tables" VALUES (?,?,?)', ("dbo", table, 42))
        db.executemany('INSERT INTO "_vida_columns" VALUES (?,?,?)',
                       [("dbo", table, "id"), ("dbo", table, "identifier")])
    return path


class SchemaInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.carcom = make_export(self.folder, "CarCom")
        self.base = make_export(self.folder, "BaseData")

    def test_01_only_schema_and_negative_acceptance(self):
        result = inspect(self.folder)
        self.assertEqual(result["status"], "metadata_only")
        self.assertIs(result["source_rows_read"], False)
        self.assertIs(result["profile_join_or_selection_verified"], False)
        self.assertIs(result["readvin_accepted"], False)
        self.assertEqual(result["databases"]["CarCom"]["profile_related_tables"][0]["table"], "T161_Profile")

    def test_02_never_echo_source_profile_values(self):
        with sqlite3.connect(self.carcom) as db:
            db.execute('CREATE TABLE "secret_owner_source"("owner_vin" TEXT)')
            db.execute('INSERT INTO "secret_owner_source" VALUES ("PRIVATE-VIN-SENTINEL")')
        output = json.dumps(inspect(self.folder))
        self.assertNotIn("PRIVATE-VIN-SENTINEL", output)
        self.assertNotIn("owner_vin", output)
        self.assertNotIn("secret_owner_source", output)

    def test_03_reject_source_identity_mismatch(self):
        with sqlite3.connect(self.base) as db:
            db.execute('UPDATE "_vida_meta" SET "value"="Wrong" WHERE "key"="source_database"')
        with self.assertRaises(SchemaError):
            inspect(self.folder)

    def test_04_reject_duplicate_table_or_column(self):
        with sqlite3.connect(self.base) as db:
            db.execute('INSERT INTO "_vida_tables" VALUES ("dbo","VEHICLEPROFILE",0)')
        with self.assertRaises(SchemaError):
            inspect(self.folder)
        with sqlite3.connect(self.base) as db:
            db.execute('DELETE FROM "_vida_tables" WHERE "table_name"="VEHICLEPROFILE"')
            db.execute('INSERT INTO "_vida_columns" VALUES ("dbo","VehicleProfile","ID")')
        with self.assertRaises(SchemaError):
            inspect(self.folder)

    def test_05_reject_export_sidecars(self):
        Path(str(self.carcom) + "-wal").write_text("pending")
        with self.assertRaises(SchemaError):
            inspect(self.folder)

    def test_06_reject_source_views_instead_of_catalog_tables(self):
        with sqlite3.connect(self.carcom) as db:
            db.execute('DROP TABLE "_vida_columns"')
            db.execute('CREATE VIEW "_vida_columns" AS SELECT 1 AS "schema_name", 2 AS "table_name", 3 AS "column_name"')
        with self.assertRaises(SchemaError):
            inspect(self.folder)

    def test_07_bounded_candidate_table_output(self):
        with sqlite3.connect(self.base) as db:
            for i in range(40):
                name = "VehicleModel" + str(i)
                db.execute('INSERT INTO "_vida_tables" VALUES (?,?,?)', ("dbo", name, 0))
                db.execute('INSERT INTO "_vida_columns" VALUES (?,?,?)', ("dbo", name, "id"))
        result = inspect(self.folder)["databases"]["BaseData"]
        self.assertTrue(result["profile_related_tables_truncated"])
        self.assertEqual(len(result["profile_related_tables"]), 24)

    def test_08_cli_sanitized_error(self):
        stream = StringIO()
        with redirect_stderr(stream):
            code = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(code, 2)
        response = json.loads(stream.getvalue())
        self.assertEqual(set(response), {"status", "error_class"})
        self.assertNotIn(str(self.folder), stream.getvalue())


if __name__ == "__main__":
    unittest.main()
