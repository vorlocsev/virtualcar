"""Synthetic XC90 generic InitHw source classifications; no real VIDA reads."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import test_vida_basedata_carcom_43_direct_links as fixture
from audit_vida_basedata_xc90_general_inithw import SchemaError, audit, main


class Xc90GeneralInitHwTests(unittest.TestCase):
    def setUp(self):
        fixture.DirectLinksTests.setUp(self)
        with closing(sqlite3.connect(self.base)) as db, db:
            db.executemany(
                'INSERT INTO "dbo_VehicleProfile" VALUES (?,?,?,?)',
                [(2000, 10, 2009, None), (2001, 10, 2009, None)]
            )
            db.execute('UPDATE "_vida_tables" SET rows_exported=45 '
                       'WHERE table_name="VehicleProfile"')
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.executemany(
                'INSERT INTO "dbo_T161_Profile" VALUES (?,?,?,?,?)',
                [(500,100,200,100,"2000"), (501,100,200,100,"2001")]
            )
            db.execute('UPDATE "_vida_tables" SET rows_exported=45 '
                       'WHERE table_name="T161_Profile"')
            for table, cols in (
                ("T130_Init", ("id",)),
                ("T131_InitValue", ("fkT130_Init", "fkT132_InitValueType", "initValue")),
                ("T132_InitValueType", ("id", "name")),
            ):
                db.execute('CREATE TABLE "dbo_' + table + '" (' +
                           ','.join('"' + c + '" TEXT' if c in ("name", "initValue") else
                                    '"' + c + '" INTEGER' for c in cols) + ')')
                db.executemany('INSERT INTO "_vida_columns" VALUES (?,?,?)',
                               [("dbo", table, c) for c in cols])
            db.execute('INSERT INTO "dbo_T130_Init" VALUES (900)')
            db.executemany('INSERT INTO "dbo_T132_InitValueType" VALUES (?,?)',
                           [(1, "CANSpeed"), (2, "Delay")])
            db.executemany('INSERT INTO "dbo_T131_InitValue" VALUES (?,?,?)',
                           [(900, 1, "ignored-secret"), (900, 2, None),
                            (900, 1, "another-secret")])
            db.execute('INSERT INTO "dbo_T136_InitHw_Profile" VALUES (500,900)')
            for table in ("T130_Init", "T131_InitValue", "T132_InitValueType"):
                count = db.execute(
                    'SELECT COUNT(*) FROM "dbo_' + table + '"').fetchone()[0]
                db.execute('INSERT INTO "_vida_tables" VALUES (?,?,?)',
                           ("dbo", table, count))
            db.execute('UPDATE "_vida_tables" SET rows_exported=1 '
                       'WHERE table_name="T136_InitHw_Profile"')

    def _refresh(self, db, table):
        db.execute('UPDATE "_vida_tables" SET rows_exported=('
                   'SELECT COUNT(*) FROM "dbo_' + table +
                   '") WHERE table_name=?', (table,))

    def test_01_two_general_one_direct_link_three_values(self):
        r = audit(self.folder)
        self.assertEqual(r["gate"], "general_direct_inithw_counts_only")
        c = r["counts"]
        self.assertEqual(c["general_source_profile_count"], 2)
        self.assertEqual(c["general_carcom_unique_matches"], 2)
        self.assertEqual(c["general_carcom_missing"], 0)
        self.assertEqual(c["general_profiles_with_direct_inithw"], 1)
        self.assertEqual(c["general_profiles_without_direct_inithw"], 1)
        self.assertEqual(c["direct_inithw_link_rows"], 1)
        self.assertEqual(c["distinct_linked_init_rows"], 1)
        self.assertEqual(c["init_value_rows_on_distinct_linked_inits"], 3)
        self.assertEqual(c["init_value_nonnull_rows_on_distinct_linked_inits"], 2)
        self.assertEqual(c["init_type_name_baud_or_speed_lexical_rows"], 2)
        self.assertFalse(r["general_candidates_are_ancestor_profiles_verified"])
        self.assertFalse(r["d2_baudrate_verified"])

    def test_02_missing_general_carcom_id_only_counted(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T161_Profile" SET identifier="missing" '
                       'WHERE id=501')
        c = audit(self.folder)["counts"]
        self.assertEqual(c["general_carcom_missing"], 1)
        self.assertEqual(c["general_carcom_unique_matches"], 1)

    def test_03_duplicate_general_identifier_ambiguous(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T161_Profile" VALUES (999,100,200,100,"2000")')
            self._refresh(db, "T161_Profile")
        c = audit(self.folder)["counts"]
        self.assertEqual(c["general_carcom_ambiguous"], 1)
        self.assertEqual(c["general_carcom_unique_matches"], 1)
        self.assertEqual(c["general_profiles_with_direct_inithw"], 0)

    def test_04_null_link_not_reported_as_setting(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T136_InitHw_Profile" VALUES (501,NULL)')
            self._refresh(db, "T136_InitHw_Profile")
        c = audit(self.folder)["counts"]
        self.assertEqual(c["general_profiles_with_direct_inithw"], 2)
        self.assertEqual(c["direct_inithw_link_rows"], 2)
        self.assertEqual(c["direct_inithw_null_target_rows"], 1)
        self.assertEqual(c["distinct_linked_init_rows"], 1)

    def test_05_type_without_target_rejected(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T131_InitValue" SET fkT132_InitValueType=99')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_06_duplicate_init_id_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T130_Init" VALUES (900)')
            self._refresh(db, "T130_Init")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_07_oversized_generic_set_fails(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.executemany('INSERT INTO "dbo_VehicleProfile" VALUES (?,?,?,?)',
                           [(3000 + i, 10, 2009, None) for i in range(500)])
            self._refresh(db, "VehicleProfile")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_08_missing_init_type_catalog_column_fails(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('DELETE FROM "_vida_columns" WHERE table_name="T132_InitValueType" '
                       'AND column_name="name"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_09_no_source_values_ids_vin_or_paths_emitted(self):
        txt = json.dumps(audit(self.folder))
        for secret in ("ignored-secret", "another-secret", "CANSpeed",
                       "XC90 PERIOD ONE", "OriginalVINSecret", str(self.folder),
                       '"2000"', '"2001"'):
            self.assertNotIn(secret, txt)
        self.assertFalse(audit(self.folder)["original_profile_ids_names_settings_or_vin_exported"])

    def test_10_sidecars_fail_closed(self):
        Path(str(self.base) + "-wal").write_text("unsafe")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_11_original_43_equality_failure_stops(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T161_Profile" SET identifier="bad" WHERE id=1')
        r = audit(self.folder)
        self.assertEqual(r["gate"], "not_43_unique_carcom_identifiers")
        self.assertIsNone(r["counts"])

    def test_12_invalid_folder_sanitizes_error(self):
        out = StringIO()
        with redirect_stderr(out):
            status = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(status, 2)
        self.assertEqual(set(json.loads(out.getvalue())), {"status", "error_class"})
        self.assertNotIn(str(self.folder), out.getvalue())


if __name__ == "__main__":
    unittest.main()
