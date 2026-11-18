# B3A297 — VIDA/J2534 request sequence audit (offline, read-only)

## Purpose

Build a **session-scoped TX chronology** from the existing
`virtualcar-backend-v1` optional backend event stream. The analysis identifies
VIN-shaped request attempts (D2 B9FB or ISO15765 22 F1 14), then counts later
six known 29-bit ECU request **destinations** from B3A291/B3A292. It does not
simulate replies or assert that VIN, ECU identity, T111 or T122 was accepted.

Source stack: B3A293 (#359), observed route labels, on top of B3A278 (#358).
This is a standalone, additive *offline analyzer*. No changes to CAN/J2534
response logic, firmware, original VIDA SQL/XML, Registry32 or ECU.

## Steps on the owner's Windows machine

Run from the checked-out **exact head** of this Draft PR. Choose a local
private output directory outside the checkout. Full original input stays
unchanged and local. Derived summary contains only allowlisted metadata:

```powershell
$private = Join-Path $env:USERPROFILE 'VIDA-original-private'
New-Item -ItemType Directory -Force -Path $private | Out-Null

$backend = Join-Path $env:LOCALAPPDATA 'VirtualCar\dev47-backend.jsonl'
$audit = Join-Path $private 'b3a297-backend-audit.json'
$timeline = Join-Path $private 'b3a297-request-sequence.json'

py -3 emulator/tools/audit_backend_evidence.py $backend --output $audit
py -3 emulator/tools/vida_j2534_sequence.py --audit-report $audit --output $timeline
```

Both output files must be new. The tools do not overwrite existing files.
Do not upload original VIDA logs, OEM VINs, SQL files or raw CAN frames to GitHub.

## Exact observation limits

- `vin_shaped_tx_requests` means a recognized request, **not** a parsed VIN.
- `post_anchor_ecu_target_requests` counts TX requests after the **first**
  VIN-shaped request in the *same backend session*. This is neither a verified
  GUI transition nor proof the ECU exists.
- `j2534_rx_dequeued_frames` means J2534 queue delivery only, not a complete
  ISO-TP/D2 response or application acceptance.
- The six target labels ECM/TCM/DEM/BCM/SAS/HCM are fixed request destinations;
  no DID support, ECU presence, ECU identity or negative response is inferred.
- A missing backend request is **not** a timeout or unsupported ECU. Sparse
  observer logs can produce empty/no-anchor reports.
- Session ordinals cannot be correlated with GUI events, another file or
  another process without independent evidence. `same_gui_workflow_verified`
  and all client acceptance flags remain false.
- Original VIDA installation details and full original data are not
  anonymized or rewritten; they remain **owner-local**. This analyzer exports
  only a separate evidence-limited summary.

## Tests

Locally executed on Python 3.13.5 in a synthetic isolated workspace:
`10/10 unittest PASS`; `compileall PASS`.

Exact locally tested Git blobs:
- `emulator/tools/vida_j2534_sequence.py`: `00cd99ee9281367ee4f99c72a6dc1562398035ce`
- `emulator/tests/test_vida_j2534_sequence.py`: `4abcee36dbec0bb7e8f59c599f135eeb6e933ebd`

Additional `audit_backend_evidence.py` allowlist adjustment has **not** been
run as a complete repository test suite or against original owner backend
JSONL. No owner VMware runtime, exact-head trusted CI, GUI ReadVin, ECU
Identification, T111/T122, physical J2534, merge, release or installation
was performed.

Next gate: inspect the owner's new original-VIDA backend JSONL (privately),
verify the new target metadata is accepted by audit, then independently
record GUI ReadVin and ECU identification results for the same run.
