# Issue #4: B9FB target-50 protocol metadata boundary

## Motivation

The B9FB evidence tool separates CEM D2 target 0x40, 0x50 and unknown
target, but its aggregate report did not describe **which J2534 protocol**
was associated with each delivery. It was possible for a late-P2 target-50
"delivered" status to be based entirely on `ISO15765` or `unknown`
channel metadata while the investigation priority advanced directly to
A3. That leap is unsupported by the source.

This follow-up is **analysis-only**, not a change to an emulator frame,
hardware route, filter, driver or model-year identity.

## Output change

- Every stage's `protocol_categories` retains the observed
  `CAN` / `ISO15765` / `other` / `unknown` distinctions.
- `b9fb_target_evidence_boundary` reports whether target-50
  **delivered** J2534 transactions contain verified `CAN`
  protocol metadata, and how many delivered transactions have a
  different/unknown protocol.
- For `P2_MY2005_lab` or `P2_MY2009_lab`, when target 50
  has delivery but *none* of those transactions has known `CAN`
  metadata, the first action is
  `verify_b9fb_target_50_can_protocol_metadata`.
  It is not "invalid frame", "unsupported ECU", an inferred
  SectorV client failure or SecurityAccess status.
- Unknown-lab observations preserve the original behavior. No
  bitrate or CAN ID is silently rewritten.

## Eight additional synthetic checks

1. Valid target-50 delivered with CAN metadata.
2. Delivered ISO15765 metadata prompts a route review.
3. Missing transport protocol stays an uncertainty, not negative ECU data.
4. Mixed CAN/ISO15765/other channels remain distinct.
5. CAN on target 40 cannot mask ISO15765 on target 50.
6. Unknown vehicle scenario does not inherit a P2-only requirement.
7. P3 and A3 protocol counters stay separate from VIN/ECU identity.
8. Invalid protocol values fail closed; arbitrary source strings never
   appear in the summary.

A target-50 J2534 "CAN" field still proves only **what the source log
said about the protocol**, not real hardware acceptance, actual VIN
validity or SectorV successful discovery.

The new Python cases are numbered 17-24 in the existing test module.
Previous 16 cases remain, and the full suite should increase from
268 to **276** on the exact PR HEAD; this is a validation target,
**not a claimed CI result** before Windows VMware runs.

No A3/E3 authorization reply, ECU programming, PIN extraction, firmware
operation, real CAN traffic or published Virtual Car release.
