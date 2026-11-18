# B3A303 — Original VIDA: manual VIN versus virtual J2534 ReadVin

**Date:** 2026-11-18. **Scope:** research-only continuation of B3A302 Draft #366.

## Motivation and evidence boundary

In the earlier original VIDA session (B3A275, see [Draft #357](https://github.com/vorlocsev/virtualcar/pull/357)), J2534 delivered `0x726 22 F1 14` and `0x72E 62 F1 14 + VIN17`, but VIDA then showed `The VIN can not be decoded on selected Partner Group`. That evidence does **not** determine whether the actual problem is VIN/Partner Group lookup, a malformed application F114 payload, original `ResponseHandler` / `AddVIN`, caching or another GUI path.

Research tools B3A298–302 produce **offline catalog candidates**, not original VIDA GUI acceptance. B3A303 adds **no simulated ECU reply**. It correlates two owner-recorded, independent GUI observations and securely checks the existence + SHA-256 of each locally retained source screenshot or log. It does not read GUI screenshots or interpret native adapter traces. A matching SHA-256 proves file integrity only.

The current original VIDA manual VIN A/B and J2534 A/B **have NOT been executed in this stage**. Empty/not-tested records remain `MISSING_OWNER_GUI_OBSERVATION`.

## New files

- `emulator/tools/vida_readvin_ab_evidence.py` — owner-local, no-SQL/no-J2534 CLI; strict observation schema and local source evidence hashes; exact VIN, Partner Group, VIDA version and Workflow DLL SHA comparability; decision matrix.
- `emulator/tests/test_vida_readvin_ab_evidence.py` — **22** synthetic regression tests.
- This document.

## Original owner-local observation schema

Use a separate JSON file for manual and virtual J2534 cases. Preserve the owner's true, unmasked 17-character VIN, original numeric Partner Group key and original GUI message in **private files only**; never copy them into GitHub.

| JSON key | Required meaning |
|---|---|
| `schema_version` | `virtualcar-vida-readvin-observation-v1` |
| `mode` | `manual` or `j2534` |
| `vin_original` | Same exact VIN in both observations |
| `partner_group_original` | Actually selected numeric SQL Partner Group ID in original VIDA; do not infer from geography |
| `vida_build` | Exact observed VIDA version/build string |
| `workflow_dll_sha256` | SHA-256 of **installed** Workflow.DLL from this VIDA environment |
| `observed_at` | Original timestamp with timezone offset |
| `gui_result` | `ACCEPTED`, `REJECTED`, or `NOT_TESTED` (owner-reported, not independently parsed) |
| `gui_message_original` | Exact GUI message if observed, `null` if NOT_TESTED |
| `transport` | `NOT_OBSERVED`, `TX_ONLY`, `RX_DEQUEUED` (owner-reported; manual must be NOT_OBSERVED) |
| `virtualcar_head_sha` | 40-character original virtual adapter source commit; `null` for manual |
| `evidence_path` | Absolute owner-local screenshot/log path if observed; `null` if NOT_TESTED |
| `evidence_sha256` | Lowercase SHA-256 for that local evidence file; `null` if NOT_TESTED |

For `ACCEPTED` or `REJECTED`, a real local evidence file, its correct SHA-256 and the original GUI message are required. For the observed J2534 case, the **exact 40-character source SHA** is also mandatory. Neither source files nor source paths are sent externally by this tool. A file hash does not attest that the owner-reported status is correct.

### Synthetic *unobserved* manual example

*Replace all shown values only in an owner-local copy. These are public synthetic placeholders, not original VIDA data.*

```json
{
  "schema_version": "virtualcar-vida-readvin-observation-v1",
  "mode": "manual",
  "vin_original": "YV1CZ000290000001",
  "partner_group_original": 1002,
  "vida_build": "VIDA2014D_SYNTHETIC",
  "workflow_dll_sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "observed_at": "2026-11-18T10:00:00+01:00",
  "gui_result": "NOT_TESTED",
  "gui_message_original": null,
  "transport": "NOT_OBSERVED",
  "virtualcar_head_sha": null,
  "evidence_path": null,
  "evidence_sha256": null
}
```

For an unobserved J2534 record change `mode` to `j2534` and provide the actual `virtualcar_head_sha` if known. When an owner performs the session, replace `NOT_TESTED` with the **real** GUI outcome and fill its exact original text and evidence file reference. Do not write `ACCEPTED` because a CAN RX was dequeued; GUI outcome must be observed separately.

## Independent owner VMware evidence collection

1. Check installed VIDA version and hash the exact local `Workflow.DLL`. Do not silently use a SHA-256 from a different VIDA research archive.
2. Record current Partner Group (original exact SQL ID), not a presumed market. Do not alter VIDA Admin or SQL during paired comparison.
3. Manual: enter the same VIN without an adapter; save original GUI outcome/screenshot. Mark `transport=NOT_OBSERVED`.
4. J2534: in a **new** session with the same VIDA build, same VIN and Partner Group, run Read Vehicle using a known registered Virtual Car head; independently record TX, RX dequeue, GUI result and unmodified screenshot/log. Keep separate from the earlier B3A275 historical experiment.
5. On Windows PowerShell, compute the source checksum, e.g. `Get-FileHash -LiteralPath 'C:\VIDA-original-private\manual.png' -Algorithm SHA256`. Store the lower-case digest in the corresponding **private** JSON.
6. Do not publish original VIN, screenshot, SQL rows, logs, DLL or the output JSON in a PR. Do not change VIDA, SQL Server, J2534 DLL/registry or physical CEM during this evidence collection.

## Run locally after creating the two JSON files

In a checkout containing this Draft:

```powershell
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
$manual = Join-Path $private 'B3A303-manual-original.json'
$j2534 = Join-Path $private 'B3A303-j2534-original.json'
$output = Join-Path $private 'B3A303-AB-report-001.json'

py -3 emulator/tools/vida_readvin_ab_evidence.py --manual $manual --j2534 $j2534 --output $output
if ($LASTEXITCODE -ne 0) { throw 'Missing, mismatched, or inconsistent original A/B evidence' }
```

Optional `--candidate-report` accepts an **owner-local** B3A302 output, only if its VIN and Partner Group agree exactly. Offline candidate counts are purely annotated, **not used as VIDA runtime acceptance**. Output is exclusive-create; original JSON/source evidence stays unmodified.

## Decision matrix (diagnostic leads, not established causes)

| Manual GUI | J2534 GUI | Result |
|---|---|---|
| Either untested | Any | `MISSING_OWNER_GUI_OBSERVATION` |
| Rejected | Rejected | `DECODER_OR_PARTNER_COVERAGE_SUSPECTED`; J2534 fault still possible |
| Accepted | Rejected | `J2534_OR_RESPONSEHANDLER_PATH_SUSPECTED` |
| Rejected | Accepted | `SESSION_OR_MANUAL_UI_PATH_DIFFERENCE` |
| Accepted | Accepted | `BOTH_GUI_OUTCOMES_OWNER_REPORTED_ACCEPTED`; **not independently verified** |
| Different VIN/Partner Group/VIDA build/Workflow DLL hash | Any | `NOT_COMPARABLE_SOURCE_CONTEXT` |

No result silently sets the flags `readvin_acceptance_independently_verified`, `original_gui_log_interpretation_independently_verified`, `original_vida_decoder_implementation_verified`, `ecu_identification_verified`, `t111_t122_verified`, or `physical_j2534_verified` to true.

## Verification on this head

Local Python **3.13.5**:
- `python -m unittest discover -s emulator/tests -p test_vida_readvin_ab_evidence.py`: **22/22 PASS** on synthetic, no-owner-data fixtures.
- `python -m compileall` for the new tool + test: **PASS**.
- Verified Git blob source: `9258e1fb841088b1f77cb69bfd86b6882ae06ecd`.
- Verified Git blob tests: `3280a9ffe715d87bfe79e5e8bb6cebbc1e5386aa`.

Not run: original owner VIDA GUI, manual VIN, J2534 ReadVin, SQL, VMware exact-head CI, physical J2534, ECU identification. No merge, release, SQL modification, DLL installation, J2534 registry, virtual ECU reply mutation, original file anonymization, or Dvinholm changes.
