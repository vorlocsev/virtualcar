# Volvo P2 CEM B9FB: binary-safe capture boundaries

Date: 2026-11-03. Scope: offline-only source-grounded audit in
Virtual Car research PR #39. No VMware or physical J2534 run.

## Source and provenance

The checked-in sample emulator/samples/p2_b9fb_public_redacted.txt is
a public historical DiCE B9FB excerpt with identifiers redacted;
the repository links it to a Matthews Volvo Site thread. The sample
is not a full authenticated P2 discovery session, cannot be assigned
to a verified XC90 V8 MY2009, and must not be treated as a coherent
vehicle identity profile.

The separate file p2_b9f0_public_excerpt.txt is a different excerpt.
It cannot prove that any client requires B9F0 before B9FB or that
the two captures belong to the same transport session.

## Byte boundaries actually present in this redacted sample

The bounded parser:
- identifies one CB 50 B9 FB request and 13 ensuing RX frames;
- validates D2 envelope and continuation shape using the existing
  import_p2_trace.validate_response transport-only rules;
- strips one control byte per frame: 13 x 7 = 91 bytes;
- checks the positive echo 50 F9 FB, leaving 88 body bytes;
- locates an embedded 00 in the initial non-text bytes;
- observes eight CRLF starts at offsets 9, 28, 39, 44, 52, 56, 64, 86;
- locates a 17-character X redaction mask at body offsets 11–27;
- notes that body byte 0x57 equals the number of bytes following it in
  this sample (87), but does NOT establish a universal length rule.

The control markers are not field separators: first control bytes of
13 recorded frames are 8F, 09, 0A, 0B, 0C, 0D, 0E, 0F, 08, 09, 0A,
0B, 4F. NUL-terminated string functions would truncate the body.

## Audit contract

New read-only program: emulator/tools/audit_p2_b9fb_layout.py.

It accepts an ideally redacted local B9FB capture, requiring exactly
one recognized response. It emits only fixed-schema lengths, offsets,
safe booleans and limitations, without VIN, raw CAN IDs, payload,
host paths or source log text. An example footprint match is NOT
authentication of the vehicle or ECU.

Example command from repository root (PowerShell):

    py -3 .\emulator\tools\audit_p2_b9fb_layout.py .\emulator\samples\p2_b9fb_public_redacted.txt --target 50 --output "$env:TEMP\vc-b9fb-layout-audit.json"

The output path must not exist and the input file is never modified.

## Unverified for XC90 V8 MY2009

- Unmasked VIN and consistency with chassis or model fields.
- Exact meaning of binary prefix and numerical fields across CEM variants.
- Payload checksum or other application integrity.
- Expected CAN response route on the target bus.
- Client requirement for B9F0 before B9FB, if any.
- Acceptance by VDASH/SectorV and whether the result enters
  DetectResult.Units or executes InitializeUnits.

Eight synthetic/source-based test groups cover the stored 13-frame
redacted sample, truncation, continuation reorder, opcode mismatch,
B9F0 non-equivalence, two candidate sessions, a modified binary prefix,
and report privacy/no-overwrite behavior.

No emulator frame fixture was filled, no raw identity was committed,
and VMware CI is intentionally skipped for this research branch.
