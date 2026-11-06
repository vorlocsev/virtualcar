"""Offline SQLite bootstrap and safe synthetic metadata regression tests (10 gates)."""
import contextlib
import hashlib
import io
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import lab_catalog as lab


class LabCatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.db = self.dir / "virtualcar-lab.db"

    def init(self):
        lab.initialize(self.db)

    def populate(self, conn):
        lab.add_synthetic_profile(conn, "lab-01", "Synthetic vehicle", "GENERIC", 2009)
        lab.add_bus(conn, "bus-HS", "lab-01", "Synthetic HS", 500000, "11bit")
        lab.add_ecu(conn, "ecu-1", "bus-HS", "Synthetic ECM", "iso15765", 0x7E0, 0x7E8)
        lab.add_draft_scenario(conn, "s1", "Offline smoke", "lab-01", "rev-1")

    def test_01_initialization_and_checksum_journal(self):
        self.init()
        with lab.open_database(self.db) as conn:
            version = conn.execute("SELECT version, checksum_sha256 FROM schema_migrations").fetchone()
            self.assertEqual(version["version"], 1)
            self.assertEqual(version["checksum_sha256"], hashlib.sha256(lab.SCHEMA.read_bytes()).hexdigest())
            self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            self.assertEqual(lab.safe_summary(conn)["counts"]["vehicle_profiles"], 0)

    def test_02_existing_db_not_overwritten(self):
        self.init()
        before = self.db.read_bytes()
        with self.assertRaises(FileExistsError):
            self.init()
        self.assertEqual(before, self.db.read_bytes())

    def test_03_repo_root_and_symlink_rejected(self):
        # The actual Git checkout must never become a database location.
        with self.assertRaises(lab.LabDbError):
            lab.initialize(lab.REPO / "private-lab-test.db")
        symlink = self.dir / "linked"
        try:
            symlink.symlink_to(self.dir, target_is_directory=True)
        except OSError:
            return  # Windows accounts may be restricted from creating symlinks.
        with self.assertRaises(lab.LabDbError):
            lab.initialize(symlink / "lab.db")

    def test_04_synthetic_profile_bus_ecu_scenario_roundtrip(self):
        self.init()
        with lab.open_database(self.db, readonly=False) as conn:
            self.populate(conn)
        with lab.open_database(self.db) as conn:
            result = lab.safe_summary(conn)["counts"]
            self.assertEqual(result["vehicle_profiles"], 1)
            self.assertEqual(result["can_buses"], 1)
            self.assertEqual(result["ecu_nodes"], 1)
            self.assertEqual(result["scenarios"], 1)
            enabled = conn.execute("SELECT enabled FROM ecu_nodes").fetchone()[0]
            sealed = conn.execute("SELECT sealed FROM scenario_revisions").fetchone()[0]
            self.assertEqual((enabled, sealed), (0, 0))

    def test_05_11bit_address_is_bounded(self):
        self.init()
        with lab.open_database(self.db, readonly=False) as conn:
            lab.add_synthetic_profile(conn, "p", "Synthetic", "GENERIC", 2009)
            lab.add_bus(conn, "b", "p", "HS", 500000, "11bit")
            with self.assertRaises(lab.LabDbError):
                lab.add_ecu(conn, "too-large", "b", "ECM", "iso15765", 0x1234, 0x7E8)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM ecu_nodes").fetchone()[0], 0)

    def test_06_missing_foreign_key_rejected(self):
        self.init()
        with lab.open_database(self.db, readonly=False) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                lab.add_bus(conn, "b", "not-defined", "HS", 500000, "11bit")
            self.assertEqual(conn.execute("SELECT count(*) FROM can_buses").fetchone()[0], 0)

    def test_07_duplicate_primary_key_no_partial_commit(self):
        self.init()
        with lab.open_database(self.db, readonly=False) as conn:
            lab.add_synthetic_profile(conn, "p", "Synthetic", "GENERIC", 2009)
            with self.assertRaises(sqlite3.IntegrityError):
                lab.add_synthetic_profile(conn, "p", "Other", "GENERIC", 2009)
            self.assertEqual(conn.execute("SELECT label FROM vehicle_profiles WHERE id='p'").fetchone()[0], "Synthetic")

    def test_08_schema_checksum_drift_fail_closed(self):
        self.init()
        with lab.open_database(self.db, readonly=False) as conn:
            conn.execute("UPDATE schema_migrations SET checksum_sha256=? WHERE version=1",
                         ("f" * 64,))
        with self.assertRaises(lab.LabDbError):
            lab.open_database(self.db)

    def test_09_readonly_and_missing_database_do_not_create(self):
        self.init()
        with lab.open_database(self.db) as conn:
            with self.assertRaises(sqlite3.OperationalError):
                lab.add_synthetic_profile(conn, "p", "Synthetic", "GENERIC", 2009)
        missing = self.dir / "missing.db"
        with self.assertRaises(lab.LabDbError):
            lab.open_database(missing)
        self.assertFalse(missing.exists())

    def test_10_cli_only_reports_counts_no_user_ids_or_paths(self):
        with contextlib.redirect_stdout(io.StringIO()):
            lab.main(["init", str(self.db)])
            lab.main(["add-profile", str(self.db), "--id", "SECRET-LAB-KEY",
                      "--label", "private label", "--platform", "GENERIC", "--year", "2009"])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            lab.main(["inspect", str(self.db)])
        safe = output.getvalue()
        self.assertNotIn("SECRET-LAB-KEY", safe)
        self.assertNotIn("private label", safe)
        self.assertNotIn(str(self.dir), safe)
        self.assertIn('"vehicle_profiles": 1', safe)


if __name__ == "__main__":
    unittest.main()
