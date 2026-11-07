# M2 | Deterministic, evidence-scoped C# scenario compiler

Status: review stage. This document does **not** assert Windows runtime/real
J2534/Volvo compatibility. Dvinholm remains the production application;
Virtual Car remains an optional read-only laboratory.

## Inputs and exact SQLite v1 limitation

Original schema remains unchanged at `emulator/schema/0001_lab_catalog.sql`.
It stores `response_fixtures.request_sha256` but NOT original request bytes.
Never infer a UDS request from the hash. A separate
`ISyntheticRequestManifest` must explicitly resolve exact synthetic request
bytes; the compiler independently recomputes SHA-256 and refuses mismatches
or omissions.

The new `LabCatalog.ReadScenarioMaterialAsync` reads a single coherent
SQLite transaction: scenario revision, provenance-labelled vehicle profile,
all enabled bindings, CAN bus metadata, ECU routes and synthetic reply bytes.
No private artifact paths, encrypted captures, donor VINs or ECU dumps are
returned. Cross-vehicle bindings and more than 256 rows fail closed.
The compiler imposes an additional maximum of 128 active fixtures.

## Security and correctness gates

- Only `vehicle_profiles.provenance=synthetic`, approved synthetic inline
  reply fixtures, enabled ECU and enabled bindings; no captured_private or
  research_only material can compile.
- Only `iso15765` and UDS `0x22 DID_HI DID_LO` with matching synthetic
  positive `0x62 DID_HI DID_LO ...` are supported in M2.
  Volvo D2/CEM, security services `0x27`, write services, programming and
  arbitrary request replay remain unsupported.
- Enforce baud rate and 11-/29-bit CAN ID limits and independent per-bus
  ECU request/response ownership. Cross-ECU collisions or duplicate
  request hashes are rejected.
- Sort by bus/ECU/fixture ID with ordinal comparisons, serialize into
  version-marked canonical binary bytes (VCSNAP1 + explicit little-endian
  numeric fields + length-prefixed UTF-8 strings + request/reply bytes).
  Length-bounded strings and snapshot size <=1 MiB.
- `PreviewDraftAsync` yields only a digest and response count, always
  marked **not approved**, so a draft cannot enable diagnostic replies.
- `CompileVerifiedAsync` requires a sealed revision and compares the
  SHA-256 of actual materialized bytes with stored revision checksum;
  then `ScenarioCoordinator` independently hashes a private copy before
  any runtime preparation.
- SQLite v1 triggers protect fixture bindings and bound fixture edits, but
  not all ECU/bus/profile rows. Full-payload rehash therefore rejects
  post-seal routing tampering. The compiler has no automatic sealing/write
  API in M2; a future controlled editor must seal transactionally.
- `VerifiedScenarioCatalog` is an optional adapter to the C# lifecycle
  contract. It is NOT connected to J2534, IPC or a real ECU responder.

## Tests (eight synthetic integration groups)

1. Draft preview cannot be executed; sealed digest and actual bytes match.
2. Canonical output independent of SQLite fixture insertion order.
3. Missing approved request bytes and wrong request SHA-256 are rejected.
4. Research-only profiles, unapproved fixtures and invalid provenance fail.
5. SecurityAccess and mismatched positive service/DID are rejected.
6. Invalid 11-bit CAN IDs and two ECUs claiming a request ID fail.
7. Post-seal ECU metadata tampering breaks stored snapshot checksum.
8. Cancellation, coordinator session guard/reset and stale tokens.

Existing C x86 J2534 and Go tests remain untouched and continue running.
CI tests on Linux/Windows do not replace testing a real native x64 DLL.

## Handoff and following steps

Once **M2 CI passes** and its PR is merged, mark M2 complete in
`docs/progress/CURRENT.md` and update ROADMAP and NEXT_CHAT; new-chat
trigger remains exactly **virtual car**.

Next M3: produce and verify *actual* C++20 x86/x64 J2534 DLL exports and
correct ABI/loader semantics, initially failing closed. Do not publish any
Virtual Car build or claim real Volvo identity acceptance.
