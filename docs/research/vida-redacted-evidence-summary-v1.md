# VIDA Analyzer: redacted evidence summary v1

Status: source-only research proposed for `development` via a separate PR. The
summary consumes **existing, already-redacted JSON reports**. It does not
open original VIDA databases, XML, trace files, or a vehicle adapter.

## Inputs

Optional inputs (at least one required):

- `--catalog-report`: output of
  `emulator/tools/vida_unified_analyzer.py`
  (`virtualcar-vida-unified-catalog-v1`).
- `--compare-report`: output of
  `emulator/tools/compare_vida_catalog_reports.py`
  (`virtualcar-vida-catalog-compare-v1`).
- `--readvin-report`: output of
  `emulator/tools/audit_vida_redacted_consistency.py`
  (`virtualcar-vida-redacted-readvin-crosscheck-v1`).
- `--dicetiming-report`: optional independent `DiceTiming` metadata-only
  output of `emulator/tools/vida_dicetiming_catalog.py`
  (`virtualcar-vida-dicetiming-metadata-v1`), see
  [DiceTiming scope](vida-dicetiming-catalog.md).
- `--dicetiming-compare-report`: optional aggregate-only comparison of
  two redacted DiceTiming SQL Server/SQLite catalogs
  (`virtualcar-vida-dicetiming-count-compare-v1`), see
  [DiceTiming count comparison](vida-dicetiming-count-comparison.md).
- `--profile-init-report`: optional CarCom Profile / InitHw static shape
  summary from `vida_profile_init_bridge.py`, bound to the exact
  `--catalog-report` and `--dicetiming-report` file bytes.
  See [metadata bridge](vida-profile-init-metadata-bridge.md).

Use only owner-controlled, redacted reports. Source reports may originate
from **different machines or installations**; supplying multiple reports
does not prove common provenance or a join between them.

## Local command

~~~powershell
py -3 -m unittest discover -s emulator/tests -p test_vida_evidence_summary.py -v
py -3 -m compileall -q emulator/tools/vida_evidence_summary.py emulator/tests/test_vida_evidence_summary.py
py -3 emulator/tools/vida_evidence_summary.py --catalog-report "E:\VIDA-private\unified-sqlite.redacted.json" --compare-report "E:\VIDA-private\catalog-compare.redacted.json" --readvin-report "E:\VIDA-private\readvin-consistency.redacted.json" --output "E:\VIDA-private\vida-summary-001.redacted.json"
~~~

The output must be **new** and outside Git, and is opened exclusively.
Only fixed stage labels, categorical statuses and bounded aggregate counts
are copied to the summary. Source paths, identifiers, raw VIN, proprietary
SQL/XML, ECU frames and unknown fields are not emitted.

## Optional source-byte binding (SHA-256)

The `--bundle-manifest` option confirms that the **already-redacted**
input report bytes match the SHA-256 values in an owner-local manifest.
It does **not** certify that the manifest is trustworthy, that files came
from the same VIDA installation or that a source runtime executed.
There is no signature or trusted authority. Without the manifest, this
gate remains `not_tested`.

An owner-only manifest example for one report is:

~~~json
{
  "schema_version": "virtualcar-vida-redacted-report-bundle-v1",
  "scope": "redacted_report_bytes_only",
  "reports": {
    "readvin": "<64-character lowercase SHA-256 of redacted ReadVin JSON>"
  },
  "same_installation_provenance_verified": false,
  "runtime_evidence_verified": false
}
~~~

Replace the placeholder with the exact SHA-256 digest of the redacted
input JSON **including its original whitespace/newlines**. Use the
`catalog`, `comparison`, `readvin`, optional `dicetiming`,
`dicetiming_compare`, and `profile_init` keys
for inputs actually supplied, no others. A digest is never included in the aggregate output.

Run:

~~~powershell
py -3 emulator/tools/vida_evidence_summary.py --readvin-report "E:\VIDA-private\readvin-consistency.redacted.json" --bundle-manifest "E:\VIDA-private\bundle-manifest.json" --output "E:\VIDA-private\summary-bound-001.redacted.json"
~~~

### Generate the SHA-256 manifest automatically

For owner-reviewed reports, the optional helper
`emulator/tools/build_vida_redacted_manifest.py` generates the fixed
`virtualcar-vida-redacted-report-bundle-v1` manifest from **the exact
bytes also parsed by this analyzer**. It rejects malformed or forged
source evidence before creating the manifest, and its output is created
exclusively outside Git.

Example for an already-redacted DiceTiming SQL Server report:

~~~powershell
py -3 emulator/tools/build_vida_redacted_manifest.py --dicetiming-report "E:\VIDA-private\dicetiming-sql.redacted.json" --output "E:\VIDA-private\dicetiming-sha-001.json"
py -3 emulator/tools/vida_evidence_summary.py --dicetiming-report "E:\VIDA-private\dicetiming-sql.redacted.json" --bundle-manifest "E:\VIDA-private\dicetiming-sha-001.json" --output "E:\VIDA-private\summary-bound-002.redacted.json"
~~~

Add `--catalog-report`, `--compare-report`, `--readvin-report`
and `--dicetiming-compare-report` consistently to **both commands**
when those sources are available. The SHA-256 manifest contains no source
paths or original report content and is **not a source attestation**.
See the [Windows VMware owner-local runbook](vida-owner-dicetiming-evidence-capture.md).
An isolated local Python 3.13.5 run completed **110/110 synthetic
tests PASS** (12 new tests plus 98 existing), `compileall` PASS.
Exact Git blob match was verified for the manifest tool and tests.
No actual VIDA or VMware run is implied by these results.

The manifest must be owner-controlled and separate from the generated
output. Inputs are read once for **both** SHA-256 and JSON parsing.
Mismatched digests, forged positive provenance/runtime flags, invalid
keys, duplicate file aliases and overlong manifest files fail closed.
A manifest cannot promote `profile_to_readvin_join` or any runtime gate.

## Fifteen evidence gates

| Stage | Meaning of `passed` |
| --- | --- |
| `report_bytes_binding` | Optional manifest proves only supplied redacted file bytes match their declared SHA-256; no origin/trust proof |
| `catalog_metadata` | A supplied metadata-only catalog report passed the summary's structural preflight; original catalog provenance is not verified |
| `dice_timing_metadata` | A supplied fourth database metadata report passed DiceTiming identity and aggregate shape preflight; no timing values or mapping verified |
| `dice_timing_visible_fk_catalog` | Optional SQL Server-only visible FK constraint inventory is structurally valid; no row joins, original timing values or complete metadata visibility proven |
| `dice_timing_count_comparison` | Two already-redacted reports agree on table and column totals only; no schema equivalence or same-origin proof |
| `dice_timing_visible_schema_hmac` | Optional two-source HMAC match for the visible normalized DiceTiming catalog using the same owner-private key; no source attestation or runtime proof |
| `carcom_profile_init_shape` | Fixed CarCom Profile/InitHw column-shape hypotheses agree with the bound redacted catalog; not actual source-row joins |
| `carcom_service_protocol_shape` | Fixed CarCom Service/Protocol/Bus column-shape hypotheses agree with the bound redacted catalog; not actual speed or selected vehicle |
| `dicetiming_to_carcom_row_join` | Always Not tested; the independent DiceTiming catalog contains no verified cross-database row relationship |
| `catalog_shape_comparison` | A supplied comparison report declares no table/column/edge shape disagreement; it is not a verified same-installation join |
| `readvin_static_graph` | A supplied redacted v2/v3 crosscheck declares seven consistent counters, nonempty ReadVin/identity nodes and identity calls |
| `profile_to_readvin_join` | Always `not_tested` until independently proven |
| `getscript_runtime_selection` | Always `not_tested` |
| `j2534_correlated_exchange` | Always `not_tested` |
| `client_vin_acceptance` | Always `not_tested` |

`failed` currently means the supplied **catalog comparison report**
contains differences. Invalid or contradictory source reports reject the
entire operation without writing a new summary. Missing reports are
`not_tested`. The output records non-passing stages in `open_blockers`.
A source-byte binding is useful for repeated review, not a signature or installation attestation.
The analyzer never produces actual runtime, target XC90, J2534, VIN or
replay approval from a static input.

The loader rejects symlinks, oversized reports, duplicate JSON keys,
nonfinite numbers, schema mismatches, boolean-as-count values, empty
ReadVin reader/identity graphs and attempts to promote upstream negative
runtime flags. Errors never print private paths or values.

## Validation and remaining work

The initial isolated synthetic suite passed **10/10** and `compileall`.
The expanded suite now contains **17 synthetic test methods**. An isolated
local execution on Python 3 passed **17/17**, zero errors/failures, with
`compileall` PASS on both files. The locally executed file contents match
the exact GitHub PR blobs, checked using `git hash-object`:
- Tool: `8fb540c8a6c67a75d6f2fba88ee468bfd9f114a9`
- Tests: `feaa0822933bb8e9471c3e8ec964d3db60f34343`

The first expanded run had **2 test expectation failures**, because
the earlier tests hardcoded seven stages and indexed the old gate ordering.
Both tests were corrected to reference stage IDs and the declared stage set;
the unchanged production byte-binding implementation then passed 17/17.
**Exact-head Windows VMware CI, the full repository test matrix and
original VIDA data remain untested** for this PR. This does not certify the entire
repository, the exact GitHub PR HEAD on Windows, original VIDA SQL Server,
T111/T122/InitHw rows, effective GetScript, VIDA/SectorV VIN acceptance,
or physical J2534.

### DiceTiming extension (2026-11-10)

A separate opt-in SQL Server / SQLite metadata scope now inventories
`DiceTiming` without altering legacy three-database reports. The new
aggregator gate is `dice_timing_metadata`; it is a **schema evidence**
classification, not a D2, ignition, timing, ECU or VIN acceptance gate.
The bundle SHA-256 manifest also supports exact `dicetiming` report bytes.

The owner-local isolated synthetic suite passed **30/30 tests** across
`test_vida_evidence_summary.py` and `test_vida_dicetiming_catalog.py`,
zero failures/errors; `compileall` PASS. These are not original VIDA
or exact-head VMware CI tests. The exact locally tested GitHub blobs are:
- DiceTiming tool: `45f8748d4ebb2ebeed2edb377b97f64955898ca7`
- DiceTiming tests: `0a29b236750aa84c75c2d9eae8da1ecdd2695f44`
- Updated summary tool: `814218507ebd645f0babe53126904944e00e6bb6`

For a fourth input, add `--dicetiming-report` and an owner-local
redacted JSON path to the existing summary command. If a hash manifest is
provided, include `dicetiming` in its exact report-key set.

**Still not confirmed:** original DiceTiming SQL Server metadata, matching
original SQLite exporter, selected profile timing rows, actual D2 baud,
VIDA GetScript selection, client VIN acceptance, physical J2534, or full
repository CI. The fourth report cannot establish cross-installation
provenance or rewrite previously unverified gates.

### DiceTiming count comparison extension

An independent, optional read-only comparator now accepts paired redacted
SQLite and SQL Server `DiceTiming` metadata reports. Differences between
aggregate table and column counts yield a `failed` summary gate; matching
counts yield a `passed` **counts-only** gate. Both reports remain
unattributed to a common installation and no source timing rows are read.
The SQL Server FK count is informational only, since the SQLite export has
no declared FK metadata.

On the local isolated Python 3.13.5 research workspace, **46/46**
synthetic tests passed, zero failures/errors; `compileall` PASS across
the four tool and three test modules, including the comparator and summary
integration. The full repo suite and exact-HEAD VMware CI are still
unverified.

Next: owner-local original DiceTiming schema evidence and source provenance,
then bounded, explicitly evidenced profile/service/ReadVin joins. Continue to keep `B9FBFrameCount=0` and
replay disabled until real, authorized, read-only client evidence exists.
No `main`, J2534 runtime or binary releases changed in this step.

### Optional HMAC comparison gate (2026-11-10)

When a pair of DiceTiming reports is generated with the same private
`VIDA_DICETIMING_HMAC_KEY`, the comparator can classify a visible catalog
fingerprint as matched, mismatched or not tested. The summary records this
as a separate `dice_timing_visible_schema_hmac` stage; absent fingerprints
leave it not tested. This does not prove source origin, complete metadata
visibility, original timing parameters, ECU profile joins, D2 baud or
actual diagnostic execution.

**Local isolated validation:** 58/58 Python 3.13.5 synthetic tests PASS,
`compileall` PASS. The locally tested production/test blobs match current
GitHub sources for this change. Exact-head owner-only Windows VMware CI,
real VIDA and physical J2534 are not verified. See
[DiceTiming comparison](vida-dicetiming-count-comparison.md).

### DiceTiming SQL Server FK metadata extension (2026-11-10)

An additional gate, `dice_timing_visible_fk_catalog`, accepts only
validated aggregate counts from `sys.foreign_keys` joined with
`sys.foreign_key_columns`. SQL Server constraints are counted once per
constraint even for composite keys, and disabled, untrusted and
self-referencing counts remain separate. The SQLite metadata exporter has
no such catalog and correctly leaves this gate `not_tested`.

No actual relational rows, source SQL definitions or original timing
parameters were inspected. The gate's `passed` result is strictly a
metadata syntax/consistency pass, **not** a verified FK join, D2 baud,
selected ECU profile, ReadVin runtime or VIN acceptance.

The isolated local Python 3.13.5 test suite passed **70/70** synthetic
tests, with `compileall` PASS. The current changed GitHub blobs match
the locally executed source/test files. Exact-head owner-only VMware CI
and original VIDA/J2534 were not tested for this revision.

### CarCom Profile / InitHw metadata bridge (2026-11-10)

The optional static bridge now consumes the already-redacted unified
CarCom catalog together with an independently redacted DiceTiming catalog
and tests only the **existing research-hint column shapes**. It binds
the two source JSON files by exact SHA-256 values and rejects missing or
changed inputs when their output is included in the master summary.
A manifest can include `profile_init` alongside `catalog` and
`dicetiming`, providing another byte-integrity check but not
authenticity or a same-installation guarantee.

The three new stages `carcom_profile_init_shape`,
`carcom_service_protocol_shape`, and
`dicetiming_to_carcom_row_join` have explicitly different semantics:
the first two can pass **shape-only** checks; the third always remains
Not tested. Even when all expected columns are present, the data-level
relationship, inherited InitHw setting, selected ECU profile, actual
D2 baud, executed ReadVin and accepted VIN remain unknown.

**Local verification:** 127/127 Python 3.13.5 isolated synthetic tests
PASS, `compileall` PASS. Test sources used a local-only transcription of
the existing published research-hint constants, not original VIDA data.
No exact-head Windows VMware CI, original 2015A SQL Server data, physical
J2534 or real client VIN acceptance was executed.
