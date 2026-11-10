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

## Three new acceptance categories

- `carcom_profile_init_shape`: Passed when the **public column
  hypothesis** is structurally present in the input report, Failed when
  fixed expected fields are missing, Not tested when no bridge report exists.
- `carcom_service_protocol_shape`: equivalent shape-only semantics for
  the service, protocol and bus hypothesis.
- `dicetiming_to_carcom_row_join`: **always Not tested**. Metadata
  inventories cannot establish an actual row-level relationship between
  separate databases, which is required before determining actual
  InitHw settings for a selected vehicle.

The master summary now has 15 acceptance gates. Even a fully
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
