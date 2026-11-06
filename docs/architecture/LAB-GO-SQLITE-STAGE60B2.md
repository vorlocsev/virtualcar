# Stage 60B-2 | Real Go SQLite driver on top of stage 60B-1

Status: PR #68 under review; verify latest CI before merging.
Primary deliverable remains Dvinholm. Virtual Car is an independent,
read-only laboratory with no production release publication.

## Existing boundary and new integration

Stage 60B-1 PR #66 already merged a Go standard-library SQL metadata
contract at emulator/control/labdb/repository.go. It uses an injected
*sql.DB, validates a schema checksum and enforces bounded metadata-only
results; its 8 fake-driver tests are retained unchanged.

Stage 60B-2 adds:
- emulator/control/labdb/sqlite_driver.go: real modernc SQLite driver;
  explicit Initialize/Open and WAL backup via VACUUM INTO.
- emulator/control/labdb/sqlite_driver_test.go: 8 additional tests
  against actual disk-backed SQLite files.
- emulator/control/go.mod and go.sum: locked modernc.org/sqlite v1.36.3,
  modernc.org/libc v1.61.13 and exact transitive checksums.
- Cross-compile smoke of labdb/labcore to Windows x64 with CGO_ENABLED=0.

The chosen driver is pure Go, BSD-3-Clause and compatible with Go 1.23.
Its transitive licenses must be reviewed before shipping binaries.
There is no new system-provided SQLite DLL.

The SQLite wrapper loads exactly emulator/schema/0001_lab_catalog.sql,
checks the migration SHA-256, schema version, quick_check, foreign_keys,
foreign_key_check and bounded metadata queries. Initialization creates
the .db exclusively and is transactionally applied. Existing databases
are NEVER implicitly upgraded or overwritten. It uses one pooled
connection, synchronous FULL, busy timeout and WAL; every management
operation stays off the CAN/J2534 hot path.

Important: a sealed metadata record cannot authorize CAN, Volvo D2
or ECU replies. The wrapper delegates GetSealedRevision to the already
reviewed stage 60B-1 Repository and exposes labcore.Catalog with
ApprovedReadOnly=false until a later, independently hashed scenario
materializer can prove exact payload bytes.

VACUUM INTO writes a consistent backup from WAL; an exclusive empty
destination is reserved, then the backup is structurally checked. The
backup never contains decrypted external private capture sidecar files,
which need their own separately controlled backup.

## Synthetic regression gates

1. Explicit schema init/reopen, version, and enforced foreign keys.
2. No implicit DB creation or overwrite.
3. Tampered migration/corrupt DB rejected without deleting source.
4. Metadata-only sealed revisions cannot activate labcore.
5. Parameterized and bounded profile/revision selectors.
6. Consistent WAL backup and backup overwrite protection.
7. Cancelled queries and concurrent safe metadata reads.
8. Symlink and invalid foreign key rejection.

The old 8 stage60B-1 tests remain part of the full Go test suite.
Actual Windows x64 binary build is only a compile smoke, not an
interactive Dvinholm J2534 or DiCE acceptance test.

## Remaining limitations

- No headless running Go Core service / Named Pipes / x64 J2534 DLL.
- No canonical scenario compiler or verified runtime CAN reply fixture.
- No XC90 V8 MY2009 VIDA or SectorV success confirmation.
- No physical J2534 or real CEM tests.
- No private VIN/PIN/EEPROM/VIDA XML uploads and no Virtual Car release.

Stage 61 next: canonical scenario compiler, hash-verification and
evidence-gated read-only activation of synthetic tests.
