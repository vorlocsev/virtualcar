# M5D-2c | In-flight synthetic read cancel and Host crash/restart

Status: **MERGED and FEATURE + POST-MERGE Windows x86/x64 SELF-HOSTED VERIFIED**.
PR #109 merged as `30bb9dcd48eeb1e4259dca43d6a31c466cd5c69c`.
Automatic [VMware #42368227332](https://github.com/vorlocsev/virtualcar/actions/runs/42368227332)
SUCCESS on this exact commit: native x86/x64 each 7/7 CTest,
managed C# Host 17/17, M5D-2c two accepted-read cancellation
and Host crash/restart tests **on each architecture**, M5D-2b
and M5C-2 baseline all PASS. Uploaded artifacts: 0.
Feature validation [#42367882755](https://github.com/vorlocsev/virtualcar/actions/runs/42367882755)
also passed on source `2500e997403d870f1957883fc5e85b076a273cdf`.
J2534 DLL remains fail-closed.
Owner-only [VMware #42367882755](https://github.com/vorlocsev/virtualcar/actions/runs/42367882755)
SUCCESS, checked-out exact feature SHA `2500e997403d870f1957883fc5e85b076a273cdf`.
Native CTest x86 7/7, x64 7/7; C# Host 17/17; M5D-2b
four read-only tests per architecture and M5D-2c two new
accepted-read tests per architecture PASS. Legacy C, Python
252, Go and .NET PASS. No GitHub Actions artifacts uploaded.
CI failures #42362605653 ($Host) and #42367076790 ($Args)
were isolated to PowerShell test harness and fixed by PRs
#112/#113 and #114/#115 before the passing feature run.

This substage extends M5D-2b **synthetic** Named Pipe reads.
It does NOT enable any PassThru, CAN physical transport, ECU
programming or arbitrary command. The J2534 DLL remains
completely fail-closed and unlinked.

## Cancellation model

`ipc::Client::request_cancel_read()` sets a sticky atomic flag
that can be written by another thread without taking the
read-side `mutex_`. Only the owning thread holding that mutex
performs `CancelIoEx` on its own single pending overlapped pipe
I/O, waits for completion, then closes the pipe. The read waits
in 40ms slices while respecting its existing absolute deadline.
This avoids the deadlock of calling `disconnect()` from
another thread while a read holds the same mutex, and avoids
a cross-thread close/use-after-free of a pipe handle.

`AuthenticatedSession::cancel_read()` requests the same
cooperative cancellation. The pending request never exposes
partially received synthetic bytes. On cancellation, local
M5C-2 lifecycle and channel slots, plus M5D-1 pending ledger,
are fully revoked; new requests require a fresh authenticated
Host. The flag resets only after a successful fresh HELLO/ACK.
The object must remain alive until the read thread joins.
Cancellation is tested only on a synthetic 0x22 DID read,
not on unrelated control verbs or J2534 callbacks.

## Deterministic Host barrier

The managed Host includes an optional injected asynchronous
read barrier which normally is null. The only test harness
entry point `--serve-once pipe read-held absolute.ready`
supplies it. The Host writes `accepted` to that marker
**after** secret authentication, session checks, strict VCRD
and sealed VCRF validation, **before** producing a positive
reply. It holds that reply for 6 seconds under a 10-second
Host deadline. The test marker itself never changes any
route, DID, response bytes, Host identity or production
security policy.

## Private VMware acceptance

Existing M5D-2b four read tests per architecture stay enabled.
Two additional M5D-2c integration cases run on each of Win32/x64:

1. `--readonly-cancel pipe pid accepted.ready`: issue a valid
   F190 request on a worker thread, wait until Host positively
   marks that read as accepted, cancel from the other thread,
   join, and require Result::cancelled, zero payload bytes,
   zero pending or channel state, and Host cleanup.
2. `--readonly-crash-restart pipe pid accepted.ready lost.txt
   next.pid`: start accepted F187 read on worker thread,
   kill the exact owned Host #1 Process object, observe a
   transport error and complete local revocation, then
   start Host #2 on same pipe name. Require new Host process
   identity despite numerical session 1/1 being reissued,
   and successful F187->AB synthetic read with no old
   response resurrected. Kill only a retained child handle,
   never by looking up an arbitrary PID.

Native MSVC /W4 /WX must pass 7/7 CTest on both x86/x64;
managed C# Host 17/17, previous M5C-2 and M5D-2b, Python
252, Go/C/.NET regression gates must remain green.
Private full x86/x64 feature CI succeeded in #42367882755
with zero uploaded artifacts. Post-merge automatic #42368227332 independently executed
on the exact development merge commit and passed.
No releases, deployments or hardware interactions.

## Limitations

This does not implement protocol-level asynchronous CANCEL
frames, eight simultaneous pending pipe reads, cancellation
of the C# Host's CPU work, or physical J2534 CAN/ISO15765.
Cancellation closes this synthetic pipe and invalidates its
entire session; a caller must start a new authenticated
session for subsequent reads. I/O deadline remains bounded.
