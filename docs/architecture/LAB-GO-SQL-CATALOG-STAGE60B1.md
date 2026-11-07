# Stage 60B-1: Go SQL metadata boundary (driver injection)

Goal: Dvinholm-first Virtual Car lab; no production Dvinholm runtime dependency.
This stage is intentionally scoped to Go's standard database/sql interfaces.
It is not the SQLite driver / migration/backup integration promised by 60B-2.

## Added

- emulator/control/labdb/repository.go: database/sql metadata reader;
  requires injected sql.DB (opened by future, fixed-path Go SQLite adapter).
  Check validates PRAGMA quick_check, PRAGMA foreign_keys, exactly one v1
  migration with exact SHA-256 hash of passed canonical schema source.
- Sealed-revision lookup is strictly parameterized and metadata-only.
  SnapshotBytesVerified, RuntimeSelected and ProductionCompatible are
  always false. A metadata hash is NOT proof of immutable snapshot bytes.
- Bounded ListProfiles (1..100) and aggregate health without VIN, PIN,
  private paths, capture payloads or test clients.
- Controlled Close invalidates future calls. The injected SQL connection
  continues to belong to the caller.
- Eight Go offline tests emulate database/sql/driver with controlled rows;
  no real SQLite driver is registered and no Windows DB is opened.

## Driver research and selection for 60B-2

Candidate: modernc.org/sqlite, a pure-Go SQLite database/sql driver,
with BSD-3-Clause licensing and Windows 386/amd64 support.
Documented source: https://pkg.go.dev/modernc.org/sqlite
As of 2026-11-06 the observed module v1.61.1 is published, but
the dependency is NOT added to go.mod in this PR. Its exact Go toolchain,
transitive modernc.org/libc pinning, dependency checksums, vulnerability
scan and Windows cross-build remain to be validated in a dedicated PR.
Do not add an unverified module version to Go CI without a complete go.sum.

## Stage 60B-2 remaining, explicitly not implemented

1. Pin and vendor/verify modernc.org/sqlite + aligned libc/go.sum under CI;
   confirm Go toolchain compatibility and Windows amd64 target.
2. Open an explicit per-user local path without symlink traversal, with
   per-connection foreign_keys=ON and busy_timeout, WAL, one writer.
3. Implement offline first-time v1 migration with fully atomic journal
   updates and crash recovery. Never overwrite an unknown existing DB.
4. Implement database backup via SQLite online backup protocol / tested
   alternative respecting WAL, not copying .db alone during active writes.
5. Integrate with labcore only once stage61 hash-verifies the full immutable
   materialized scenario. A sealed metadata digest must not authorize CAN TX.
6. Add 6-8 actual SQLite + concurrency, crash/cancel, backup/restore and
   unknown schema tests, then native x86/x64 packaging evidence.

## Evidence boundaries

Go fake driver only proves SQL query/scan logic and policy checks. This
stage does NOT demonstrate a SQLite file opened by Go, real IPC, x64
J2534 DLL, real VIDA/SectorV recognition, CEM PIN, ECU programming,
physical DiCE, authorized hardware support, or a published release.
