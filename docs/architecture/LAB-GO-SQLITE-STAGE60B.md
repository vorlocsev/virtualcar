# Stage 60B | Go SQLite catalog (Dvinholm-first Virtual Car Lab)

Status: experimental branch, pending PR and CI verification.
The main deliverable is Dvinholm; Virtual Car is only its independent
read-only J2534 test bench.

## Go driver choice

- modernc.org/sqlite **v1.36.3**, BSD-3-Clause, no CGO, supports Go 1.23.0.
- It supports Windows x86 and x64 but this stage builds the existing
  x86 J2534 DLL only and does NOT provide a new x64 virtual DLL.
- Review module's third-party license notices before redistributing.
- Exact dependency checksums are committed in emulator/control/go.sum;
  CI should use go.mod/go.sum, not unpinned go get of latest release.
- SQLite's canonical schema remains emulator/schema/0001_lab_catalog.sql;
  no second schema is embedded, and there is no new migration version.

## New Go catalog

Location: emulator/control/labdb/catalog.go.

Functions:
- Initialize(ctx, databasePath, schemaPath): exclusive new-file create;
  transactionally applies schema v1 and records exact SHA-256 of
  migration source. Does not overwrite existing data.
- Open(ctx, databasePath, schemaPath): existing file only; checks
  SQLite quick_check, migration journal and foreign_key_check;
  rejects unknown schema instead of doing implicit upgrades.
- ListProfiles: local structured metadata, limit <=100.
- Health: aggregate counts and integrity only.
- LoadSealedSnapshot: read-only descriptor implementing labcore.Catalog,
  returns ApprovedReadOnly=false intentionally. This blocks
  labcore.Core.Select until stage 61's canonical snapshot compiler
  independently verifies actual snapshot bytes and provenance.
- Backup: creates a new, consistent database in another path using
  SQLite VACUUM INTO rather than copying the WAL-backed .db alone,
  verifies checksum and structural health, never overwrites existing backup.
- Close: closes owned connection.

SQLite connections: one writer/read connection per catalog object;
foreign_keys=ON, journal_mode=WAL, busy_timeout=5000ms,
synchronous=FULL, trusted_schema=OFF. No DB calls per CAN frame.

All inputs are local; no network service, credential storage, shell or
diagnostic ECU access. No SQLite record grants physical vehicle support.

## Eight Go tests

1. Exact migration initialization, reopen, FK and pool limit.
2. Missing file never created in open mode, existing DB never overwritten.
3. Tampered checksum and corrupted file rejected, content not erased.
4. Sealed descriptor cannot authorize a replay through labcore.
5. Bounded metadata list, safe selectors and missing revision.
6. Consistent WAL backup and no overwrite on repeated backup.
7. Cancelled contexts and concurrent bounded metadata readers.
8. Symlink and invalid foreign key rejected.

## Reality boundaries

- A sealed metadata row with a SHA-256 is not a compiled scenario.
- A synthetic ECU response cannot prove real XC90 MY2009 support.
- No original VIDA/VDASH ECU run, physical DiCE test or Windows GUI
  acceptance has been performed by this change.
- The private developer database is NOT stored in GitHub.
- The existing Python v1 offline tool remains useful independently.
- No Stable changes or Virtual Car releases.

Next: Stage 61 scenario compiler with independent verified materialized
snapshot bytes, bus/ECU evidence gates and deterministic runtime activation.
