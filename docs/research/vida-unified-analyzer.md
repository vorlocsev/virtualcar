# VIDA Unified Analyzer v1: SQL Server + SQLite metadata graph

Status: **source-only, owner-local research**. No original VIDA SQL Server,
private SQLite copy, script content, VIN, ECU payload or VMware session was read
in preparing this PR. This is not proof of SectorV/VDASH ReadVin acceptance.

## What it does

One command-line analyzer supports two schema metadata backends:

* `sqlite-export`: reads **only** `_vida_meta`, `_vida_tables` and
  `_vida_columns` from the existing `CarCom.sqlite`,
  `DiagSwdlRepository.sqlite` and `BaseData.sqlite` *metadata-only exports*.
  It opens immutable, read-only files only after rejecting any adjacent
  `-wal`, `-shm` or `-journal` file. These sidecars may indicate that a
  single-file SQLite snapshot was not checkpointed. It cannot reconstruct
  missing original user rows or SQL Server foreign-key constraints that the
  exporter omitted.
* `sqlserver`: uses the `pyodbc` ODBC DSN configured locally in the owner VM.
  It connects individually to the three known VIDA database names and issues
  only fixed queries against `sys.tables`, `sys.columns`,
  `sys.schemas`, `sys.foreign_keys` and `sys.foreign_key_columns`.
  It verifies `SELECT DB_NAME()` matches the intended database before any catalog discovery. It never selects from application/user tables.

Both backends use the same source of known research hints in
`audit_vida_carcom_schema_links.py`; they do not duplicate assumptions
about `T111_Service`, `T122_Protocol` or `InitHw`. Existing scripts remain
available for backwards compatibility. The future goal is to consolidate
specific research stages behind this shared inventory interface.

The report includes overall table, column and declared FK counts for each
database; only **allowlisted** table and column names appear. Relations have
explicit evidence classes:

* `service_shape` / `hardware_shape`: expected columns exist on both
  tables; **not** a verified join and **not** original diagnostic evidence.
* `sqlserver_declared_fk`: the SQL Server schema declares an FK with
  allowlisted endpoints. Disabled/untrusted flags are preserved, but even a
  trusted FK is **not** an executed ReadVin step or independently verified
  source-row association.

SQL Server catalog queries are subject to metadata visibility permissions:
empty table and column catalogs, or any visible table with zero visible
columns, are rejected; a nonempty result still does **not**
prove that every table or foreign key is visible. The JSON field
`catalog_visibility_complete_verified=false` explicitly records this
limitation, even when the connection and declared FK discovery succeed.

Unknown table names, column names, SQL definitions, rows, IDs, VIN and
credentials are not emitted. Errors do not print connection strings.
No database modification, D2 speed inference, CEM fixture generation or
automatic replay is permitted.

## Owner-local usage in isolated Windows VMware

Prerequisites for direct SQL Server mode: owner-reviewed ODBC Driver for SQL
Server and Python `pyodbc`, and a **Windows-integrated-authentication**
read-only account with permission to view the required metadata. Configure
an ODBC **System DSN** locally; no username or password is accepted as a
command-line argument. DNS and TLS must be set up for certificate validation;
the tool enforces `Encrypt=Yes;TrustServerCertificate=No`. It also
limits SQL Server login and each catalog query independently to eight seconds;
a failed query-timeout configuration aborts before discovery. The
`ApplicationIntent=ReadOnly` connection-string option is advisory, **not**
access control: enforce permissions on the SQL Server itself.

Run from a reviewed checkout, after successful focused tests:

```powershell
$env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
py -3 -m unittest discover -s emulator/tests -p test_vida_unified_analyzer.py -v
py -3 -m compileall -q emulator/tools/vida_unified_analyzer.py emulator/tests/test_vida_unified_analyzer.py
py -3 emulator/tools/vida_unified_analyzer.py --backend sqlserver --output 'E:\VirtualCar\VIDA-private\unified-sqlserver-001.redacted.json'
```

Or use existing offline SQLite *metadata exports* with no ODBC dependency:

```powershell
py -3 emulator/tools/vida_unified_analyzer.py --backend sqlite-export --folder 'E:\VirtualCar\VIDA-private' --output 'E:\VirtualCar\VIDA-private\unified-sqlite-001.redacted.json'
```

Each output path must be a **new** file outside the Git working tree. Paths
and database identities are not printed on failure. The source SQLite files
must not be symlinks. Generated reports stay private in the VM; review them
before sharing even aggregate results.

## Acceptance gates

1. Synthetic SQLite inventory and twelve shape candidates, no source names.
2. Missing table and absent expected column remain explicit negatives.
3. Malformed exporter metadata schema is rejected before any data SELECT.
4. Invalid identity, orphan columns or duplicated catalog identity fail.
5. SQL Server DSN injection and connection error redaction.
6. SQL Server metadata-only query contract, exact `DB_NAME()` identity,
   TLS and trusted connection shape.
7. Declared FK evidence distinguished from unverified row joins; hidden
   original table/column names do not escape to JSON.
8. Exclusive output file, no SQLite source modification, and rejection of
   active SQLite WAL or rollback-journal sidecars.
9. Empty or metadata-invisible SQL Server table or column catalogs rejected,
   including one table with zero visible columns. A nonempty catalog still does
   not prove that its visibility is complete.

Eighteen unit tests cover these behaviors synthetically; run them on a reviewed exact
commit before connecting to real data. **No exact-head VMware CI or live SQL
Server result is claimed by this document.**

## Isolated PR-head test automation

`.github/workflows/vida-unified-analyzer-pr-tests.yml` adds a narrowly
scoped GitHub-hosted `pull_request` check for PR #307 only. It checks out
`github.event.pull_request.head.sha`, asserts that exact Git commit, compiles
the two analyzer modules and test file, and runs the synthetic unittest file
with Python 3.12. The job has read-only repository permissions and an
eight-minute limit; it has **no** private VIDA sources, J2534 adapter or VM
access. The authoritative Windows VMware workflow still runs exclusively
on trusted development pushes or main-controlled manual dispatch.

This is merely the **automation definition** until GitHub supplies an
actual successful workflow run against an exact SHA. Neither a YAML file
nor local SQLite probes qualify as a passing 18/18 test run or VMware gate.

## Still not established

* Whether the exact original 2015A SQL Server instance is reachable with
  valid trusted credentials and server certificate.
* Whether the owner's 2015A schema contains all 2014D research-port hints.
* Which `InitHw` values apply to the actually selected XC90 V8 MY2009
  ReadVin profile, or whether the relevant D2 baud is inherited.
* Actual SQL row joins, GetScript runtime selection, original XML/SQL
  semantics, target VIN, CAN/ISO-TP frames and ECU discovery.

Keep `B9FBFrameCount=0`, real vehicle data private, and `main`, releases,
SecurityAccess, coding and ECU programming untouched.
