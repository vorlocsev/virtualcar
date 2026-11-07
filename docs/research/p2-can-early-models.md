# External research: Volvo P2 CAN, early model years

Source: https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering
Reviewed: 2026-10-31
Status: research only. **Not** a verified XC90 V8 MY2009 CAN signal map.

## Source inventory

- Captures for 2002 Volvo S60 B5244S2 M56 (two buses, ignition / driving / HVAC / DDM / lighting scenarios).
- Captures for 2003 Volvo V70 II D5244T M56 (README identifies its model year as 2004; high-speed bus only).
- Two DBC definitions of selected decoded signals.
- Notes on CAN message format and firmware-derived CEM receive-message tables.
- CSV timing / counter / ID-inspection utilities.

Sources:
- https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering/blob/main/docs/message_format.md
- https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering/blob/main/2002%20Volvo%20S60%20B5244S2%20M56/README.md
- https://github.com/damienmaguire/Volvo-V70-P2-CAN-Reverse-Engineering/blob/main/2003%20Volvo%20V70%20II%20D5244T%20M56/README.md

## Confirmed *for the source vehicles*, not for our target

1. The authors report 250 kbit/s powertrain CAN and 125 kbit/s body CAN for early P2. Our target vehicle profile remains HS 500 / LS 125 kbit/s; do not silently override it.
2. Raw captures mostly use 29-bit extended arbitration IDs and 8-byte classic-CAN data. The V70 capture also contains anomalous `LEN=15` entries for `10C41FBE` and `120171F7`; treat these as capture/format anomalies, **not** valid classic-CAN payloads.
3. `0x000FFFFE` is present in the 2002 and 2003 CEM firmware-derived HS receive lists as a diagnostic broadcast CAN ID. This alone does not establish any positive D2 response payload.
4. The sets of observed message IDs differ substantially across the 2002 and 2003 vehicles; even the 29-bit frame for the same functional subsystem can move. Do not transplant an arbitration ID, data offset, rolling-counter scheme, or timing profile across generations without verification.
5. Volvo Volcano signals can be non-byte-aligned. Treat field descriptions as bit-precise and DBC-based; do not infer meaning from an entire byte.
6. The early S60 field logs describe four wake/activity phases (Off, Sleepy, Awake, Active). These are observational traffic states, **not** diagnostic CEM normal-mode acknowledgements or proof of ignition reference 0x1A04.

## Comparison with olegel/VolvoCan (also unverified for MY2009)

- VolvoCan reports CEM ignition-key state on body-CAN `0x00617FF8`.
- The 2002 S60 inventory contains body-CAN `0x00613DF8` but does not decode it as the same key signal.
- Shared-looking prefixes are insufficient to assert identical layout or ECU ownership.
- Keep the dev24 body-CAN observer disabled by default for XC90 V8 MY2009 unless a relevant capture confirms the ID and field location.

Source: https://github.com/olegel/VolvoCan/blob/master/VolvoCan/include/VolvoCan.h

## Implementation policy for Virtual Car dev29+

- Preserve the existing validated B9FB replay fixture and its 13 frames; do not replace with broadcast data.
- Keep D2 A3, A6, B9F0, B9D0 and CEM P3 F114/29-bit paths **unverified** until trusted response examples are supplied and transport is checked.
- Do not synthesize 'normal mode', ignition-on, module presence, or a valid vehicle identity solely from periodic CAN status traffic.
- Separate a **bus state machine** (awake/asleep, HS/LS, measured periodic schedules) from **diagnostic session state** (J2534 channels, D2 request/response correlation, ISO-TP).
- Validate J2534 Data[0..3] as the 32-bit CAN ID in big-endian form, then decode only observed payloads. Check extended-ID flags and 0..8 classic-CAN length on raw-CAN replay.
- Reject unsupported source-year ID maps at runtime unless a user explicitly selects experimental compatibility mode.
- Keep security/immobilizer handshake material out of the read-only emulator and out of default tests.
- Do not copy GPL-3.0 Python scripts or other source into Virtual Car. Treat this as an original, separately authored research summary linked to its source; review licensing before using any code.

## Proposed offline validation (one stage, eight groups)

1. 2002 and 2003 CAN ID sets are separate profiles; MY2009 remains unset/experimental.
2. 250 kbit/s source captures do not alter the MY2009 HS 500 kbit/s default.
3. 29-bit bus frames are not confused with 11-bit P3 `0x726` requests.
4. DBC extended frame IDs: preserve extended marker and underlying 29-bit arbitration value.
5. Payload decoder checks bit offsets and sign/endianness against defined signals.
6. Period/jitter parser tolerates missing frames, time discontinuities and counter resets.
7. Classic CAN replay rejects `LEN>8` entries and records an explicit warning.
8. Diagnostic B9FB replay, A3/B9F0 unresolved status, and J2534 READ128 behavior remain unchanged.

No claims here about successful detection in SectorV or VMware; these still require end-to-end testing.
