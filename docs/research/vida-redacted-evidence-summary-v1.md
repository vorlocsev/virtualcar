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

## Seven evidence gates

| Stage | Meaning of `passed` |
| --- | --- |
| `catalog_metadata` | A supplied metadata-only catalog report passed the summary's structural preflight; original catalog provenance is not verified |
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
The analyzer never produces actual runtime, target XC90, J2534, VIN or
replay approval from a static input.

The loader rejects symlinks, oversized reports, duplicate JSON keys,
nonfinite numbers, schema mismatches, boolean-as-count values, empty
ReadVin reader/identity graphs and attempts to promote upstream negative
runtime flags. Errors never print private paths or values.

## Validation and remaining work

Local isolated Python execution of the new ten synthetic tests:
**10/10 PASS**; `compileall` PASS. This does not certify the entire
repository, the exact GitHub PR HEAD on Windows, original VIDA SQL Server,
T111/T122/InitHw rows, effective GetScript, VIDA/SectorV VIN acceptance,
or physical J2534.

Next: cross-report source provenance and bounded, explicitly evidenced
profile/service/ReadVin joins. Continue to keep `B9FBFrameCount=0` and
replay disabled until real, authorized, read-only client evidence exists.
No `main`, J2534 runtime or binary releases changed in this step.
