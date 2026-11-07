# M5B: native C++20 client for the M5A local pipe

Status: **WINDOWS x86/x64 PRE-FLIGHT VERIFIED** on private VMware run
[#42318278748](https://github.com/vorlocsev/virtualcar/actions/runs/42318278748).
M5A parent PR #85 merged to development as `410ade408`; M5B is PR #87.
This is a protocol and transport preflight only. The C++ J2534 DLL remains fail-closed and does
not link this client yet.

## Scope

- Add a Windows-native C++20 client library in
  `emulator/native-cpp/include/virtualcar/ipc_client.hpp` and
  `emulator/native-cpp/src/ipc_client.cpp`.
- Mirror the M5A version-1 28-byte little-endian frame exactly:
  `VCLB`, u16 version, u16 kind, i32 payload length, u64 session ID,
  u64 generation, payload capped at 256 bytes.
- Permit only HELLO, KEEPALIVE and GOODBYE from the client; ACK is the
  only accepted server response. There is no arbitrary command API.
- Use Windows Named Pipes with overlapped I/O, explicit bounded connect,
  read and write deadlines, session/generation binding, strict pipe-name
  allowlisting and fail-closed handle cleanup.
- Require the expected server PID from the trusted launcher and verify it
  with `GetNamedPipeServerProcessId` **before sending the launch secret**.
  Open the client handle with `SECURITY_SQOS_PRESENT | SECURITY_IDENTIFICATION`
  so the server cannot impersonate the client.
- Serialize public operations with a mutex. No SQLite calls, CAN frames,
  ECU requests, J2534 success returns, or physical device access.
- Wipe the temporary HELLO secret payload and encoded frame buffers after
  transmission. The client does not retain the launch secret.

## Gates

Eight native offline gates:
1. Exact C#-compatible HELLO golden vector.
2. ACK roundtrip and session token preservation.
3. Roundtrip of all four protocol kinds.
4. Reject bad magic, version and kind.
5. Reject truncated, oversized and trailing-byte frames.
6. Refuse unsupported commands and payloads above 256 bytes.
7. Pipe-name allowlist rejects path injection and invalid characters.
8. Missing server and a peer that trickles an incomplete ACK both obey absolute connect/read deadlines.

Additional native integration:
- C# `VirtualCar.Service.Checks --serve-once <pipe>` hosts one approved
  synthetic scenario using a test-only fixed 32-byte secret.
- Native C++ x86 and x64 clients independently connect, authenticate,
  send two concurrent session-bound KEEPALIVEs (serialized by the client), send GOODBYE, and require both processes to exit successfully. The C# host resets the coordinator afterward to prove the session was released.
- This test secret is only for CI and must never be used by a production
  launcher. Production launcher provisioning of the expected PID and launch secret remains a separate task.

## Safety boundaries

- The IPC client is not linked into `VirtualCarJ2534Cpp`.
- The J2534 DLL still returns fail-closed results and is not registered.
- No PassThru operation is enabled, no real vehicle identity is asserted,
  and no CAN/ECU data plane exists yet.
- M5B does not complete M5. Still outstanding: production secret
  provisioning, separate control/admin pipe, client identity/authorization
  policy, backpressure and crash recovery, wiring into J2534 lifecycle,
  Dvinholm E2E and physical J2534 acceptance.
- No Virtual Car release, package or artifact publication.

## Verification record and next stage

M5A host validated 9/9 on private VMware #42314429323 and merged
into `development` via PR #85 (merge commit `410ade408`).

M5B native source head `053e60e5996228b1776f4d728d61de839cad9256`
was exercised by private VMware workflow #42318278748, using the
workflow definition from `main` commit `84f12eb22c837c32ff03728878edf3ccd10a5004`.
Results:
- C++ x86: 4/4 CTest including all eight M5B gates.
- C++ x64: 4/4 CTest including all eight M5B gates.
- Wrong-server-PID before HELLO: PASS separately on x86 and x64;
  host exit code zero in both cases.
- Client ↔ C# Host HELLO, concurrent session-bound KEEPALIVE and
  GOODBYE: PASS independently on x86/x64; host exit code zero.
- M5A 9/9 and baseline Python/C/Go/.NET checks: PASS.
- No artifacts, packages, deployments or releases.

Prior run #42317744015 hit an orchestrator-only Windows PowerShell
5.1 `Start-Process -PassThru` blank ExitCode. CI-only PR #89 fixed
the owning Process handle on `main`; re-run #42318278748 passed.

**M5A + M5B are not complete M5.** Next is M5C: bind the verified
local IPC session to deliberately fail-closed J2534 lifecycle state,
test bounded channel ownership, lease/heartbeat expiry, restart/crash
invalidation and backpressure, *before* any CAN/ECU data plane is
enabled. No real vehicle, programming, PIN, external J2534
registration, Dvinholm E2E or production launch-secret provisioning.
