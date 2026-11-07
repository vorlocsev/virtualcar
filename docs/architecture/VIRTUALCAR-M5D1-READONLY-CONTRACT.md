# M5D-1 | Bounded synthetic read-only request/reply preflight

Status: **MERGED, SELF-HOSTED WINDOWS x86/x64 VALIDATED**.
PR #99 merged to development at `4485ae46171ecf84c5ac11dee17848a886654357`.
Post-merge private Windows
[#42341507066](https://github.com/vorlocsev/virtualcar/actions/runs/42341507066)
SUCCESS on that exact commit, with 7/7 native CTest on both x86
and x64 and all baseline managed/legacy/M5A/M5B/M5C2 gates PASS.
Zero uploaded artifacts or releases.
Private VMware [#42341213124](https://github.com/vorlocsev/virtualcar/actions/runs/42341213124)
SUCCESS. Exact checked-out source `622cd526253e6310065ebc8abceaa82b1db60242`.
Native MSVC x86 7/7 CTest, x64 7/7 CTest, including all 8
M5D-1 contract gates on each architecture. All previous
M5A/M5B/M5C-2, C, Python, Go and .NET gates also PASS.
Zero artifacts, packages or releases. The first validation
#42340891720 FAILED on MSVC /WX C4244 from untyped
initializer-list test values, not the contract library.
The explicit typed-array repair was retested and PASSED.
This is a stand-alone offline contract. The C++ J2534 DLL stays
fail-closed; no actual CAN/ECU command, live pipe data transport,
driver registration, physical adapter or package publication occurs.

## Upstream boundaries

M5C-2 authenticates a C# Host via VCLB v1 Named Pipe and binds
each session to its process identity. M4A includes an isolated
bounded CAN/ISO-TP synthetic engine. M4B includes isolated ISO15765
synthetic RX presentation. M5D-1 does NOT link these into the DLL
or activate any data-plane path.

## Proposed VCRD v1 format

The frame is distinct from the existing VCLB v1 control messages.
All fields are little-endian; its 60-byte header has:

- Offset 0: four ASCII bytes VCRD.
- Offset 4: version u16 = 1.
- Offset 6: kind u16 = 1 request or 2 positive response.
- Offset 8: payload length u16; requests exactly 3, replies 4..64.
- Offset 10: flags u16, only bit 0 (extended CAN ID) supported.
- Offset 12: strictly positive operation ID u64.
- Offset 20: session ID u64, generation u64 (at 28).
- Offset 36: Host server PID u32, process creation FILETIME u64 at 40.
- Offset 48: request CAN ID u32, response CAN ID u32 at 52.
- Offset 56: reserved u32, must be zero.
- Offset 60: exactly the declared payload, max 64 bytes.

Maximum wire frame is 124 bytes. No extra, trailing or partial
bytes, unsupported header variants, equal request and response IDs,
or invalid 11-bit/29-bit CAN route values are accepted.

Requests must be exactly 22 F1 87, 22 F1 89 or 22 F1 90:
synthetic software/ECU/VIN identification read operations.
Responses must start with 62 followed by the exact matching DID
and at least one synthetic response byte. The synthetic DID whitelist
is a project design choice; it is not a claim of actual XC90 support.

Unsafe services (0x27 SecurityAccess, 0x2E writes, 0x31 routines,
0x34 download, ECU reset), unknown DIDs, unexpected negative
responses and arbitrary CAN messages are not in this proposal.

## Correlation ledger

A fixed-size, mutex-serialized in-memory ledger accepts at most
eight pending requests. A caller-supplied monotonic millisecond clock
enforces a 100..5000ms per-request timeout. At time >= deadline,
a reply is expired. Operation IDs increase strictly and cannot
be reused across cancel/revoke/rebind in the same ledger instance.

Response matching uses process-bound owner, exact CAN route,
operation ID, positive-read service and DID. Wrong Host, route
or DID revokes the entire ledger; unsupported frames are rejected.
Cancel, expiry tick, revocation and clock rollback are explicit.

CRITICAL: Passing owner fields to Ledger.bind() does not authenticate
anything. Only a future M5D-2 binding can pass a session approved by
the real M5C-2 authentication and a sealed synthetic scenario. The
Codec does not prove response provenance.

## Eight deterministic self-hosted CTest groups

1. Little-endian request/response golden vectors and max payload.
2. Reject wrong magic/version/kind/flags/reserved/trailing/truncated.
3. Reject writes, unsafe services, unknown DID and invalid CAN route.
4. Default deny; invalid owner/timeout/overflow cannot bind.
5. Match owner, route, operation and DID; revoke on mismatch.
6. Eight-slot backpressure, cancel, no replay across reset.
7. Exact expiry boundary, clock rollback and overflow handling.
8. Wrong process identity and twenty-four concurrent submitters.

Both Windows Win32 and x64 must compile with MSVC /W4 /WX and
pass all eight test groups in the private VMware runner.

## Next stage

M5D-2: authenticate the Host and scenario for each operation;
connect a bounded read-only VCRD request/reply path to the C#
Host with true synthetic fixture provenance. Test Host loss,
cancel, timeouts and cross-language bytes on x86/x64.
Review a separate future fail-closed-to-read-only J2534 integration
only after the end-to-end Host behavior is proved.

No Virtual Car builds, artifacts, prereleases or releases.
No physical ECU, PIN, SecurityAccess, writes or programming.
