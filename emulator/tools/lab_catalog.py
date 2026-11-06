#!/usr/bin/env python3
"""Explicit, offline SQLite catalog bootstrap for the Dvinholm-first Virtual Car lab.

This is a developer-only bridge until the Go service owns SQLite. It is NEVER
called from the native J2534 DLL or the CAN hot path. No private vehicle data.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import tempfile

SCHEMA = Path(__file__).resolve().parents[1] / "schema" / "0001_lab_catalog.sql"
REPO = Path(__file__).resolve().parents[2]
IDENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\Z")
ALLOWED_BUS_SPEEDS = (125000, 250000, 500000, 1000000)
TABLES = ("vehicle_profiles", "can_buses", "ecu_nodes", "response_fixtures",
          "scenarios", "scenario_revisions", "test_cases", "test_runs")


class LabDbError(ValueError):
    pass


def _safe_location(db_path):
    p = Path(db_path).absolute()
    if p.suffix.lower() != ".db":
        raise LabDbError("a .db file is required")
    if not p.parent.is_dir() or p.parent.is_symlink() or p.is_symlink():
        raise LabDbError("existing non-symlink parent and file required")
    if p.resolve().is_relative_to(REPO):
        raise LabDbError("lab data must stay outside the Git checkout")
    return p


def _schema_digest():
    data = SCHEMA.read_bytes()
    return data.decode("utf-8"), hashlib.sha256(data).hexdigest()


def _integrity(conn):
    if conn.execute("PRAGMA quick_check").fetchone()[0] != "ok":
        raise LabDbError("SQLite integrity check failed")


def initialize(db_path):
    path = _safe_location(db_path)
    if path.exists():
        raise FileExistsError("database exists; no overwrite or implicit migration")
    schema, checksum = _schema_digest()
    fd, tmp = tempfile.mkstemp(prefix=".virtualcar-lab-", suffix=".db", dir=path.parent)
    os.close(fd)
    try:
        if os.name == "posix":
            os.chmod(tmp, 0o600)
        with sqlite3.connect(tmp) as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
                raise LabDbError("SQLite foreign key enforcement unavailable")
            conn.execute("PRAGMA journal_mode=DELETE")
            created = datetime.now(timezone.utc).isoformat()
            # sqlite3.executescript commits any earlier transaction; put the
            # entire migration AND its checksum journal in one explicit one.
            journal = (
                "INSERT INTO schema_migrations(version,checksum_sha256,applied_utc) "
                "VALUES(1,'" + checksum + "','" + created + "');"
            )
            conn.executescript("BEGIN IMMEDIATE;\n" + schema + "\n" + journal + "\nCOMMIT;")
            _integrity(conn)
            if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise LabDbError("schema foreign key violation")
        with open(tmp, "rb") as stream:
            os.fsync(stream.fileno())
        # Same-filesystem exclusive hardlink: never replace even under a race.
        # NTFS and POSIX support hardlinks; fail closed on incompatible disks.
        os.link(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def open_database(db_path, *, readonly=True):
    path = _safe_location(db_path)
    if not path.is_file():
        raise LabDbError("existing database required")
    uri = path.resolve().as_uri() + ("?mode=ro" if readonly else "?mode=rw")
    conn = sqlite3.connect(uri, uri=True, timeout=5, isolation_level="DEFERRED")
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        if readonly:
            conn.execute("PRAGMA query_only=ON")
        if conn.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise LabDbError("foreign keys are disabled")
        _, digest = _schema_digest()
        versions = conn.execute(
            "SELECT version,checksum_sha256 FROM schema_migrations ORDER BY version"
        ).fetchall()
        if len(versions) != 1 or versions[0][0] != 1 or versions[0][1] != digest:
            raise LabDbError("unknown schema version or migration checksum drift")
        _integrity(conn)
        if not readonly:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
        return conn
    except BaseException:
        conn.close()
        raise


def _id(value):
    if not isinstance(value, str) or not IDENT.fullmatch(value):
        raise LabDbError("invalid laboratory identifier")
    return value


def _text(value, limit=96):
    if not isinstance(value, str) or not (1 <= len(value.strip()) <= limit):
        raise LabDbError("invalid lab label or field")
    if any(ord(x) < 32 or ord(x) == 127 for x in value):
        raise LabDbError("control characters forbidden")
    return value.strip()


def _timestamp():
    return datetime.now(timezone.utc).isoformat()


def add_synthetic_profile(conn, profile_id, label, platform, model_year):
    profile_id = _id(profile_id)
    label = _text(label)
    platform = _text(platform, 40)
    if not isinstance(model_year, int) or not 1900 <= model_year <= 2200:
        raise LabDbError("invalid synthetic model year")
    with conn:
        conn.execute(
            "INSERT INTO vehicle_profiles(id,label,platform,model_year,provenance,created_utc)"
            " VALUES(?,?,?,?,'synthetic',?)",
            (profile_id, label, platform, model_year, _timestamp()))


def add_bus(conn, bus_id, profile_id, label, bitrate, id_format):
    bus_id, profile_id = _id(bus_id), _id(profile_id)
    label = _text(label)
    if bitrate not in ALLOWED_BUS_SPEEDS or id_format not in ("11bit", "29bit"):
        raise LabDbError("invalid bus specification")
    with conn:
        conn.execute(
            "INSERT INTO can_buses(id,vehicle_profile_id,label,bitrate,id_format)"
            " VALUES(?,?,?,?,?)",
            (bus_id, profile_id, label, bitrate, id_format))


def add_ecu(conn, ecu_id, bus_id, label, transport, request_id, response_id):
    ecu_id, bus_id = _id(ecu_id), _id(bus_id)
    label = _text(label)
    if transport not in ("raw_can", "iso15765", "volvo_d2"):
        raise LabDbError("invalid transport type")
    bus = conn.execute("SELECT id_format FROM can_buses WHERE id=?", (bus_id,)).fetchone()
    if bus is None:
        raise LabDbError("unknown bus")
    limit = 0x7FF if bus["id_format"] == "11bit" else 0x1FFFFFFF
    if any(not isinstance(v, int) or v < 0 or v > limit for v in (request_id, response_id)):
        raise LabDbError("CAN identifier exceeds bus identifier format")
    with conn:
        conn.execute(
            "INSERT INTO ecu_nodes(id,bus_id,label,transport,request_can_id,response_can_id,enabled)"
            " VALUES(?,?,?,?,?,?,0)",
            (ecu_id, bus_id, label, transport, request_id, response_id))


def add_draft_scenario(conn, scenario_id, label, profile_id, revision_id):
    scenario_id, profile_id, revision_id = map(_id, (scenario_id, profile_id, revision_id))
    label = _text(label)
    stamp = _timestamp()
    with conn:
        conn.execute("INSERT INTO scenarios(id,label,vehicle_profile_id,created_utc)"
                     " VALUES(?,?,?,?)", (scenario_id, label, profile_id, stamp))
        conn.execute(
            "INSERT INTO scenario_revisions(id,scenario_id,revision,sealed,snapshot_sha256,created_utc)"
            " VALUES(?,?,1,0,NULL,?)", (revision_id, scenario_id, stamp))


def safe_summary(conn):
    return {
        "schema_version": 1,
        "repository": "sqlite_offline_developer_tool",
        "counts": {table: conn.execute("SELECT count(*) FROM " + table).fetchone()[0]
                   for table in TABLES},
        "vin_verified": False,
        "real_cem_supported": False,
        "dvinholm_e2e_verified": False,
        "runtime_engine_connected": False,
        "physical_j2534_tested": False
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Local Virtual Car SQLite lab catalog bootstrap")
    sub = parser.add_subparsers(dest="command", required=True)
    for cmd in ("init", "inspect", "add-profile", "add-bus", "add-ecu", "add-scenario"):
        sub.add_parser(cmd).add_argument("database", type=Path)
    sub.choices["add-profile"].add_argument("--id", required=True)
    sub.choices["add-profile"].add_argument("--label", required=True)
    sub.choices["add-profile"].add_argument("--platform", required=True)
    sub.choices["add-profile"].add_argument("--year", required=True, type=int)
    sub.choices["add-bus"].add_argument("--id", required=True)
    sub.choices["add-bus"].add_argument("--profile", required=True)
    sub.choices["add-bus"].add_argument("--label", required=True)
    sub.choices["add-bus"].add_argument("--bitrate", required=True, type=int)
    sub.choices["add-bus"].add_argument("--format", required=True, choices=["11bit", "29bit"])
    sub.choices["add-ecu"].add_argument("--id", required=True)
    sub.choices["add-ecu"].add_argument("--bus", required=True)
    sub.choices["add-ecu"].add_argument("--label", required=True)
    sub.choices["add-ecu"].add_argument("--transport", required=True,
                                      choices=["raw_can", "iso15765", "volvo_d2"])
    sub.choices["add-ecu"].add_argument("--request-id", required=True, type=lambda s: int(s, 0))
    sub.choices["add-ecu"].add_argument("--response-id", required=True, type=lambda s: int(s, 0))
    sub.choices["add-scenario"].add_argument("--id", required=True)
    sub.choices["add-scenario"].add_argument("--label", required=True)
    sub.choices["add-scenario"].add_argument("--profile", required=True)
    sub.choices["add-scenario"].add_argument("--revision-id", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            initialize(args.database)
            print("Lab database initialized locally; no emulator connected")
            return
        with open_database(args.database, readonly=(args.command == "inspect")) as conn:
            if args.command == "add-profile":
                add_synthetic_profile(conn, args.id, args.label, args.platform, args.year)
            elif args.command == "add-bus":
                add_bus(conn, args.id, args.profile, args.label, args.bitrate, args.format)
            elif args.command == "add-ecu":
                add_ecu(conn, args.id, args.bus, args.label, args.transport,
                        args.request_id, args.response_id)
            elif args.command == "add-scenario":
                add_draft_scenario(conn, args.id, args.label, args.profile, args.revision_id)
            elif args.command == "inspect":
                print(json.dumps(safe_summary(conn), indent=2, ensure_ascii=False))
                return
        print("Local lab metadata updated; diagnostic/runtime support NOT verified")
    except (LabDbError, OSError, sqlite3.Error, FileExistsError, UnicodeError) as error:
        parser.error("lab database operation failed: " + type(error).__name__)


if __name__ == "__main__":
    main()
