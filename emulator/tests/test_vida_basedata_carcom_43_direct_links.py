"""Synthetic owner-data-free CarCom 43-profile direct link classification tests."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from audit_vida_basedata_carcom_43_direct_links import (
    CARCOM_REQUIRED, SchemaError, audit, main,
)
from test_vida_basedata_carcom_43_equality import BaseDataCarCom43Tests


class DirectLinksTests(unittest.TestCase):
    def setUp(self):
        # Only synthetic 43-profile fixture, no original private SQLITE.
        BaseDataCarCom43Tests.setUp(self)
        with closing(sqlite3.connect(self.carcom)) as db, db:
            for table in ("T160_DefaultEcuVariant", "T100_EcuVariant",
                          "T101_Ecu", "T136_InitHw_Profile"):
                cols = CARCOM_REQUIRED[table]
                db.execute(
                    'CREATE TABLE "dbo_' + table + '" (' +
                    ','.join('"' + x + '" INTEGER' if x != "identifier"
                             else '"identifier" TEXT' for x in cols) + ')'
                )
                db.executemany('INSERT INTO "_vida_columns" VALUES (?,?,?)',
                               [("dbo", table, col) for col in cols])
            db.executemany('INSERT INTO "dbo_T101_Ecu" VALUES (?,?)', [
                (1, "CEM"), (2, "ECM"), (3, "DIM"),
            ])
            db.executemany('INSERT INTO "dbo_T100_EcuVariant" VALUES (?,?)', [
                (variant, 1 if variant in (100, 105) else
                 (2 if variant == 101 else 3))
                for variant in range(100, 109)
            ])
            db.executemany('INSERT INTO "dbo_T160_DefaultEcuVariant" VALUES (?,?)', [
                (1 if variant <= 104 else 2, variant)
                for variant in range(100, 109)
            ])
            for table in ("T160_DefaultEcuVariant", "T100_EcuVariant",
                          "T101_Ecu", "T136_InitHw_Profile"):
                count = db.execute(
                    'SELECT COUNT(*) FROM "dbo_' + table + '"'
                ).fetchone()[0]
                db.execute('INSERT INTO "_vida_tables" VALUES (?,?,?)',
                           ("dbo", table, count))

    def _change_count(self, db, table: str):
        db.execute('UPDATE "_vida_tables" SET "rows_exported"=('
                   'SELECT COUNT(*) FROM "dbo_' + table +
                   '") WHERE "table_name"=?', (table,))

    def test_01_43_matches_nine_defaults_two_profiles_zero_direct_inithw(self):
        r = audit(self.folder)
        self.assertEqual(r["gate"], "all_43_direct_links_counted")
        counts = r["counts"]
        self.assertEqual(counts["matched_exact_profile_count"], 43)
        self.assertEqual(counts["profiles_with_direct_defaults"], 2)
        self.assertEqual(counts["profiles_without_direct_defaults"], 41)
        self.assertEqual(counts["direct_default_link_rows"], 9)
        self.assertEqual(counts["direct_default_cem_rows"], 2)
        self.assertEqual(counts["direct_default_ecm_rows"], 1)
        self.assertEqual(counts["direct_default_other_ecu_rows"], 6)
        self.assertEqual(counts["profiles_with_direct_inithw"], 0)
        self.assertEqual(counts["profiles_without_direct_inithw"], 43)
        self.assertEqual(counts["direct_inithw_link_rows"], 0)
        self.assertFalse(r["same_as_previous_43_source_set_verified"])
        self.assertFalse(r["effective_inithw_inheritance_verified"])
        self.assertFalse(r["client_ecu_alive_verified"])
        self.assertFalse(r["original_vida_readvin_accepted"])

    def test_02_one_direct_inithw_link_is_counted_not_inherited(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T136_InitHw_Profile" VALUES (3, 500)')
            self._change_count(db, "T136_InitHw_Profile")
        c = audit(self.folder)["counts"]
        self.assertEqual(c["profiles_with_direct_inithw"], 1)
        self.assertEqual(c["direct_inithw_link_rows"], 1)

    def test_03_null_inithw_target_is_explicit_count(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T136_InitHw_Profile" VALUES (3, NULL)')
            self._change_count(db, "T136_InitHw_Profile")
        c = audit(self.folder)["counts"]
        self.assertEqual(c["null_direct_inithw_target_rows"], 1)

    def test_04_missing_carcom_identifier_stops_before_direct_query(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T161_Profile" SET identifier="broken" WHERE id=1')
        r = audit(self.folder)
        self.assertEqual(r["gate"], "carcom_exact_identifier_equality_not_unique")
        self.assertIsNone(r["counts"])

    def test_05_null_default_variant_reference_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T160_DefaultEcuVariant" VALUES (3, NULL)')
            self._change_count(db, "T160_DefaultEcuVariant")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_06_duplicate_variant_key_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T100_EcuVariant" VALUES (100, 1)')
            self._change_count(db, "T100_EcuVariant")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_07_unlisted_ecu_name_classified_only_as_other(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T101_Ecu" SET identifier="TCM" WHERE id=3')
        c = audit(self.folder)["counts"]
        self.assertEqual(c["direct_default_other_ecu_rows"], 6)
        self.assertEqual(c["direct_default_cem_rows"], 2)

    def test_08_extra_cem_classification_without_ecu_acceptance(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T100_EcuVariant" SET fkT101_Ecu=1 WHERE id=102')
        r = audit(self.folder)
        self.assertEqual(r["counts"]["direct_default_cem_rows"], 3)
        self.assertFalse(r["client_ecu_alive_verified"])

    def test_09_catalog_source_count_mismatch_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "_vida_tables" SET rows_exported=10 '
                       'WHERE table_name="T160_DefaultEcuVariant"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_10_sidecar_fails_closed(self):
        Path(str(self.carcom) + "-wal").write_text("unsafe")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_11_required_column_missing_from_exporter_metadata(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('DELETE FROM "_vida_columns" WHERE '
                       'table_name="T136_InitHw_Profile" AND column_name="fkT130_Init"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_12_private_values_never_leave_report(self):
        s = json.dumps(audit(self.folder))
        for secret in (str(self.folder), "XC90 PERIOD ONE", "OriginalVINSecret",
                       '"1000"', '"1001"', "DIM"):
            self.assertNotIn(secret, s)
        self.assertFalse(audit(self.folder)["original_source_identifiers_or_values_emitted"])
        self.assertFalse(audit(self.folder)["private_profile_lists_created"])

    def test_13_error_message_contains_only_class(self):
        stream = StringIO()
        with redirect_stderr(stream):
            status = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(status, 2)
        parsed = json.loads(stream.getvalue())
        self.assertEqual(set(parsed), {"status", "error_class"})
        self.assertNotIn(str(self.folder), stream.getvalue())


if __name__ == "__main__":
    unittest.main()
