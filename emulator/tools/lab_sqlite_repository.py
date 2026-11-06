#!/usr/bin/env python3
"""Isolated, local-only SQLite metadata repository for Virtual Car Lab.

This tool uses Python stdlib for *development-time* database verification.
The future Go service must have its own audited driver. No SQL is accessed
from the CAN/J2534 frame handling hot path. No private captures are imported.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re
import sqlite3
from contextlib import contextmanager

SCHEMA_VERSION = 1
MAX_DB_BYTES = 64 * 1024 * 1024
MIGRATION = Path(__file__).resolve().parents[1] / "schema" / "0001_lab_catalog.sql"
_ID = re.compile(r"[A-Za-z0-9_-]{1,96}\Z")
_SHA = re.compile(r"[0-9a-fA-F]{64}\Z")


class RepositoryError(Exception):
    """Safe generic repository failure with no user-specific data."""


def _id(s: str) -> str:
    if not isinstance(s, str) or not _ID.fullmatch(s):
        raise RepositoryError("invalid local catalog identifier")
    return s


def _digest(s: str) -> str:
    if not isinstance(s, str) or not _SHA.fullmatch(s):
        raise RepositoryError("invalid SHA-256 digest")
    return s.lower()


def _validate_path(path: Path) -> Path:
    original = Path(path).expanduser()
    # Check symlinks before canonicalization hides their presence.
    if original.is_symlink() or original.parent.is_symlink():
        raise RepositoryError("database symlink paths are not permitted")
    path = original.resolve(strict=False)
    if path.suffix.lower() != ".db" or path.is_dir():
        raise RepositoryError("invalid local .db destination")
    if not path.parent.is_dir():
        raise RepositoryError("database parent must already exist")
    return path


def _connect(path: Path) -> sqlite3.Connection:
    # SQLite URI/extension loading are not enabled. Scope is local process.
    conn = sqlite3.connect(str(path), timeout=5.0, isolation_level=None)
    conn.execute("PRAGMA trusted_schema=OFF")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _migration_bytes() -> bytes:
    return MIGRATION.read_bytes()


def open_repository(db_path: Path, *, create: bool = False) -> sqlite3.Connection:
    """Open existing checked database or explicitly create the first schema.

    Never performs an implicit upgrade, creates a parent directory, imports
    private source material, or claims a scenario has been runtime-verified.
    """
    path = _validate_path(db_path)
    if path.exists() and path.stat().st_size > MAX_DB_BYTES:
        raise RepositoryError("database exceeds local size limit")
    if create and path.exists():
        raise RepositoryError("database already exists; use open mode")
    if not create and not path.is_file():
        raise RepositoryError("database not found; initialization is explicit")
    conn = None
    made_file = False
    try:
        if create:
            # Exclusive creation prevents overwriting an unknown user file.
            with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb"):
                pass
            made_file = True
        conn = _connect(path)
        ddl_bytes = _migration_bytes()
        expected_hash = hashlib.sha256(ddl_bytes).hexdigest()
        if create:
            sql = ddl_bytes.decode("utf-8")
            # executescript commits a pending transaction; there is none here.
            # Everything, including the migration record, is in this BEGIN.
            safe_hash = expected_hash
            conn.executescript(
                "BEGIN IMMEDIATE;\n" + sql + "\n"
                "INSERT INTO schema_migrations(version,checksum_sha256,applied_utc)"
                " VALUES(1,'" + safe_hash + "',strftime('%Y-%m-%dT%H:%M:%fZ','now'));\n"
                "COMMIT;\n"
            )
        else:
            if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
                raise RepositoryError("database integrity check failed")
        migrations = list(conn.execute(
            "SELECT version,checksum_sha256 FROM schema_migrations ORDER BY version"
        ))
        if len(migrations) != 1 or migrations[0][0] != SCHEMA_VERSION or migrations[0][1] != expected_hash:
            raise RepositoryError("database migration version or checksum mismatch")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RepositoryError("foreign key enforcement unavailable")
        return conn
    except (sqlite3.DatabaseError, UnicodeError, OSError, ValueError) as exc:
        if conn is not None:
            conn.close()
        if made_file:
            # A failed first-time create should not leave a trusted-looking
            # partially migrated file; user databases are never deleted.
            for p in (path, Path(str(path) + "-wal"), Path(str(path) + "-shm")):
                try:
                    p.unlink(missing_ok=True)
                except OSError:
                    pass
        raise RepositoryError("SQLite catalog could not be initialized or verified") from exc
    except RepositoryError:
        if conn is not None:
            conn.close()
        raise


@contextmanager
def repository(db_path: Path, *, create: bool = False):
    conn = open_repository(db_path, create=create)
    try:
        yield conn
    finally:
        conn.close()


def list_profiles(conn: sqlite3.Connection, *, limit: int = 100) -> list[dict]:
    """Metadata-only; never fetches replies, private artifacts or raw frame data."""
    if not isinstance(limit, int) or not 1 <= limit <= 100:
        raise RepositoryError("profile listing limit out of range")
    rows = conn.execute(
        "SELECT id,label,platform,model_year,provenance "
        "FROM vehicle_profiles ORDER BY id LIMIT ?", (limit,)
    )
    return [dict(r) for r in rows]


def get_sealed_revision(conn: sqlite3.Connection, scenario_id: str, revision: int) -> dict | None:
    """Read descriptor only, never claim snapshot bytes have been validated."""
    scenario_id = _id(scenario_id)
    if not isinstance(revision, int) or not 1 <= revision <= 2**31 - 1:
        raise RepositoryError("invalid scenario revision number")
    row = conn.execute(
        "SELECT sr.id,sr.scenario_id,sr.revision,sr.snapshot_sha256,"
        "s.vehicle_profile_id,v.provenance "
        "FROM scenario_revisions sr "
        "JOIN scenarios s ON s.id=sr.scenario_id "
        "JOIN vehicle_profiles v ON v.id=s.vehicle_profile_id "
        "WHERE sr.scenario_id=? AND sr.revision=? AND sr.sealed=1",
        (scenario_id, revision)
    ).fetchone()
    if row is None:
        return None
    result = dict(row)
    result["snapshot_sha256"] = _digest(result["snapshot_sha256"])
    result["snapshot_bytes_verified"] = False
    result["runtime_selected"] = False
    result["production_compatible"] = False
    return result


def database_health(conn: sqlite3.Connection) -> dict:
    """Non-identifying, aggregate checkpoint for a local lab database."""
    integrity = conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    links = conn.execute("PRAGMA foreign_key_check").fetchall()
    return {
        "schema_version": SCHEMA_VERSION,
        "sqlite_quick_check_passed": integrity,
        "foreign_key_violations": len(links),
        "vehicle_profile_count": conn.execute("SELECT COUNT(*) FROM vehicle_profiles").fetchone()[0],
        "sealed_scenario_count": conn.execute("SELECT COUNT(*) FROM scenario_revisions WHERE sealed=1").fetchone()[0],
        "no_raw_capture_export": True,
        "physical_j2534_verified": False,
    }
