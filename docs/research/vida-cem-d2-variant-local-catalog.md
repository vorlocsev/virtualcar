# Volvo XC90 V8 MY2009: VIDA CarCom candidate 31296075 AA (D2 v7)

## Evidence and scope

DriveRAP diagnostic coverage lists 31296075 AA / D2 v7 for XC90 2009
B8444S. This is a catalog candidate, not an OEM capture or a specific VIN match.

The existing CarCom SQLite audit validated seven common tables and six
aggregate relationships. The new local lookup extends that research to
T120_Config_EcuVariant, T121_Config and T123_Bus. It looks up the exact
T100_EcuVariant.identifier 31296075 AA and follows T110/T111 services,
T120/T121/T122/T123 route metadata and the count of T160 default-profile
links, using only an existing owner-local CarCom.sqlite export.

The private report preserves original commAddress, busRate (including NULL),
CAN IDs, protocol, bus, service and mode; it does not guess baud from GGD.
VIN, XML, SQL, passwords, arbitrary profile identifiers and scripts are not
exported. Missing identifier means missing in this export only.

## Local Windows invocation

Use a reviewed development checkout with validated Windows CI and an existing
authorized private export. Run these commands in Windows PowerShell:

    $python = (Get-Content 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
    & $python '.\emulator\tools\audit_vida_cem_d2_variant.py' --folder 'E:\VirtualCar\VIDA-private' --output 'E:\VirtualCar\VIDA-private\cem-d2-31296075-aa-001.private.json'

Always choose a NEW output filename. The report remains outside the repository
and should be reviewed locally rather than posted to a public PR.

## Proof boundary

Metadata does not prove original VIDA selection, D2 bitrate, an installed
CEM, real E3/E6/F9 replies, security session success or VIN acceptance.
No original VIDA SQL Server, ECU, physical J2534, INI, replay or releases are
modified. The new tests use synthetic SQLite only.

## Owner-local B9FB field-layout evidence (20 November 2026)

The owner's private CarCom SQLite export contains diagnostic candidate
`T100_EcuVariant.identifier = 31296075 AA` (internal ID 2160), with
five default-profile links. It is **not** proof of a real MY2009 vehicle,
installed CEM or original VIDA runtime selection. The catalog links
D2 communication addresses `50` (bus identifier 1) and `40` (bus
identifier 0). Both busRate values are NULL; no OEM bitrate was inferred.

The catalog contains 236 non-excluded direct-root `REID` entries for this
variant; `0x1A04` is `IgnitionKeyPos CAN_LS CAN_HS`, not VIN. The
`BLOFF 0xFB` block (ID 4687470) is named `Vehicle Information Section`
with declared length 1328 bits / 166 bytes. Its 16 children include an
ASCII VIN (type 51) at offset 88 bits / 11 bytes, length 136 bits /
17 bytes. The scaling entry ID 1 is `x*1`. This is a field-definition
layout, **not a verified ECU payload or proof of client acceptance**.

The separately published 88-byte D2 B9FB response ends immediately after
the catalog's `Package Identity` field (bytes 66..85) and a CRLF at bytes
86..87. Catalog fields at positions 88..165 are absent in that sample.
The first sample byte `0x57` equals the following 87 bytes and aligns
with a field named `Data length`, but neither variable-length B9FB nor
an accepted full-size 166-byte CEM reply has been demonstrated. Do **not**
automatically pad, extend, invent identity data, or promote the sample to
an XC90 V8 MY2009 replay fixture.

The existing privacy-safe `audit_p2_b9fb_shape.py` now respects the
D2 terminal-byte count in the last frame. This prevents zero padding from
inflating `payload_byte_count` for longer synthetic cases (e.g. 166
bytes in 25 frames, terminal marker `0x49`). Special sub-block control
series remain valid transport candidates but their application payload is
not decoded by this audit. No emulator J2534 responses were changed.
