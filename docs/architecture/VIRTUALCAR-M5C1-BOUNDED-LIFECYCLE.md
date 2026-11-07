# M5C-1: bounded C++20 session/channel lifecycle preflight

Status: **WINDOWS x86/x64 VMWARE VALIDATED**.
Private Windows VMware #42319530476 SUCCESS, M5C-1 CTest passed
on both x86 and x64, with five total native CTest targets on each.
Native source under test: `89553e37e47b86a3ced83d2c1de01827669bc039`.
The isolated library is NOT connected to the J2534 DLL.

## Why

M5A and M5B prove an authenticated C# Host ↔ C++ client handshake
(Windows VMware #42318278748, x86 and x64). They do NOT make the
fail-closed J2534 DLL a working adapter. M5C-1 prepares bounded
lifecycle state without trusting the process, enabling CAN frames,
or registering a virtual J2534 adapter.

## Contract

- `BoundedSession` is a separate C++20 static library, not linked
  to `VirtualCarJ2534Cpp` or `VirtualCarIpcClient`.
- No external J2534 entrypoint, ECU request or transport route calls
  into this library yet. It exposes only private opaque channel-slot
  reservations, heartbeats and cleanup, NOT a frame API.
- The caller must authenticate the expected Host PID, 256-bit launch
  secret and approved synthetic scenario through existing M5A/M5B
  gates, **before** accepting a `SessionKey`. The `approved_synthetic`
  parameter is a test precondition, NOT an authorization credential.
- A valid session binds nonzero id/generation, uses a monotonic
  millisecond clock, a 100..60000 ms lease and at most 8 slots.
- At `now >= expiry`, the next timed operation returns
  `expired` and drops the session and all its slots. Clock rollback,
  incorrect id/generation and duplicate begin also revoke the
  current session. Arithmetic overflow is rejected.
- A new valid generation closes all slots of the old generation.
  Channel IDs are nonzero, monotonically issued and never reused
  within the process. They cannot serve as authorization across
  process restarts. Refuse 32-bit ID exhaustion.
- Public operations are mutex-serialized; concurrent reservations
  can never exceed 8. `reset()` revokes the session.
- `snapshot()` is a diagnostic read and performs no time validation;
  it MUST NOT be used to authorize transport. Lease invalidation is
  lazy until a timed operation or explicit reset.

## Offline tests: eight independent gates

1. Default deny, no implicit session or slot.
2. Verified synthetic prerequisite, nonzero token and duplicate begin
   fail closed.
3. Heartbeat renewal, exact expiry boundary and cleanup.
4. Monotonic rollback and 64-bit expiry arithmetic overflow.
5. Incorrect generation revokes and invalidates prior slots.
6. Eight-slot cap, invalid kind, close semantics and no ID reuse.
7. Reauthentication clears old slots; reset invalidates all.
8. Twenty-four concurrent reservation attempts yield at most eight
   unique nonzero channel IDs.

Windows proof: private VMware workflow
[#42319530476](https://github.com/vorlocsev/virtualcar/actions/runs/42319530476),
which checked out source SHA `89553e3`:
- Native x86 MSVC configure/build and 5/5 CTest: PASS, including
  `m5c1_bounded_session_lifecycle_8_groups`.
- Native x64 MSVC configure/build and 5/5 CTest: PASS, including
  `m5c1_bounded_session_lifecycle_8_groups`.
- C# M5A 9/9; C++ x86/x64 ↔ C# M5B authentication and GOODBYE;
  Python, legacy C, Go and managed Core/Storage/Scenario: PASS.
- No artifacts, releases, deployments or external adapter registration.

The 8 M5C-1 assertions are synthetic offline tests. The test
does NOT verify real Host lifecycle binding or J2534 routing.

## Next M5C-2 (NOT IMPLEMENTED)

Bind the real authenticated M5A/M5B peer's session/generation to the
lifecycle coordinator. Add crash/heartbeat-disconnect/Host restart
tests and ensure any stale IPC session invalidates the native slots.
Use a trusted monotonic clock at this boundary. Retain J2534
`NOT_CONNECTED` until all separate data-plane tests pass.

Do not claim production launch-secret provisioning, installed
adapter functionality, Dvinholm ECU/VIN acceptance, physical Volvo
ECU access, SecurityAccess, PIN retrieval or programming.
No Virtual Car packages, installers, artifacts or releases.
