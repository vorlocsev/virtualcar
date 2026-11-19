"""Synthetic CarCom T161 constraint comparison: private IDs/values never output."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import test_vida_basedata_xc90_general_inithw as fixture
from audit_vida_xc90_generic_inithw_constraints import (
    SchemaError, _rank, audit, main,
)


class Xc90StoredGenericConstraintsTests(unittest.TestCase):
    def setUp(self):
        fixture.Xc90GeneralInitHwTests.setUp(self)
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'ALTER TABLE "dbo_T161_Profile" ADD COLUMN "folderLevel" INTEGER'
            )
            db.execute(
                'INSERT INTO "_vida_columns" VALUES (?,?,?)',
                ("dbo", "T161_Profile", "folderLevel")
            )
            db.execute(
                'UPDATE "dbo_T161_Profile" SET '
                '"fkT162_ProfileValue_Model"=100, '
                '"fkT162_ProfileValue_Year"=200, '
                '"fkT162_ProfileValue_Engine"=100, '
                '"folderLevel"=4 WHERE id BETWEEN 1 AND 43'
            )
            db.execute(
                'UPDATE "dbo_T161_Profile" SET '
                '"fkT162_ProfileValue_Model"=100, '
                '"fkT162_ProfileValue_Year"=200, '
                '"fkT162_ProfileValue_Engine"=NULL, '
                '"folderLevel"=2 WHERE id IN (500,501)'
            )

    def test_01_43_exact_model_year_equal_engine_general_null(self):
        r = audit(self.folder)
        self.assertEqual(r["gate"], "carcom_stored_constraint_comparison_only")
        c = r["counts"]
        self.assertEqual(c["exact_profiles_compared"], 43)
        self.assertEqual(c["general_init_bearing_candidates"], 1)
        self.assertEqual(c["same_model_key_both_present"], 43)
        self.assertEqual(c["same_year_key_both_present"], 43)
        self.assertEqual(c["general_engine_key_null"], 43)
        self.assertEqual(c["same_engine_key_both_present"], 0)
        self.assertEqual(c["exact_folderlevel_greater_than_generic"], 43)
        self.assertFalse(r["folderlevel_order_is_precedence_or_parentage_verified"])
        self.assertFalse(r["general_profile_is_runtime_ancestor_verified"])
        self.assertFalse(r["original_vida_readvin_accepted"])

    def test_02_model_different_is_counted_not_assumed_inherited(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET '
                '"fkT162_ProfileValue_Model"=200 WHERE id=1'
            )
        c = audit(self.folder)["counts"]
        self.assertEqual(c["same_model_key_both_present"], 42)
        self.assertEqual(c["different_model_key_both_present"], 1)

    def test_03_general_null_model_does_not_prove_wildcard(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET '
                '"fkT162_ProfileValue_Model"=NULL WHERE id=500'
            )
        r = audit(self.folder)
        self.assertEqual(r["counts"]["general_model_key_null"], 43)
        self.assertEqual(r["counts"]["same_model_key_both_present"], 0)
        self.assertFalse(r["general_profile_is_runtime_ancestor_verified"])

    def test_04_null_exact_key_is_its_own_class(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET '
                '"fkT162_ProfileValue_Year"=NULL WHERE id=1'
            )
        c = audit(self.folder)["counts"]
        self.assertEqual(c["same_year_key_both_present"], 42)
        self.assertEqual(c["exact_year_key_null_when_general_present"], 1)

    def test_05_folderlevel_less_equal_greater_unavailable(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET "folderLevel"=1 WHERE id=1'
            )
            db.execute(
                'UPDATE "dbo_T161_Profile" SET "folderLevel"=2 WHERE id=2'
            )
            db.execute(
                'UPDATE "dbo_T161_Profile" SET "folderLevel"="unknown" WHERE id=3'
            )
        c = audit(self.folder)["counts"]
        self.assertEqual(c["exact_folderlevel_less_than_generic"], 1)
        self.assertEqual(c["exact_folderlevel_equal_generic"], 1)
        self.assertEqual(c["exact_folderlevel_greater_than_generic"], 40)
        self.assertEqual(c["folderlevel_not_comparable"], 1)

    def test_06_two_generic_with_direct_init_returns_no_comparison(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T136_InitHw_Profile" VALUES (501,900)')
            db.execute('UPDATE "_vida_tables" SET rows_exported=2 '
                       'WHERE table_name="T136_InitHw_Profile"')
        r = audit(self.folder)
        self.assertEqual(r["gate"], "not_one_generic_init_bearing_profile")
        self.assertIsNone(r["counts"])

    def test_07_zero_generic_direct_init_returns_no_comparison(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('DELETE FROM "dbo_T136_InitHw_Profile"')
            db.execute('UPDATE "_vida_tables" SET rows_exported=0 '
                       'WHERE table_name="T136_InitHw_Profile"')
        r = audit(self.folder)
        self.assertEqual(r["gate"], "not_one_generic_init_bearing_profile")
        self.assertIsNone(r["counts"])

    def test_08_two_init_links_on_one_generic_not_used_as_one(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T136_InitHw_Profile" VALUES (500,900)')
            db.execute('UPDATE "_vida_tables" SET rows_exported=2 '
                       'WHERE table_name="T136_InitHw_Profile"')
        r = audit(self.folder)
        self.assertEqual(r["gate"], "general_direct_init_link_not_unique")
        self.assertIsNone(r["counts"])

    def test_09_missing_folderlevel_in_catalog_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('DELETE FROM "_vida_columns" WHERE '
                       'table_name="T161_Profile" AND column_name="folderLevel"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_10_missing_physical_folderlevel_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('ALTER TABLE "dbo_T161_Profile" DROP COLUMN "folderLevel"')
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_11_43_equality_failure_stops_structural_comparison(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET identifier="bad" WHERE id=1'
            )
        r = audit(self.folder)
        self.assertEqual(r["gate"], "not_43_unique_carcom_identifiers")
        self.assertIsNone(r["counts"])

    def test_12_missing_generic_carcom_id_returns_no_comparison(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET identifier="unknown" WHERE id=501'
            )
        r = audit(self.folder)
        self.assertEqual(r["gate"], "general_carcom_identifier_missing")
        self.assertIsNone(r["counts"])

    def test_13_report_no_private_source_values(self):
        txt = json.dumps(audit(self.folder))
        for secret in ("XC90 PERIOD ONE", "CANSpeed", "ignored-secret",
                       "900", '"1000"', '"2000"', str(self.folder), "VINSECRET"):
            self.assertNotIn(secret, txt)
        self.assertFalse(audit(self.folder)["original_profile_ids_or_values_emitted"])

    def test_14_rank_parse_is_bounded(self):
        self.assertEqual(_rank(2), 2)
        self.assertEqual(_rank("0003"), 3)
        self.assertIsNone(_rank("bad"))
        self.assertIsNone(_rank(1_000_001))
        self.assertIsNone(_rank(None))

    def test_15_cli_failure_sanitized(self):
        buf = StringIO()
        with redirect_stderr(buf):
            code = main(["--folder", str(self.folder / "absent")])
        self.assertEqual(code, 2)
        self.assertEqual(set(json.loads(buf.getvalue())), {"status", "error_class"})
        self.assertNotIn(str(self.folder), buf.getvalue())


if __name__ == "__main__":
    unittest.main()
