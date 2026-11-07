# M5D-2a | Authenticated C# synthetic fixture reads

Status: **VALIDATED ON PRIVATE WINDOWS SELF-HOSTED RUNNER, PR #102 PENDING MERGE**.
[VMware #42342961556](https://github.com/vorlocsev/virtualcar/actions/runs/42342961556)
executed actual M5D-2a source `5c650ee03a2f1e73af6b7d462dacca0792cc1c38` on
`VirtualCar-CI-WIN`: 17/17 C# Host Named Pipe checks,
MSVC x86 7/7 CTest, MSVC x64 7/7 CTest, M5B and M5C-2
x86/x64 Host-loss/recovery, Python 252, C/Go/.NET PASS.
Uploaded artifacts: zero. This is not native C++ read integration.

This is the Host-side half of M5D-2. Native C++ authenticated
read requests and linkage to the J2534 DLL are not implemented.

## Read-only IPC extension

Existing VCLB v1 HELLO/ACK/KEEPALIVE/GOODBYE stay unchanged.
Two VCLB kinds are added for this laboratory:

- kind 5: ReadRequest with EXACTLY 63 inner bytes, a VCRD v1
  60-byte header and 3-byte UDS synthetic 0x22 DID.
- kind 6: ReadReply with a VCRD v1 positive 0x62 DID reply
  containing 1..61 fixture bytes; maximum inner wire size 124.

The C# Host only handles ReadRequest after verifying the 32-byte
launch secret in constant time and opening a valid core session
backed by an approved synthetic scenario. All subsequent messages
must match the authenticated outer session ID and generation.
Inner VCRD owner must ALSO match that session and this server's PID
and process creation FILETIME. Operation IDs must increase
strictly per authenticated pipe. Invalid frames close the pipe
and the core session is released in the finally block.

## VCRF v1 sealed fixture format

Only an immutable ScenarioSnapshot which passed
ScenarioSnapshot.VerifySynthetic may be used as a fixture source.
The selected scenario's bytes are independently checked as:
- ASCII VCRF at bytes 0..3; version 1 at byte 4
- extended CAN flag at byte 5 (0 or 1)
- request/response CAN IDs LE32 at bytes 6..9 and 10..13
- entry count byte 14, range 1..3
- sorted unique entries: DID BE16, length u8 1..61,
  followed by exactly that many synthetic bytes.
- entire fixture <=256 bytes, no trailing or partial records.

Only synthetic DIDs F187, F189 and F190 are accepted.
The exact CAN route/extended flag must match the fixture.
The Host does not generate a VIN, read physical CAN or query
research/captured scenarios. The digest validates data integrity
relative to the selected synthetic candidate; it is not a
cryptographic signature or proof that input came from a real car.

## Safety and resource constraints

A one-client Named Pipe executes read operations serially with
bounded read/write deadlines; there is no unbounded request task
queue. Outer frames are capped at 256 payload bytes, inner VCRD
frames at 124, and each read request must be exactly 63 bytes.
Requests other than 0x22 DID and replies other than 0x62 DID are
not in this protocol. Failure cases return no positive response
and close the session.

This Host-side integration does NOT use the native M5D-1 eight-slot
ledger yet. It does not promise request cancellation, native
backpressure, client-side replay checks or restart recovery through
a new read endpoint. Those require M5D-2b integration and tests.
J2534.dll remains fail-closed; no physical adapter or ECU access.

## Eight new managed Windows pipe tests

Added to the existing nine M5A checks (target 17/17):
10. Authenticate and read F187/F190 from sealed synthetic bytes;
    KEEPALIVE and GOODBYE continue to work.
11. Wrong Host creation FILETIME is rejected.
12. Wrong CAN route is rejected.
13. SecurityAccess 0x27 is rejected after authentication.
14. Unknown DID / invalid VCRD kind rejected.
15. Replayed operation ID after successful read rejected.
16. Unsealed/non-VCRF scenario, malformed/trailing/oversized
    VCRF records are rejected.
17. Nonzero reserved field and truncated VCRD frame rejected.

Private Windows self-hosted CI was executed successfully for this
feature source on 2026-11-07. It is still not a C++ VCRD data-plane test.
M5A/B/C2 regressions and native x86/x64 CTest must still PASS before
merging. No artifacts, packages, installs or releases.

## Next: M5D-2b

Connect native M5C-2 session and M5D-1 ledger to VCLB read requests,
validate read reply ownership, exact operation/DID/route correlation,
timeouts, cancellation, replay, Host restart and release of all
pending slots. Test a real managed Host with native clients on both
Win32 and x64. J2534 remains fail-closed until separate review.
