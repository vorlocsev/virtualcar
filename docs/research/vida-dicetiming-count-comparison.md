# VIDA DiceTiming aggregate-only SQL Server / SQLite comparison

Research extension to [DiceTiming metadata scope](vida-dicetiming-catalog.md).
This optional command compares **only** two already-redacted reports produced
by `emulator/tools/vida_dicetiming_catalog.py`. It never connects to VIDA,
reads original timing data, or opens SQL/SQLite databases.

## Local commands

First generate the separate reports from reviewed owner-local sources, using
the documented DiceTiming metadata collector, then compare the outputs:

~~~powershell
py -3 emulator/tools/compare_vida_dicetiming_catalog.py --sqlite-report "E:\VirtualCar\VIDA-private\dicetiming-sqlite.redacted.json" --sqlserver-report "E:\VirtualCar\VIDA-private\dicetiming-sqlserver.redacted.json" --output "E:\VirtualCar\VIDA-private\dicetiming-count-compare-001.redacted.json"
py -3 emulator/tools/vida_evidence_summary.py --dicetiming-compare-report "E:\VirtualCar\VIDA-private\dicetiming-count-compare-001.redacted.json" --output "E:\VirtualCar\VIDA-private\vida-summary-counts-001.redacted.json"
~~~

A new, exclusive output path outside the Git checkout is mandatory. Optional
bundle manifest integration uses the `dicetiming_compare` key and the exact
lowercase SHA-256 of the redacted comparison file.

## What is compared

The input pair must refer to the fixed logical database `DiceTiming`, with
exact reporter schema/status and complementary `sqlite-export` versus
`sqlserver` backends. It checks bounded nonzero table totals, bounded
column totals, and strictly negative evidence flags. It compares:

- total number of user tables
- total number of user-table columns

The SQL Server **declared foreign-key column count** is recorded separately
as an aggregate. The SQLite metadata exporter does not carry FK constraints,
so the comparison **never** treats SQLite FK count zero as an actual database
claim or checks FK parity.

`aggregate_counts_equal=true` means **only that the two pairs of integers
match**. Different schemas can produce exactly the same counts. Matching
totals do not establish same-installation provenance, timestamps, source
table names, FK joins, original timing values, ECU profile mapping, D2 baud,
GetScript runtime, J2534 delivery, VIN acceptance or replay permission.

In the unified summary, the new `dice_timing_count_comparison` gate is
`passed` for matching aggregate counts, `failed` for differing counts and
`not_tested` when missing. The gate has **no causal/runtime implication**.
Malformed source reports, forged true acceptance flags, duplicate JSON keys,
nonfinite numbers, overlarge inputs and unsafe paths fail closed before
writing any output.

## Verification and still-open evidence

On an isolated Python 3.13.5 workspace containing the modified DiceTiming
and evidence-summary modules, **46/46 synthetic tests PASS** (12 new count
comparison checks, four new integration checks, and the 30 existing tests),
with `compileall` PASS. Source/test Git blob SHA-1 values matched
the exact GitHub PR files when committed.

**Not tested:** original VIDA 2015A DiceTiming source tables, original
SQL Server/SQLite snapshot equivalence, selected XC90 V8 profile, D2
timing and baud, physical adapter or client VIN, and full repository
exact-HEAD Windows VMware CI. Do not change `B9FBFrameCount=0` or enable
replay from these counts.

## Optional private keyed visible-schema comparison (2026-11-10)

For a stricter **opt-in** comparison, use the same privately held 256-bit
random HMAC key when generating both DiceTiming reports. In the local
PowerShell session, generate the key once and keep the same value for both
collector executions:

~~~powershell
$env:VIDA_DICETIMING_HMAC_KEY = py -3 -c "import secrets; print(secrets.token_hex(32))"
~~~

Run the SQLite exporter and SQL Server catalog commands documented in
[DiceTiming metadata scope](vida-dicetiming-catalog.md), without replacing
or re-generating the key between them. The variable contains 64 lowercase
hexadecimal characters encoding 32 random bytes. Keep it outside Git,
terminal transcripts, reports and logs. Clearing the environment variable
restores the legacy counts-only report format.

The collector computes an HMAC-SHA-256 over a canonical sorted set of
**visible case-folded** schema/table names and column names. The output
contains the digest and fixed `visible_schema_hmac_scope`, but never the
secret key, original identifiers or data values. The comparison rejects
incorrectly formatted fingerprints, a partial one-sided digest pair,
and claims that equal digests accompany contradictory table/column counts.

The new comparison category `visible_schema_hmac_comparison` is:

- `matched`: both HMACs match using the supplied key and normalization;
  this is evidence only of agreement of the visible normalized inventory
- `mismatched`: digests differ, potentially because of different keys,
  metadata visibility, source schema differences, or nonmatching exports
- `not_tested`: both reports omitted the optional digest

The unified summary independently exposes the
`dice_timing_visible_schema_hmac` gate as passed/failed/not_tested
according to those categories. **Matched is not proof** of common
installation origin, a complete SQL catalog, case-sensitive identifier
equivalence, original row relationships, timing profile assignment, D2
baud, ECU response, client VIN or successful VIDA diagnostics. For these
reasons `schema_equivalence_verified=false` and all runtime acceptance
flags remain false. Without the original data and actual SQL metadata
permissions, even a valid HMAC comparison is not a final acceptance gate.

The isolated local Python 3.13.5 suite passed **58/58 synthetic tests**
(46 earlier plus 12 keyed HMAC regressions) with `compileall` PASS.
All three changed production files and the added test source have exact
GitHub blob SHA matching the locally executed files:
`218557bdbea6aa808699b4a2016a792aa3c463ad`,
`b80b213175328b0fb1d28d2919d855b802536f0a`,
`f70daf59daa568f27afeab18b8a9ca66b12d18c7`,
`52bae7aef49cdbec45b3b8f1f61c72dadf066d20`.
Exact-HEAD Windows VMware CI and actual VIDA databases remain untested.

## Independent SQL Server FK metadata coverage

The DiceTiming source collector now optionally reports counts of visible
SQL Server FK **constraints**, including disabled, untrusted and
self-referencing constraints. Composite foreign keys are grouped as one
constraint while the legacy `declared_fk_column_count` still counts
individual FK column pairs. The SQLite exporter contains no corresponding
constraint metadata. Therefore neither the table/column count comparison
nor the HMAC visible-table/column signature can prove FK equivalence.
These optional FK aggregates are reviewed only in the separate unified
summary gate `dice_timing_visible_fk_catalog`, not in this comparator.

Even if the SQL Server FK catalog contains zero visible entries, metadata
visibility is not proved complete; neither SQL cross-database references
nor runtime timing/profile associations are established by these counts.
