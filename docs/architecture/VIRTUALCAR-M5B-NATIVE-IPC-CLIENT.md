# M5B: native C++20 client for the M5A local pipe

Status: **IN PROGRESS**, stacked on Draft PR #85. This is a protocol and
transport preflight only. The C++ J2534 DLL remains fail-closed and does
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

Parent M5A is verified 9/9 on VMware workflow #42314429323 at head 42df2953. M5B itself remains unverified until its own Windows x86/x64 workflow executes.

The owner-only VMware dispatch selector and x86/x64 cross-language workflow are enabled by PR #88, merged to main as `80e18c201b8167612e3a8eb71e9c23eb58043b19`. The M5B VMware run is still pending.

CI is the authority for compile/runtime claims. Do not mark M5B complete
until Windows x86 and x64 native builds, all 8 offline gates and both
cross-language C++-to-C# integration runs pass.
