# Stage 44: Volvo P2 B9FB content evidence, not vehicle acceptance

Read-only research for Issue #4. This report is a *privacy-safe structural aid* for
previously recorded D2 CEM B9FB responses; it does not create replay fixtures,
change the J2534 DLL, or infer acceptance by SectorV, VDASH, or VIDA.

## Evidence boundaries

- `transport=complete`: the existing D2 importer validated frame headers, CAN ID
  consistency, sequence and positive B9FB echo. It does not establish client's parsing result.
- `published_88_byte_shape`: this is **one observed example**, with a 6-byte binary
  prefix, eight CRLF-terminated fields and widths (3,17,9,3,6,2,6,20).
  It is NOT a universal OEM B9FB layout or a schema for XC90 V8 MY2009.
- `vin_shaped_field`: a 17-character ASCII candidate at offset 11. No VIN
  checksum, model-year, actual WMI, car-identity or parser-acceptance test is performed.
- `six_digit_field_compared_with_vin_suffix`: literal comparison of two candidate
  strings at published-example positions. The other string has not been proven
  to be a chassis serial by a verified OEM schema.
- `observed_length_marker_relation`: in the 88-byte sample, byte 0x57 numerically
  equals 87 remaining bytes; treating it as an OEM length definition is UNVERIFIED.
- `checksum_status=unknown`, `vehicle_identity_verified=false`,
  `client_result=client_result_unknown`, `normal_mode_result=unknown`,
  and `replay_approved=false` must remain unchanged by a matching layout.
- `channel_and_baud_verified=false`: the simpler importer does not establish
  the channel tuple. Use the existing J2534 discovery audit as separate evidence.

## Usage (private log stays local)

```sh
python emulator/tools/audit_p2_b9fb_shape.py PRIVATE-J2534.log --target 50 --output NEW-audit.json
```

Use `--target 40|50` for D2 targets, not model years. For multiple separate
responses specify `--session-index N` (zero based); the tool will NOT silently
pick the longest. The JSON output is exclusively created and never overwrites.
No raw payload, VIN, six-digit field, private path, PID, host or identity hashes
are serialized. The input trace must not be committed to GitHub.

## Terminal marker parity for the published 13-frame example

The 13-frame, `0x8F` / `0x08`-series D2 example has a final
`0x4F` control byte, indicating seven bytes of last-frame data.
Previously the Python importer and native DLL validator accepted any
`0x48..0x4F` as the last frame of the same 13-frame shape, while
`p2audit` already required `0x4F`. That could mark a truncated
last-frame length as valid transport and copy its padded bytes into a
lab profile.

The importer, native DLL and Go fixture audit now agree that for this
**observed 13-frame, 0x08-series form**, the terminal must be `0x4F`.
For other sequence lengths and the separate `0x10`-series form, the
existing generic terminal rules remain unchanged. This is not a
universal B9FB byte-length specification, does not verify the application
checksum (unknown), and does not show SectorV accepted or parsed a VIN.
Native-C, Python importer and privacy-safe shape-audit synthetic
regressions cover the boundary. The source fixture remains read-only,
and no raw vehicle identifiers are introduced.

## SectorV normal-mode gate still unresolved

Research of a separate MY2005 PR #30 session shows a 13/13 B9FB client matcher,
then A3 target50/40 Hardware requests without matching response and approximately
5-second timeouts. It does not identify the exact normal-mode predicate.
A3 may be a security-access family command. Do not invent E3 positives or
reinterpret transport delivery as a successful CEM identity.

Primary local source: [p2-public-capture-followup.md](p2-public-capture-followup.md).
Published B9FB example: https://www.matthewsvolvosite.com/forums/viewtopic.php?p=573073
(indexed excerpt, origin/model/baud incomplete).
A separate P1 D2 reverse-engineering report, NOT a P2 MY2009 reference:
https://github.com/MarvinParanoid/VolvoDiagToolkit/blob/main/docs/volvo-protocol.md .

## Eight synthetic test groups

1. Full 13-frame B9FB, 88 bytes, CRLF and binary NUL, no client acceptance.
2. Contradicting six-digit candidate detected without leaking values.
3. Malformed VIN-shaped field does not become verified identity.
4. Wrong D2 sequence and missing final are transport errors.
5. Negative B9 response is not a positive B9FB result.
6. Different text layout retains valid transport with unknown schema.
7. Target40/50 and CAN response ID mismatch fail closed.
8. Ambiguous multiple sessions, exclusive output, privacy and no overwrite.

Next evidence required for genuine XC90 V8 MY2009: one version-bound, read-only
client trace from PassThruOpen through CEM requests and client UI result;
including channels, CAN speeds, CLEAR_RX, exact client acceptance or rejection.
Do not publish Virtual Car binaries or add unverified A3/A6/B9F0 fixtures.
