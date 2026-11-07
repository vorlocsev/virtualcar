# M5D-2d | Synthetic read replay, deadline and repeatability gates

Status: **FEATURE BRANCH TESTS PREPARED; PRIVATE WINDOWS CI PENDING**.

This is an incremental validation stage for the authenticated,
single-client synthetic VCRD read path completed at M5D-2c.
No new production CAN/J2534 features are added, no route/DID
allowlist is expanded, and no physical adapter, vehicle, PIN,
SecurityAccess or programming is invoked.

## Standalone VCRD ledger tests

`readonly_contract_checks.cpp` has three additional gates (11 total):

9. **Reused numeric session, new Host process**: a previous
   response from an old creation FILETIME is denied even if
   numeric session ID/generation and PID match. Old operation
   IDs cannot be replayed into a re-bound Ledger. A new,
   higher operation ID with the new owner is accepted.
10. **Serial repeated identification under ownership changes**:
    256 offline synthetic requests across eight epochs with
    strictly increasing operations, synthetic DID cycling
    F187/F189/F190 and zero pending entries after every reply.
    Replayed prior operation IDs are denied across revoke/rebind.
11. **Exact timeout boundary repeatability**: 40 synthetic
    pending operations each expire at their exact deadline,
    and replies cannot resurrect the expired slot.

The C++ Ledger is an offline synthetic correlator; these unit
tests do not communicate with a real vehicle or Host.

## Native to C# Host integration stress

New native CLI mode `--readonly-stress <pipe> <pid>` uses one
authenticated M5C-2 session and one C# test Host with the
immutable, digest-verified VCRF fixture. It performs 64
consecutive allowlisted identification requests with exact
expected A/B/C/LAB invented bytes, and verifies pending Ledger
count is zero after each response. It periodically heartbeats
the session, rejects unsupported F191 without closing a healthy
authenticated connection, then performs another F187 read and
cleanly disconnects. The test runs independently for native
Win32 and x64.

The implementation deliberately serializes read requests.
The Ledger maximum of eight remains defense in depth; this
step does NOT demonstrate eight parallel requests, arbitrary
CAN traffic, a deployed J2534 data plane or real ECU responses.

## Acceptance

Private owner-only Windows VMware CI must check out the exact
feature branch source, compile native x86/x64 with MSVC /W4 /WX,
run all 7/7 CTest each with 11/11 inner Ledger gates, managed
Host 17/17, M5D-2b and M5D-2c prior integration cases, plus
one successful new 64-read native ↔ managed Host stress run
on EACH architecture. C/Python 252/Go/.NET baseline must stay
green. All results must be checked in logs before merging.

The feature PR is draft until verified, and must receive a
separate post-merge development push CI. No uploads, packages,
releases, installers, public artifacts or hardware activity.
