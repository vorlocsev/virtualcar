"""Synthetic-only eight gates for private VIDA CarCom aggregate relationship audit."""
from contextlib import closing, redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

SOURCE = (Path(__file__).resolve().parents[1] / "tools" /
          "audit_vida_carcom_aggregate_joins.py")
spec = importlib.util.spec_from_file_location("vida_carcom_aggregate", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SAMPLE = {
    "T111_Service": (
        ("id", "service", "mode", "fkT122_Protocol"),
        ((1, "GET", "R", 10), (2, "GET", "R", 20),
         (3, "GET", "R", 99), (4, "GET", "R", None)),
    ),
    "T122_Protocol": (
        ("id", "identifier"),
        ((10, "PRIVATE_TEST_D2"), (20, "PRIVATE_TEST_P3")),
    ),
    "T110_Service_EcuVariant": (
        ("fkT100_EcuVariant", "fkT111_Service"),
        ((100, 1), (100, 3), (101, 99), (999, 2), (None, 4)),
    ),
    "T100_EcuVariant": (
        ("id", "identifier", "fkT101_Ecu"),
        ((100, "PRIVATE_TEST_ECU_A", 1000), (101, "PRIVATE_TEST_ECU_B", 1001)),
    ),
    "T101_Ecu": (("id",), ((1000,), (1001,))),
    "T160_DefaultEcuVariant": (
        ("fkT161_Profile", "fkT100_EcuVariant"),
        ((2000, 100), (2000, 999), (None, 101)),
    ),
    "T161_Profile": (("id", "identifier"), ((2000, "PRIVATE_PROFILE_X"), (3000, "PRIVATE_PROFILE_Y"))),
}


class VidaAggregateJoinTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "CarCom.sqlite"
        with closing(sqlite3.connect(self.path)) as db:
            db.execute("CREATE TABLE _vida_meta (key TEXT, value TEXT)")
            db.execute(
                "CREATE TABLE _vida_tables (schema_name TEXT, table_name TEXT, rows_exported INTEGER)")
            db.execute(
                "CREATE TABLE _vida_columns (schema_name TEXT, table_name TEXT, column_name TEXT, system_type_id INTEGER)")
            for key, value in (
                ("schema_version", mod.EXPORT_SCHEMA),
                ("source_database", "CarCom"),
                ("scope", "all_user_tables"),
            ):
                db.execute("INSERT INTO _vida_meta VALUES (?,?)", (key, value))
            for table, (columns, values) in SAMPLE.items():
                name = "dbo__" + table
                ddl = ", ".join('"' + x + '" TEXT' for x in columns)
                db.execute('CREATE TABLE "' + name + '" (' + ddl + ')')
                args = ",".join("?" for _ in columns)
                db.executemany('INSERT INTO "' + name + '" VALUES (' + args + ')', values)
                db.execute("INSERT INTO _vida_tables VALUES (?,?,?)",
                           ("dbo", table, len(values)))
                db.executemany("INSERT INTO _vida_columns VALUES (?,?,?,?)",
                               (("dbo", table, column, 231) for column in columns))
            db.commit()

    def sql(self, statements):
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript(statements)
            db.commit()

    def test_01_six_edges_are_actual_offline_joins_not_vehicle_proof(self):
        data = mod.audit(self.root)
        self.assertEqual(data["status"], "offline_sqlite_aggregate_only")
        self.assertEqual(len(data["edges"]), 6)
        self.assertTrue(data["all_fixed_table_counts_match_export_catalog"])
        self.assertFalse(data["original_sql_server_fk_semantics_verified"])
        self.assertFalse(data["client_vin_accepted"])
        self.assertFalse(data["xc90_v8_my2009_profile_verified"])
        self.assertFalse(data["replay_approved"])
        self.assertTrue(all(row["join_executed_against_offline_export"]
                            for row in data["edges"]))

    def test_02_all_four_relationship_buckets_reconcile(self):
        edges = mod.audit(self.root)["edges"]
        self.assertEqual([(e["source_row_count"], e["null_source_fk_rows"],
                           e["missing_target_rows"], e["unique_match_rows"],
                           e["ambiguous_match_rows"]) for e in edges], [
            (4, 1, 1, 2, 0),
            (5, 0, 1, 4, 0),
            (5, 1, 1, 3, 0),
            (2, 0, 0, 2, 0),
            (3, 1, 0, 2, 0),
            (3, 0, 1, 2, 0),
        ])

    def test_03_duplicate_target_key_is_not_unique_match(self):
        self.sql('''
            INSERT INTO "dbo__T122_Protocol" VALUES ('10','ANOTHER_PRIVATE_TOKEN');
            UPDATE _vida_tables SET rows_exported=3
              WHERE table_name='T122_Protocol';
        ''')
        result = mod.audit(self.root)["edges"][0]
        self.assertEqual(result["source_row_count"], 4)
        self.assertEqual(result["unique_match_rows"], 1)
        self.assertEqual(result["ambiguous_match_rows"], 1)
        self.assertEqual(result["duplicate_target_key_groups"], 1)
        self.assertEqual(result["missing_target_rows"], 1)

    def test_04_unknown_names_and_original_values_not_emitted(self):
        self.sql('''
            ALTER TABLE "dbo__T111_Service"
              ADD COLUMN "TOP_PRIVATE_VIN_FIELD" TEXT;
            UPDATE "dbo__T111_Service"
              SET "TOP_PRIVATE_VIN_FIELD"='PRIVATE_VIN_ABC1234567890';
        ''')
        report = json.dumps(mod.audit(self.root))
        for token in ("TOP_PRIVATE_VIN_FIELD", "PRIVATE_VIN_ABC1234567890",
                      "PRIVATE_PROFILE_X", "PRIVATE_TEST_ECU_A",
                      "PRIVATE_TEST_D2"):
            self.assertNotIn(token, report)

    def test_05_metadata_row_count_mismatch_is_rejected(self):
        self.sql("UPDATE _vida_tables SET rows_exported=100 WHERE table_name='T111_Service'")
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)

    def test_06_ambiguous_physical_table_or_missing_catalog_column_rejected(self):
        self.sql('CREATE TABLE "dbo_T111_Service" AS SELECT * FROM "dbo__T111_Service"')
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)
        self.sql('DROP TABLE "dbo_T111_Service"')
        self.sql("DELETE FROM _vida_columns WHERE column_name='fkT122_Protocol'")
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)

    def test_07_wrong_export_source_or_unrecognized_physical_name_rejected(self):
        self.sql("UPDATE _vida_meta SET value='BaseData' WHERE key='source_database'")
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)
        self.sql("UPDATE _vida_meta SET value='CarCom' WHERE key='source_database'")
        self.sql('ALTER TABLE "dbo__T111_Service" RENAME TO "unexpected_private_table"')
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)

    def test_08_cli_new_redacted_output_without_source_changes(self):
        before = self.path.read_bytes()
        output = self.root / "new-redacted.json"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(["--folder", str(self.root),
                                       "--output", str(output)]), 0)
            self.assertEqual(mod.main(["--folder", str(self.root),
                                       "--output", str(output)]), 2)
            self.assertEqual(mod.main(["--folder", str(self.root),
                                       "--output", str(self.path)]), 2)
        self.assertEqual(before, self.path.read_bytes())
        report = output.read_text(encoding="utf-8")
        self.assertEqual(json.loads(report)["status"], "offline_sqlite_aggregate_only")
        self.assertNotIn("PRIVATE_TEST_D2", report)


if __name__ == "__main__":
    unittest.main()
