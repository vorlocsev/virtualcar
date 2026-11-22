/* B3A91: validation of optional positive Volvo D2 B9F0 lab fixtures only.
 * This checks shape and BCD_ASCII encoding; it never authenticates an OEM ECU.
 * Do not infer identifiers from VIN, catalog labels, or unrelated CEM captures.
 */
#ifndef P2_B9F0_FIXTURE_GUARD_H
#define P2_B9F0_FIXTURE_GUARD_H

/* A 15-byte B9F0 block is packed as target/F9/F0 + 8-byte complete P/N
 * (5 decimal-BCD + 3 printable ASCII) + 7-byte diagnostic SW P/N
 * (4 decimal-BCD + 3 printable ASCII): 18 significant D2 stream bytes.
 * Observed 0x08-series framing is 7 + 7 + 4 data bytes, then 3 pad zeros:
 * 8F target F9 F0 PN0 PN1 PN2 PN3
 * 09 PN4 PN5 PN6 PN7 SW0 SW1 SW2
 * 4C SW3 SW4 SW5 SW6 00 00 00
 */
static int p2_b9f0_fixture_frames_valid(unsigned int frame_count,
                                         unsigned char frames[][8],
                                         unsigned char target)
{
    unsigned char stream[18];
    unsigned int i, offset = 0, j;
    if (!frames || frame_count != 3u) return 0;
    if (target != 0x40u && target != 0x50u) return 0;
    if (frames[0][0] != 0x8Fu || frames[0][1] != target ||
        frames[0][2] != 0xF9u || frames[0][3] != 0xF0u ||
        frames[1][0] != 0x09u || frames[2][0] != 0x4Cu) return 0;
    for (i = 5u; i < 8u; i++) if (frames[2][i] != 0u) return 0;
    for (i = 0; i < 3u; i++) {
        unsigned int meaningful = (i == 2u) ? 4u : 7u;
        for (j = 0; j < meaningful; j++)
            stream[offset++] = frames[i][j + 1u];
    }
    if (offset != 18u || stream[0] != target ||
        stream[1] != 0xF9u || stream[2] != 0xF0u) return 0;
    /* 5 bytes of hardware complete P/N BCD, then 4 of diagnostic SW BCD. */
    for (i = 3u; i < 8u; i++)
        if ((stream[i] >> 4u) > 9u || (stream[i] & 0x0Fu) > 9u) return 0;
    for (i = 11u; i < 15u; i++)
        if ((stream[i] >> 4u) > 9u || (stream[i] & 0x0Fu) > 9u) return 0;
    /* ASCII suffix characters may include spaces, but not NUL/control/DEL. */
    for (i = 8u; i < 11u; i++)
        if (stream[i] < 0x20u || stream[i] > 0x7Eu) return 0;
    for (i = 15u; i < 18u; i++)
        if (stream[i] < 0x20u || stream[i] > 0x7Eu) return 0;
    return 1;
}

/* Preserve the preexisting one-frame negative D2 B9 response shape.
 * Only POSITIVE B9F0 data requires the strict three-frame BCD_ASCII schema.
 * The caller still runs its generic validate_d2_fixture() first.
 */
static int p2_b9f0_fixture_allowed(unsigned int frame_count,
                                   unsigned char frames[][8],
                                   unsigned char target)
{
    if (!frames || (target != 0x40u && target != 0x50u)) return 0;
    if (frame_count == 1u && (frames[0][0] & 0xF8u) == 0xC8u &&
        frames[0][1] == target && frames[0][2] == 0x7Fu &&
        frames[0][3] == 0xB9u) return 1;
    return p2_b9f0_fixture_frames_valid(frame_count, frames, target);
}

#endif /* P2_B9F0_FIXTURE_GUARD_H */
