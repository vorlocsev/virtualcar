"""Eight synthetic checks for opt-in Virtual Car Lab SQLite schema.

No real VIN, PIN, J2534 traffic, original VIDA XML or donor dump is used.
"""
import sqlite3
from pathlib import Path
import unittest

DDL = (Path(__file__).resolve().parents[1] / "schema" / "0001_lab_catalog.sql").read_text(encoding="utf-8")
HASH = "a" * 64
NOW = "2026-11-06T00:00:00Z"


def new_db():
    db = sqlite3.connect(":memory:")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(DDL)
    return db


def seed(db):
    db.execute("INSERT INTO vehicle_profiles VALUES(?,?,?,?,?,?)",
               ("vehicle-synthetic", "Laboratory car", "GENERIC", 2009, "synthetic", NOW))
    db.execute("INSERT INTO can_buses VALUES(?,?,?,?,?)",
               ("bus-1", "vehicle-synthetic", "HS", 500000, "11bit"))
    db.execute("INSERT INTO ecu_nodes VALUES(?,?,?,?,?,?,?)",
               ("ecu-1", "bus-1", "ECM", "iso15765", 0x7E0, 0x7E8, 0))
    db.execute("INSERT INTO response_fixtures VALUES(?,?,?,?,?,?,?)",
               ("fixture-1", "ecu-1", HASH, "synthetic",
                "approved_for_readonly_lab", b"\x62\xF1\x90synthetic", None))
    db.execute("INSERT INTO scenarios VALUES(?,?,?,?)",
               ("scenario-1", "Lab smoke", "vehicle-synthetic", NOW))
    db.execute("INSERT INTO scenario_revisions VALUES(?,?,?,?,?,?)",
               ("rev-1", "scenario-1", 1, 0, None, NOW))
    db.execute("INSERT INTO scenario_bindings VALUES(?,?,?)",
               ("rev-1", "fixture-1", 1))


class LabCatalogSqlTests(unittest.TestCase):
    def test_01_tables_present_and_fk_enabled(self):
        with new_db() as db:
            expected = {"schema_migrations", "vehicle_profiles", "can_buses", "ecu_nodes",
                        "response_fixtures", "private_artifacts", "scenarios",
                        "scenario_revisions", "scenario_bindings", "test_cases",
                        "test_runs", "test_events"}
            names = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertTrue(expected <= names)
            self.assertEqual(db.execute("PRAGMA foreign_keys").fetchone()[0], 1)

    def test_02_fk_and_speed_restrictions(self):
        with new_db() as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO can_buses VALUES(?,?,?,?,?)",
                           ("a", "missing", "HS", 500000, "11bit"))
            db.execute("INSERT INTO vehicle_profiles VALUES(?,?,?,?,?,?)",
                       ("p", "Synthetic", "GENERIC", 2009, "synthetic", NOW))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO can_buses VALUES(?,?,?,?,?)",
                           ("a", "p", "HS", 123456, "11bit"))

    def test_03_synthetic_fixture_cannot_hide_private_artifact(self):
        with new_db() as db:
            seed(db)
            db.execute("INSERT INTO private_artifacts VALUES(?,?,?,?,?,?,?)",
                       ("art", "private/trace.enc", HASH, 100, "dpapi_current_user", "private_response", NOW))
            for path in ("../escape.enc", "/absolute.enc", "C:/drive.enc", "private\\escape.enc"):
                with self.assertRaises(sqlite3.IntegrityError):
                    db.execute("INSERT INTO private_artifacts VALUES(?,?,?,?,?,?,?)",
                               ("badpath" + str(len(path)), path, HASH, 100, "dpapi_current_user", "private_response", NOW))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO response_fixtures VALUES(?,?,?,?,?,?,?)",
                           ("bad", "ecu-1", HASH, "captured_private", "draft", b"private", "art"))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO response_fixtures VALUES(?,?,?,?,?,?,?)",
                           ("bad2", "ecu-1", HASH, "synthetic", "draft", None, None))
            db.execute("INSERT INTO response_fixtures VALUES(?,?,?,?,?,?,?)",
                       ("captured", "ecu-1", HASH, "captured_private", "draft", None, "art"))

    def test_04_unapproved_fixture_cannot_be_enabled(self):
        with new_db() as db:
            seed(db)
            db.execute("UPDATE response_fixtures SET lab_approval='draft' WHERE id='fixture-1'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO scenario_bindings VALUES(?,?,?)",
                           ("rev-1", "fixture-1", 1))
            db.execute("DELETE FROM scenario_bindings WHERE revision_id='rev-1'")
            db.execute("INSERT INTO scenario_bindings VALUES(?,?,?)",
                       ("rev-1", "fixture-1", 0))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE scenario_bindings SET enabled=1 WHERE revision_id='rev-1'")

    def test_05_sealed_revision_and_bound_fixture_are_immutable(self):
        with new_db() as db:
            seed(db)
            db.execute("UPDATE scenario_revisions SET sealed=1,snapshot_sha256=? WHERE id='rev-1'", (HASH,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE scenario_revisions SET snapshot_sha256=? WHERE id='rev-1'", ("b"*64,))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("DELETE FROM scenario_bindings WHERE revision_id='rev-1'")
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("UPDATE response_fixtures SET lab_approval='draft' WHERE id='fixture-1'")

    def test_06_test_run_provenance_must_not_claim_physical_without_reference(self):
        with new_db() as db:
            seed(db)
            db.execute("INSERT INTO test_cases VALUES(?,?,?,?,?)",
                       ("case-1", "rev-1", "dvinholm_e2e", "{}", NOW))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute(
                    "INSERT INTO test_runs(id,test_case_id,scenario_sha256,origin,status,started_utc,finished_utc) VALUES(?,?,?,?,?,?,?)",
                    ("r1", "case-1", HASH, "physical_j2534", "passed", NOW, NOW))
            db.execute(
                "INSERT INTO test_runs(id,test_case_id,scenario_sha256,origin,status,started_utc,finished_utc) VALUES(?,?,?,?,?,?,?)",
                ("r2", "case-1", HASH, "synthetic_offline", "passed", NOW, NOW))
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO test_events(run_id,elapsed_ns,category,count) VALUES(?,?,?,?)",
                           ("nonexistent", 1, "can_rx", 1))

    def test_07_sensitive_columns_absent_from_result_tables(self):
        with new_db() as db:
            for table in ("test_runs", "test_events", "vehicle_profiles"):
                cols = {r[1].lower() for r in db.execute("PRAGMA table_info(" + table + ")")}
                for secret in ("vin", "pin", "raw_payload", "eeprom", "secret", "raw_can_frame"):
                    self.assertNotIn(secret, cols)
            self.assertEqual(db.execute("SELECT count(*) FROM vehicle_profiles").fetchone()[0], 0)

    def test_08_transaction_savepoint_and_unique_revision(self):
        with new_db() as db:
            seed(db)
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute("INSERT INTO scenario_revisions VALUES(?,?,?,?,?,?)",
                           ("rev-duplicate", "scenario-1", 1, 0, None, NOW))
            db.execute("SAVEPOINT dryrun")
            db.execute("INSERT INTO scenario_revisions VALUES(?,?,?,?,?,?)",
                       ("rev-2", "scenario-1", 2, 0, None, NOW))
            db.execute("ROLLBACK TO dryrun")
            db.execute("RELEASE dryrun")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM scenario_revisions").fetchone()[0], 1)


if __name__ == "__main__":
    unittest.main()
