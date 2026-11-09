"""Synthetic owner-private, offline InitHw coverage classification gates."""
from contextlib import closing, redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
import audit_vida_inithw_profile_coverage as mod
from test_vida_carcom_inithw_aggregate import SAMPLE


class VidaProfileInitHwCoverageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.dbpath = self.root / "CarCom.sqlite"
        self.exact_path = self.root / "owner-exact-profiles.txt"
        self.general_path = self.root / "owner-general-profiles.txt"
        self.exact_names = ("PRIVATE_VIN_PROFILE_A",) + tuple(
            "PRIVATE_EXACT_CEM_PROFILE_%02d" % i for i in range(1, 43)
        )
        self.exact_path.write_text("\n".join(self.exact_names) + "\n", encoding="utf-8")
        self.general_path.write_text("PRIVATE_PROFILE_B\n", encoding="utf-8")
        with closing(sqlite3.connect(self.dbpath)) as db:
            db.execute('CREATE TABLE _vida_meta ("key" TEXT,"value" TEXT)')
            db.execute('CREATE TABLE _vida_tables ("schema_name" TEXT,"table_name" TEXT,"rows_exported" INTEGER)')
            db.execute('CREATE TABLE _vida_columns ("schema_name" TEXT,"table_name" TEXT,"column_name" TEXT,"system_type_id" INTEGER)')
            db.executemany('INSERT INTO _vida_meta VALUES (?,?)', (
                ("schema_version", mod.base.EXPORT_SCHEMA),
                ("source_database", "CarCom"),
                ("scope", "all_user_tables")))
            for table, (columns, rows) in SAMPLE.items():
                qname = '"dbo__' + table + '"'
                create = ", ".join('"' + name + '" TEXT' for name in columns)
                db.execute("CREATE TABLE " + qname + " (" + create + ")")
                db.executemany("INSERT INTO " + qname + " VALUES (" +
                               ",".join("?" for _ in columns) + ")", rows)
                db.execute("INSERT INTO _vida_tables VALUES (?,?,?)",
                           ("dbo", table, len(rows)))
                db.executemany('INSERT INTO _vida_columns VALUES (?,?,?,?)',
                               (("dbo", table, name, 231) for name in columns))
            db.executemany(
                'INSERT INTO "dbo__T161_Profile" VALUES (?,?,?)',
                ((100 + i, name, 1) for i, name in enumerate(self.exact_names[1:]))
            )
            db.execute("UPDATE _vida_tables SET rows_exported=44 WHERE table_name='T161_Profile'")
            db.commit()

    def sql(self, statements):
        with closing(sqlite3.connect(self.dbpath)) as db:
            db.executescript(statements)
            db.commit()

    def report(self):
        return mod.audit(self.root, self.exact_path, self.general_path)

    def test_01_exact_43_and_comparator_direct_counts(self):
        r = self.report()
        self.assertTrue(r["read_only"])
        self.assertFalse(r["original_profile_inheritance_priority_verified"])
        self.assertFalse(r["d2_baudrate_verified"])
        self.assertFalse(r["client_vin_accepted"])
        exact = r["exact_xc90_v8_my2009"]
        general = r["owner_selected_general_comparators"]
        self.assertEqual(exact["input_profile_count"], 43)
        self.assertEqual(exact["unique_matched_profile_count"], 43)
        self.assertEqual(exact["direct_init_profile_count"], 1)
        self.assertEqual(exact["no_direct_init_profile_count"], 42)
        self.assertEqual(exact["linked_init_value_rows"], 2)
        self.assertEqual(exact["linked_init_value_nonnull_rows"], 2)
        self.assertEqual(exact["baud_or_speed_lexical_type_rows"], 1)
        self.assertEqual(general["direct_init_profile_count"], 1)
        self.assertEqual(general["linked_init_value_rows"], 1)
        self.assertEqual(general["linked_init_value_nonnull_rows"], 0)

    def test_02_general_init_not_inherited_by_exact_43(self):
        self.sql("""DELETE FROM "dbo__T136_InitHw_Profile" WHERE fkT161_Profile='10';
                    UPDATE _vida_tables SET rows_exported=3
                    WHERE table_name='T136_InitHw_Profile';""")
        report = self.report()
        self.assertEqual(report["exact_xc90_v8_my2009"]["direct_init_profile_count"], 0)
        self.assertEqual(report["exact_xc90_v8_my2009"]["no_direct_init_profile_count"], 43)
        self.assertEqual(report["owner_selected_general_comparators"]["direct_init_profile_count"], 1)
        self.assertFalse(report["original_profile_inheritance_priority_verified"])

    def test_03_ambiguous_exact_profile_is_not_counted_as_selected(self):
        self.sql("""INSERT INTO "dbo__T161_Profile" VALUES (999, 'PRIVATE_VIN_PROFILE_A', 7);
                    UPDATE _vida_tables SET rows_exported=45
                    WHERE table_name='T161_Profile';""")
        report = self.report()["exact_xc90_v8_my2009"]
        self.assertEqual(report["ambiguous_profile_count"], 1)
        self.assertEqual(report["unique_matched_profile_count"], 42)
        self.assertEqual(report["direct_init_profile_count"], 0)
        self.assertEqual(report["no_direct_init_profile_count"], 42)

    def test_04_missing_exact_profile_does_not_guess_alias(self):
        self.sql("""DELETE FROM "dbo__T161_Profile" WHERE identifier='PRIVATE_VIN_PROFILE_A';
                    UPDATE _vida_tables SET rows_exported=43 WHERE table_name='T161_Profile';""")
        report = self.report()["exact_xc90_v8_my2009"]
        self.assertEqual(report["missing_profile_count"], 1)
        self.assertEqual(report["unique_matched_profile_count"], 42)
        self.assertEqual(report["direct_init_profile_count"], 0)

    def test_05_wrong_count_or_duplicate_input_fails_closed(self):
        self.exact_path.write_text("PRIVATE_VIN_PROFILE_A\n", encoding="utf-8")
        with self.assertRaises(mod.CoverageError):
            self.report()
        self.exact_path.write_text("\n".join(
            ("PRIVATE_VIN_PROFILE_A",) * 43) + "\n", encoding="utf-8")
        with self.assertRaises(mod.CoverageError):
            self.report()

    def test_06_overlap_and_invalid_input_rejected(self):
        self.general_path.write_text("PRIVATE_VIN_PROFILE_A\n", encoding="utf-8")
        with self.assertRaises(mod.CoverageError):
            self.report()
        self.general_path.write_text(" PRIVATE_PROFILE_B\n", encoding="utf-8")
        with self.assertRaises(mod.CoverageError):
            self.report()

    def test_07_private_identifiers_setting_names_and_baud_values_redacted(self):
        r = json.dumps(self.report())
        for private in ("PRIVATE_VIN_PROFILE_A", "PRIVATE_PROFILE_B",
                        "PRIVATE_BAUD_TYPE", "PRIVATE_VIN_SECRET",
                        "125000_PRIVATE", "500000_PRIVATE",
                        "PRIVATE_EXACT_CEM_PROFILE_"):
            self.assertNotIn(private, r)
        self.assertNotIn('"folderLevel": 7', r)

    def test_08_multiple_and_duplicate_direct_links_reported_without_ids(self):
        self.sql("""INSERT INTO "dbo__T136_InitHw_Profile" VALUES ('10','40');
                    INSERT INTO "dbo__T136_InitHw_Profile" VALUES ('10','30');
                    UPDATE _vida_tables SET rows_exported=6
                    WHERE table_name='T136_InitHw_Profile';""")
        result = self.report()["exact_xc90_v8_my2009"]
        self.assertEqual(result["direct_init_link_rows"], 3)
        self.assertEqual(result["duplicate_direct_init_link_rows"], 1)
        self.assertEqual(result["multiple_direct_init_profile_count"], 1)
        self.assertEqual(result["distinct_linked_init_count"], 2)
        self.assertEqual(result["linked_init_value_rows"], 3)

    def test_09_sql_injection_like_profile_is_bound_as_data(self):
        values = list(self.exact_names)
        values[0] = "' OR 1=1 --"
        self.exact_path.write_text("\n".join(values) + "\n", encoding="utf-8")
        report = self.report()["exact_xc90_v8_my2009"]
        self.assertEqual(report["missing_profile_count"], 1)
        self.assertEqual(report["unique_matched_profile_count"], 42)
        self.assertEqual(report["direct_init_profile_count"], 0)

    def test_10_cli_exclusive_output_and_unchanged_source(self):
        output = self.root / "profile-coverage.redacted.json"
        before = self.dbpath.read_bytes()
        args = ["--folder", str(self.root), "--exact-profiles", str(self.exact_path),
                "--general-profiles", str(self.general_path), "--output", str(output)]
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(mod.main(args), 0)
            self.assertEqual(mod.main(args), 2)
        self.assertEqual(self.dbpath.read_bytes(), before)
        doc = output.read_text(encoding="utf-8")
        self.assertEqual(json.loads(doc)["status"], "owner_selected_profile_direct_coverage_only")
        self.assertNotIn("PRIVATE_VIN", doc)

    def test_11_identity_or_catalog_row_mismatch_rejected(self):
        self.sql("UPDATE _vida_meta SET value='BaseData' WHERE key='source_database';")
        with self.assertRaises(mod.base.AuditError):
            self.report()
        self.sql("UPDATE _vida_meta SET value='CarCom' WHERE key='source_database';")
        self.sql("UPDATE _vida_tables SET rows_exported=99 WHERE table_name='T161_Profile';")
        with self.assertRaises(mod.base.AuditError):
            self.report()


if __name__ == "__main__":
    unittest.main()
