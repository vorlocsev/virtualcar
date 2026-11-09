"""Synthetic tests: real SQLite join counts but no original VIDA files."""
from contextlib import closing, redirect_stderr, redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_vida_carcom_inithw_aggregate.py"
spec = importlib.util.spec_from_file_location("vida_carcom_inithw_aggregate", SOURCE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

SAMPLE = {
    "T136_InitHw_Profile": (
        ("fkT161_Profile", "fkT130_Init"),
        ((10, 30), (20, 40), (999, 30), (None, 30)),
    ),
    "T161_Profile": (
        ("id", "identifier", "folderLevel"),
        ((10, "PRIVATE_VIN_PROFILE_A", 2), (20, "PRIVATE_PROFILE_B", None)),
    ),
    "T130_Init": (("id",), ((30,), (40,))),
    "T131_InitValue": (
        ("fkT130_Init", "fkT132_InitValueType", "initValue", "sortOrder"),
        ((30, 50, "125000_PRIVATE", 1), (40, 60, None, 2),
         (30, 99, "PRIVATE_VIN_SECRET", 3), (None, 50, "500000_PRIVATE", 4)),
    ),
    "T132_InitValueType": (
        ("id", "name"), ((50, "PRIVATE_BAUD_TYPE"), (60, None)),
    ),
    "T121_Config": (
        ("id", "busRate", "fkT122_Protocol", "fkT123_Bus"),
        ((70, None, 80, 90), (71, 500000, 81, 90),
         (72, None, 999, 90), (73, None, None, 999)),
    ),
    "T122_Protocol": (("id", "identifier"), ((80, "PRIVATE_D2"), (81, "PRIVATE_GGD"))),
    "T123_Bus": (("id", "identifier"), ((90, "PRIVATE_CAN"),)),
}


class VidaInitHwAggregateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "CarCom.sqlite"
        with closing(sqlite3.connect(self.path)) as db:
            db.execute('CREATE TABLE _vida_meta ("key" TEXT,"value" TEXT)')
            db.execute('CREATE TABLE _vida_tables ("schema_name" TEXT,"table_name" TEXT,"rows_exported" INTEGER)')
            db.execute('CREATE TABLE _vida_columns ("schema_name" TEXT,"table_name" TEXT,"column_name" TEXT,"system_type_id" INTEGER)')
            db.executemany('INSERT INTO _vida_meta VALUES (?,?)', (
                ("schema_version", mod.EXPORT_SCHEMA), ("source_database", "CarCom"),
                ("scope", "all_user_tables")))
            for table, (cols, rows) in SAMPLE.items():
                if not all(isinstance(row, tuple) and len(row) == len(cols) for row in rows):
                    raise AssertionError("synthetic fixture has non-row parameters")
                physical = "dbo__" + table
                decl = ", ".join('"' + col + '" TEXT' for col in cols)
                db.execute('CREATE TABLE "' + physical + '" (' + decl + ')')
                db.executemany('INSERT INTO "' + physical + '" VALUES (' + ",".join("?" for _ in cols) + ')', rows)
                db.execute('INSERT INTO _vida_tables VALUES (?,?,?)', ("dbo", table, len(rows)))
                db.executemany('INSERT INTO _vida_columns VALUES (?,?,?,?)',
                               (("dbo", table, col, 231) for col in cols))
            db.commit()

    def sql(self, statements):
        with closing(sqlite3.connect(self.path)) as db:
            db.executescript(statements)
            db.commit()

    def test_01_six_actual_aggregate_edges_but_no_selected_profile(self):
        report = mod.audit(self.root)
        self.assertEqual(report["schema_version"], "virtualcar-vida-inithw-aggregate-joins-v1")
        self.assertEqual(len(report["edges"]), 6)
        self.assertTrue(all(e["join_executed_against_offline_export"] for e in report["edges"]))
        self.assertFalse(report["hardware_init_profile_priority_verified"])
        self.assertFalse(report["d2_baudrate_verified"])
        self.assertFalse(report["selected_xc90_v8_my2009_profile_verified"])
        self.assertFalse(report["may_infer_d2_rate_from_ggd"])
        self.assertFalse(report["replay_approved"])

    def test_02_fk_buckets_match_null_missing_unique_counts(self):
        edges = mod.audit(self.root)["edges"]
        actual = [(e["source_row_count"], e["null_source_fk_rows"],
                   e["missing_target_rows"], e["unique_match_rows"],
                   e["ambiguous_match_rows"]) for e in edges]
        self.assertEqual(actual, [
            (4, 1, 1, 2, 0),
            (4, 0, 0, 4, 0),
            (4, 1, 0, 3, 0),
            (4, 0, 1, 3, 0),
            (4, 1, 1, 2, 0),
            (4, 0, 1, 3, 0),
        ])

    def test_03_aggregate_only_null_presence_never_values(self):
        values = mod.audit(self.root)["value_presence"]
        self.assertEqual([(x["table"], x["column"], x["total_rows"],
                           x["null_rows"], x["non_null_rows"]) for x in values], [
            ("T161_Profile", "folderLevel", 2, 1, 1),
            ("T131_InitValue", "initValue", 4, 1, 3),
            ("T132_InitValueType", "name", 2, 1, 1),
            ("T121_Config", "busRate", 4, 3, 1),
        ])
        self.assertTrue(all(not x["values_disclosed"] for x in values))

    def test_04_duplicate_target_id_must_be_ambiguous_not_unique(self):
        self.sql("""
            INSERT INTO "dbo__T130_Init" VALUES ('30');
            UPDATE _vida_tables SET rows_exported=3 WHERE table_name='T130_Init';
        """)
        edges = mod.audit(self.root)["edges"]
        self.assertEqual(edges[1]["ambiguous_match_rows"], 3)
        self.assertEqual(edges[1]["unique_match_rows"], 1)
        self.assertEqual(edges[1]["duplicate_target_key_groups"], 1)
        self.assertEqual(edges[2]["ambiguous_match_rows"], 2)

    def test_05_private_values_and_unknown_schema_names_never_emitted(self):
        self.sql("""
            ALTER TABLE "dbo__T131_InitValue" ADD COLUMN "VIN_SECRET_SOURCE" TEXT;
            UPDATE "dbo__T131_InitValue" SET "VIN_SECRET_SOURCE"='PRIVATE_UID_123';
        """)
        result = json.dumps(mod.audit(self.root))
        for token in ("VIN_SECRET_SOURCE", "PRIVATE_UID_123", "PRIVATE_BAUD_TYPE",
                      "PRIVATE_VIN_PROFILE_A", "PRIVATE_D2", "125000_PRIVATE",
                      "500000_PRIVATE"):
            self.assertNotIn(token, result)

    def test_06_declared_row_count_mismatch_fails_closed(self):
        self.sql("UPDATE _vida_tables SET rows_exported=999 WHERE table_name='T121_Config'")
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)

    def test_07_ambiguous_physical_names_and_missing_required_column_fail(self):
        self.sql('CREATE TABLE "dbo_T136_InitHw_Profile" AS SELECT * FROM "dbo__T136_InitHw_Profile"')
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)
        self.sql('DROP TABLE "dbo_T136_InitHw_Profile"')
        self.sql("DELETE FROM _vida_columns WHERE column_name='folderLevel'")
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)

    def test_08_wrong_export_identity_and_missing_physical_table_fail(self):
        self.sql("UPDATE _vida_meta SET value='BaseData' WHERE key='source_database'")
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)
        self.sql("UPDATE _vida_meta SET value='CarCom' WHERE key='source_database'")
        self.sql('ALTER TABLE "dbo__T132_InitValueType" RENAME TO "unexpected_raw_table"')
        with self.assertRaises(mod.AuditError):
            mod.audit(self.root)

    def test_09_output_exclusive_and_sqlite_file_unchanged_on_windows(self):
        out = self.root / "inithw-aggregate-redacted.json"
        before = self.path.read_bytes()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(["--folder", str(self.root), "--output", str(out)]), 0)
            self.assertEqual(mod.main(["--folder", str(self.root), "--output", str(out)]), 2)
            self.assertEqual(mod.main(["--folder", str(self.root), "--output", str(self.path)]), 2)
        self.assertEqual(self.path.read_bytes(), before)
        content = out.read_text(encoding="utf-8")
        self.assertEqual(json.loads(content)["status"], "offline_sqlite_aggregate_only")
        self.assertNotIn("PRIVATE_D2", content)
        self.assertNotIn("500000_PRIVATE", content)

    def test_10_non_null_baud_does_not_verify_d2_speed(self):
        self.sql("UPDATE \"dbo__T121_Config\" SET \"busRate\"=500000")
        result = mod.audit(self.root)
        self.assertEqual(result["value_presence"][3]["non_null_rows"], 4)
        self.assertFalse(result["d2_baudrate_verified"])
        self.assertFalse(result["may_infer_d2_rate_from_ggd"])


if __name__ == "__main__":
    unittest.main()
