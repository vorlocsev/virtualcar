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
- Exactly one active listener per host, enforced by an atomic guard;
  a concurrent ServeOnceAsync call is rejected without replacing the
  authenticated client. Guard release is protected by a finally block.
- Single client per pipe, one incoming frame processed before any ACK;
  the host applies a per-frame deadline both to reads and to outbound ACK writes.
  Integration checks configure a 3-second deadline. This is bounded IPC
  preflight only; no ECU/CAN operation exists.

## Eight native-Windows synthetic gate groups
1. HELLO, session allocation and authenticated KEEPALIVE ACK.
2. No selected synthetic scenario, no session.
3. Wrong 256-bit secret or spoofed initial generation, no session.
4. Invalid header magic and protocol version.
5. Oversize, negative length, truncated header and partial post-auth body disconnect.
6. Stale generation after HELLO.
7. Forged session identifier and unsupported command.
8. Concurrent-listener rejection, abrupt disconnect, session cleanup, and new generation after reset.

The managed CI is configured to compile on Linux, cross-build for Windows
x64 and run eight native Windows pipe check groups. **Only GitHub workflow
runs establish actual pass/fail; adding a test is not passing it.**

## CI blocker observed 2026-11-06
- Last Windows job that executed M5A tests: **6/8** on earlier head
  `29e54e16`. Invalid-frame injection groups 04/05 failed with
  `IOException` during early pipe rejection. Later test code permits
  those expected broken-pipe writes and requires no ACK, but **8/8 is
  still unconfirmed**.
- At head `8d193db5`, workflow [42260830270](https://github.com/vorlocsev/virtualcar/actions/runs/42260830270)
  failed with zero job steps in all four jobs. The corresponding
  emulator and VMware workflow runs also failed before executing
  jobs. This is an execution/scheduling or repository-level blocker
  of **undetermined cause**, not proof of C# test failure.
- Changes after that head add ACK write deadlines and extra negative
  regression cases. They also require a real Windows CI execution.
- Do not merge M5A or mark M5 complete without green, executed CI.


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
