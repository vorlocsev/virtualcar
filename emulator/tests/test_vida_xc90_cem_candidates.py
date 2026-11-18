"""Synthetic-only read-only offline CarCom profile-to-CEM gate tests.

No original VIDA files or VIN/ECU firmware bytes are used.
"""
from __future__ import annotations

import importlib.util
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / "tools" / "audit_vida_xc90_cem_candidates.py"
SPEC = importlib.util.spec_from_file_location("audit_vida_xc90_cem_candidates", SOURCE)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


class CarComSyntheticTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.folder = self.root / "VIDA-private"
        self.folder.mkdir()
        self.path = self.folder / "CarCom.sqlite"
        self.exact = self.folder / "exact-43.txt"
        self.general = self.folder / "general.txt"
        self.exact.write_text("".join(f"synthetic_exact_{i:02}\n" for i in range(43)), encoding="utf-8")
        self.general.write_text("synthetic_general\n", encoding="utf-8")
        self._build()

    def _build(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.executescript('''
            CREATE TABLE "_vida_meta" ("key" TEXT, "value" TEXT);
            CREATE TABLE "_vida_tables" ("schema_name" TEXT, "table_name" TEXT, "rows_exported" INTEGER);
            CREATE TABLE "_vida_columns" ("schema_name" TEXT, "table_name" TEXT, "column_name" TEXT);
            CREATE TABLE "dbo_T161_Profile" ("id" INTEGER, "identifier" TEXT);
            CREATE TABLE "dbo_T160_DefaultEcuVariant" ("fkT161_Profile" INTEGER, "fkT100_EcuVariant" INTEGER);
            CREATE TABLE "dbo_T100_EcuVariant" ("id" INTEGER, "fkT101_Ecu" INTEGER);
            CREATE TABLE "dbo_T101_Ecu" ("id" INTEGER, "identifier" TEXT);
            CREATE TABLE "dbo_T120_Config_EcuVariant" ("fkT100_EcuVariant" INTEGER, "fkT121_Config" INTEGER);
            CREATE TABLE "dbo_T121_Config" ("id" INTEGER, "fkT122_Protocol" INTEGER, "busRate" INTEGER);
            CREATE TABLE "dbo_T122_Protocol" ("id" INTEGER, "identifier" TEXT);
            ''')
            db.executemany('INSERT INTO "_vida_meta" VALUES (?,?)', [
                ("schema_version", mod.EXPORT_SCHEMA),
                ("source_database", "CarCom"),
                ("scope", "all_user_tables"),
            ])
            for i in range(43):
                db.execute('INSERT INTO "dbo_T161_Profile" VALUES (?,?)',
                           (i+1, f"synthetic_exact_{i:02}"))
            db.execute('INSERT INTO "dbo_T161_Profile" VALUES (?,?)', (90, "synthetic_general"))
            db.executemany('INSERT INTO "dbo_T160_DefaultEcuVariant" VALUES (?,?)',
                           [(90, 101), (90, 102), (90, 103)])
            db.executemany('INSERT INTO "dbo_T100_EcuVariant" VALUES (?,?)',
                           [(101, 5), (102, 5), (103, 6)])
            db.executemany('INSERT INTO "dbo_T101_Ecu" VALUES (?,?)',
                           [(5, "CEM"), (6, "ECM")])
            db.executemany('INSERT INTO "dbo_T120_Config_EcuVariant" VALUES (?,?)',
                           [(101, 501), (101, 502), (102, 503)])
            db.executemany('INSERT INTO "dbo_T121_Config" VALUES (?,?,?)',
                           [(501, 10, None), (502, 10, 250000), (503, 11, 500000)])
            db.executemany('INSERT INTO "dbo_T122_Protocol" VALUES (?,?)',
                           [(10, "D2"), (11, "GGD")])
            self._rebuild_meta(db)

    def _rebuild_meta(self, db):
        db.execute('DELETE FROM "_vida_tables"')
        db.execute('DELETE FROM "_vida_columns"')
        for name in mod.TABLES:
            quoted = '"dbo_' + name + '"'
            count = db.execute('SELECT COUNT(*) FROM ' + quoted).fetchone()[0]
            db.execute('INSERT INTO "_vida_tables" VALUES (?,?,?)', ("dbo", name, count))
            fields = [r[1] for r in db.execute('PRAGMA table_info(' + quoted + ')')]
            db.executemany('INSERT INTO "_vida_columns" VALUES (?,?,?)',
                           [("dbo", name, c) for c in fields])

    def test_01_exact_and_general_aggregates(self):
        r = mod.audit(self.folder, self.exact, self.general)
        self.assertEqual(r["vehicle_catalog_hint"]["generation"], "P2-Restyling")
        a = r["exact_xc90_v8_my2009"]
        self.assertEqual(a["input_profiles"], 43)
        self.assertEqual(a["profiles_without_defaults"], 43)
        self.assertEqual(a["default_cem_variant_rows"], 0)
        b = r["general_profile_comparators"]
        self.assertEqual(b["default_cem_variant_rows"], 2)
        self.assertEqual(b["default_other_ecu_rows"], 1)
        self.assertEqual(b["cem_config_rows"], 3)
        self.assertEqual(b["cem_d2_config_rows"], 2)
        self.assertEqual(b["cem_ggd_config_rows"], 1)
        self.assertEqual(b["cem_config_missing_bitrate_rows"], 1)

    def test_02_never_promote_profile_to_hardware_runtime_or_fixture(self):
        r = mod.audit(self.folder, self.exact, self.general)
        for key in ("cem_hardware_h_l_verified", "actual_selected_vida_profile_verified",
                    "original_vida_readvin_accepted", "response_fixture_selection_approved",
                    "client_ecu_alive_verified", "profile_parentage_or_effective_inithw_verified"):
            self.assertIs(r[key], False)
        self.assertNotIn("synthetic_general", json.dumps(r))
        self.assertNotIn("synthetic_exact_00", json.dumps(r))
        self.assertNotIn("250000", json.dumps(r))

    def test_03_missing_defaults_is_a_valid_result(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM "dbo_T160_DefaultEcuVariant"')
            self._rebuild_meta(db)
        a = mod.audit(self.folder, self.exact, self.general)
        self.assertEqual(a["general_profile_comparators"]["profiles_without_defaults"], 1)
        self.assertEqual(a["general_profile_comparators"]["cem_config_rows"], 0)

    def test_04_exact_and_general_must_not_overlap(self):
        self.general.write_text("synthetic_exact_00\n", encoding="utf-8")
        with self.assertRaises(mod.EvidenceError):
            mod.audit(self.folder, self.exact, self.general)

    def test_05_duplicate_or_missing_profiles_fail(self):
        self.exact.write_text("synthetic_exact_00\n" * 43, encoding="utf-8")
        with self.assertRaises(mod.EvidenceError):
            mod.audit(self.folder, self.exact, self.general)
        self.exact.write_text("".join(f"synthetic_exact_{i:02}\n" for i in range(42)) +
                              "unmatched_profile\n", encoding="utf-8")
        with self.assertRaises(mod.EvidenceError):
            mod.audit(self.folder, self.exact, self.general)

    def test_06_corrupt_exporter_schema_or_counts_fail(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('DELETE FROM "_vida_columns" WHERE "table_name" = ? AND "column_name" = ?',
                       ("T101_Ecu", "identifier"))
        with self.assertRaises(mod.EvidenceError):
            mod.audit(self.folder, self.exact, self.general)
        with closing(sqlite3.connect(self.path)) as db, db:
            self._rebuild_meta(db)
            db.execute('UPDATE "_vida_tables" SET "rows_exported" = 999 WHERE "table_name"=?',
                       ("T161_Profile",))
        with self.assertRaises(mod.EvidenceError):
            mod.audit(self.folder, self.exact, self.general)

    def test_07_broken_links_or_ambiguous_target_fail(self):
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE "dbo_T160_DefaultEcuVariant" SET "fkT100_EcuVariant"=999 WHERE "fkT100_EcuVariant"=101')
        with self.assertRaises(mod.EvidenceError):
            mod.audit(self.folder, self.exact, self.general)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute('UPDATE "dbo_T160_DefaultEcuVariant" SET "fkT100_EcuVariant"=101 WHERE "fkT100_EcuVariant"=999')
            db.execute('INSERT INTO "dbo_T101_Ecu" VALUES (?,?)', (5, "CEM"))
            self._rebuild_meta(db)
        with self.assertRaises(mod.EvidenceError):
            mod.audit(self.folder, self.exact, self.general)

    def test_08_read_only_output_exclusive_and_sidecar_guard(self):
        output = self.root / "new-summary.json"
        self.assertEqual(mod.main(["--folder", str(self.folder),
                                   "--exact-profiles", str(self.exact),
                                   "--general-profiles", str(self.general),
                                   "--output", str(output)]), 0)
        original = self.path.read_bytes()
        self.assertEqual(mod.main(["--folder", str(self.folder),
                                   "--exact-profiles", str(self.exact),
                                   "--general-profiles", str(self.general),
                                   "--output", str(output)]), 2)
        self.assertEqual(self.path.read_bytes(), original)
        (self.folder / "CarCom.sqlite-wal").write_bytes(b"synthetic sidecar")
        with self.assertRaises(mod.EvidenceError):
            mod.audit(self.folder, self.exact, self.general)


if __name__ == "__main__":
    unittest.main()
