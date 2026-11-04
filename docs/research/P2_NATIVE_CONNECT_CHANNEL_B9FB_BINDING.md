# Native J2534 Connect channel binding before P2 CEM B9FB

Research checkpoint: 2026-11-04. Draft PR #39, read-only only.

## Previous evidence gap

The client capture report counted successful PassThruConnect calls
from all metadata events in a native log. Those results recorded the
protocol, flags, speed and status but **not the allocated channel ID**.

A complete B9FB transport observed on channel 1 could therefore be
preceded by a successful Connect on *another* channel, or its only
successful Connect could appear later in the same log. A positive
aggregate Connect count did not establish that the B9FB TX was sent
through the previously created virtual channel.

## Native instrumentation

virtualcar.c now emits one additional local metadata line after
channel allocation, before the successful Connect result:

    J2534 Connect bound channel/protocol/flags/baud (BE)

It contains only four big-endian unsigned 32-bit values: the local
J2534 channel ID, protocol, flags and baud. It does not contain VIN,
CAN payload, ECU credentials, source path, PID or client identity.
Existing Connect result records remain intact for old diagnostics.

This is **not** a process signature. Native source text is untrusted
and may be incomplete, altered, or from a synthetic harness.

## Source-local audit

tools/audit_native_connect_b9fb_channel.py walks native events in
source order. A successful Connect channel binding is recognized only
if a binding metadata line is followed by a matching Connect result
with status OK. An earlier successful connection is retained until
PassThruDisconnect or PassThruClose. For the first CEM B9FB app TX,
the preceding TX context supplies channel, protocol and baud.

The result is positive only when **exactly one** B9FB is observed in
the supplied source, its matching channel was successfully bound
earlier, the protocol is CAN (J2534 5), and the target's configured
network speed agrees with that channel (target 0x40 = 125k,
target 0x50 = 500k).

Old logs without the new marker remain
legacy_no_channel_connect_binding_metadata, NOT proof that the
client did anything wrong. Channel mismatch, a prior disconnect,
a late Connect, a mismatched Connect result, bad metadata or two
B9FB requests cannot establish one source-local handoff.

prepare_p2_client_run.py now includes the sanitized
native_b9fb_connect_channel_binding report in client-boundary.json.
When the aggregate Connect count is positive but this stricter
link is missing, diagnostic_focus becomes
b9fb_channel_connect_provenance_missing_or_invalid before claiming
further B9FB to B9F0 to P3 progression.

Every client-side acceptance and ECU identity flag stays false.
No source PID, executable basename, timestamp, CAN bytes, VIN,
DID or ECU part numbers are exported.

## Prevent one-PID multi-cycle source attribution

A second guard now lives **inside the Connect/B9FB auditor itself**,
rather than relying only on the outer client-boundary summary.
To classify a positive same-channel B9FB Connect, the source must
contain exactly one successful `PassThruOpen -> device 1` and exactly
one `PassThruClose` for one native PID/process-label scope.

Two sequential Open/Close cycles in the same PID return
`multiple_native_device_cycles`, not positive Connect evidence.
Nested Open, orphan Close, Connect events outside an open device,
missing final Close, malformed source markers and explicit session
separators fail closed. Open/Close counts and fixed error categories
can be exported, but not the PID, process name, timestamps or bytes.

Within *one* valid Open/Close cycle, disconnecting a channel and
then successfully connecting again on that reused ID is permitted.
The new Connect result is required before the later B9FB TX:
an unpaired Connect marker or a duplicate Connect against a still-live
channel is invalid. This distinction matters for diagnostic clients
that reconnect without exiting their process.

The primary capture report already checks single-device lifecycle
separately. Independent agreement keeps individual
`native_b9fb_connect_channel_binding` results from looking
positive when a different epoch contains the actual CEM request.

## Verification

Eight synthetic regression groups exercise: correct matching
channel; late Connect; wrong channel; wrong protocol or baud; a
claimed binding followed by failure; disconnection before B9FB;
legacy native log with no channel marker; and repeated B9FB or
malformed native binding metadata.

The Windows native-routes CI additionally checks this binding on
the read-only synthetic B9FB/B9F0/P3 log produced by the **compiled
x86 J2534 DLL**, including multiple successful Connect channels.
The LAB archive contains the auditor and its sanitized report
dependencies; the extracted ZIP verifier checks their presence.

Neither local event order nor a positive DLL response establishes
SectorV/VDASH accepting a real vehicle. Independent observation
of the proprietary diagnostic client is still outstanding.
