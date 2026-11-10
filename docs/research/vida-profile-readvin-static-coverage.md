# VIDA: Profile / Service to ReadVin static prerequisite coverage

Status: **metadata-only and source-only research**. The new tool
`emulator/tools/vida_profile_readvin_static_coverage.py` checks the
**independent presence** of already-redacted CarCom Profile/InitHw,
Profile/Service, Service/Protocol, and ReadVin declared-identity-graph
evidence. It never reads original VIDA XML/SQL, ECU messages, VINs,
selected GetScript identifiers or J2534 traffic.

## Evidence inputs and limitations

The four owner-reviewed inputs are all required:

- `--catalog-report`: redacted unified CarCom/DiagSwdlRepository/BaseData
  metadata catalog, containing public allowlisted column-shape hints
- `--dicetiming-report`: independent redacted DiceTiming catalog
- `--profile-init-report`: the SHA-bound Profile/InitHw/Service shape
  bridge generated from **those exact** catalog and DiceTiming bytes
- `--readvin-report`: existing redacted ReadVin v2/v3 structural
  crosscheck; counts declared identity-output nodes and methods but
  never proves that a selected GetScript returned or executed this XML

The new report stores the SHA-256 of the exact bytes of each source
report, four fixed boolean **static_prerequisites**, a fixed allowlisted
list of missing prerequisites and a `static_coverage` value:

- `present`: all four independent metadata prerequisites are present
- `incomplete`: at least one required static prerequisite is absent

All of `source_row_joins_verified`,
`same_vida_installation_verified`,
`profile_to_getscript_binding_verified`,
`getscript_to_readvin_selection_verified`,
`original_dice_timing_values_verified`, `d2_baud_verified`,
`runtime_readvin_execution_verified`, `client_vin_accepted`,
`physical_j2534_verified` and `replay_approved` remain **false**.

The SHA-256s bind redacted bytes only. They do not authenticate that the
reports were generated on one VIDA 2015A installation, that the
metadata inventory is complete, or that a selected ECU uses the
ReadVin graph. A successful static coverage check is **not** a
Profile → GetScript → ReadVin link.

## Local Windows owner-only example

After creating the four already-redacted source reports, in PowerShell
from the reviewed feature-branch repository root:

~~~powershell
$root = Join-Path $env:USERPROFILE "VIDA-evidence-private"
$catalog = Join-Path $root "unified-catalog.redacted.json"
$dice = Join-Path $root "dicetiming.redacted.json"
$profile = Join-Path $root "profile-init.redacted.json"
$readvin = Join-Path $root "readvin-static.redacted.json"
$coverage = Join-Path $root "profile-readvin-static-001.redacted.json"
$manifest = Join-Path $root "profile-readvin-manifest-001.json"
$summary = Join-Path $root "profile-readvin-summary-001.redacted.json"

py -3 emulator/tools/vida_profile_readvin_static_coverage.py --catalog-report "$catalog" --dicetiming-report "$dice" --profile-init-report "$profile" --readvin-report "$readvin" --output "$coverage"
if ($LASTEXITCODE -ne 0) { throw "Static coverage check failed" }

py -3 emulator/tools/build_vida_redacted_manifest.py --catalog-report "$catalog" --dicetiming-report "$dice" --profile-init-report "$profile" --readvin-report "$readvin" --profile-readvin-coverage-report "$coverage" --output "$manifest"
if ($LASTEXITCODE -ne 0) { throw "Byte-binding manifest failed" }

py -3 emulator/tools/vida_evidence_summary.py --catalog-report "$catalog" --dicetiming-report "$dice" --profile-init-report "$profile" --readvin-report "$readvin" --profile-readvin-coverage-report "$coverage" --bundle-manifest "$manifest" --output "$summary"
if ($LASTEXITCODE -ne 0) { throw "Static evidence summary failed" }
~~~

Each output must have a **new, exclusive filename** outside Git.
The summary re-computes all source-derived coverage claims from the
four original parsed redacted inputs; a forged coverage value, missing
source, digest mismatch or extra field fails closed. The manifest binds
all five JSON reports, including the generated coverage result. No
source paths, original proprietary names, VIN or report content are
copied to the generated coverage JSON.

## Acceptance interpretation

The master summary has **17 stages**, adding
`profile_readvin_static_prerequisites`:

- **Passed** means four *independent static prerequisites* were present
  and checked against their exact source bytes
- **Failed** means the available source metadata lacks one or more of
  those prerequisites
- **Not tested** means the new coverage report was not supplied

The separate `profile_to_readvin_join`,
`getscript_runtime_selection`, `j2534_correlated_exchange`, and
`client_vin_acceptance` gates remain **Not tested**; they are never
promoted by static coverage. Actual row-level profile/script selection,
service execution, timing/baud values, and physical CAN/ISO-TP/J2534
must be validated later using independently collected owner evidence.

## Verification boundary

Executed locally on Python 3.13.5: **157/157 synthetic tests PASS**
(141 earlier + 16 new cases), `compileall` PASS. The new cases cover
complete/incomplete static shapes, wrong or missing source digests,
tampered reports, false runtime claims, output aliases, file symlinks,
the manifest round-trip and legacy compatibility. The tested exact Git
blob SHA-1 values are:

- coverage tool: `7b45d43b716b7127146373b6fd68a20a533f85cd`
- summary: `b025d0e0894661601583780dd92164dd6293baf4`
- manifest builder: `1204fdafcd2cd6e202615115bdd899d568508330`
- coverage tests: `00944ff924d59216ee2c9ad1afaafe3b1b03cfdf`

These tests used synthetic JSON, not original VIDA or the owner VMware
environment. No exact-head VMware CI, original database rows, real
ReadVin execution, or physical J2534 test is claimed.
