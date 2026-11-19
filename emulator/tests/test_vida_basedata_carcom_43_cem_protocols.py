"""Synthetic read-only CEM D2/GGD grouping tests: never read owner-private data."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import test_vida_basedata_carcom_43_direct_links as fixtures
from audit_vida_basedata_carcom_43_cem_protocols import (
    CONFIG_REQUIRED, SchemaError, audit, main,
)


class CemProtocolCategoryTests(unittest.TestCase):
    def setUp(self):
        fixtures.DirectLinksTests.setUp(self)
        with closing(sqlite3.connect(self.carcom)) as db, db:
            for table in ("T120_Config_EcuVariant", "T121_Config", "T122_Protocol"):
                cols = CONFIG_REQUIRED[table]
                db.execute('CREATE TABLE "dbo_' + table + '" (' +
                           ','.join('"' + col + '" TEXT' if col == "identifier" else
                                    '"' + col + '" INTEGER' for col in cols) + ')')
                db.executemany(
                    'INSERT INTO "_vida_columns" VALUES (?,?,?)',
                    [("dbo", table, col) for col in cols],
                )
            db.executemany('INSERT INTO "dbo_T120_Config_EcuVariant" VALUES (?,?)',
                           [(100, 2000), (100, 2001), (105, 2002)])
            db.executemany('INSERT INTO "dbo_T121_Config" VALUES (?,?,?)',
                           [(2000, 10, None), (2001, 11, 500000), (2002, 10, None)])
            db.executemany('INSERT INTO "dbo_T122_Protocol" VALUES (?,?)',
                           [(10, "D2"), (11, "GGD")])
            for table in ("T120_Config_EcuVariant", "T121_Config", "T122_Protocol"):
                self._refresh(db, table)

    @staticmethod
    def _refresh(db, table):
        rows = db.execute('SELECT COUNT(*) FROM "dbo_' + table + '"').fetchone()[0]
        db.execute('INSERT INTO "_vida_tables" VALUES (?,?,?)', ("dbo", table, rows))

    @staticmethod
    def _set_count(db, table):
        db.execute('UPDATE "_vida_tables" SET rows_exported=('
                   'SELECT COUNT(*) FROM "dbo_' + table + '") WHERE table_name=?',
                   (table,))

    def test_01_two_cem_defaults_d2_null_ggd_nonnull(self):
        r = audit(self.folder)
        self.assertEqual(r["gate"], "exact_cem_direct_config_categories_counted")
        c = r["counts"]
        self.assertEqual(c["matched_source_profiles"], 43)
        self.assertEqual(c["direct_cem_default_rows"], 2)
        self.assertEqual(c["cem_defaults_with_configs"], 2)
        self.assertEqual(c["cem_defaults_without_configs"], 0)
        self.assertEqual(c["cem_config_link_rows"], 3)
        self.assertEqual(c["cem_d2_config_rows"], 2)
        self.assertEqual(c["cem_d2_null_busrate_rows"], 2)
        self.assertEqual(c["cem_d2_nonnull_busrate_rows"], 0)
        self.assertEqual(c["cem_ggd_config_rows"], 1)
        self.assertEqual(c["cem_ggd_null_busrate_rows"], 0)
        self.assertEqual(c["cem_ggd_nonnull_busrate_rows"], 1)
        self.assertEqual(c["cem_other_protocol_config_rows"], 0)
        self.assertFalse(r["source_default_cem_is_live_ecu"])
        self.assertFalse(r["original_vida_readvin_accepted"])
        self.assertFalse(r["source_d2_bus_rate_missing_value_inferred"])

    def test_02_d2_bitrate_presence_only_not_its_value(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T121_Config" SET busRate=125000 WHERE id=2000')
        c = audit(self.folder)["counts"]
        self.assertEqual(c["cem_d2_nonnull_busrate_rows"], 1)
        self.assertEqual(c["cem_d2_null_busrate_rows"], 1)
        self.assertNotIn("125000", json.dumps(audit(self.folder)))

    def test_03_no_config_is_not_a_missing_ecu(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('DELETE FROM "dbo_T120_Config_EcuVariant" WHERE fkT100_EcuVariant=105')
            self._set_count(db, "T120_Config_EcuVariant")
        c = audit(self.folder)["counts"]
        self.assertEqual(c["direct_cem_default_rows"], 2)
        self.assertEqual(c["cem_defaults_without_configs"], 1)
        self.assertEqual(c["cem_config_link_rows"], 2)

    def test_04_other_protocol_is_bounded_class(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T122_Protocol" SET identifier="OTHER" WHERE id=11')
        c = audit(self.folder)["counts"]
        self.assertEqual(c["cem_ggd_config_rows"], 0)
        self.assertEqual(c["cem_other_protocol_config_rows"], 1)
        self.assertEqual(c["cem_other_protocol_nonnull_busrate_rows"], 1)

    def test_05_duplicate_config_link_not_mistaken_for_unique(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T120_Config_EcuVariant" VALUES (100,2000)')
            self._set_count(db, "T120_Config_EcuVariant")
        c = audit(self.folder)["counts"]
        self.assertEqual(c["cem_config_link_rows"], 4)
        self.assertEqual(c["cem_config_duplicate_refs_within_variant"], 1)

    def test_06_null_config_reference_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T120_Config_EcuVariant" VALUES (100,NULL)')
            self._set_count(db, "T120_Config_EcuVariant")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_07_missing_config_reference_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T120_Config_EcuVariant" SET fkT121_Config=9999 '
                       'WHERE fkT121_Config=2002')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_08_duplicate_config_primary_key_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T121_Config" VALUES (2001,11,500000)')
            self._set_count(db, "T121_Config")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_09_missing_original_config_column_in_exporter_fails(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('DELETE FROM "_vida_columns" WHERE table_name="T121_Config" '
                       'AND column_name="busRate"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_10_catalog_rowcount_mismatch_fails(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "_vida_tables" SET rows_exported=99 WHERE table_name="T122_Protocol"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_11_sidecars_rejected(self):
        Path(str(self.carcom) + "-wal").write_text("unsafe")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_12_raw_names_ids_and_rates_not_exported(self):
        output = json.dumps(audit(self.folder))
        for secret in ("500000", "2000", "2001", "2002", "XC90 PERIOD ONE",
                       str(self.folder), "OriginalVINSecret", '"ECM"'):
            self.assertNotIn(secret, output)
        self.assertFalse(audit(self.folder)["original_profile_identifiers_ecu_keys_or_bus_rates_exported"])

    def test_13_broken_43_carcom_equality_stops_config_classification(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('UPDATE "dbo_T161_Profile" SET identifier="bad" WHERE id=1')
        r = audit(self.folder)
        self.assertEqual(r["gate"], "not_43_unique_carcom_identifiers")
        self.assertIsNone(r["counts"])

    def test_14_wrong_base_profile_count_stops(self):
        with closing(sqlite3.connect(self.base)) as db, db:
            db.execute('DELETE FROM "dbo_VehicleProfile" WHERE Id=1000')
            db.execute('UPDATE "_vida_tables" SET rows_exported=42 WHERE table_name="VehicleProfile"')
        r = audit(self.folder)
        self.assertEqual(r["gate"], "not_43_exact_profiles")
        self.assertIsNone(r["counts"])

    def test_15_sanitized_error_only(self):
        output = StringIO()
        with redirect_stderr(output):
            result = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(result, 2)
        parsed = json.loads(output.getvalue())
        self.assertEqual(set(parsed), {"status", "error_class"})
        self.assertNotIn(str(self.folder), output.getvalue())


if __name__ == "__main__":
    unittest.main()
