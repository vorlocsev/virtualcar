# First P3 ECU response following a completed B9F0

Research checkpoint: 2026-11-04. Virtual Car Draft PR #39,
branch `research/vdash-functional-keepalive`.

## What the native trace can establish

A completed positive CEM B9F0 D2 response is an observed transport event.
The first later application TX, including a P3/UDS 0x22 ReadDataByIdentifier,
is another transport observation, not proof that the diagnostic client has
accepted a VIN, vehicle identity, hardware number or ECU inventory.

The privacy-safe `emulator/tools/audit_native_b9f0_response.py` now opens
a bounded response window **only** when exactly one completed B9F0 response
precedes the first P3 DID application request in one native PID/epoch.
A new P3 request on a different channel is permitted, but its response
must match that **request's** native J2534 channel, protocol, baud and the
documented request/response CAN route.

The existing `audit_j2534_discovery._p3_frame` and `_p3_uds` validators
are reused. No second DID decoder is introduced. Only the UDS service
and matching DID *header* are checked in memory, never exported.

Native routes scoped by existing source:
- Standard P3 CAN TX 0x726 expects RX 0x72E.
- Extended P3 TX 0x18DA50F1 expects RX 0x18DAF150.
- CAN protocol 5 expects classic eight-byte ISO-TP PCI frames, including
  single and multiple-frame/sequence validation.
- ISO15765 protocol 6 expects a reassembled UDS RX record.
- TX_MSG_TYPE, START_OF_MESSAGE and TX_INDICATION are not ECU RX.
  CAN_29BIT_ID metadata is not itself an indication.
- Flow Control is transport, not another first application request.
- NRC 0x78 responsePending is nonterminal. A later positive read
  response can complete the same request. A logged timeout after only
  pending is not a negative ECU identity verdict.

## Source-local outcome classes

Each positive B9F0 observation now has
`first_next_p3_response_status`, with values such as:

- `not_a_p3_read`: first next TX was not a recognized P3 DID read;
- `positive_transport_complete`: positive 0x62 DID echo, nonempty data
  record and matching transport continuity were observed;
- `negative_response`: terminal UDS negative reply 0x7F 0x22;
- `response_pending_only` / `response_pending_timeout`;
- `partial_rx` or `invalid_transport`: incomplete/wrong ISO-TP;
- `missing_did_record` or `mismatched_did_or_service`;
- `no_matched_rx`, `off_route_rx_only`, `read_timeout_observed`;
- `ambiguous_multiple_b9f0_predecessors`: more than one positive
  B9F0 completion could be the source of one first request.

Each result exposes only counters, a relative native TX-to-RX interval,
transport-completion Boolean and a bounded reason for the end of the
observation. No raw CAN data, DID, part number, VIN, process ID, hostname,
private source path, or arbitrary UDS body is copied.

## Existing three-file capture integration

`prepare_p2_capture.py` still produces the same three redacted JSON files
from a single PRIVATE native J2534 log. The
`capture-summary.json.b9f0_native_transport_audit` section now contains:

- `post_positive_first_p3_response_status_counts`
- `post_positive_first_p3_positive_transport_count`

These are not an ECU discovery count. The report deliberately retains
`ecu_enumeration_verified=false`, `client_acceptance_verified=false`
and `b9f0_response_verified=false` (semantic/original identity remains
unverified even if the B9F0 transport is well framed).

Run the local command from the repository root:

    py -3 emulator/tools/prepare_p2_capture.py PRIVATE.log --output-dir NEW-PRIVATE-REPORT

The destination directory must not exist. Keep the original log private;
review sanitized output before sharing.

## Eight synthetic regression groups

1. Single-frame positive P3 DID data on standard CAN route.
2. Variable-size ISO15765 RX on 29-bit route and second channel.
3. Terminal negative, NRC 0x78 pending followed by positive, and
   pending-plus-timeout.
4. Mismatched DID and missing data record.
5. Multiframe complete, partial and wrong consecutive-frame sequence.
6. Cross-PID/channel/CAN-ID/baud and TX indication are excluded.
7. Disconnect, clear buffer, superseding TX and session epoch boundaries.
8. Three-file privacy-safe integration and unchanged client verdict flags.

All tests are offline synthetic examples. This work does not execute
SectorV/VDASH, read a real Volvo CEM, test a physical J2534/DiCE adapter,
extract a PIN, bypass access control or publish Virtual Car.

## Remaining obstacle

Only an authorized, **single-run** native capture plus an independent
client-side display/log state can establish whether real SectorV/VDASH
accepted a CEM identity and actually populated an ECU inventory.
A positive UDS response in the virtual transport layer is necessary
but never sufficient evidence.
