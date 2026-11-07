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


## VERIFIED: M5D-2d replay/deadline and serial read stress (FEATURE CI PASS, 2026-11-07)

**Private VMware feature verification SUCCESS:** [CI #42369341323](https://github.com/vorlocsev/virtualcar/actions/runs/42369341323)
checked out exact source `5fff8957dd6963d013be6a6f0b0fee3f78b7ac1b`. Native MSVC x86 and x64
each passed 7/7 CTest (including 11 Ledger groups in the
M5D-1 test executable), C# Host 17/17, and new authenticated
64-read C++ ↔ C# Host serial stress on BOTH x86 and x64 PASS.
M5B/M5C-2/M5D-2b/M5D-2c, legacy C, Python 252, Go, and .NET
also passed. No GitHub Actions artifact uploads, releases,
or deployments. **Post-merge CI is still required.** M5D-2d extends
the isolated M5D-1 Ledger C++ CTest suite from eight to eleven
deterministic groups:
- rebind with reused numeric session/generation but a different
  Host FILETIME, denying a stale positive response and reused
  operation ID;
- 256 repeated synthetic requests across eight Host ownership
  epochs, with zero pending slots after every response;
- 40 exact timeout-boundary cycles rejecting expired replies
  and preventing their resurrection after revoke/rebind.

The existing native `vc_ipc_client_checks` also gains
`--readonly-stress`, which makes 64 sequential authenticated
F187/F189/F190 fixture requests against one real C# Host process,
checks exact invented A/B/C/LAB bytes and zero M5D-1 pending slots
after every response, refreshes session KEEPALIVE, rejects F191,
then tests one final permitted read and clean disconnect.

These tests stress the *existing* serial synthetic reader, not a
new multi-request pipeline. There are no new write services,
J2534 DLL links, real vehicle identification or physical CAN.
Owner-only Windows x86/x64 feature VMware gate #42369341323
PASSED; PR #117 is now eligible for merge after the docs-only
evidence update. Independent automatic development CI on the
merge commit must still run the identical 64-read checks.

## COMPLETED: M5D-2c in-flight synthetic read cancellation and Host restart (Windows x86/x64, 2026-11-07)

**Merged and independently reverified:** PR #109 merged into
`development` as `30bb9dcd48eeb1e4259dca43d6a31c466cd5c69c`. Automatic owner-only
[VMware #42368227332](https://github.com/vorlocsev/virtualcar/actions/runs/42368227332) completed
SUCCESS on this exact merge commit. Native MSVC x86 7/7 and
x64 7/7 CTest, managed C# Host 17/17, M5B/M5C-2/M5D-2b
and Python 252/C/Go/.NET PASS. The M5D-2c step *actually ran*
both new cases on each architecture: cancellation of an already
accepted synthetic read with no stale payload, and Host kill
during the accepted read followed by a new PID+FILETIME-bound
Host and clean F187 recovery. Uploaded artifacts: 0. No
releases or deployments. The J2534 DLL remains fail-closed.


M5D-2c introduces a strictly read-only, cooperative cancel
signal for the existing native `ipc::Client`. A different thread
may atomically request cancellation while an overlapped response
read is pending. The owning I/O thread wakes within a bounded
40ms polling slice, cancels the exact OVERLAPPED request through
CancelIoEx, waits for its completion, closes its pipe, and
revokes M5C-2 channels and M5D-1 ledger state. No unsafe
cross-thread `CloseHandle` or PID-based kill APIs are exposed.
A cancellation signal is sticky until a fresh Host is fully
authenticated. A reply that races cancellation is discarded
before the caller sees synthetic bytes.

The C# test Host adds an opt-in `read-held` scenario: after
authenticating the 256-bit HELLO, validating the live process-bound
VCRD read, and resolving a SHA256-sealed synthetic VCRF fixture,
it writes an explicitly requested test marker and holds the
positive reply for six seconds. Production Host has no barrier.
This allows deterministic tests of cancellation **during** a
validated read, and loss of Host #1 *during* the pending read.
The runner kills only its own retained C# child Process handle,
then starts Host #2 with the same pipe name, confirming numeric
session IDs can be reused while process identity changes.

M5D-2c adds dedicated native CLI integration modes and an
owner-only self-hosted VMware step for BOTH x86 and x64.
The acceptance criteria are two tests per arch: active-read
cancel with no exposed payload, and mid-read Host kill,
full revoke, reconnect and successful clean synthetic F187
read on a new Host. **Private VMware validated feature SHA `2500e997403d870f1957883fc5e85b076a273cdf`:**
[#42367882755](https://github.com/vorlocsev/virtualcar/actions/runs/42367882755)
SUCCESS. Both x86 and x64 passed the two new accepted-read
integration tests: cancellation with no stale reply and Host
kill/restart with refreshed PID+FILETIME and successful synthetic
F187 recovery. Native x86 7/7 CTest, native x64 7/7 CTest,
C# Host 17/17, M5B/M5C-2/M5D-2b, Python 252, legacy C, Go and
.NET all PASS. GitHub Actions uploaded 0 artifacts.
The previous failures #42362605653 (reserved PowerShell $Host)
and #42367076790 (automatic $Args parameter) were limited to
the test launcher. CI PRs #112/#113 and #114/#115 corrected them
before the successful feature run; no feature logic changed.
Post-merge CI #42368227332 passed; retain fail-closed J2534. The existing M5D-2b four per-arch
read tests, M5C-2 restart, managed 17/17 and CTest 7/7
must remain green. There is no public arbitrary CAN/J2534
data plane, physical ECU, writes, PIN, SecurityAccess,
programming, package publication or Virtual Car release.

## NEXT: M5D synthetic read-only hardening (NOT IMPLEMENTED)

M5D-2c's serial read, active cancellation and Host crash/recovery
have now passed both feature and post-merge private Windows CI.
Further proposed work is stress/repeatability validation of the
same synthetic-only lifecycle, explicit stale-token/replay
negative tests across reconnect, and inspection of per-operation
deadline accounting. No eight-request concurrent pipe transport
or J2534 CAN data plane is claimed as implemented. Keep
`VirtualCarJ2534Cpp` fail-closed and unlinked; no vehicle
identification, physical CAN, PIN, SecurityAccess, programming
or Virtual Car binary publishing.

## COMPLETED: M5D-2b native authenticated synthetic VCRD reader (Windows x86/x64 PASS, 2026-11-07)

**Merged and post-merge reverified:** PR #105 merged as `08b3a9da3c6693f655b7157a68ff5ad26bdf1dda`.
Its first automatic CI #42344476899 passed baseline gates, but
still used older `development` workflow YAML lacking the new
cross-language M5D-2b step. PR #107 synchronized the self-hosted
central workflow byte-for-byte with `main`. Automatic
[CI #42344666980](https://github.com/vorlocsev/virtualcar/actions/runs/42344666980) then passed on
`2989dcbf77676e6555b6de164539fe6a5dd2253b`, explicitly running four M5D-2b
C++↔C# cases on each of Windows x86 and x64: sealed synthetic
F187/F189/F190 data, wrong-route refusal, missing fixture refusal
and pre-read lease expiry. Native CTest 7/7 each, C# Host 17/17,
Python 252, C/Go/.NET, M5B/M5C-2 all PASS. Artifacts: 0.


**Private VMware verified:** [#42344223822](https://github.com/vorlocsev/virtualcar/actions/runs/42344223822)
SUCCESS on exact source `8742b687c388f1603b90d95af95827b86f09b92b` checked out by
`VirtualCar-CI-WIN`. Native MSVC x86 7/7 and x64 7/7 CTest,
managed Host 17/17, Python 252, C/Go/.NET, M5B and M5C-2 all PASS.
For EACH of x86/x64, real C++ ↔ C# pipe runs confirmed sealed
synthetic F187/F189/F190 reads, wrong CAN route rejection,
missing fixture denial, and local lease expiry. No uploaded
artifacts, packages or releases. The J2534 DLL remains fail-closed.

Implementation branch: `feature/m5d2b-native-readonly-ipc-client`.
The M5B native Windows Named Pipe Client now has a dedicated
`read_synthetic` method that accepts only valid M5D-1 0x22 requests,
writes an authenticated VCLB kind=5 envelope, and expects VCLB kind=6
containing one exact bounded VCRD positive reply. It verifies the
outer session/generation, process-bound owner identity, operation ID,
CAN route, DID and 0x62 service before exposing any bytes.

M5C-2 `AuthenticatedSession` now composes M5D-1 `Ledger` and
native IPC read. It first validates and heartbeats the authenticated
Host; its first route is fixed for the rest of that session;
operation IDs increase across disconnect and reconnect; only
F187/F189/F190 may be requested; Ledger records, correlates, times
out and revokes operations. Host denial, malformed reply, timeout,
lease expiry and disconnect revoke all channel and pending state.

New Windows cross-language CLI modes are being prepared for BOTH
native Win32 and x64: positive sealed synthetic fixture reads,
denial of mismatched CAN route, missing VCRF fixture rejection,
and local lease expiry before any read. Existing M5A 17/17,
M5B/M5C-2 and native CTest must remain green. No asynchronous
8-in-flight IPC pipeline is claimed: reads serialize by mutex;
the eight-slot ledger is retained for exact correlation/limits.
Live in-flight read crash/restart and cancellation tests remain for
the next follow-up. **x86/x64 integration verified; PR #105 merged.**

No `VirtualCarJ2534Cpp` linkage, no physical CAN, real ECU/vehicle
identity, SecurityAccess, PIN, programming, artifacts or releases.

## COMPLETED: M5D-2a authenticated C# Host synthetic fixture reads (Windows PASS, 2026-11-07)

**Merged and verified:** PR #102 merged into `development`
as `850cc049ac7b78316f3c6e59808e9fbe957b9e0e`. Automatic [VMware CI #42343287172](https://github.com/vorlocsev/virtualcar/actions/runs/42343287172)
completed **SUCCESS** on this exact merge commit: C# Host 17/17,
Win32 7/7 CTest, x64 7/7 CTest, M5B/M5C-2 and baseline Python/C/Go/.NET
checks PASS. Artifacts: 0. This does not expose a native read client
or activate the J2534 data plane.


M5D-2a introduces a strict C# VCRD v1 codec and synthetic VCRF
fixture parser inside the existing current-user VCLB Named Pipe Host.
After an authenticated 256-bit-secret HELLO and valid core scenario
session, VCLB kind 5 accepts only exact 63-byte VCRD synthetic
22 F187/F189/F190 read requests. The embedded session/generation,
Host process PID and creation FILETIME must match; operation IDs
must increase strictly. The Host revalidates the core session and
returns only 62 + DID + bytes from a verified synthetic VCRF fixture
in VCLB kind 6. Wrong route, unsafe services, missing/corrupt fixture,
forged Host identity, malformed frames and replay fail closed.
The fixture is SHA256-verified and copied by ScenarioSnapshot before
it can be read; no captured/real-car bytes are accepted.

Eight new managed Windows pipe checks (10..17), on top of the nine
M5A checks, cover valid reads, Host identity, route mismatch,
SecurityAccess denial, unknown DID/kind, replay, bad scenario and
malformed VCRD. **Self-hosted Windows CI VERIFIED:** [VMware #42342961556](https://github.com/vorlocsev/virtualcar/actions/runs/42342961556)
SUCCESS on the exact M5D-2a code commit `5c650ee03a2f1e73af6b7d462dacca0792cc1c38`.
Runner `VirtualCar-CI-WIN`, C# Host checks 17/17 (nine pre-existing
and eight new), native Win32 7/7 CTest, native x64 7/7 CTest,
M5B x86/x64, M5C-2 host loss/restart x86/x64 and Python 252,
Legacy C, Go, .NET all PASS. Zero uploaded artifacts.
Verified only the Host-side synthetic read path; C++ read client
M5D-2b is subsequently implemented and verified as documented above.
This step only enables serial read-only fixture responses inside the
C# Host; M5D-1's eight-slot native C++ ledger is still isolated.

**M5D-2b** subsequently connected the native M5C-2 authenticated
client to M5D-1 ledger and the C# Host for x86/x64 synthetic
reads (evidence above). Separate in-flight read cancel and
Host crash/restart coverage is still pending. No J2534 DLL
linkage or CAN/ECU physical activity. No releases.

## COMPLETED: M5D-1 offline synthetic read-only VCRD contract (Windows PASS, 2026-11-07)

**Merged & post-merge verification:** PR #99 merged to
`development` at `4485ae46171ecf84c5ac11dee17848a886654357`. The owner-only
[VMware #42341507066](https://github.com/vorlocsev/virtualcar/actions/runs/42341507066)
completed SUCCESS on this exact source commit. C++ native x86
and x64 each passed 7/7 CTest including the new 8-group
`m5d1_synthetic_readonly_contract_8_groups`; all managed C#,
legacy C/Python/Go, M5A, M5B and M5C-2 gates also passed.
Zero uploaded artifacts. This does not activate a J2534 data plane.


M5C-2 provides a verified local Host and session lifecycle, but
not a functional J2534 adapter. M5D-1 adds a standalone synthetic
read-only VCRD v1 binary envelope and bounded correlation ledger,
distinct from M5A/M5B VCLB v1 control IPC. The fixed 60-byte header
carries process-bound owner, operation ID and exact CAN route;
payload <=64 bytes, wire <=124 bytes. Only 0x22 read requests
and matching 0x62 positive replies for synthetic DIDs F187, F189,
F190 are permitted. Unknown service/kind/DID and writes are denied.

A maximum-eight-operation ledger enforces strictly increasing
operation IDs, 100..5000 ms deadlines, exact response identity/route/
DID correlation, explicit cancel/reset, replay denial, clock rollback,
bounded capacity and concurrent safety. Eight deterministic CTest
groups PASSED private Windows x86/x64 self-hosted CI:
[#42341213124](https://github.com/vorlocsev/virtualcar/actions/runs/42341213124),
which checked out exact feature source `622cd526253e6310065ebc8abceaa82b1db60242` on
`VirtualCar-CI-WIN`. MSVC native x86: 7/7 CTest; x64:
7/7 CTest, including `m5d1_synthetic_readonly_contract_8_groups`
on both architectures. M5A 9/9, M5B x86/x64, M5C-2 Host
loss/restart on x86/x64, Python 252, Go, Legacy C and
.NET gates passed. GitHub Actions artifacts: 0. First
attempt #42340891720 failed at /WX C4244 implicit integral
initializer conversions in the test source only; fix commit
`622cd526253e6310065ebc8abceaa82b1db60242` passed the complete follow-up CI.
The caller MUST authenticate M5C-2 and the sealed synthetic
scenario before binding the ledger: this isolated contract cannot
prove authentication or response provenance by itself.

M5D-1 does NOT touch the C# Host, IPC socket, CAN transceiver or
J2534 DLL. It is an OFFLINE proposed wire contract, not a working
data plane. M5D-2 will bind the authenticated Host and sealed
fixtures with end-to-end x86/x64 tests; separate J2534 bridging is
later. No physical devices, real ECUs, PIN, writes or releases.

## COMPLETED checkpoint: M5C-2 authenticated Host-bound lifecycle PASSED (2026-11-07)

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
PR #96 **MERGED** into `development` as
`7bde901cbd1cc78f1b03efecba44347acacadb10`. The post-merge private self-hosted Windows
[#42339851382](https://github.com/vorlocsev/virtualcar/actions/runs/42339851382)
completed **SUCCESS** on exactly that merge commit.
Both native x86/x64, CTest, M5C-2 Host-loss/restart, M5A/M5B,
legacy C/Python/Go/.NET checks passed, and artifact count was zero.
The J2534 DLL remains fail-closed and unlinked to this wrapper. No CAN/ECU data plane,
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
