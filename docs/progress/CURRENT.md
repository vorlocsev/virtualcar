# CURRENT | Dvinholm / Virtual Car Lab

## Self-hosted-only CI migration (2026-11-07)

The previous separate GitHub-hosted workflows are replaced by one
authoritative Windows self-hosted VM validation on
`[self-hosted, Windows, X64, virtualcar-win]`.
The core workflow `.github/workflows/vmware-development-validation.yml`
runs automatically on trusted `development` pushes, and is reusable
for owner-only manual dispatch from `main`. Five former workflow names
are preserved as **manual aliases** to that same validation.
They do **not** accept pull_request events or execute unreviewed fork
code on the persistent VM. The operator may validate a feature branch
only by explicitly adding its name to the core allowlist on `main`.

This Windows suite executes legacy C/Python/Go, MSVC native x86/x64,
old-C-vs-C++ synthetic RX parity, .NET 10 managed/storage/scenario,
M5A host, M5B C++ <-> C# peer, and M5C2 authenticated lifecycle checks (when source is present).
It does not provide identical Linux-host smoke, retired Native AOT ABI
probe, old legacy trace-oneclick or VMware prerelease packaging coverage.
Do not treat removal of GitHub-hosted checks as an equivalent pass
for the retired Linux-specific steps. No artifact upload, prerelease,
adapter install, software publication or physical ECU access is allowed.
See `docs/architecture/VIRTUALCAR-SELFHOSTED-CI.md`.

Self-hosted migration VERIFIED after merge: private VMware
[#42320812710](https://github.com/vorlocsev/virtualcar/actions/runs/42320812710)
completed SUCCESS on `development` commit
`479fd0d3785869e8922adc6844dad80766808785`.
Python 252 tests, native MSVC x86/x64 5/5 CTest each (including M5C-1),
.NET Core/SQLite/Scenarios 8/8 each, M5A 9/9, M5B C++ ↔ C#
x86/x64, Go, legacy C and C/C++ parity PASS. GitHub Actions
reports zero uploaded artifacts. The `managed-migration.yml` manual alias was independently dispatched
from `main` and completed SUCCESS in #42321161342, validating
`development` commit `2b5bef8`. Four other aliases remain untested.


## ACTIVE checkpoint: M5C-2 authenticated Host-bound lifecycle PASSED (2026-11-07)

Implementation branch: `feature/m5c2-authenticated-session-lifecycle`,
source commit `80d144b24b29cd52691b0cfa50fdcfe2c5f309a3`
plus documentation and workflow follow-up.

The native M5B client captures the verified server PID and its
process creation FILETIME after checking PID and before sending the
32-byte test launch secret. The C++ session key is now
`(sessionId, generation, serverPid, serverCreationTime)`. This is
necessary because a new C# Host process restarts its in-memory
coordinator counters and can legitimately issue the same numeric
token (1,1); PID plus creation time distinguishes process instances
even if Windows reuses a PID.

New `AuthenticatedSession` composes the real M5B pipe client and
M5C-1 bounded lifecycle. It opens local state only after a successful
authenticated ACK from the verified Host; it has no public
caller-controlled synthetic-approval flag. Heartbeats validate the
local lease before remote I/O and extend it only after a matching Host
ACK. Channel reservations remain bounded to eight and carry no frame
or ECU/CAN API. Host loss, local lease expiry, and GOODBYE revoke local
slots and clear the client session.

Added four native process-identity tests and three cross-language
Windows test modes: authenticated session/channel operation,
lease expiry, and forced synthetic Host process loss followed by
restart on the same pipe. The restart test checks that the restarted
C# coordinator reissues the same numeric 1/1 token, while process
creation identity differs and the old channel ID cannot be reused.

**Windows verification: PASS.** Private self-hosted VMware
[#42339519459](https://github.com/vorlocsev/virtualcar/actions/runs/42339519459) checked out exact feature source
`7fd40d02be9561e787bb4f701a5d7609cd21ddbf` on runner `VirtualCar-CI-WIN`.
MSVC x86: 6/6 CTest including M5C-2 process-identity four gates PASS.
MSVC x64: 6/6 CTest including the same M5C-2 gates PASS.
For EACH architecture, the actual C++ client and C# Host passed
authenticated lifecycle/channel reservations, local lease expiry,
forced loss of the owned synthetic Host process and client revocation,
then restart on the same pipe with identical numeric session token
but different host process identity and rejected stale channel IDs.
M5A 9/9, M5B cross-language x86/x64, Python 252, Go, Legacy C,
C/C++ parity and .NET checks also PASSED. Artifacts: zero.
PR #96 is ready for merge, but the deployed J2534 DLL remains
fail-closed and unlinked to this wrapper. No CAN/ECU data plane,
physical adapters, PIN, SecurityAccess, programming or releases.
J2534 DLL remains fail-closed and unlinked from this lifecycle.
No CAN/ECU data plane, physical adapters, PIN, SecurityAccess,
programming, artifacts, releases or deployments.

## COMPLETED checkpoint: M5C-1 Windows x86/x64 lifecycle preflight PASSED (2026-11-07)

### M5A C# current-user Named Pipe host: MERGED into development

PR #85 merged with ancestry preserved as
`410ade408388468f727dceef063e1194747e8162`.
The .NET 10 Windows test host provides current-user-only Named Pipe
isolation, a separately provisioned 256-bit launch secret, bounded
little-endian v1 frames, generation-bound core sessions and fail-closed
HELLO / KEEPALIVE / GOODBYE. Private VMware #42314429323 passed M5A
9/9; the M5B validation run below also passed M5A 9/9.

### M5B native C++20 IPC client: x86/x64 preflight VERIFIED

PR #87, source branch `feature/m5b-cpp-named-pipe-client`, exact tested
head `053e60e5996228b1776f4d728d61de839cad9256`.
The isolated C++20 library checks the expected Named Pipe server PID
**before** sending the launch secret, requests SECURITY_IDENTIFICATION,
uses bounded overlapped I/O and an absolute deadline per transfer,
checks a versioned 28-byte VCLB header and maximum 256-byte payload,
serializes client operations, binds keepalives to the session generation
and wipes temporary buffers. It is NOT linked into the J2534 DLL.

**Private VMware SUCCESS #42318278748**
(https://github.com/vorlocsev/virtualcar/actions/runs/42318278748).
Workflow definition on `main` was `84f12eb22c837c32ff03728878edf3ccd10a5004`,
while the selected checkout was the M5B branch named above.
- Native C++ x86: 4/4 CTest; x64: 4/4 CTest; M5B eight native
  offline test gates included on both architectures.
- x86 and x64 separately: rejection of a wrong server PID before
  HELLO and clean C# host exit code 0.
- x86 and x64 separately: authenticated client/host
  HELLO / KEEPALIVE / GOODBYE, both processes exit 0.
- M5A: 9/9. .NET Core/Storage/Scenario: 8/8 each.
- Python regression, legacy C host and DLL regressions, Go tests/vet,
  legacy C/C++ parity: PASS.
- No packages, artifacts, installers, releases or deployments.

Previous private VMware #42317744015 failed solely on a Windows
PowerShell 5.1 `Start-Process -PassThru` empty ExitCode in the
orchestrator, *after* the x86 wrong-PID denial passed. Workflow fix
PR #89 merged into `main` as `84f12eb22c837c32ff03728878edf3ccd10a5004`;
the subsequent full run #42318278748 passed.

### NEXT: M5C secure fail-closed session/channel lifecycle

The M5A/M5B preflight proves a local *control handshake*, NOT a
functional PassThru data plane or production credential provisioning.
Next: define owned C# host/native DLL session hand-off, channel states,
lease/heartbeat expiry, crash/restart invalidation, bounded outstanding
work and rigorous failure/cleanup tests before enabling any CAN path.
Keep SecurityAccess/programming, physical adapters, real ECU requests
and J2534 successful routes disabled. Keep existing C/Go references
until full parity and end-to-end acceptance.

Dvinholm is the PRIMARY product; Virtual Car is a private, optional,
synthetic read-only laboratory. No Virtual Car releases without a
separate explicit instruction.

### M5C-1: isolated bounded lifecycle, VMware x86 and x64 PASSED

PR #90 source branch: `feature/m5c1-bounded-lifecycle-preflight`;
exact **tested native source** commit
`89553e37e47b86a3ced83d2c1de01827669bc039`.
Private VMware SUCCESS [#42319530476](https://github.com/vorlocsev/virtualcar/actions/runs/42319530476)
checked out that exact branch commit, with workflow at `main`
`6661014373e07464b99ed02aa03f03aff3947828`.
The workflow is owner-only, self-hosted Windows, and publishes no
artifacts, releases, installers or deployments.

Windows x86: 5/5 CTest including
`m5c1_bounded_session_lifecycle_8_groups` PASS.
Windows x64: 5/5 CTest including the same M5C-1 group PASS.
Each new M5C-1 CTest executable runs eight deterministic gates:
default deny; session/generation and duplicate begin; exact heartbeat
expiry; monotonic rollback/overflow; wrong-generation invalidation;
eight-slot capacity/nonrecycled IDs; reauthentication/reset; and
24 simultaneous reservations without exceeding capacity.
M5A 9/9, C++ ↔ C# M5B x86/x64, Python, Go, legacy C,
C/C++ parity and .NET Core/Storage/Scenarios also PASS.

`VirtualCarLifecycle` remains **separate from** the fail-closed
`VirtualCarJ2534Cpp` DLL and the IPC client. Synthetic approval is
a caller precondition, NOT authentication. Lazy expiry is checked
on the next timed operation, never authorized from `snapshot()`.
No CAN/ECU, SecurityAccess, PIN, programming, adapter registration,
real-vehicle or Dvinholm E2E test has occurred.

**M5C-2 implementation** is tracked in the active checkpoint above.
Host process identity and crash/restart behavior remain pending the
owner-run Windows x86/x64 integration workflow.


Completed:
- M0 PR #71 C# Core and C++ ABI, CI #1 SUCCESS.
- M1 PR #72 C# SQLite v1, CI #4 SUCCESS.
- M2 PR #75 synthetic sealed scenario compiler, CI #6 SUCCESS.
- M3 PR #77 C++ x86/x64 J2534 14-export FAIL-CLOSED ABI DLLs,
  CI #10 and legacy x86 #624 SUCCESS.
- M4A PR #79 C++ bounded CAN/ISO-TP, FIFO/FC/STmin, CI #13,
  legacy x86 #628 SUCCESS.
- M4B-1 PR #81 C++ isolated J2534 ISO15765 RX, 8 synthetic ECU
  routes, exact metadata, atomic START_OF_MESSAGE pair, CI #15,
  legacy x86 #631 SUCCESS.
- **M4B-2 PR #83 MERGED**, SHA
  **49f616f3af8ed266ecd793f0718ddb0b67c9792e**:
  actual Windows x86 BLACK-BOX comparison: independently built
  original C PassThru DLL loaded via LoadLibraryExW and called via
  PassThruOpen/Connect/StartMsgFilter/WriteMsgs/ReadMsgs/Disconnect,
  compared with separately built C++20 Iso15765Rx module for eight
  identical explicitly synthetic read-only F187/F189 test traces.
  Same synthetic INI source; C++ outputs are NOT derived from old DLL
  received bytes. Compared ProtocolID/RxStatus/TxFlags/DataSize/
  ExtraDataIndex and EVERY payload byte; only dynamic microsecond
  timestamps excluded. Eight groups passed (short, long START pair,
  two ECU, two channels, broad filter, wrong FC destination,
  63-entry FIFO pair rejection, disconnect/reset state).
  Final emulator x86 CI **#638 SUCCESS** (real DLL+new code 8/8),
  managed C#/C++ CI **#21 SUCCESS**, VMware LAB packaging
  **#453 SUCCESS**. No DLL/public releases.
  Test source: emulator/native-cpp/tests/legacy_c_cpp_parity.cpp.
  Scope: docs/architecture/VIRTUALCAR-LEGACY-C-CPP-EXEC-PARITY-M4B2.md.

## Latest Windows VMware Runner validation (2026-11-06)

[Run #42313066763](https://github.com/vorlocsev/virtualcar/actions/runs/42313066763)
completed **SUCCESS** against development HEAD
`c4d436b0aae2262bce440b4b60c7b734accc895c`.

- Python: 252 tests passed.
- Legacy C host protocol regression: PASS.
- Clang/LLD Windows x86 DLL build: PASS.
- PE32/i386 validation: exactly 14 undecorated J2534 exports.
- Native x86 legacy DLL route regression and evidence audit: PASS.
- Go tests/vet: PASS.
- Native C++20 x86 and x64 build/CTest: PASS.
- .NET 10 Core, SQLite Storage and Scenario Compiler: PASS.
- M4B-2 independent legacy C DLL vs C++20 RX comparison: **8/8 PASS**.
- No artifacts uploaded, no releases or deployments.

The run selected `source_ref=development`, so M5A was **skipped** because
`VirtualCar.Service.Checks` is not present on that branch. M5A remains in
Draft [PR #85](https://github.com/vorlocsev/virtualcar/pull/85), current head
`42df2953cb8287eb81a1e94052020b353a80eb03`. Its current head has the Windows
host-shim, Git Bash path-conversion and exact-export fixes, but still needs
a fresh VMware run. The previous 9/9 M5A result in PR #85 belongs to an older
source head. PR CI attempts #42313398352, #42313398144 and #42313398379
failed before runner assignment (runner_id=0, no executed steps/logs); they
are not evidence of a code regression.

Next: dispatch `vmware-development-validation.yml` from `main` with
`source_ref=feature/m5a-secure-local-ipc-preflight`, verify the current
M5A 9/9 integration groups and all other gates, then review PR #85.
M5B PRs #87 and #88 remain Draft and depend on M5A. No main merge, release,
driver registration or physical adapter test.

**EVIDENCE LIMITS:** This is actual old C J2534 DLL versus compiled
new C++ RX *module*, NOT old versus a FUNCTIONAL new J2534 DLL.
At the M4B-2 checkpoint, the M3 C++ PassThru DLL deliberately
returned NOT_CONNECTED. Later M5A/M5B now authenticate a separate
local host/client test harness, but no J2534 CAN transport serves
Dvinholm yet. Tested trace set is synthetic ISO15765 F187/F189 only.
Not verified: full 29-bit/raw-CAN/physical bus parity, vendor
extensions, Volvo P2 CEM B9FB replies, VIN acceptance by real software,
VIDA/SectorV/VDASH client discovery, physical DiCE or actual vehicle.
VMware LAB packaging != guest application test. Preserve old C/Go.

**NEXT M5C:** M5A and M5B have verified isolated Windows
C# ↔ C++20 local Named Pipe handshakes on x86/x64 (#42318278748).
Implement and verify owned J2534 DLL / Host session and channel lifecycle,
lease expiration, crash/restart invalidation, timeouts and bounded
backpressure. The J2534 DLL remains fail-closed and unregistered;
there is no CAN/ECU data plane, real-vehicle access or programming.

Read first: docs/architecture/VIRTUALCAR-CSHARP-CPP-MIGRATION.md,
docs/architecture/VIRTUALCAR-LEGACY-C-CPP-EXEC-PARITY-M4B2.md,
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md.

Exact cross-chat continuation phrase: **virtual car**.

Verified checkpoint: 2026-11-07.
This document is the canonical cross-chat continuation note. Re-read the
current GitHub PR/CI state before changing code; do not rely only on chat memory.

## Product and rules

- Dvinholm is the MAIN application. Target: WinUI 3 .NET 10 self-contained
  x64. Priority: CEM PIN, CEM configuration, ECU inventory and diagnostics.
- Virtual Car is an OPTIONAL private J2534/ECU simulator for Dvinholm tests,
  not a competing production diagnostic application.
- Do not publish Virtual Car releases or enable writes/programming.
- Never use synthetic/donor XC90 data as proof of OEM compatibility.
- Distinguish synthetic offline CI from Windows GUI and physical DiCE tests.

## Verified work completed

- Virtual Car PR #59 (Go labcore skeleton and SQLite v1 schema):
  https://github.com/vorlocsev/virtualcar/pull/59
  MERGED to development as e51c3397d78ad99a86bd15ced856a22066865444.
  Windows x86 CI #577 and VMware LAB packaging #417 SUCCESS.
- Virtual Car PR #62 (Stage 60A and permanent roadmap):
  https://github.com/vorlocsev/virtualcar/pull/62
  MERGED to development as 73c4f375d5775ae3ed32ba3822158a97c8e3ed27.
  Windows x86 CI #587 and VMware LAB packaging #426 SUCCESS at
  head 8cb064d923875b69dd0d90749076a61a1caec049.
  Note: earlier CI #586 failed from a test placement NameError; corrected
  in the final merge. This is not a hidden remaining failure.
- Dvinholm PR #703: lab contract documentation MERGED to main at
  558f816d2b0a4d8ef9a1daf0cede8df1ab7e3d27, head CI #5151 SUCCESS.
  https://github.com/vorlocsev/dvinholm/pull/703
- Dvinholm x64 WinUI 3 migration PR #702 remains a separate workstream:
  https://github.com/vorlocsev/dvinholm/pull/702
  Verify current status before acting; no public x64 acceptance asserted.

- Virtual Car PR #66: stage 60B-1 Go database/sql metadata boundary,
  MERGED to development as 0d0ecdeaa63e483d8c2e80b70d187780916678b3.
  Windows x86 CI #598 and VMware LAB packaging #434 SUCCESS.
  Eight synthetic Go driver tests, no real SQLite Go driver and no runtime
  J2534 change. https://github.com/vorlocsev/virtualcar/pull/66

## Actual technical state

Implemented and tested:
- Go labcore skeleton with session generations, stop/reset/selection.
- SQLite metadata schema draft: emulator/schema/0001_lab_catalog.sql.
- Python standard-library development-time SQLite repository and CLI:
  emulator/tools/lab_sqlite_repository.py
  emulator/tools/lab_db_cli.py
  Eight synthetic tests: emulator/tests/test_lab_sqlite_repository.py.
- CLI supports explicit local init and privacy-safe aggregate health;
  refuses implicit creation, overwrite, unknown migration/corrupt DB.
- No private trace, VIN, PIN, EEPROM or VIDA XML committed.

NOT IMPLEMENTED:
- Go SQLite metadata integration is implemented and tested but has not
  been connected to running J2534/IPC/ECU engine.
- Existing Go database/sql boundary is metadata-only and cannot activate a scenario.
- Hash-verified compiled scenario snapshot and runtime fixture selection.
- Named Pipe IPC, headless Go service, actual x64 J2534 DLL.
- Dvinholm real native x64 J2534 end-to-end tests.
- Authorized live VIDA/SectorV identification of target XC90 MY2009.
- Physical J2534/vehicle testing.

## Stage 60B-2 COMPLETED | Real Go SQLite (PR #68)

- https://github.com/vorlocsev/virtualcar/pull/68
- MERGED to development: 4942fb412d85c9e6e4057a7ded44542cc72e86ce
- Final Windows x86 CI #604 SUCCESS (build + native routes).
- VMware LAB workflow #438 SUCCESS (packaging/synthetic tests,
  not a performed physical J2534 or actual VMware client run).
- New Go sqlite_driver.go uses modernc.org/sqlite v1.36.3,
  locked go.mod/go.sum, fixed local SQLite v1 schema, WAL,
  migration checksums, exclusive initialization, consistent
  VACUUM INTO backup and fail-closed corruption rejection.
- Reuses stage 60B-1 labdb.Repository; both sets of eight Go
  synthetic tests execute under CI. Windows x64 no-CGO Go
  cross-build passed, but no x64 native J2534 DLL exists.
- No scenario reply enabled: Snapshot.ApprovedReadOnly=false.
- Older PR #65 was CLOSED WITHOUT MERGE as superseded by #68.
  Its original CI #597 was successful but conflicted with
  merged parallel PRs #66 and #67. No forced overwrite performed.
- No real XC90 V8 MY2009 VIN/CEM/VIDA acceptance proven.

## NEXT STAGE: 61 Scenario Compiler

1. Create canonical, immutable scenario payloads from scoped approved
   fixture bindings and exact ECU/CAN routes.
2. Verify the SHA-256 of the entire materialized snapshot.
3. Refuse missing/research-only/ambiguous Volvo CEM evidence.
4. Add 6-8 deterministic tests and preserve J2534 native regressions.
5. Never publish Virtual Car; keep Dvinholm the primary product.

Canonical roadmap:
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md

## New priority (2026-11-06): full C# / .NET 10 migration

The user requested rewriting **all Virtual Car implementation in C#**.
This decision starts after the already completed Stage 60B-2 Go SQLite
PR #68 (merge 4942fb41, CI #604 success). Previous Go stage 60B-2 is
COMPLETED historically, but new Go Stage 61+ plans are SUPERSEDED.
Keep working C/Go as parity baseline, do not delete.

New migration ADR:
docs/architecture/VIRTUALCAR-CSHARP-DOTNET10-MIGRATION.md
New pilot: PR #70, branch feature/csharp-dotnet10-migration-foundation
(CS-01). Check latest head CI before claiming build success.
Introduced: .NET 10 C# lab controller, 8 synthetic C# tests, Native AOT
J2534 ABI-only 14-export probe and x86/x64 matching loader check.
The probe returns ERR_NOT_SUPPORTED and MUST NOT be registered or shipped.
No CAN simulation, full C# SQLite, physical J2534 or Dvinholm native
integration has been completed yet.

NEXT: complete CS-01 native x86/x64 CI, then CS-02 Microsoft.Data.Sqlite.
Keep Dvinholm primary and NEVER publish Virtual Car without permission.

## Короткая фраза для продолжения в новом чате

**virtual car**

Когда пользователь пишет только эту фразу, нужно восстановить контекст
проекта по этому файлу и
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md из ветки development
репозитория vorlocsev/virtualcar, проверить актуальные PR, CI, коммиты
и продолжить первый незавершённый этап (сейчас этап CS-01, затем CS-02).

Dvinholm остаётся основным продуктом. Virtual Car используется только
как независимый тестовый стенд. Сборки и релизы Virtual Car не публиковать
без отдельного разрешения. Не выдавать синтетические испытания за
реальную совместимость CEM/J2534.
