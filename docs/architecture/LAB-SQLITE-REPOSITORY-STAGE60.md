# Stage 60A | SQLite repository initialization and cross-chat progress

Purpose: Virtual Car remains a read-only Dvinholm test laboratory.
Dvinholm product code and Stable releases are untouched.

## Included in branch feature/lab-sqlite-repository-stage60

- Canonical roadmap: docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md
- Persistent checkpoint: docs/progress/CURRENT.md
- Offline SQLite repository: emulator/tools/lab_sqlite_repository.py
- Local explicit CLI: emulator/tools/lab_db_cli.py
- Eight synthetic repository tests: emulator/tests/test_lab_sqlite_repository.py
- Uses existing emulator/schema/0001_lab_catalog.sql from merged PR #59,
  no competing schema and no private data import.

The Python standard library provides this **development-time offline**
repository. This does not connect SQLite to the Go Core service and does
not make Python a requirement for the future standalone Windows x64 runtime.

## Safe local usage

Run only on a local private folder that already exists. Do not put real
VIN, PIN, dump or VIDA XML data into the lab database:

    python emulator/tools/lab_db_cli.py init --database PRIVATE_LAB_FOLDER/lab.db
    python emulator/tools/lab_db_cli.py health --database PRIVATE_LAB_FOLDER/lab.db

- Init refuses to overwrite an existing database and never creates
  directories automatically.
- Opening existing DB verifies database integrity and exact migration
  schema version SHA-256. There is NO implicit schema upgrade.
- WAL mode, foreign key enforcement, bounded profile listings and
  parameterized sealed-revision queries. No raw response bytes are
  returned from repository listing/read methods.
- Sealed-revision metadata is NOT sufficient to activate a scenario:
  snapshot_bytes_verified=false until a separately implemented compiler
  hashes the materialized immutable scenario.
- No SQL in frame/RX path, no J2534/IPC/GUI integration at this stage.
- Database corruption returns an error and does not silently reset,
  rewrite or overwrite an existing private database.

## Eight synthetic offline gates

1. Schema create/reopen, checksum, and foreign key enforcement.
2. Reject missing DB in open mode; reject re-init overwrite.
3. Reject malformed SQLite and changed/unknown migration.
4. Safe sealed revision lookup, no runtime verification claim.
5. Reject invalid selector/revision, bounded list, parameterized SQL.
6. Foreign keys and metadata-only aggregate health.
7. No accidental private capture disclosure or physical attestation.
8. No unexpected parent directory creation, transaction rollback,
   reject symlink to existing DB when supported.

The CLI prints only aggregate counters. Runtime acceptance through a
physical DiCE/J2534 or Dvinholm native DLL is NOT performed here.

## Next gate: stage 60B

- Confirm Windows x86 CI Go/Python/native routes against this PR HEAD.
- Review safety of DB file initialization on Windows, and migration crash
  semantics with actual WAL.
- Implement a Go-owned SQLite adapter and explicitly licensed driver,
  migrations/backup and transactional scenario editor under CI.
- Test adapter through existing labcore.Catalog and hash-checked
  materialized scenarios. Do NOT activate a DB descriptor without
  verifying the exact scenario snapshot payload.
- Continue to stage 61 compiler after the Go service owns the DB.

No Virtual Car release is to be published.
