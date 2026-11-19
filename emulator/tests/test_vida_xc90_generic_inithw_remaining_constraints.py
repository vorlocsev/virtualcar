"""Synthetic category-only comparison of seven additional CarCom T161 fields."""
from contextlib import closing, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import sqlite3
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import test_vida_xc90_generic_inithw_constraints as fixture
from audit_vida_xc90_generic_inithw_remaining_constraints import (
    DIMENSIONS, SchemaError, _aggregate, audit, main,
)


class Xc90RemainingSevenConstraintTests(unittest.TestCase):
    def setUp(self):
        fixture.Xc90StoredGenericConstraintsTests.setUp(self)
        with closing(sqlite3.connect(self.carcom)) as db, db:
            for i, (label, col) in enumerate(DIMENSIONS.items(), 1):
                db.execute('ALTER TABLE "dbo_T161_Profile" ADD COLUMN "' + col + '" INTEGER')
                db.execute(
                    'INSERT INTO "_vida_columns" VALUES (?,?,?)',
                    ("dbo", "T161_Profile", col)
                )
                default = None if label in ("chassis_from", "chassis_to") else (i * 100)
                db.execute(
                    'UPDATE "dbo_T161_Profile" SET "' + col + '"=? WHERE id IN (500,501)',
                    (default,)
                )
                db.execute(
                    'UPDATE "dbo_T161_Profile" SET "' + col + '"=? WHERE id BETWEEN 1 AND 43',
                    (i * 100,)
                )

    def test_01_all_seven_stored_dimensions_nonconflicting(self):
        r = audit(self.folder)
        self.assertEqual(r["gate"], "remaining_seven_stored_constraint_classes_only")
        c = r["counts"]
        self.assertEqual(c["exact_profiles_compared"], 43)
        self.assertEqual(c["generic_profiles_scanned"], 2)
        self.assertEqual(c["exact_profiles_all_seven_equal_or_generic_null"], 43)
        self.assertEqual(c["exact_profiles_with_one_or_more_filled_conflicts"], 0)
        self.assertEqual(c["exact_profiles_with_one_or_more_null_exact_against_filled_generic"], 0)
        for name in ("chassis_from", "chassis_to"):
            self.assertEqual(c["dimension_counts"][name]["general_null"], 43)
        for name in ("body", "control_unit", "market", "steering", "transmission"):
            self.assertEqual(c["dimension_counts"][name]["same_both_present"], 43)
        self.assertFalse(r["general_profile_parentage_verified"])
        self.assertFalse(r["d2_baudrate_verified"])
        self.assertFalse(r["client_vin_accepted"])

    def test_02_filled_key_conflict_is_not_hidden(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET "fkT162_ProfileValue_Market"=? WHERE id=1',
                (999,)
            )
        c = audit(self.folder)["counts"]
        self.assertEqual(c["dimension_counts"]["market"]["same_both_present"], 42)
        self.assertEqual(c["dimension_counts"]["market"]["different_both_present"], 1)
        self.assertEqual(c["exact_profiles_with_one_or_more_filled_conflicts"], 1)
        self.assertEqual(c["exact_profiles_all_seven_equal_or_generic_null"], 42)

    def test_03_exact_null_with_filled_generic_has_separate_category(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET "fkT162_ProfileValue_Body"=NULL WHERE id=1'
            )
        c = audit(self.folder)["counts"]
        self.assertEqual(c["dimension_counts"]["body"]["exact_null_when_general_present"], 1)
        self.assertEqual(c["exact_profiles_with_one_or_more_null_exact_against_filled_generic"], 1)

    def test_04_generic_null_not_promoted_to_wildcard(self):
        r = audit(self.folder)
        self.assertEqual(r["counts"]["dimension_counts"]["chassis_from"]["general_null"], 43)
        self.assertFalse(r["null_generic_constraint_is_wildcard_verified"])

    def test_05_two_conflicts_same_profile_counted_once_per_profile(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET '
                '"fkT162_ProfileValue_Market"=?, '
                '"fkT162_ProfileValue_Steering"=? WHERE id=1',
                (900, 901)
            )
        c = audit(self.folder)["counts"]
        self.assertEqual(c["exact_profiles_with_one_or_more_filled_conflicts"], 1)
        self.assertEqual(c["dimension_counts"]["market"]["different_both_present"], 1)
        self.assertEqual(c["dimension_counts"]["steering"]["different_both_present"], 1)

    def test_06_missing_declared_column_rejected(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'DELETE FROM "_vida_columns" WHERE table_name="T161_Profile" '
                'AND column_name="fkT162_ProfileValue_Transmission"'
            )
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_07_missing_physical_column_rejected(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'ALTER TABLE "dbo_T161_Profile" DROP COLUMN '
                '"fkT162_ProfileValue_Transmission"'
            )
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_08_extra_direct_init_candidate_refuses_selection(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute('INSERT INTO "dbo_T136_InitHw_Profile" VALUES (501,900)')
            db.execute('UPDATE "_vida_tables" SET rows_exported=2 '
                       'WHERE table_name="T136_InitHw_Profile"')
        r = audit(self.folder)
        self.assertEqual(r["gate"], "not_one_init_bearing_generic_profile")
        self.assertIsNone(r["counts"])

    def test_09_missing_generic_carcom_identifier_refuses_comparison(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET identifier="missing" WHERE id=501'
            )
        r = audit(self.folder)
        self.assertEqual(r["gate"], "generic_carcom_identifier_missing")
        self.assertIsNone(r["counts"])

    def test_10_missing_original_exact_43_fails_closed(self):
        with closing(sqlite3.connect(self.carcom)) as db, db:
            db.execute(
                'UPDATE "dbo_T161_Profile" SET identifier="missing" WHERE id=1'
            )
        r = audit(self.folder)
        self.assertEqual(r["gate"], "not_43_unique_carcom_identifiers")
        self.assertIsNone(r["counts"])

    def test_11_no_private_data_disclosure(self):
        s = json.dumps(audit(self.folder))
        for original in (
            "XC90 PERIOD ONE", "ignored-secret", "CANSpeed",
            '"1000"', '"2000"', str(self.folder), "secret-vin",
        ):
            self.assertNotIn(original, s)
        self.assertFalse(audit(self.folder)["original_identifiers_or_values_emitted"])

    def test_12_sidecar_rejected(self):
        Path(str(self.carcom) + "-shm").write_text("pending")
        with self.assertRaises(SchemaError):
            audit(self.folder)

    def test_13_sanitized_cli_failure(self):
        output = StringIO()
        with redirect_stderr(output):
            status = main(["--folder", str(self.folder / "missing")])
        self.assertEqual(status, 2)
        report = json.loads(output.getvalue())
        self.assertEqual(set(report), {"status", "error_class"})
        self.assertNotIn(str(self.folder), output.getvalue())


if __name__ == "__main__":
    unittest.main()
