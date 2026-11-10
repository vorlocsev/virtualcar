"""Synthetic, offline tests for VIDA unified metadata-only SQL/SQLite analyzer."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
SPEC = importlib.util.spec_from_file_location("vida_unified_analyzer", TOOLS / "vida_unified_analyzer.py")
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class FakeCursor:
    def __init__(self, dbname, queries):
        self.dbname = dbname
        self.queries = queries
        self.current = []

    def execute(self, sql):
        self.queries.append(sql)
        self._assert_metadata_only(sql)
        names = mod.TABLES[self.dbname]
        if "FROM sys.foreign_key_columns" in sql:
            self.current = ([("dbo", "T111_Service", "fkT122_Protocol",
                              "dbo", "T122_Protocol", "id", 0, 1),
                             ("dbo", "SECRET_USER", "secret_ref",
                              "dbo", "T122_Protocol", "id", 0, 0)]
                            if self.dbname == "CarCom" else [])
        elif "FROM sys.columns" in sql:
            self.current = [
                ("dbo", t, c) for t, cols in names.items() for c in cols
            ] + [("dbo", "SECRET_USER", "SECRET_VIN_1234567890")]
        elif "FROM sys.tables" in sql:
            self.current = [("dbo", t) for t in names] + [("dbo", "SECRET_USER")]
        else:
            raise AssertionError("unexpected SQL")
        return self

    @staticmethod
    def _assert_metadata_only(sql):
        assert "sys." in sql
        for forbidden in (" SELECT * FROM dbo", " OPENROWSET", " EXEC ", "FROM CarCom",
                          "ScriptContent", "PRIVATE_VIN_PAYLOAD"):
            assert forbidden not in sql

    def fetchmany(self, amount):
        return self.current[:amount]


class FakeConnection:
    def __init__(self, database, queries):
        self.database = database
        self.queries = queries
        self.closed = False

    def cursor(self):
        return FakeCursor(self.database, self.queries)

    def close(self):
        self.closed = True


class UnifiedVidaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        for database in mod.TABLES:
            self.build(database)

    def build(self, database, override=None):
        file = self.folder / (database + ".sqlite")
        if file.exists():
            file.unlink()
        with contextlib.closing(sqlite3.connect(file)) as db:
            db.executescript("""
                CREATE TABLE _vida_meta ("key" TEXT, "value" TEXT);
                CREATE TABLE _vida_tables
                  ("schema_name" TEXT, "table_name" TEXT, "rows_exported" INTEGER);
                CREATE TABLE _vida_columns
                  ("schema_name" TEXT, "table_name" TEXT, "column_name" TEXT,
                   "system_type_id" INTEGER);
                CREATE TABLE SECRET_PAYLOAD (secret TEXT);
                INSERT INTO SECRET_PAYLOAD VALUES ('MY_PRIVATE_VIN_123456789');
            """)
            for key, value in (
                ("schema_version", mod.EXPORT_SCHEMA),
                ("source_database", database),
                ("scope", "all_user_tables"),
            ):
                db.execute("INSERT INTO _vida_meta VALUES (?,?)", (key, value))
            for table, columns in mod.TABLES[database].items():
                db.execute("INSERT INTO _vida_tables VALUES (?,?,?)",
                           ("dbo", table, 3))
                for column in columns:
                    db.execute("INSERT INTO _vida_columns VALUES (?,?,?,?)",
                               ("dbo", table, column, 56))
            # Arbitrary original source names may be in the metadata but are
            # never emitted. No source user-table SELECTs are performed.
            db.execute("INSERT INTO _vida_tables VALUES (?,?,?)",
                       ("dbo", "PRIVATE_CUSTOMER_XYZ", 1))
            db.execute("INSERT INTO _vida_columns VALUES (?,?,?,?)",
                       ("dbo", "PRIVATE_CUSTOMER_XYZ", "PRIVATE_VIN_KEY", 165))
            if override:
                override(db)
            db.commit()

    def test_01_sqlite_discovers_known_graph_without_private_names(self):
        report = mod.render(mod.load_sqlite_export(self.folder), "sqlite-export")
        self.assertEqual(report["status"], "metadata_only")
        self.assertEqual(len(report["edges"]), 12)
        self.assertTrue(all(edge["column_shape_present"] for edge in report["edges"]))
        self.assertFalse(report["client_vin_accepted"])
        self.assertFalse(report["replay_approved"])
        self.assertFalse(report["record_joins_verified"])
        self.assertEqual(report["databases"]["CarCom"]["declared_fk_column_count"], 0)
        blob = json.dumps(report)
        for secret in ("PRIVATE_CUSTOMER", "PRIVATE_VIN", "MY_PRIVATE", "SECRET_PAYLOAD"):
            self.assertNotIn(secret, blob)

    def test_02_missing_table_marks_shape_missing_not_verified(self):
        def erase(db):
            db.execute("DELETE FROM _vida_tables WHERE table_name='T122_Protocol'")
            db.execute("DELETE FROM _vida_columns WHERE table_name='T122_Protocol'")
        self.build("CarCom", override=erase)
        report = mod.render(mod.load_sqlite_export(self.folder), "sqlite-export")
        self.assertFalse(report["edges"][0]["column_shape_present"])
        self.assertFalse(report["databases"]["CarCom"]["known_tables"]
                         ["T122_Protocol"]["present"])

    def test_03_missing_exporter_column_rejected_before_select(self):
        def corrupt(db):
            db.execute('ALTER TABLE _vida_tables RENAME TO _old')
            db.execute('CREATE TABLE _vida_tables AS '
                       'SELECT table_name, rows_exported FROM _old')
            db.execute('DROP TABLE _old')
        self.build("CarCom", override=corrupt)
        with self.assertRaises(mod.AnalyzerError):
            mod.load_sqlite_export(self.folder)

    def test_04_wrong_export_identity_rejected(self):
        self.build("CarCom", override=lambda db: db.execute(
            "UPDATE _vida_meta SET value='BadDatabase' WHERE key='source_database'"))
        with self.assertRaises(mod.AnalyzerError):
            mod.load_sqlite_export(self.folder)

    def test_05_ambiguous_known_table_rejected(self):
        def duplicate(db):
            db.execute("INSERT INTO _vida_tables VALUES (?,?,?)",
                       ("another", "T111_Service", 0))
        self.build("CarCom", override=duplicate)
        with self.assertRaises(mod.AnalyzerError):
            mod.render(mod.load_sqlite_export(self.folder), "sqlite-export")

    def test_06_orphaned_and_duplicate_columns_fail_closed(self):
        self.build("CarCom", override=lambda db: db.execute(
            "INSERT INTO _vida_columns VALUES (?,?,?,?)",
            ("dbo", "UNKNOWN_MISSING_TABLE", "col", 56)))
        with self.assertRaises(mod.AnalyzerError):
            mod.load_sqlite_export(self.folder)
        self.build("CarCom", override=lambda db: db.execute(
            "INSERT INTO _vida_columns VALUES (?,?,?,?)",
            ("dbo", "T111_Service", "ID", 56)))
        with self.assertRaises(mod.AnalyzerError):
            mod.load_sqlite_export(self.folder)

    def test_07_sql_server_dsn_rejects_connection_string_injection(self):
        for malicious in ("", "foo;PWD=secret", "{db}", "dsn name", "a"*129):
            with self.subTest(malicious=malicious[:10]):
                with self.assertRaises(mod.AnalyzerError):
                    mod.load_sqlserver(malicious, connector=lambda *_a, **_k: None)

    def test_08_sql_server_declared_fk_is_not_a_join_proof(self):
        queries, connections = [], []
        def connect(string, autocommit, timeout):
            self.assertIn("Trusted_Connection=Yes", string)
            self.assertIn("Encrypt=Yes", string)
            self.assertIn("TrustServerCertificate=No", string)
            self.assertTrue(autocommit)
            self.assertEqual(timeout, 8)
            dbname = string.split("DATABASE=")[1].split(";")[0]
            self.assertIn(dbname, mod.TABLES)
            conn = FakeConnection(dbname, queries)
            connections.append(conn)
            return conn
        report = mod.render(mod.load_sqlserver("VIDA_LOCAL", connect), "sqlserver")
        declared = [e for e in report["edges"] if e["evidence"] == "sqlserver_declared_fk"]
        self.assertEqual(len(declared), 1)
        self.assertEqual(declared[0]["source"], "T111_Service")
        self.assertTrue(declared[0]["fk_untrusted"])
        self.assertFalse(declared[0]["referential_rows_verified"])
        self.assertFalse(report["record_joins_verified"])
        self.assertNotIn("SECRET_USER", json.dumps(report))
        self.assertEqual(len(connections), 3)
        self.assertTrue(all(c.closed for c in connections))
        self.assertEqual(len(queries), 9)

    def test_09_sql_errors_do_not_leak_dsn_or_credentials(self):
        def fail(*_a, **_kw):
            raise RuntimeError("SECRET_CONNECTION_KEY=PRIVATE")
        with self.assertRaisesRegex(mod.AnalyzerError, "metadata read failed") as cm:
            mod.load_sqlserver("goodDSN", fail)
        self.assertNotIn("SECRET_CONNECTION", str(cm.exception))

    def test_10_cli_writes_once_without_source_data(self):
        output = self.folder / "redacted.json"
        before = (self.folder / "CarCom.sqlite").read_bytes()
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(["--backend", "sqlite-export", "--folder",
                                       str(self.folder), "--output", str(output)]), 0)
            self.assertEqual(mod.main(["--backend", "sqlite-export", "--folder",
                                       str(self.folder), "--output", str(output)]), 2)
        body = output.read_text(encoding="utf-8")
        self.assertNotIn("MY_PRIVATE", body)
        self.assertNotIn("PRIVATE_CUSTOMER", body)
        self.assertEqual((self.folder / "CarCom.sqlite").read_bytes(), before)

    def test_11_missing_export_and_symlink_rejected(self):
        (self.folder / "BaseData.sqlite").unlink()
        with self.assertRaises(mod.AnalyzerError):
            mod.load_sqlite_export(self.folder)
        self.build("BaseData")
        original = self.folder / "BaseData.sqlite"
        redirect = self.folder / "redirect.sqlite"
        original.rename(redirect)
        try:
            original.symlink_to(redirect)
        except OSError:
            self.skipTest("Symlinks unavailable without Windows privilege")
        with self.assertRaises(mod.AnalyzerError):
            mod.load_sqlite_export(self.folder)


if __name__ == "__main__":
    unittest.main()
