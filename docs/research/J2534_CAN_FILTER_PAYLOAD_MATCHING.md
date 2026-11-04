# J2534 CAN PASS/BLOCK filters: full ID + payload mask matching

Research checkpoint: 2026-11-04, Virtual Car Draft PR #39.
Scope: read-only receive filtering of synthetic CAN responses. This is not
a SectorV/VDASH acceptance test and does not reconstruct Volvo CEM data.

## Problem observed in the original DLL

The original PassThruStartMsgFilter accepted mask/pattern messages whose
DataSize was greater than four bytes, but stored only mask[4] and pattern[4].
filter_allows() compared only the first four bytes (the CAN identifier).
Thus an application wanting to receive only an ID + a first service-byte
pattern would receive other same-ID payloads as well.

The SAE J2534 04.04 filter interface permits masked comparison with
filter-message bytes beyond just the CAN identifier. The public 04.04
API descriptions also distinguish CAN PASS/BLOCK filters from ISO15765
FLOW_CONTROL filters:
https://scandoc.org/en/develop/j2534/pt_start_msgfilt.html

## Fix

- CAN PASS_FILTER (type 1) and BLOCK_FILTER (type 2) now preserve masks
  and patterns from four to twelve bytes: four CAN-ID bytes plus up to
  eight CAN-payload bytes.
- Each incoming synthetic frame is evaluated against the entire declared
  mask length, not merely the CAN ID. Mask bits set to zero do not affect
  acceptance. If the requested payload length exceeds the actual frame,
  the filter does not match and no out-of-bounds read occurs.
- Unequal mask/pattern lengths and filters longer than twelve bytes are
  rejected with ERR_INVALID_MSG. Rejected registrations do not alter
  existing installed filters.
- Legacy four-byte ID-only CAN masks remain supported.
- The ISO15765 FLOW_CONTROL_FILTER retains its existing header-only
  comparison path. Its extended-addressing and flow-control behavior
  are **not** upgraded or claimed as fully compliant by this change.
- The current lab emulator still passes unsolicited frames when there
  are no PASS filters, as a preexisting compatibility choice. This is
  **not full strict J2534 filtering** and must be re-evaluated against
  independently captured real client behavior before claiming compliance.

## Regression checks

Eight host C regression groups cover:

1. Five-byte PASS accepts the right ID + data byte.
2. Same ID with a different data byte is suppressed.
3. Different ID with matching data is suppressed.
4. Five-byte BLOCK allows same-ID data that does not match.
5. Five-byte BLOCK suppresses matching ID + data.
6. Partial high-nibble masks compare only significant bits.
7. Twelve-byte filter compares all eight CAN-data bytes, and shorter
   frames cannot match an oversized filter.
8. Malformed unequal/oversized masks are rejected, while four-byte
   ID-only masks still work.

The Windows x86 native-routes CI runs an independent actual DLL test
via PassThruStartMsgFilter, PassThruWriteMsgs and PassThruReadMsgs in
a disposable isolated process. A three-frame synthetic B9F0 response
uses one CAN RX ID but three different D2 control bytes. A five-byte
PASS receives only its first 0x8F frame; a matching BLOCK suppresses
only that frame and allows 0x09 and 0x4C. The probe uses a synthetic
INI and no OEM ECU, real VIN or proprietary client. Its raw log is not
uploaded.

## Explicit CAN CLEAR_MSG_FILTERS lifecycle

The default after `PassThruConnect` remains **permissive on an untouched
filterless synthetic CAN channel** for compatibility with existing
laboratory test clients. This is a conscious deviation from the strict
J2534 v04.04 *initial* filterless behavior and must not be interpreted as
full compliance.

However, after the diagnostic client explicitly calls
`PassThruIoctl(channel, CLEAR_MSG_FILTERS)` on a CAN channel, the
emulator now follows the standard's **no NEW RX until a PASS filter is
installed** behavior. This is a sticky per-channel condition until
`PassThruDisconnect`. The following rules are verified:

- CLEAR on an initially empty filter set is still meaningful: it makes
  the channel stop enqueueing new CAN messages.
- A matching PASS_FILTER restores delivery of only matching messages.
  A BLOCK_FILTER may further suppress matching CAN data.
- Removing the last PASS_FILTER returns the explicitly cleared channel
  to the blocked state, even if a BLOCK_FILTER remains.
- CLEAR invalidates existing FilterIDs; old IDs cannot be stopped later.
  It does not retroactively discard already-queued RX messages.
  CLEAR_RX_BUFFER remains the explicit queue removal operation.
- Clearing one CAN channel does not change a second channel's filters.
  Disconnecting and reopening a channel resets this specific laboratory
  compatibility state.
- ISO15765 filtering and FLOW_CONTROL remain unchanged. No claim of
  strict initial no-filter behavior, extended ISO-TP addressing or
  full SAE conformance is made.

Eight host C regression groups exercise explicit clearing, matching
PASS, BLOCK precedence, stop, stale FilterIDs, preserved queued frames,
cross-channel isolation and reconnect. The native Windows x86
`-PayloadFilterProbe` also uses the **compiled J2534 DLL** to ensure
that CLEAR blocks a subsequent synthetic B9F0 reply, PASS restores a
filtered first frame and Stop blocks new replies again.

Specification references: SAE J2534-1 revision DEC2004 §7.3.10
(CLEAR_MSG_FILTERS), and the public v04.04 API description at
https://www.scandoc.org/en/develop/j2534/pt_ioctl.html .

## Evidence boundary

Matching J2534 filter semantics does not prove SectorV/VDASH saw,
parsed or accepted a CEM, vehicle VIN or ECU inventory. Windows x86 CI
confirms only this isolated filter behavior and other synthetic
transport checks. A real read-only client session remains necessary.
