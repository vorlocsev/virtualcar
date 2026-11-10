# VIDA DiceTiming: read-only catalog scope

Research stage, 2026-11-10. This module is an optional, independent **fourth
database input** to the VIDA Analyzer's redacted evidence summary. It does
not change the existing three-database SQL/SQLite analyzer or require that
existing `CarCom`, `DiagSwdlRepository` and `BaseData` exports be replaced.

The owner's original data inventory recorded a small
`DiceTiming_Data.MDF`, but this source file is **not opened** by the
module. The real owner installation's contents, table relationships and
timing parameters have **not been examined** in this change.

## Supported inputs

`emulator/tools/vida_dicetiming_catalog.py` has two backends:

1. `sqlite-export`: require a separate `DiceTiming.sqlite` **metadata-only**
   exporter snapshot containing the ordinary main-schema tables
   `_vida_meta`, `_vida_tables`, `_vida_columns`. Require exact exporter
   identity `schema_version=virtualcar-vida-offline-sqlite-v1`,
   `source_database=DiceTiming`, `scope=all_user_tables`. Reject malformed
   schemas, zero-column source tables, missing files, symlinks, and active
   `-wal`, `-shm`, `-journal` companions before inspection. Do not query
   any original application table or its timing values.
2. `sqlserver`: optional owner-local `pyodbc` System DSN with Windows
   authentication. Require database identity `DB_NAME() = DiceTiming`,
   `Encrypt=Yes`, `TrustServerCertificate=No`, 8-second login and query
   timeouts, and an actual read-only SQL principal. Only fixed
   `sys.tables`, `sys.columns`, `sys.schemas` and
   `sys.foreign_key_columns` metadata queries are allowed. No application
   rows, function calls, stored procedures or SQL definitions are read.

The JSON contains only fixed fields and aggregate **table count, column
count and declared FK column count**. For SQLite, FK count 0 means
**not exported**, not proof that the original database has no FKs.
Unknown proprietary names, values, VIN, ECU data and connection details
are never written into JSON or diagnostic errors. Empty or partially
invisible metadata catalogs fail closed where detectable, but nonempty
catalogs still do not prove complete metadata permissions.

## Owner-local commands

Run tests first from the reviewed checkout:

~~~powershell
py -3 -m unittest discover -s emulator/tests -p 'test_vida_dicetiming_catalog.py' -v
py -3 -m unittest discover -s emulator/tests -p 'test_vida_evidence_summary.py' -v
py -3 -m compileall -q emulator/tools/vida_dicetiming_catalog.py emulator/tools/vida_evidence_summary.py emulator/tests/test_vida_dicetiming_catalog.py
~~~

For a clean, existing owner-local metadata export:

~~~powershell
py -3 emulator/tools/vida_dicetiming_catalog.py --backend sqlite-export --folder 'E:\VirtualCar\VIDA-private' --output 'E:\VirtualCar\VIDA-private\dicetiming-001.redacted.json'
~~~

Or for an explicitly reviewed SQL Server read-only connection:

~~~powershell
$env:VIDA_SQLSERVER_DSN = 'VIDA_READONLY'
py -3 emulator/tools/vida_dicetiming_catalog.py --backend sqlserver --output 'E:\VirtualCar\VIDA-private\dicetiming-sql-001.redacted.json'
~~~

Integrate the new output alongside the existing three-database report,
catalog comparison, ReadVin graph report, or **by itself**:

~~~powershell
py -3 emulator/tools/vida_evidence_summary.py --dicetiming-report 'E:\VirtualCar\VIDA-private\dicetiming-001.redacted.json' --output 'E:\VirtualCar\VIDA-private\vida-summary-with-dicetiming-001.redacted.json'
~~~

For multi-source runs add the existing `--catalog-report`,
`--compare-report` and `--readvin-report` options. When using the
optional SHA-256 bundle manifest, include the exact supplied
`"dicetiming": "<lowercase 64-digit SHA-256>"` digest in
`reports`. A hash matches bytes only, **not same-installation provenance**.

## Optional SQL/SQLite redacted count comparison

After generating both independent, already-redacted `DiceTiming` metadata
reports, use [the aggregate-only comparison](vida-dicetiming-count-comparison.md)
to compare table and column totals without reading original data. The
`--dicetiming-compare-report` input adds a separate gate to the evidence
summary; matching totals are not a verified identical schema or timing link.

## Optional keyed schema fingerprint

Use the same owner-private random 256-bit key in
`VIDA_DICETIMING_HMAC_KEY` when generating both the SQL Server and SQLite
metadata reports, if stronger visible-schema comparison is needed. The
collector then emits only `visible_schema_hmac_sha256` and a fixed scope
label, without original table/column names or the key. A key is optional;
reports without it preserve the existing format. See
[the comparison documentation](vida-dicetiming-count-comparison.md)
for command examples and strict evidence limits.

## Evidence boundary

The aggregate gate `dice_timing_metadata` is `passed` only for accepted
structural **metadata**; absent inputs stay `not_tested`.
`dice_timing_profile_mapping_verified=false` and independent D2 baud,
ReadVin execution, accepted VIN, physical J2534 and replay flags remain
false. Never infer timing values, CAN bitrate, an actual XC90 V8 profile,
or a CEM response from `DiceTiming` catalog presence.

This step does **not** change J2534 runtime, B9FB frame behavior, main,
releases or ECU coding. No original VIDA data, exact-HEAD VMware CI,
or physical hardware has been tested in this change.

## Visible SQL Server foreign-key catalog (2026-11-10)

SQL Server mode now reads additional fixed **system catalog metadata** only:
`sys.foreign_keys.object_id`, `is_disabled` and `is_not_trusted`,
joined to existing `sys.foreign_key_columns`. No original application
records, source SQL definitions or timing values are retrieved. The analyzer
groups composite FK column pairs by constraint ID before counting, avoiding
the error of treating a two-column FK as two distinct constraints.

The additional optional `visible_fk_catalog` object includes only fixed
scope and aggregated counts:

- `constraint_count`
- `disabled_constraint_count`
- `untrusted_constraint_count`
- `self_referencing_constraint_count`

`complete_metadata_visibility_verified=false` and
`referential_rows_verified=false` are unconditional. FK constraint IDs,
source/target table names, column names and actual timing values never leave
the local analysis process. Contradictory composite-FK metadata, duplicate
column pairs, invalid bit flags and missing referenced catalog columns fail
closed.

SQLite metadata exports **do not include this object**, because their
exporter does not retain SQL Server FK definitions. Legacy SQL Server
redacted reports without this optional object remain compatible.
In the unified summary, `dice_timing_visible_fk_catalog` is **passed**
only if a supplied SQL Server report has structurally valid visible FK
metadata; otherwise it is `not_tested`. Passed here is not a claim that
any FK is trusted/enabled or that the catalog is complete.

An isolated local Python 3.13.5 focused suite passed **70/70 synthetic
tests**, `compileall` PASS (12 new FK-specific tests). Exact Git blobs
were compared against the locally tested files:
- catalog `1168a9d5df9a03e7cd6c04ff1eb87aec4beead0c`
- summary `bb7884dfaaf6e09e0219ad55f73a42a8512af5ed`
- FK tests `57662f5ab8e5d13392513ab747a8c741e98ac458`
- summary tests `5f97880c6eb15a8a59b2d43a64a854851eaf6039`

No source-original VIDA 2015A tables, actual `DiceTiming` MDF, VMware
exact-head CI, D2 baud or physical J2534 were inspected.

### Composite-key ordinal validation (2026-11-10)

The SQL Server FK metadata query now also reads the documented
`sys.foreign_key_columns.constraint_column_id` ordinal (1 through n)
for each column of a foreign-key constraint. The collector rejects:

- ordinal zero, negative, boolean, noninteger and values above SQL
  Server's 32-column FK limit;
- duplicated ordinal positions for one FK;
- a missing initial ordinal or an interior gap;
- repeated source or repeated referenced columns in one FK;
- noncanonical row widths and inconsistent constraint identities.

Rows from the fixed query may arrive in any order. Accepted ordinals must
form the set `1..N` per FK even when returned out of order. The redacted
output remains unchanged: it contains only counts and negative evidence
flags, never FK IDs, ordinals, private table/column names or SQL definitions.

**Limit:** a truncated *suffix* can still look like `1..N` if the
expected total number of members is not independently available. This
preflight therefore does not establish complete metadata visibility or
correct database-level referential integrity.

Six new regression methods extend the isolated focused suite to
**76/76 PASS** on Linux Python 3.13.5; `compileall` PASS.
Verified local Git blobs and committed GitHub blobs match exactly:
- collector: `eb2f7fa27d0480ad9b6fb849179a8c624735c493`
- FK tests: `06c7e34785a944a208527daae8f330e5c71421ca`

No original VIDA, VMware runner, client VIN acceptance or J2534
hardware was used for this change.
