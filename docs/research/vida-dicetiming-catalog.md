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
