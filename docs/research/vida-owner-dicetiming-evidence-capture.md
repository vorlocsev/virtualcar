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


## Optional CarCom Profile / InitHw evidence bridge

If the same owner-controlled environment also produced the separate
metadata-only `vida_unified_analyzer.py` catalog report for
CarCom/DiagSwdlRepository/BaseData, use the research-only
[Profile/InitHw shape bridge](vida-profile-init-metadata-bridge.md).
Run its script locally, then pass **all three** redacted reports
(`--catalog-report`, `--dicetiming-report`, and
`--profile-init-report`) to the manifest builder and evidence summary.
The bridge report's SHA-256 fields must correspond exactly to the two
source report bytes. This prevents accidental reuse of old source files;
it cannot authenticate the original SQL Server installation or imply
a true `InitHw` row association.

The three additional master gates distinguish passing **column-shape**
hypotheses from `dicetiming_to_carcom_row_join=Not tested`.
Even when CarCom contains all known profile/init columns, the owner still
must verify actual profile selection, priority/inheritance, read-only
source rows and VIN acceptance separately before using any timing value.

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

## Optional independent static Profile/Service → ReadVin coverage

When the owner also has a reviewed redacted static ReadVin crosscheck,
run `vida_profile_readvin_static_coverage.py` against the redacted
`catalog`, `dicetiming`, `profile_init` and `readvin` inputs.
Then include its `--profile-readvin-coverage-report` in **both**
the manifest generator and the master evidence summary.

The output is a source-byte-bound coverage inventory, **not** evidence
that a GetScript selection corresponds to the profiled ECU. For exact
PowerShell commands and status definitions, see
[Profile-to-ReadVin static coverage](vida-profile-readvin-static-coverage.md).
The `profile_to_readvin_join`, `getscript_runtime_selection` and
`client_vin_acceptance` gates remain Not tested without new runtime
and row-level evidence. Synthetic suite: 157/157 PASS;
actual VMware/original VIDA not run for this extension.

## Основной режим исследования: исходные данные без обезличивания

По решению владельца проекта оригинальные поля и значения VIDA **не
обезличиваются при техническом анализе**. Приведённый выше процесс
создания редуцированных отчётов оставлен для совместимости с ранними
статическими acceptance-gates, но не является обязательной заменой
оригинальных данных.

Для чтения настоящих строк и идентификаторов из выбранной таблицы
SQL Server используйте [новый локальный инструмент для оригинальных
данных](vida-original-data-no-anonymization.md). Он не отправляет
исходные строки в GitHub или CI. Источники, тайминги, VIN и содержимое
таблиц в локальном JSON не маскируются.
