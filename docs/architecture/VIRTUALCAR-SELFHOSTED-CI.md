# Virtual Car: Windows self-hosted-only GitHub Actions

## Policy

- The primary CI for this private repository is the owner's persistent
  `[self-hosted, Windows, X64, virtualcar-win]` GitHub Actions runner.
- No workflow may run user/fork-controlled `pull_request` source on
  this persistent runner. Owner-only push to `development` and owner
  manual dispatch from default `main` are the trusted entrypoints.
- Manual feature-branch validation requires a named `source_ref`
  **choice** pre-approved in the default branch workflow. The checkout
  disables persisted Git credentials.
- All permissions remain `contents: read`; never upload build
  artifacts, publish GitHub releases, install/register virtual J2534
  adapters, deploy or touch live ECU/security/programming paths.

## Six GitHub Actions workflow files

`.github/workflows/vmware-development-validation.yml` is the only
workflow with an actual `runs-on` job. It also supports
`workflow_call` and runs its full validated Windows suite when
called by a trusted manual alias on the `main` ref.

These five preserved workflow file names are compatibility aliases:
`ci.yml`, `csharp-migration.yml`, `emulator.yml`,
`managed-migration.yml`, and `vmware-release.yml`.
They are **manual-only** (not automatic PR or push workflows)
and delegate to the central Windows workflow with
`source_ref: development`. The legacy `vmware-release.yml` now
performs **validation only**: no package ZIP upload, no prerelease
publication, no `contents: write` credentials.

## Automatic and manual validation

- On a trusted `development` push affecting source/tooling/workflow
  paths, the central CI triggers automatically and checks out
  `development`.
- For approved feature sources, the owner dispatches from `main`:
  `gh workflow run vmware-development-validation.yml -R vorlocsev/virtualcar --ref main -f source_ref=feature/m5c2-authenticated-session-lifecycle`
  (the current M5C-2 feature branch is an explicit hardcoded choice).
- To manually run an old-named workflow on the shared runner:
  `gh workflow run managed-migration.yml -R vorlocsev/virtualcar --ref main`
  (the alias checks out `development`).
- Check: `gh run list -R vorlocsev/virtualcar --limit 10`;
  use the numeric run ID with `gh run watch <ID> -R vorlocsev/virtualcar --exit-status`.
- Avoid starting several aliases at once; all target one VM and
  have a shared concurrency group.

## Coverage and exclusions

The core Windows suite verifies: Python emulator test discovery,
legacy C host regression, Clang/LLD legacy x86 DLL build and PE
exports, x86 native route and evidence audit, Go tests and vet,
C++20 MSVC native x86/x64 configure/build/CTest, actual legacy C
DLL versus C++ read-only synthetic RX parity, .NET 10
Core/SQLite/Scenario, M5A 9-gate local Named Pipe tests, and M5B
native x86/x64 C++ client against C# Host when the source contains
the required projects. For M5C-1 native lifecycle, the x86/x64
CTest targets include the new 8-gate lifecycle executable. M5C-2 adds
  four process-identity CTest gates and a separate cross-language
  x86/x64 integration step for authenticated lifecycle, lease expiry,
  Host process loss, revocation and restart recovery when the selected
  source contains M5C-2.

This refactor does **not** claim test-for-test equivalence with the
retired `ubuntu-latest` C++/Go/Clang Linux smoke lane,
`csharp-migration.yml` historical Native AOT ABI probe,
the old `build_dev26.sh` trace/one-click pipeline,
the old extra Windows filter-policy modes, or the former
VMware artifact ZIP packaging lane. These are explicitly recorded
as gaps; restore unique test coverage using safe, local Windows
test steps or a separate trusted Linux self-hosted runner if needed,
never by executing unreviewed pull requests on the persistent VM.

Verification after migration: owner-run self-hosted
[#42320812710](https://github.com/vorlocsev/virtualcar/actions/runs/42320812710)
completed SUCCESS with source SHA `479fd0d3785869e8922adc6844dad80766808785`.
The logged native x86 and x64 tests each passed 5/5 CTest,
M5A passed 9/9 and M5B passed C++ ↔ C# for both architectures.
Python 252, .NET Core/SQLite/Scenarios 8/8 each, Go, legacy C,
and exact synthetic C/C++ parity also passed.
GitHub Actions artifact listing for that run: **empty**.
`managed-migration.yml` was independently dispatched from `main`
and completed SUCCESS in #42321161342, validating development
`2b5bef8`. Four other manual aliases remain untested.
M5C-2 feature source exact SHA `7fd40d02be9561e787bb4f701a5d7609cd21ddbf` was
validated on the private runner in
[#42339519459](https://github.com/vorlocsev/virtualcar/actions/runs/42339519459): SUCCESS, x86/x64
6/6 CTest each including M5C-2 host identity, and each architecture
passed live C++↔C# lifecycle, local expiry, Host process loss and
reconnect with reused numeric token but distinct process identity.
Zero artifacts. PR #95 added the self-hosted test and PR #97 made
Host termination safe by using the retained child Process handle.
PR #96 then merged into development as `7bde901cbd1cc78f1b03efecba44347acacadb10`,
and automatic push CI
[#42339851382](https://github.com/vorlocsev/virtualcar/actions/runs/42339851382)
also completed SUCCESS with all M5C-2 gates, without artifacts.

## Safety boundary

The new C++ J2534 DLL is still fail-closed. CI does not imply
Dvinholm VIN/ECU identity acceptance, functional J2534 over CAN,
real Volvo P2 protocol compatibility, physical adapter validation
or authorization for SecurityAccess, PIN/immobilizer functions or
flash/programming. No Virtual Car releases without explicit direction.


## M5D-2b native read regression coverage (2026-11-07)

Private feature VMware #42344223822 passed actual x86/x64 C++↔C#
synthetic F187/F189/F190 reads, wrong-route/missing-fixture denial,
and lease expiry. Merged PR #105 as `08b3a9da3c6693f655b7157a68ff5ad26bdf1dda`. The first
post-merge automatic CI #42344476899 passed but did not include
the new read E2E step because development YAML lagged behind main.
PR #107 synchronized the central self-hosted workflow on both refs.
A fresh automatic [#42344666980](https://github.com/vorlocsev/virtualcar/actions/runs/42344666980)
SUCCESS on exact `2989dcbf77676e6555b6de164539fe6a5dd2253b` then executed
four M5D-2b cases on **each architecture**, with CTest x86/x64
7/7 each, managed Host 17/17 and all baseline checks PASS.
Zero artifacts/releases. Next M5D-2c pending-read cancel and
crash/restart tests remain unimplemented; J2534 still fail-closed.


## M5D-2d synthetic replay and read-stress acceptance (2026-11-07)

- Feature PR #117 source `5fff8957dd6963d013be6a6f0b0fee3f78b7ac1b`
  checked out by owner-dispatched [VMware #42369341323](https://github.com/vorlocsev/virtualcar/actions/runs/42369341323),
  SUCCESS, CTest 7/7 on x86 and x64 with 11 VCRD Ledger
  groups, Host 17/17 and actual 64-read synthetic C++ ↔ C#
  Host stress PASS on both architectures.
- PR #117 merged into development as `f3f907e98669c172edb15265ae015f222a82be7e`.
  Automatic [VMware #42369754826](https://github.com/vorlocsev/virtualcar/actions/runs/42369754826)
  completed SUCCESS on that exact SHA: x86/x64 native CTest
  7/7 each, C# Host 17/17, old M5D-2b/c tests,
  64-read synthetic stress PASS separately on x86 and x64,
  Python 252, Legacy C, Go and .NET checks PASS.
- GitHub reports zero uploaded artifacts; no releases,
  deployments, physical CAN/ECU or J2534 read bridge.
  The J2534 DLL continues fail-closed, unlinked to IPC.
