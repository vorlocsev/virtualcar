# Native B9F0 RX evidence, P2 research

Checkpoint: 2026-11-04. Virtual Car Draft PR #39 on research/vdash-functional-keepalive.

## Scope

The prior B9FB-to-B9F0 handoff observer could attest that a B9F0 application
request was present but not whether matching J2534 RX followed. The new
read-only emulator/tools/audit_native_b9f0_response.py follows B9F0 requests
on the same process, native J2534 channel and known P2 CAN route. It invokes
the existing D2 framing validator from import_p2_trace.py.

For CEM50 it considers CAN RX IDs 0x01000003 and 0x01200003 on 500 kbit/s;
for CEM40 it considers 0x00800003 on 125 kbit/s. These are route candidates,
not a universal MY2009 hardware identification contract.

It distinguishes positive_transport_complete, negative_b9_service_reply,
partial_rx, invalid_transport, read_timeout_observed, no_matched_rx and
off_route_rx_only. A positive F9 F0 echo with valid framing is transport
evidence only. A negative 7F B9 is not a successful B9F0 response.

Different channels and PIDs cannot share an RX. TX indication and start
indication status bits do not count as ECU data. Disconnect or CLEAR_RX_BUFFER
with verified channel metadata affects only that channel, while missing
metadata creates a conservative whole-process boundary. No VIN, raw CAN
payload, ECU part number, process ID, host or source path is exported.

The historical three-frame B9F0 excerpt in the repository uses 8F/09/4C
and RX ID 0x01000003, but comes from a different donor and is not verified
XC90 V8 MY2009 identity evidence. Synthetic tests use zero-filled bodies.

## Integration

The existing local capture preparation continues to emit its same three
sanitized reports. capture-summary.json now carries the bounded
b9f0_native_transport_audit: request count, status counts, positive transport
presence and parser error counts. The existing b9f0_response_verified flag
remains false, because original CEM identity and diagnostic-client
interpretation cannot be authenticated by framing alone.

Local usage, private source only:

    py -3 emulator/tools/audit_native_b9f0_response.py PRIVATE.log --output NEW-B9F0.json

An existing output is never overwritten. Input cap is 4 MiB and output
records are bounded.

## Eight synthetic checks

1. Complete positive three-frame B9F0, no decoded part number.
2. Negative B9 service response stays negative.
3. Partial RX, timeout and no response remain distinct.
4. Wrong CAN route, other channel and TX indication cannot complete B9F0.
5. Foreign service echo and wrong bus speed fail closed.
6. Channel-specific disconnect and RX buffer clear preserve isolation.
7. Repeated same-channel requests and different PIDs never concatenate.
8. Existing three-file summary, privacy-safe CLI and exclusive output.

These are offline synthetic checks. They do not run SectorV, VDASH, VMware,
physical J2534 or DiCE, and do not generate a verified positive CEM identity.

## Missing evidence

A single real client run must contain a complete same-epoch sequence:
B9FB TX/RX, then B9F0 TX/RX, then the client's parse or acceptance verdict.
Do not combine unrelated historical reports, VINs or clocks. No PIN,
programming, ECU write or Virtual Car release is included in this checkpoint.
