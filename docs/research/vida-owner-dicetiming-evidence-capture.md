# Owner-local DiceTiming evidence capture for VIDA Analyzer

This runbook describes an **optional, operator-triggered**, read-only
DiceTiming *metadata* check on an owner-controlled Windows/VMware guest. The
research PR does **not** run commands on VMware, install SQL Server, attach
an MDF, modify VIDA, send logs to GitHub, or schedule CI jobs.

## Prerequisites

- A reviewed checkout of the feature branch and Python 3; for SQL Server,
  locally installed `pyodbc` and the appropriate ODBC driver
- An existing DSN `VIDA_READONLY` pointing at a lawfully accessible instance
  containing the logical database `DiceTiming`
- A SQL principal with **actually enforced read-only permissions** and
  sufficient metadata visibility for `sys.tables`, `sys.columns`,
  `sys.foreign_keys`, `sys.foreign_key_columns`, and `sys.index_columns`
- A trusted SQL Server certificate (`TrustServerCertificate=No`). The
  analyzer intentionally refuses implicit insecure TLS bypass
- A private directory **outside the checkout**; never upload original MDF,
  original SQL rows, XML, ECU traffic, DSN credentials, or HMAC keys

The `ApplicationIntent=ReadOnly` connection property is not an
authorization mechanism. Validate effective database permissions separately.
No `CREATE`, `ATTACH`, `RESTORE`, `INSERT`, `UPDATE`, `DELETE`, or
vehicle programming commands are required for this stage.

## First owner-only metadata run

Use a new filename on every attempt; the analyzers never overwrite evidence.
From the repository root, in the owner-controlled PowerShell shell:

~~~powershell
$env:VIDA_SQLSERVER_DSN = "VIDA_READONLY"
$privateRoot = Join-Path $env:USERPROFILE "VIDA-evidence-private"
New-Item -ItemType Directory -Force -Path $privateRoot | Out-Null
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$report = Join-Path $privateRoot "dicetiming-sql-$stamp.redacted.json"
$manifest = Join-Path $privateRoot "dicetiming-sha-$stamp.json"
$summary = Join-Path $privateRoot "vida-summary-$stamp.redacted.json"

py -3 emulator/tools/vida_dicetiming_catalog.py --backend sqlserver --output "$report"
if ($LASTEXITCODE -ne 0) { throw "DiceTiming metadata-only check failed" }

py -3 emulator/tools/build_vida_redacted_manifest.py --dicetiming-report "$report" --output "$manifest"
if ($LASTEXITCODE -ne 0) { throw "Redacted manifest creation failed" }

py -3 emulator/tools/vida_evidence_summary.py --dicetiming-report "$report" --bundle-manifest "$manifest" --output "$summary"
if ($LASTEXITCODE -ne 0) { throw "Evidence summary failed" }
~~~

All artifacts stay in the owner-local private directory. The manifest
contains only fixed schema fields and SHA-256 digests of the original bytes
of **already-redacted JSON reports**, not report contents or source paths.
Its file permissions are owner-only on POSIX; on Windows, actual access is
controlled by the containing directory ACL. Check folder permissions before
moving any file.

For a separately generated **owner-reviewed metadata-only**
`DiceTiming.sqlite` exporter copy, first generate its redacted report via
`vida_dicetiming_catalog.py --backend sqlite-export --folder <private-dir>
--output <new-json>`, then generate a pairwise count/HMAC comparison using
`compare_vida_dicetiming_catalog.py`. Include
`--dicetiming-compare-report <comparison-json>` in both the manifest
generator and the summary, using new output paths. The report input-key
sets must match the manifest exactly.

The optional `VIDA_DICETIMING_HMAC_KEY` is a private random 256-bit key
that should be identical across two catalog captures when comparing visible
normalized table and column names. It is not included in any redacted file.
The SHA-256 manifest is not a signature or installation attestation.

## Required acceptance interpretation

The generated summary may pass `dice_timing_metadata`,
`dice_timing_visible_fk_catalog`, and `report_bytes_binding` for
structurally consistent inputs. None establishes actual DiceTiming timing
values, verified associations with `InitHw` or `ECU Profile`, selected
XC90 V8 MY2009 data, D2 baud, executed GetScript/ReadVin, accepted VIN,
J2534 hardware results or replay permission.

Keep `same_installation_provenance_verified=false` and the runtime gates
`not_tested`. A checksum proves only the bytes match the owner's manifest.
If you need to share a result for review, manually inspect the **summary**
first. Do not share original reports or database files automatically.

## Local software verification vs owner evidence

The manifest generator was verified with 12 new isolated synthetic tests,
and the focused research suite completed **110/110 PASS** with
`compileall` PASS on Python 3.13.5. These tests used generated fixtures,
not original VIDA. They did **not** run owner-only VMware, actual SQL Server
or real automotive hardware. Exact-head CI and full repository tests remain
separate acceptance requirements.
