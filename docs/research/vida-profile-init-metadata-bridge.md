# VIDA: CarCom Profile / InitHw and DiceTiming metadata bridge

Status: static, **owner-local, source-only research**. The bridge consumes
two already-redacted JSON reports. It does not access raw VIDA databases,
read a selected vehicle profile, query original user rows, select GetScript,
or start a J2534 diagnostic exchange.

## Scope and evidence

The bridge checks the previously curated CarCom hints in
`audit_vida_carcom_schema_links.py`. These are hypotheses derived from
published VIDA 2014D research, not confirmed table layouts for this owner's
VIDA 2015A. The fixed column-shape routes inspected are:

- Profile / InitHw: `T161_Profile` →
  `T136_InitHw_Profile` → `T130_Init` →
  `T131_InitValue` → `T132_InitValueType`.
  This checks the existing four `hardware_shape` edge hints plus
  `folderLevel`, `initValue`, and `name` columns.
- Service / protocol / bus: `T111_Service` →
  `T122_Protocol`, `T121_Config` →
  `T122_Protocol` / `T123_Bus`, with
  `busRate` and `addressSize` columns.
- DiceTiming: its independent report must have valid catalog metadata
  and explicitly negative runtime claims. **No inferred DiceTiming ↔
  CarCom cross-database FK or value mapping** is ever reported as verified.

The tool recomputes shape expectations from the supplied allowlisted
`known_tables`, rejecting duplicated or contradictory candidate edges,
missing fixed research hints, forged row joins, unexpected column labels,
and unsupported positive timing/VIN flags. It emits only fixed statuses
(`candidate_shape`, `incomplete_shape`), public hint counts and exact
SHA-256 digests of the **already-redacted** input report bytes. These
digests are not signatures, proof of database origin, or provenance.

## Owner-local invocation

First produce redacted outputs with the existing reviewed
`vida_unified_analyzer.py` and `vida_dicetiming_catalog.py` tools.

~~~powershell
$privateRoot = Join-Path $env:USERPROFILE "VIDA-evidence-private"
$catalog = Join-Path $privateRoot "unified-catalog.redacted.json"
$dice = Join-Path $privateRoot "dicetiming-sql.redacted.json"
$bridge = Join-Path $privateRoot "profile-init-001.redacted.json"
$manifest = Join-Path $privateRoot "profile-init-manifest-001.json"
$summary = Join-Path $privateRoot "profile-init-summary-001.redacted.json"

py -3 emulator/tools/vida_profile_init_bridge.py --catalog-report "$catalog" --dicetiming-report "$dice" --output "$bridge"
if ($LASTEXITCODE -ne 0) { throw "Profile/InitHw metadata check failed" }

py -3 emulator/tools/build_vida_redacted_manifest.py --catalog-report "$catalog" --dicetiming-report "$dice" --profile-init-report "$bridge" --output "$manifest"
if ($LASTEXITCODE -ne 0) { throw "Source byte manifest check failed" }

py -3 emulator/tools/vida_evidence_summary.py --catalog-report "$catalog" --dicetiming-report "$dice" --profile-init-report "$bridge" --bundle-manifest "$manifest" --output "$summary"
if ($LASTEXITCODE -ne 0) { throw "Profile/InitHw aggregate summary failed" }
~~~

Use a **new output filename** for each run. All reports stay outside Git
on the owner-controlled system, where the operator must review them.
The summary refuses a profile bridge when either original redacted input
is absent or its bytes differ from the bridge's declared SHA-256.

## Four static acceptance categories

- `carcom_profile_init_shape`: Passed when the **public column
  hypothesis** is structurally present in the input report, Failed when
  fixed expected fields are missing, Not tested when no bridge report exists.
- `carcom_profile_service_shape`: separately checks the **complete**
  previously researched CarCom column-shape route
  `T161_Profile → T160_DefaultEcuVariant → T100_EcuVariant →
  T110_Service_EcuVariant → T111_Service → T122_Protocol`.
  This requires the six known `service_shape` hints and fixed
  profile/variant/service/protocol identifiers. A missing link causes Failed,
  while absent bridge input stays Not tested. **No row-level association
  or selected ECU is confirmed.**
- `carcom_service_protocol_shape`: equivalent shape-only semantics for
  the service, protocol and bus hypothesis.
- `dicetiming_to_carcom_row_join`: **always Not tested**. Metadata
  inventories cannot establish an actual row-level relationship between
  separate databases, which is required before determining actual
  InitHw settings for a selected vehicle.

The master summary now has 16 acceptance gates. Even a fully
`candidate_shape` result does **not** imply a real selected XC90 V8
MY2009 ECU profile, inherited InitHw precedence, timing values, D2 baud,
successful ReadVin or permission to enable replay.

## Verified locally and not verified

The isolated Python 3.13.5 research suite passed **127/127 synthetic tests**
(110 previous + 17 bridge/security/integration tests) with `compileall`
PASS. The local test environment used only the constants transcribed
from the development-branch research hints; the original 2015A databases
and live client data were not inspected. Exact local blob SHA-1 matches
were verified for the new bridge, its tests, the summary, and manifest
generator. This is **not** full-repository or exact-head VMware CI.

Next meaningful evidence is an **owner-local metadata-only** report from
actual VIDA 2015A, followed by explicitly authorized, bounded
read-only validation of any candidate associations. No row joins,
real baud, VIN acceptance, original XML or physical J2534 are certified.

## Independent recomputation in the master summary (2026-11-10)

Earlier revisions of the master summary checked the bridge's source-file
SHA-256 and internal shape/count consistency, but **did not recalculate
the claimed shape from source metadata**. A forged bridge could therefore
report `candidate_shape` with `missing_public_hints=0` even when its
correctly hashed CarCom input lacked `folderLevel`. This failure was
reproduced using synthetic reports before the fix.

The master summary now requires **both original parsed, already-redacted
inputs**, reuses the fixed research allowlists, and independently calls the
same static shape computation before accepting a bridge. It compares
the entire reported bridge to the recomputed canonical JSON, including
nested count types, exact source digests and negative runtime flags.
Missing original inputs, changed source bytes, inconsistent counts,
a forged passing Profile or Service shape, or unexpected extra fields
fail closed. The manifest generator inherits this check because it
reuses the master summary's preflight.

The statuses retain their limited meaning: only public metadata
column-shape hypotheses can pass. The
`dicetiming_to_carcom_row_join` stage remains **Not tested**, as do
InitHw source values, ECU profile selection, D2 baud, ReadVin execution
and J2534 acceptance.

Actual isolated local validation: **134/134 synthetic Python tests PASS**
(previous 127 plus seven regression methods), with
`python -m compileall -q emulator/tools emulator/tests` PASS.
The direct CLI entrypoint was also executed in a separate subprocess on
synthetic reports, confirming successful processing and no accidental
top-level import cycle. Verified exact Git blob hashes:
- `vida_evidence_summary.py`: `1bb6b1a902d0fb9853d5886e8f506159673fe749`
- `test_vida_profile_init_bridge.py`: `f6352df535a9cd3a40bd057c370383e3ddb9f935`

No original VIDA SQL, VMware exact-head workflow, physical J2534 or
client VIN acceptance was run. Recalculation does **not** authenticate
the source files or prove same-installation provenance.

## Profile-to-Service structural route extension (2026-11-10)

The original static bridge assessed the Profile/InitHw and Service/Protocol
shapes **separately**. The two checks could pass while `T110_Service_EcuVariant`
or `T160_DefaultEcuVariant` lacked a column needed to associate a profile
with its diagnostic services. The independent
`carcom_profile_service_shape` gate closes this *metadata-only* gap using
the six existing `CANDIDATE_EDGES` and fixed, public CarCom research hints.

The report now carries `profile_service_shape` and a corresponding
`missing_public_hints.profile_service` count. The master summary
recomputes and checks this new field from the SHA-bound, already-redacted
catalog and DiceTiming inputs before displaying Passed or Failed.
Neither matched column shapes nor a Passed stage proves actual record
joins, original 2015A layout, a selected XC90 V8 MY2009 profile,
GetScript selection, D2 baud, VIN acceptance, or J2534.

**Actual local checks:** the focused synthetic Python suite completed
**141/141 PASS**, zero errors/failures, with `compileall` PASS.
Seven new cases cover middle-link absence, default-variant/profile
absence, forged status/count, a missing candidate edge, no-bridge
behavior and independent downstream runtime negatives.
GitHub files match the locally tested Git blobs:
- `vida_profile_init_bridge.py` `f5823030913270403fbfcf92b41e8b29aad05229`
- `vida_evidence_summary.py` `39ec059b0a382533e648576e277bae2b19a5e7c3`
- `test_vida_profile_init_bridge.py` `f8b26d25c59e3296becdc18ef90ae7efb5f8e92e`

The earlier 127/127 count elsewhere in this document is historical.
No exact-head VMware CI, original VIDA data or physical hardware
was tested in this extension.
