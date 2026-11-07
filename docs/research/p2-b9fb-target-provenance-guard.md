# Issue #4: guard B9FB CEM target provenance (late P2)

This fixes one **concrete ambiguity** in the privacy-safe boundary report:
the earlier audit grouped J2534 B9FB delivery from D2 target **0x40** and
**0x50** into a single success count. Under a late-P2 laboratory scenario,
an unrelated target-40 B9FB delivery could move the recommended next
investigation straight to A3, even if no target-50 B9FB had been observed.

## Changed evidence, not emulator behavior

- Keep the existing `stage_evidence.B9FB` aggregate for compatibility.
- Add `stage_evidence.B9FB_40`, `B9FB_50`, and
  `B9FB_unknown_target` with separate status, bitrate, 11/29-bit
  and missing-channel metadata counters.
- For `P2_MY2005_lab` and `P2_MY2009_lab`, a B9FB target-40
  `delivered` result **never substitutes** for missing or partial
  target-50 delivery. Distinguish `verify_b9fb_target_50_transport`
  from `investigate_b9fb_target_50_transport`.
- For `unknown_lab`, do **not** assert a target-50 requirement from
  the unknown vehicle. Keep the original aggregate flow.
- The current curated SectorV gate schema does **not include** a
  B9FB matcher target or a cross-process transaction ID. Therefore
  even a target-50 J2534 positive and a 13/13 client matcher remain
  independent observations, not proven to refer to the same request.
  The new `b9fb_target_evidence_boundary` explicitly records this.
- **No VIN**, A3 operands, CAN payloads, original channel IDs,
  private log names or ECU identifiers are exported.

## Source boundary

The late-P2 target-50 convention is documented separately in
[p2-xc90-v8-cem-node-and-can-source-audit.md](p2-xc90-v8-cem-node-and-can-source-audit.md).
It is source-based **service node context**, not proof of a real MY2009
XC90 V8 wire response. The known SectorV MY2005 laboratory trace and
older donor B9FB cannot establish SectorV ECU or VIN acceptance.

## Regression gates

The eight new synthetic Python unit groups verify:

1. Target-40-only complete B9FB never satisfies late-P2 target 50.
2. Target-40 delivery plus partial target 50 prioritizes target 50.
3. Target-50 transport permits *investigating* A3, not accepting VIN/ECU.
4. Unknown-target delivery cannot silently become target 50.
5. Separate target, baud, CAN format and missing-channel counters.
6. Unknown-lab scenarios do not hardcode a late-P2 target.
7. No B9FB and failed transport retain prior priority behavior.
8. Private injected values do not appear in output; client acceptance
   and SecurityAccess remain unknown and replay remains forbidden.

Tests are **synthetic input metadata only**. No J2534 driver, positive
A3/A6/B9F0 response, PIN, registration, release, hardware or CAN
transmission is modified. Only promote code after exact-SHA Windows
VMware validation (existing Python/C/Go/MSVC/.NET gates).
