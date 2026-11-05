# D2 B9FB: P1/P2 transport forms and supported bridge evidence

Date: 2026-11-04. Branch: research/vdash-functional-keepalive;
Virtual Car Draft PR #39. This is offline, read-only framing research.

## Independent sources

1. **Historical P2 XC70 donor** (Matthew's Volvo Site, 2005-era DiCE).
   The already-checked-in `p2_b9fb_public_redacted.txt` represents a
   13-frame `B9FB` response with controls `8F, 09..0F, 08..0B, 4F`.
   The response CAN ID in that donor is `0x01200003`, with 88 bytes
   following the three-byte `50 F9 FB` positive echo. This is **not**
   an authenticated XC90 V8 MY2009 CEM identity.

2. **Independent P1 Volvo V50 2007 D4164T capture**, published in
   MarvinParanoid/VolvoDiagToolkit. Its public unit-test fixture
   `tests/test_volvo_protocol.py` shows the **truncated first eight
   frames** of a CEM50 B9FB response, starting `97 50 F9 FB` and
   continuing `11, 12, 13, 14, 15, 16, 17` on CAN ID `0x00400003`.
   The author's P1 codec can extract a VIN from the incomplete subset,
   but that is **not** evidence of a complete D2 reply or acceptance
   by SectorV. Its source sample carries a real donor VIN; our
   regression keeps only the control sequence and zero-filled body.

3. **Existing Virtual Car synthetic VIDA sub-block test**:
   `97 → 11 → 55 → 8F → 4C` on CEM50. This is already tested
   in `emulator/tests/virtualcar_test.c` and must remain valid.
   It is a synthetic representation of an observed VIDA-style
   sub-block boundary, not a verified MY2009 B9FB response.

Source URLs:
- https://www.matthewsvolvosite.com/forums/viewtopic.php?p=573059
- https://github.com/MarvinParanoid/VolvoDiagToolkit/blob/main/docs/volvo-protocol.md
- https://github.com/MarvinParanoid/VolvoDiagToolkit/blob/main/tests/test_volvo_protocol.py

## Why the original validation needed a narrow guard

The existing P2 importer and C fixture validator accepted both an
`8F` beginning and a `97` beginning. A `97` beginning selected
`11/12/...` counters, while any `48..4F` last frame immediately
terminated the response. Consequently a synthetic, **unobserved**
`97 → 11 → 4C` three-frame series could falsely validate as a
complete B9FB reply, with no verified transition to the `4x`
family. The truncated P1 example is a particularly relevant
counterexample: recognizing an embedded VIN does not establish
that the whole D2 transport completed.

The importer and C validator now require an observed **`5x`
sub-block boundary followed by a repeated positive `8F`
service header** before a `97` beginning may terminate with
a `4x` last-frame control. This preserves the existing tested
VIDA sub-block form while rejecting an unsupported shortcut.

This is intentionally conservative: it applies to known replay
fixtures, **not** a claim about every P1/P2 ECU transport dialect.
If a later real XC90 V8 MY2009 recording proves another legal
completion form, that new form must be separately added with
source-specific test evidence rather than silently guessed.

Response CAN ID alone does not authenticate a platform.
Neither the P1 `0x00400003` nor the XC70 donor
`0x01200003` should be set as a universal XC90 V8 2009 default.
No CAN IDs, vehicle VIN or positive E3 bytes have been changed
in the Virtual Car runtime.

## Eight regression groups

File: `emulator/tests/test_d2_transport_family_provenance.py`.

1. The existing redacted 13-frame P2 donor remains valid.
2. The tested `97/11/55/8F/4C` VIDA bridge remains valid.
3. A bare `97/11/4C` crossover fails closed.
4. The truncated `97/11..17` P1-style record remains incomplete.
5. A foreign positive service echo is rejected.
6. A mismatched CEM target is rejected.
7. Invalid continuation/early terminal controls are rejected.
8. Both observed CAN response IDs may be parsed for *framing*
   under a valid controlled sequence; mixed IDs fail. This is
   a deliberate distinction between transport and identity.

An additional C regression rejects the unbridged form while
preserving the already-tested valid synthetic sub-block series.

## Next necessary evidence

To advance SectorV beyond Hardware, obtain a complete,
single-session **real XC90 V8 MY2009** CEM B9FB/B9F0
read-only trace with J2534 channel IDs and the client's
parse/acceptance result. These public P1 and earlier P2
examples cannot establish the missing client success
predicate. In particular, A3 is listed as Security Access
in the independent P1 protocol reference, but no verified
P2 XC90 MY2009 positive E3 or authorization state is present.

No VMware, physical J2534, EEPROM access, PIN cracking,
ECU write or Virtual Car release was performed at this stage.
