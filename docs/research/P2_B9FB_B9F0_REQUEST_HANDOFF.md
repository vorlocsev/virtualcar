# P2 B9FB → first B9F0: native request-only handoff

Research checkpoint: 2026-11-04. Virtual Car Draft PR #39;
branch `research/vdash-functional-keepalive`. No VMware run, real
SectorV/VDASH acceptance test or physical DiCE test is claimed.

## Why a separate B9F0 check is necessary

The existing native J2534 follow-up auditor can label a first post-B9FB
`CB 40/50 B9 F0` TX as `d2_b9f0`, but the independent
channel-chronology auditor previously counted B9F0 only as generic
intervening app traffic. Consequently, the three-file local capture
preparation could not independently corroborate the first observed
B9F0 read request after a complete B9FB RX.

This is an **observation of application TX in native DLL logs**.
It does **not** demonstrate `PassThruWriteMsgs` succeeded on hardware,
the ECU replied, the part number is genuine or the diagnostic client
accepted an identity.

## Added offline-only checks

- `audit_native_p2_channel_chronology.py` records `b9f0_tx` only
  for the supported `CB 40/50 B9 F0` request family and retains it
  as a barrier before any later A3. A dedicated
  `first_completed_b9fb_to_later_b9f0` record checks native event
  order, channel, channel generation, CEM target, bitrate, clock and
  intervening app TX or RX-clear barriers.
- `prepare_p2_capture.py` cross-checks this B9F0 record against the
  *first* next application TX from the independent B9FB follow-up
  auditor. A later B9F0 is never relabeled as the first TX. Timing is
  released only when both audits agree within 0.001 ms.
- The existing three filenames remain unchanged:
  `channel-chronology.json`, `b9fb-followup.json`,
  `capture-summary.json`. The summary now includes B9F0 request
  count and its bounded cross-audit status. The field
  `b9f0_response_verified` remains `false`; no B9F0 RX or
  part-number parser is introduced.
- Source scope, private fields, allowlisted labels, bounded inputs,
  output-only-new-directory rule and native clock semantics are
  retained. No replay profile, CAN response or J2534 DLL behavior
  has been changed.

## Eight synthetic regression groups

1. First B9F0 on the original channel/target with a verified 100 ms gap.
2. B9F0 on another channel is not marked as a direct matching pair.
3. B9F0 targeting another CEM route cannot inherit the original target.
4. First A3 before later B9F0 remains the first TX and blocks direct B9F0.
5. Intervening repeated B9FB blocks direct B9F0 attribution.
6. CLEAR_RX_BUFFER breaks the candidate pair even when TX follows.
7. Native 32-bit microsecond clock rollover is measured locally.
8. Exclusive, privacy-safe JSON output and explicit *unverified*
   B9F0 response and identity.

Tests: `emulator/tests/test_p2_b9f0_followup.py`, plus the existing
native J2534, channel chronology, follow-up, B9 probe and preparation
regressions. Passing them establishes only synthetic parser behavior.

## Next required authentic evidence

Use **one** complete read-only native J2534 capture from the actual
diagnostic client's single continuous process/epoch, including
`B9FB` delivery, first next app TX, any `B9F0` reply, and the
client-side parse/recognition result. Historical PR30 and run 188
reports do not share a confirmed native clock/channel binding and
must not be joined.

Do not synthesize `B9F0` numbers, `E3` authorization responses,
security access or model-year-specific CEM identity from public
donor XC70 records. Do not publish a Virtual Car release or merge
Draft PR #39 based solely on this offline check.
