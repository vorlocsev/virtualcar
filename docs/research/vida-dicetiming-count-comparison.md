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
