# M5C-2: authenticated Host-bound native lifecycle

Status: **MERGED and Windows x86/x64 SELF-HOSTED VMWARE VALIDATED**.
PR #96 merge SHA `7bde901cbd1cc78f1b03efecba44347acacadb10`. Feature self-hosted VMware
#42339519459 SUCCESS; post-merge `development` VMware #42339851382
SUCCESS on this exact merge commit. Both six-Ctest native suites
and both architectures' live Host-loss/restart integration passed.
No uploaded artifacts or releases.

Branch: `feature/m5c2-authenticated-session-lifecycle`.
Base: development commit `2b5bef82d0ee7cd0e21d92e2acf0790b51060f7a`.

## Problem found

M5C-1 keys a bounded session only by the C# coordinator's
`sessionId` and `generation`. A new Host process creates a new
in-memory `ScenarioCoordinator`, whose counters restart. Therefore
a restarted process can legitimately issue the same numeric token
as the old process. PID alone is also insufficient because Windows
may recycle a PID.

## Process-bound identity

After the M5B client opens the pipe, it:
1. Checks the actual Named Pipe server PID against the trusted
   expected PID before sending the launch secret.
2. Opens that process with `PROCESS_QUERY_LIMITED_INFORMATION`.
3. Captures the process creation FILETIME via `GetProcessTimes`.
4. Stores the identity with the returned ACK token.

The lifecycle key is:

`(sessionId, generation, serverPid, serverCreationTime100ns)`.

The creation timestamp distinguishes a new process even when the
OS reuses the PID and the C# coordinator reissues the same numeric
session/generation pair.

## AuthenticatedSession wrapper

`VirtualCarAuthenticatedSession` composes the existing M5B
`ipc::Client` and M5C-1 `BoundedSession`. It does not expose raw
frames, J2534 calls, ECU commands, CAN transmission or an
`approvedSynthetic` override.

- Begin local lifecycle state only after the PID-verified,
  256-bit-secret HELLO receives a valid ACK. The C# Host creates
  that ACK only after `ScenarioCoordinator.OpenSessionAsync`
  accepts the selected verified synthetic scenario.
- Validate the local lease before remote KEEPALIVE.
- Extend the local lease only after a matching remote ACK.
- Reject channel reserve/close after expiry, disconnect or stale
  process identity. At most eight opaque channel slots are exposed.
- On remote failure, GOODBYE, lease expiry or explicit disconnect,
  revoke local state and clear every slot.
- The 5-second default lease is client-side bookkeeping; it is
  not yet a distributed server lease protocol. The Host retains
  its existing bounded pipe I/O deadlines and closes the core
  session in its `finally` path.

## Test coverage added

Four CTest process-identity groups:
1. Host PID and creation time are mandatory.
2. Same numeric token after Host restart is accepted only as a
   new process instance; old slots are dropped and IDs not reused.
3. Duplicate token from the same process instance is rejected.
4. Validation does not extend the lease; stale Host identity
   revokes the current lifecycle.

Three cross-language test modes, run against the actual C#
`VirtualCar.Service.Checks` Host:
- `--lifecycle`: authenticate, verify process identity, reserve
  CAN/ISO15765 slots, remote heartbeat, close slots and GOODBYE.
- `--lifecycle-expire`: let the local lease expire, verify new
  channel reservation is denied, send GOODBYE and clear state.
- `--lifecycle-restart`: authenticate to the first Host, reserve
  a channel, terminate that exact synthetic Host PID, verify
  KEEPALIVE detects pipe loss and revokes all local state; wait
  for the test orchestrator to start a replacement Host on the
  same pipe; reconnect through the *same* AuthenticatedSession
  object; verify the new Host can issue the same numeric 1/1
  token but has a distinct process creation identity; verify old
  channel ID is invalid and the next channel ID is not reused.

The workflow step runs the above separately for native x86 and x64
on the private self-hosted Windows runner. It starts and terminates
only its own synthetic test Host processes. No user/system service,
J2534 driver, physical adapter or ECU is touched.

## Verification boundary

The workflow entrypoint and test step were merged to `main` in
PR #95; the PID-safe orchestrator correction was merged in PR #97.
The feature branch is in the hardcoded owner-only source allowlist.
PowerShell kills only the retained `.NET Process` object it created
for the synthetic Host. The native client never opens a PID with
`PROCESS_TERMINATE` and never terminates an arbitrary process. A manual dispatch from `main` is required:

```powershell
gh workflow run vmware-development-validation.yml `
  -R vorlocsev/virtualcar `
  --ref main `
  -f source_ref=feature/m5c2-authenticated-session-lifecycle
```

## Windows verification: PASS

Private owner-only VMware GitHub Actions
[#42339519459](https://github.com/vorlocsev/virtualcar/actions/runs/42339519459)
completed SUCCESS. The checkout log verifies exact source commit
`7fd40d02be9561e787bb4f701a5d7609cd21ddbf`, which is the PR #96 feature head before this
documentation-only follow-up. Runner: `VirtualCar-CI-WIN`.
- Windows native x86: 6/6 CTest PASS including M5C-2 identity 4 gates.
- Windows native x64: 6/6 CTest PASS including M5C-2 identity 4 gates.
- Windows x86 and x64 separately: C++/C# authenticated lifecycle,
  bounded channel reservation, heartbeat, closing and GOODBYE PASS.
- Windows x86 and x64 separately: local 250ms lease expiry revokes
  slots; host closes and releases its core session PASS.
- Windows x86 and x64 separately: PowerShell terminates only its
  own retained synthetic C# child process handle; C++ reports broken
  pipe, revokes session and channels; replacement Host on same pipe
  reissues numeric 1/1 token with different process identity; stale
  channel IDs are rejected and recovery succeeds PASS.
- M5A 9/9, M5B x86/x64 C++↔C# handshake, Python 252,
  Go, legacy C, actual read-only C/C++ parity and .NET gates PASS.
- GitHub Actions reports **zero uploaded artifacts**. No releases.

The verification criteria below are satisfied by this run:
- MSVC x86 and x64 builds and CTest, including
  `m5c2_host_process_identity_4_groups`.
- Normal authenticated lifecycle + bounded channels on x86/x64.
- Lease expiry + GOODBYE + host cleanup on x86/x64.
- Forced Host loss, local revocation, same-token/new-process
  recovery and stale-channel rejection on x86/x64.
- M5A/M5B and all baseline C/Python/Go/.NET regression gates pass.

No build artifacts, packages, releases or deployments. The C++
J2534 DLL remains fail-closed and is not linked to the new session
wrapper. This stage does not establish a working CAN data plane,
physical J2534 behavior, real Volvo identity, PIN, SecurityAccess
or programming.
