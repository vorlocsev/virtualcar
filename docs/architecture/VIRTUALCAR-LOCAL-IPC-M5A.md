# M5A: local, read-only Named Pipe preflight

Status: **DRAFT PR #85**, not M5 completion; CI result must be checked independently.

## Implemented boundary
- New `VirtualCar.Service` .NET10 library, **not** an installed Windows service.
- One Windows byte-mode Named Pipe instance per `ServeOnceAsync` call,
  with `PipeOptions.CurrentUserOnly` and no TCP/network socket.
- Caller-provisioned 32-byte launch secret, copied inside the host and
  compared in constant time, before opening a `ScenarioCoordinator`
  session. Future trusted launcher must provide secret out of band.
- Only an independently verified selected synthetic scenario can open
  the core session; close/invalid commands release it.
- LE v1 envelope: 4 ASCII bytes `VCLB`, u16 version (1), u16 command,
  i32 payload length, u64 session ID, u64 generation; total 28 bytes.
  Payload is strictly capped at 256 bytes and checked **before allocation**.
- Command 1 HELLO: 32-byte secret, session/generation both zero.
  Command 2 KEEPALIVE: empty payload, current session/generation only.
  Command 3 GOODBYE: empty payload, current session/generation only.
  Command 4 ACK: emitted by server, empty payload, issued core token.
  Any other command, version, bad magic, truncated frame, wrong token,
  length or timeout fails closed.
- Single client per pipe, one incoming frame processed before any ACK;
  3-second read timeout in integration checks; no ECU/CAN operation exists.

## Eight native-Windows synthetic gate groups
1. HELLO, session allocation and authenticated KEEPALIVE ACK.
2. No selected synthetic scenario, no session.
3. Wrong 256-bit secret, no session.
4. Invalid header magic and protocol version.
5. Oversize, negative length and truncated header.
6. Stale generation after HELLO.
7. Forged session identifier and unsupported command.
8. Abrupt disconnect, session cleanup, new generation after reset.

The managed CI compiles on Linux, cross-builds for Windows x64 and
runs all eight native Windows pipe checks. **Only GitHub workflow runs
may establish actual pass/fail; adding a test is not passing it.**

## Not yet integrated
- No native x86/x64 C++ J2534 client connection or positive DLL responses.
- No control/admin pipe, peer identity verification beyond OS ACL,
  production launch-secret provisioning or installed headless service.
- No full backpressure queue, crash recovery or multiclient arbitration.
- No Dvinholm E2E / SectorV / VDASH / VIDA acceptance and no
  real XC90 V8 MY2009 diagnostic identity.
- No security access, programming, PIN functionality, release/installer
  publication or physical adapter activity.

M5 cannot be marked complete on M5A alone. Work in the separate private
repository and merge to development only after review and green CI.
