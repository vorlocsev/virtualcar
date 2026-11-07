# M5D-2eA | Controlled synthetic reply fault injection

Status: **MERGED; Windows x86/x64 FEATURE + POST-MERGE CI VERIFIED**.

PR #121 merged into development as `97c8e429160d994b749553592db1ac785a8d70f6`.
Automatic [owner-only VMware #42371693670](https://github.com/vorlocsev/virtualcar/actions/runs/42371693670)
completed SUCCESS on that exact SHA. Each native x86 and x64
executed all five fault-injection cases and checked an exact
PASS marker, returned zero user bytes and complete ledger
cleanup. Native CTest 7/7 per architecture, managed Host 17/17,
M5D-2b/c/d, Python 252, Go, Legacy C and .NET PASS.
Artifact count: zero. Feature CI #42371326557 also PASS.
J2534 remains fail-closed and independent of these tests.

[Owner-only VMware #42371326557](https://github.com/vorlocsev/virtualcar/actions/runs/42371326557)
completed SUCCESS on exact feature source `263ea3fc6071d881f0e27d953629204d9c1da3e8`.
Native x86 and x64 each passed 7/7 CTest and all five
separate authenticated negative reply tests: partial outer
header, partial inner body, stalled body, operation mismatch,
DID mismatch. Both the strict native per-case success marker
and managed Host clean exit were checked by the workflow.
Managed Host 17/17, M5D-2b/c/d, Python 252, legacy C,
Go and .NET gates PASS. Zero artifacts, releases or deployment.

This is a narrowly limited *negative-path laboratory test* for
existing read-only authenticated VCRD v1 traffic. It adds no new
general ECU command, CAN bridge, J2534 export or diagnostic write
capability.

## Injection boundary

`LocalLabPipeHost` has a fixed `SyntheticReplyFault` enum whose
default is `None`. The real Host's normal caller uses `None`,
so no wire behavior changes for normal read-only scenarios.

Only `VirtualCar.Service.Checks --serve-once` selects one of
five fixed test modes. A Host must first verify the current-user
Named Pipe, launch secret, live coordinator session, process-bound
VCRD owner identity, monotonic operation ID, exact 0x22 DID and
sealed VCRF route/fixture. Only AFTER all of that may it construct
the normal positive synthetic VCRD response, then alter its
outgoing wire representation for this single test request.

| Host test mode | Native test flag | Required native outcome |
| --- | --- | --- |
| `fault-header` | `--fault-header` | VCLB header stops after 11 bytes, disconnect |
| `fault-body` | `--fault-body` | Full VCLB header + 9 inner bytes, disconnect |
| `fault-stall` | `--fault-stall` | Partial body remains open beyond client I/O deadline, timeout |
| `fault-operation` | `--fault-operation` | Valid VCRD, wrong operation ID, protocol error |
| `fault-did` | `--fault-did` | Valid VCRD, allowlisted but wrong DID, protocol error |

For EVERY case, `AuthenticatedSession::read_synthetic` must
return no user bytes, zero length and entirely reset M5C-2
lifecycle/channels and M5D-1 pending ledger. Faults never
inject vehicle data or produce an accepted positive result.

## CI gates

Run the five new cases against actual C# Host child processes
for each native x86 and x64 executable on the owner-only
`VirtualCar-CI-WIN` runner. Each case must finish with native
and managed child exit code zero; the harness must not treat
a skipped test or a no-argument native executable as success.
Existing native 7/7 CTest both architectures, managed Host 17/17,
M5D-2b 64-read stress, M5D-2c accepted-read cancel/restart,
and C/Python 252/Go/.NET baseline must all remain green.
No uploads, packages, release publishing or hardware changes.

## Limits

This step verifies single-request truncated replies, one
stalled partial body and two correlation mutations. It
does not yet stress repeated Host restart sequences or
higher-frequency cancellation races. Those are future M5D-2eB
work requiring separate CI. No actual J2534 data plane.
