# First application request after positive CEM B9F0 transport

Research checkpoint: 2026-11-04. Virtual Car, Draft PR #39,
branch `research/vdash-functional-keepalive`.

## Why it matters

A native J2534 log may show complete D2 B9FB and B9F0 positive transport,
yet the client could still reject the identity or stop scanning. The first
application TX after B9F0 is a useful source-local observation, but is not
a decoded ECU inventory, proof of VIN acceptance, or a diagnostic-client
parse result.

The existing `audit_native_b9f0_response.py` already validates the
B9F0 transport sequence. It now also tracks the first subsequent
application-TX event **after a completed positive response**, without
mixing the process/PID or log epochs. It records only allowlisted labels:
- `p3_read_data_by_identifier`: a recognized P3 UDS service 0x22 request;
- `p3_other`: other supported P3 request shape;
- `d2_b9f0`, `d2_b9fb`, `d2_b9fc`, `d2_a3`, `d2_a6`:
  recognized D2 application service;
- `other_or_unclassified_tx`: everything else;
- `unattributed_app_tx`: observed but unusable native TX record.

For requests with verifiable native channel metadata, the record includes
whether the next TX used the same J2534 channel, the same baud and a native
source-local millisecond gap from final B9F0 RX. Only relative times are
exported; no raw timestamp, CAN bytes, DID, VIN, part number, PID,
client name or private source path is copied.

The first TX can be on another channel: it remains an observation rather
than being mistaken for a same-channel identity continuation. An unrelated
TX takes precedence over any later recognized P3 request. ISO-TP Flow
Control on a recognized P3 or OBD route is transport-only and is not counted
as a fresh app TX or permitted to supersede an active request. A response
observation ending at PassThruClose, EOF, explicit session marker,
disconnect or CLEAR_RX_BUFFER does not prove a client timeout or silence.

## ISO15765 specifics

J2534 native TX data sizes are not always exactly 12 bytes. The tool
parses a bounded byte prefix of variable-length native ISO15765 TX for
**classification only**, including `0x22` ReadDataByIdentifier. The B9F0
request and reply transport validator retains its strict classic-CAN
length, source-target and route requirements. This change does not
classify a UDS request as an ECU response.

## Integration

The existing `prepare_p2_capture.py` still writes the same three
sanitized JSON files, with these additional fields inside
`capture-summary.json.b9f0_native_transport_audit`:
- `post_positive_first_next_tx_service_counts`;
- `post_positive_first_next_tx_observed_count`;
- `ecu_enumeration_verified: false`.

The original `client_acceptance_verified`, `b9f0_response_verified`
and part-number identity flags remain false. They cannot be upgraded
from a later UDS application TX.

## Eight offline regression cases

1. First later P3 DID read on the original channel and native clock.
2. Variable-length ISO15765 P3 DID read on a different channel.
3. Repeat B9F0 or A3 is not an ECU inventory verdict.
4. An unrelated first TX blocks later P3 relabeling.
5. Channel-specific disconnect and clear are explicit barriers.
6. Cross-PID, cross-session or malformed TX cannot be joined.
7. Close and EOF cannot be claimed as measured silence; microsecond
   timer wraparound remains source-local.
8. Three-file privacy-safe aggregation and permanently unverified
   client acceptance.

All tests are synthetic and read-only. No real SectorV/VDASH run,
real J2534 adapter, EEPROM, PIN, security access, ECU write or
Virtual Car release is involved.

## Remaining external evidence

An authorized single-source run must establish:
1. B9FB and B9F0 diagnostic requests and same-channel matched RX;
2. whether an application *attempted* P3 DID/ECU enumeration after B9F0;
3. separate client-side diagnostic state or ECU list evidence showing
   what the client actually accepted, and on which native epoch.

Historical SectorV, VIDA and donor XC70 transcripts cannot substitute
for a genuine XC90 V8 MY2009 client acceptance capture.
