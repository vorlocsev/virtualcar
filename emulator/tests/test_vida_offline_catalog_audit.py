"""Synthetic-only offline VIDA SQLite catalog auditor tests (no owner databases)."""
from contextlib import closing, redirect_stdout, redirect_stderr
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

AUDIT_PATH = Path(__file__).resolve().parents[1] / "tools" / "audit_vida_offline_catalog.py"
spec = importlib.util.spec_from_file_location("vida_catalog_audit", AUDIT_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def synthetic_db(path, name):
    with closing(sqlite3.connect(path)) as db, db:
        db.executescript("""
            CREATE TABLE _vida_meta("key" TEXT, "value" TEXT);
            CREATE TABLE _vida_tables("schema_name" TEXT, "table_name" TEXT,
                                     "rows_exported" INTEGER);
            CREATE TABLE _vida_columns("schema_name" TEXT, "table_name" TEXT,
                                       "column_name" TEXT, "system_type_id" INTEGER);
            CREATE TABLE _vida_modules("module_name" TEXT, "definition" TEXT);
            CREATE TABLE _vida_foreign_keys("constraint_name" TEXT);
            CREATE TABLE _vida_indexes("index_name" TEXT);
        """)
        db.executemany("INSERT INTO _vida_meta VALUES (?,?)", [
            ("schema_version", "virtualcar-vida-offline-sqlite-v1"),
            ("source_database", name), ("scope", "all_user_tables")
        ])
        db.executemany("INSERT INTO _vida_tables VALUES (?,?,?)", [
            ("dbo", "Script", 5), ("dbo", "ScriptType", 1), ("dbo", "Vehicle", 2)
        ])
        db.executemany("INSERT INTO _vida_columns VALUES (?,?,?,?)", [
            ("dbo", "Script", "id", 56),
            ("dbo", "Script", "payload", 165),
            ("dbo", "ScriptType", "description", 231),
            ("dbo", "Vehicle", "vin", 167),
            ("dbo", "Vehicle", "SENSITIVE_HIDDEN_NAME", 167),
        ])
        db.executemany("INSERT INTO _vida_modules VALUES (?,?)", [
            ("GetScript", "ReadVin VehicleIdentity F114 SECRET_TEST_VIN_ABCDE"),
            ("Unknown", None),
        ])
        db.execute("INSERT INTO _vida_foreign_keys VALUES ('fk')")
        db.execute("INSERT INTO _vida_indexes VALUES ('pk')")


class OfflineVidaCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        for name in mod.DATABASES:
            synthetic_db(self.folder / (name + ".sqlite"), name)

    def test_all_nine_and_counts(self):
        result = mod.audit(self.folder)
        self.assertEqual(result["database_count"], 9)
        self.assertEqual(result["table_count"], 27)
        self.assertEqual(result["declared_row_count"], 72)
        self.assertTrue(result["read_only"])
        self.assertFalse(result["verified_hashes_in_this_audit"])

    def test_readvin_getscript_literal_hits_not_execution(self):
        result = mod.audit(self.folder)
        data = result["databases"]["DiagSwdlRepository"]
        self.assertEqual(data["literal_sql_module_hits"]["ReadVin"]["module_bodies"], 1)
        self.assertEqual(data["literal_sql_module_hits"]["GetScript"]["module_names"], 1)
        self.assertEqual(data["literal_sql_module_hits"]["F114"]["module_bodies"], 1)
        self.assertEqual(data["sql_definitions_unavailable"], 1)
        self.assertFalse(result["runtime_vehicle_identification_proven"])

    def test_script_role_hints_and_binary(self):
        data = mod.audit(self.folder)["databases"]["DiagSwdlRepository"]
        self.assertEqual(data["known_role_table_counts"]["Script"], 1)
        self.assertEqual(data["known_role_table_counts"]["ScriptType"], 1)
        self.assertEqual(data["known_role_column_hints"]["Script"], ["id", "payload"])
        self.assertEqual(data["binary_columns"], 1)

    def test_never_print_private_source_sql_or_unapproved_names(self):
        output = json.dumps(mod.audit(self.folder))
        for secret in ("SECRET_TEST_VIN_ABCDE", "SENSITIVE_HIDDEN_NAME",
                       "VehicleIdentity F114 SECRET", str(self.folder)):
            self.assertNotIn(secret, output)

    def test_missing_copy_fails_closed(self):
        (self.folder / "CarCom.sqlite").unlink()
        with self.assertRaises(mod.CatalogError):
            mod.audit(self.folder)

    def test_reject_mismatched_database_identity(self):
        with closing(sqlite3.connect(self.folder / "CarCom.sqlite")) as db, db:
            db.execute("UPDATE _vida_meta SET value='wrong' WHERE key='source_database'")
        with self.assertRaises(mod.CatalogError):
            mod.audit(self.folder)

    def test_reject_partial_export(self):
        with closing(sqlite3.connect(self.folder / "CarCom.sqlite")) as db, db:
            db.execute("UPDATE _vida_meta SET value='selected_tables' WHERE key='scope'")
        with self.assertRaises(mod.CatalogError):
            mod.audit(self.folder)

    def test_read_only_does_not_create_sidecars(self):
        before = set(self.folder.iterdir())
        mod.audit(self.folder)
        self.assertEqual(before, set(self.folder.iterdir()))

    def test_cli_sanitized_output_and_error(self):
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = mod.main(["--folder", str(self.folder)])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["database_count"], 9)
        self.assertEqual(stderr.getvalue(), "")
        (self.folder / "CarCom.sqlite").unlink()
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = mod.main(["--folder", str(self.folder)])
        self.assertEqual(code, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("error_class", stderr.getvalue())
        self.assertNotIn(str(self.folder), stderr.getvalue())

    def test_read_only_source_constraints(self):
        source = AUDIT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("SELECT *", source)
        self.assertNotIn("ATTACH DATABASE", source)
        self.assertIn("PRAGMA query_only=ON", source)
        self.assertIn("mode=ro&immutable=1", source)


if __name__ == "__main__":
    unittest.main()
