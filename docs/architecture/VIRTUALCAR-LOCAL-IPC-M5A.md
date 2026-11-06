# M5A: local, read-only Named Pipe preflight

Status: **DRAFT PR #85**. Windows VMware validation is **8/8 PASS** (run #42303814581, attempt 2); not merged and not M5 completion.

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
  the host applies the configured deadline to connection acceptance, reads and outbound ACK writes.
  Integration checks configure a 3-second deadline. This is bounded IPC
  preflight only; no ECU/CAN operation exists.

## Nine native-Windows synthetic gate groups
1. HELLO, session allocation and authenticated KEEPALIVE ACK.
2. No selected synthetic scenario, no session.
3. Wrong 256-bit secret or spoofed initial generation, no session.
4. Invalid header magic and protocol version.
5. Oversize, negative length, truncated header and partial post-auth body disconnect.
6. Stale generation after HELLO.
7. Forged session identifier and unsupported command.
8. Concurrent-listener rejection, abrupt disconnect, session cleanup, and new generation after reset.
9. Idle listener accept deadline, listener-guard release and successful re-arm.

The managed CI is configured to compile on Linux, cross-build for Windows
x64 and run eight native Windows pipe check groups. **Only GitHub workflow
runs establish actual pass/fail; adding a test is not passing it.**

## CI history and verified Windows run

### Earlier blockers (2026-11-06)
- Earlier M5A head `29e54e16` executed **6/8** groups; invalid-frame
  groups 04/05 exposed broken-pipe handling in the test harness.
- Workflow [42260830270](https://github.com/vorlocsev/virtualcar/actions/runs/42260830270)
  failed before job steps executed; it did not establish a code-level
  pass or failure.
- First run against the M5A branch,
  [#42303814581 attempt 1](https://github.com/vorlocsev/virtualcar/actions/runs/42303814581),
  stopped in the Python suite with Windows `WinError 32`: an SQLite
  native handle remained open after a failed PRAGMA, and a direct test
  connection used a context manager that does not close the connection.

### Verified Windows VMware run (2026-11-07)
- [#42303814581 attempt 2](https://github.com/vorlocsev/virtualcar/actions/runs/42303814581)
  checked out `feature/m5a-secure-local-ipc-preflight` at
  `e223b902903047758077546dd55a34e3861ed6cc` and completed **SUCCESS**.
- Python: **252 tests, 1 expected skip**.
- Go tests and vet: PASS.
- Native C++ x86 and x64 configure/build/CTest: PASS.
- .NET Core: **8/8**; SQLite Storage: **8/8**; Scenario Compiler: **8/8**.
- M5A Windows Named Pipe integration: **8/8**, all eight groups PASS.
- The WinError 32 fix is included in commits `8b86de8` and
  `e223b90`: failed SQLite connection setup closes its native handle,
  and the direct test connection is explicitly closed before temp cleanup.

The eight-group Windows synthetic CI gate is green on the validated commit above. PR #85 remains Draft for review. A subsequent hardening patch (`9479e2a`, `a50c1a3`) now also bounds idle connection acceptance and adds gate 09 for timeout/listener re-arm. **That ninth gate and the current branch head have not yet been re-run on VMware.** Do not mark M5 complete: the validated eight-group preflight does not prove C++ J2534 client interop, production secret provisioning, Dvinholm integration, or physical adapter acceptance.


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
