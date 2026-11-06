"""Eight offline safety/consistency tests for the SQLite lab repository."""
import hashlib
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lab_sqlite_repository import (
    RepositoryError, database_health, get_sealed_revision, list_profiles,
    open_repository, repository,
)

HASH = "a" * 64
NOW = "2026-11-06T00:00:00Z"


def seed(conn):
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("INSERT INTO vehicle_profiles VALUES(?,?,?,?,?,?)",
                 ("lab", "Synthetic vehicle", "GENERIC", 2009, "synthetic", NOW))
    conn.execute("INSERT INTO scenarios VALUES(?,?,?,?)",
                 ("scenario", "Synthetic scenario", "lab", NOW))
    conn.execute("INSERT INTO scenario_revisions VALUES(?,?,?,?,?,?)",
                 ("rev", "scenario", 1, 1, HASH, NOW))
    conn.execute("COMMIT")


class SqliteRepositoryTests(unittest.TestCase):
    def test_01_explicit_create_reopen_and_migration_checksum(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lab.db"
            with repository(p, create=True) as conn:
                row = conn.execute("SELECT version,checksum_sha256 FROM schema_migrations").fetchone()
                self.assertEqual(row["version"], 1)
                self.assertEqual(len(row["checksum_sha256"]), 64)
                self.assertEqual(conn.execute("PRAGMA foreign_keys").fetchone()[0], 1)
            with repository(p) as conn:
                self.assertEqual(database_health(conn)["vehicle_profile_count"], 0)
            symlink = parent / "symlink.db"
            try:
                symlink.symlink_to(p)
            except (OSError, NotImplementedError):
                pass
            else:
                with self.assertRaises(RepositoryError):
                    open_repository(symlink)


    def test_02_no_implicit_create_or_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lab.db"
            with self.assertRaises(RepositoryError):
                open_repository(p)
            with repository(p, create=True):
                pass
            data = p.read_bytes()
            with self.assertRaises(RepositoryError):
                open_repository(p, create=True)
            self.assertEqual(p.read_bytes(), data)

    def test_03_failed_schema_and_unknown_migration_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lab.db"
            p.write_bytes(b"not a sqlite database")
            with self.assertRaises(RepositoryError):
                open_repository(p)
            p.unlink()
            with repository(p, create=True) as conn:
                conn.execute("UPDATE schema_migrations SET checksum_sha256=?", ("f" * 64,))
            with self.assertRaises(RepositoryError):
                open_repository(p)
            with sqlite3.connect(p) as conn:
                conn.execute("UPDATE schema_migrations SET version=99,checksum_sha256=?", ("a" * 64,))
            with self.assertRaises(RepositoryError):
                open_repository(p)

    def test_04_sealed_revision_is_metadata_only(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lab.db"
            with repository(p, create=True) as conn:
                seed(conn)
                descriptor = get_sealed_revision(conn, "scenario", 1)
                self.assertEqual(descriptor["snapshot_sha256"], HASH)
                self.assertFalse(descriptor["snapshot_bytes_verified"])
                self.assertFalse(descriptor["production_compatible"])
                self.assertIsNone(get_sealed_revision(conn, "scenario", 2))

    def test_05_sql_injection_rejected_and_bounds_enforced(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lab.db"
            with repository(p, create=True) as conn:
                seed(conn)
                with self.assertRaises(RepositoryError):
                    get_sealed_revision(conn, "'; DROP TABLE scenarios;--", 1)
                with self.assertRaises(RepositoryError):
                    get_sealed_revision(conn, "scenario", -1)
                with self.assertRaises(RepositoryError):
                    list_profiles(conn, limit=100000)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()[0], 1)

    def test_06_foreign_keys_and_readonly_summaries(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lab.db"
            with repository(p, create=True) as conn:
                seed(conn)
                self.assertEqual(len(list_profiles(conn)), 1)
                self.assertEqual(database_health(conn)["sealed_scenario_count"], 1)
                with self.assertRaises(sqlite3.IntegrityError):
                    conn.execute("INSERT INTO can_buses VALUES(?,?,?,?,?)",
                                 ("bad", "no-profile", "HS", 500000, "11bit"))

    def test_07_private_source_never_mapped_to_production_verified(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "lab.db"
            with repository(p, create=True) as conn:
                seed(conn)
                self.assertFalse(get_sealed_revision(conn, "scenario", 1)["runtime_selected"])
                self.assertFalse(database_health(conn)["physical_j2534_verified"])
                conn.execute("INSERT INTO private_artifacts VALUES(?,?,?,?,?,?,?)",
                             ("private", "private/capture.enc", HASH, 16, "dpapi_current_user", "captured_trace", NOW))
                rows = list_profiles(conn)
                self.assertNotIn("private/capture.enc", str(rows))

    def test_08_no_directory_creation_and_transaction_rollbacks(self):
        with tempfile.TemporaryDirectory() as d:
            parent = Path(d)
            with self.assertRaises(RepositoryError):
                open_repository(parent / "missing" / "db.db", create=True)
            p = parent / "lab.db"
            with repository(p, create=True) as conn:
                try:
                    conn.execute("BEGIN IMMEDIATE")
                    conn.execute("INSERT INTO vehicle_profiles VALUES(?,?,?,?,?,?)",
                                 ("temp", "Synthetic", "GENERIC", 2009, "synthetic", NOW))
                    raise RuntimeError("abort")
                except RuntimeError:
                    conn.execute("ROLLBACK")
                self.assertEqual(database_health(conn)["vehicle_profile_count"], 0)


if __name__ == "__main__":
    unittest.main()
