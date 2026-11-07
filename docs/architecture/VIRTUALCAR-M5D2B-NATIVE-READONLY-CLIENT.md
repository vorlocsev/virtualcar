# M5D-2b | Authenticated native synthetic read client

Status: **IMPLEMENTED ON FEATURE BRANCH; PRIVATE WINDOWS CI PENDING**.
The J2534 DLL remains fail-closed and does not link this module.
This is *not* a real CAN/ISO15765/J2534 adapter.

## Native wire contract

`ipc::Client::read_synthetic` is a dedicated read-only method.
Its input must pass `readonly::Codec::encode` as an exactly
three-byte, allowlisted 0x22 DID request. It transmits a VCLB v1
`read_request` (kind 5) on the already authenticated Named Pipe,
then accepts only `read_reply` (kind 6) with:
- the current authenticated outer session ID and generation,
- inner VCRD v1 valid version/header/kind and 4..64 payload bytes,
- matching 0x62 DID, correlation operation ID and exact CAN route,
- the same M5C-2 process-bound session, Host PID and FILETIME.
All frames are bounded and transport failures close the IPC handle.
Unknown CAN/ECU/write commands are never exposed.

`AuthenticatedSession::read_synthetic(route,did)` enforces
M5C-2 lifecycle validation and remote KEEPALIVE before each read.
It owns one M5D-1 `readonly::Ledger`: first route becomes fixed
until disconnect, at most eight operations can be pending,
per-operation deadline is 3000 ms, operation IDs increase
monotonically across reconnect in this wrapper. The current
implementation serializes reads by one mutex: the eight-slot cap
is defense in depth, not eight concurrent live requests.

A positive response is accepted only after `Ledger::complete`
correlates request ID, owner identity, CAN route and DID. The
lifecycle lease is revalidated after the I/O. Host denial, malformed
data, timeout and lease expiry revoke both session and ledger.
Caller receives 1..61 *synthetic fixture* bytes, not a CAN frame.

## Cross-language Windows tests

Test executable `vc_ipc_client_checks` gains four integration modes.
Both x86 and x64 are to run independently against actual
`VirtualCar.Service.Checks` C# Host child processes:
1. `--readonly` with `read-session`: F187 -> AB, F189 -> C,
   F190 -> LAB, then reject F191 locally, forbid route switching,
   KEEPALIVE and GOODBYE.
2. `--readonly-deny` with `read-session`: wrong CAN route,
   remote closes, native client revokes session and channels.
3. `--readonly-no-fixture` with legacy `session`: old M5A
   synthetic bytes aren't VCRF; Host denies and native revokes.
4. `--readonly-expire` with `read-session`: 250ms local
   lease expires before read, no reply exposed, Host cleans up.

These are distinct from the existing 8 native M5B CTest gates,
M5D-1 standalone VCRD eight-group CTest and M5C-2 live Host
loss/restart preflight. All existing regressions must remain green.

## Known limitations and next work

A one-client serial Named Pipe does not provide eight parallel
read operations, cancellation of an active native read, or a
fully tested in-flight read during Host crash/restart. These are
future follow-ups. The wire path is restricted to the sealed
synthetic fixture route and cannot inject arbitrary request
or CAN data. Real J2534 ABI exports stay NOT_SUPPORTED.

No physical adapter, ECU, PIN, SecurityAccess, CAN transmission,
programming, package, artifact, release or deployment.
