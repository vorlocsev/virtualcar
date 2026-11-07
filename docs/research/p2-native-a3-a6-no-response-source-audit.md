# P0 / Issue #4: distinguish native CEM no-response from J2534 timeout

## Source-level finding (development, 2026-11-07)

In `emulator/src/virtualcar.c`, the read-only native emulator
`process_d2()` first checks **CAN** requests on ID `0x000FFFFE`
against the complete `cem_d2_probe_shape()` envelope: significant
length prefix `0xCA..0xCF`, target `0x40/0x50`, opcode `A3/A6`.
For such requests it emits exactly:

```text
P2 D2 CEM A3/A6: no verified response implementation
```

Then it marks the request `unimplemented_probe/no_response`
in the internal backend and returns **without queuing a CEM RX frame**.
A caller's later `PassThruReadMsgs` timeout is therefore predictable
for this implementation branch. This is **not** proof that the
SectorV client expects a particular E3 reply, ignition state, security
permission, normal-mode predicate or that any physical XC90 behaved so.

Earlier, `audit_j2534_discovery.py` recognized the A3/A6 TX
and potential read timeout, but ignored the exact native marker,
making an **implemented response absent by design** indistinguishable
from a generic transport timeout when the source record was available.

## Evidence classification after this change

- The exact native marker applies **only** to a pending same-process,
  recognized D2 A3/A6 transaction on CEM target 40/50; it cannot
  annotate an unrelated B9FB/P3 or a different PID.
- With no reported RX, status is `unsupported`, reason
  `cem_response_not_implemented`.
- A subsequent observed J2534 read timeout remains an independent
  boolean `j2534_timeout_observed`. Source marker visibility is
  `native_cem_response_unimplemented`.
- If a contradictory RX record is present for that transaction,
  classify as **unverified**, reason
  `cem_unimplemented_marker_rx_conflict`; never trust it as a
  genuine accepted CEM reply.
- Without the exact marker, a read timeout stays a timeout.
  A missing response fixture for B9FB/B9F0 remains a different
  `no_fixture` reason.
- Logs from earlier emulator builds and third-party J2534 adapters
  cannot be presumed to emit this new-recognized (but already
  implemented in source) marker. Missing marker is not evidence
  of CEM functionality or failure.
- No operand bytes, VIN, paths, PIN, E3 bytes, ECU identity or
  client acceptance are exported. The analysis script never
  synthesizes or transmits CAN frames.

## Eight synthetic regression gates

1. A3/50 exact marker, no RX, explicitly unsupported.
2. A6/40 marker plus J2534 timeout retains both observations.
3. Timeout without marker remains transport timeout.
4. Similar but inexact source lines cannot inject the marker.
5. Unrelated B9FB/P3 do not inherit the A3/A6 marker.
6. Concurrent channels bind only the most recently selected TX.
7. Separate PID and target-unknown probes cannot claim native CEM support.
8. Contradictory synthetic A6 RX cannot turn native no-response into
   a genuine delivered ECU. Output remains privacy-safe.

The native text audit and the downstream
`audit_p2_discovery_boundary.py` now both retain this evidence:

- `stage_evidence.A3_40`, `A3_50`, and `A6` count
  `native_unimplemented_no_rx` and `native_marker_followed_by_j2534_timeout`.
- An explicitly conflicting RX is counted separately as
  `native_marker_with_unverified_rx`, never interpreted as a positive ECU.
- The report's first investigation priority, **only after manual same-run
  provenance and B9FB route/matcher checks**, is
  `native_cem_a3_a6_response_not_implemented`.
- Older J2534 reports without the new booleans remain supported and
  cannot acquire invented "unimplemented" evidence; a fabricated boolean
  or contradictory route/reason fails validation.
- A manual same-run review does not establish per-transaction cross-client
  matching, SectorV acceptance, or the contents of an absent CEM reply.

This is a **diagnostic source-evidence fix**, not a CEM response
implementation. The two additional synthetic test modules contribute
**16 tests** (8 native text and 8 downstream boundary groups). The
expected full Python suite increases from **276 to 292** tests; this
is **not a claimed Windows result** before exact-SHA feature validation.

## Next unblocker

Run one permitted, continuous, locally held read-only
SectorV + Virtual Car J2534 session. Run the existing
`audit_j2534_discovery.py` and `audit_sectorv_gate.py` locally
and compare their sanitized reports with
`audit_p2_discovery_boundary.py`. If the native marker is
present, the correct immediate diagnosis is **emulator
unimplemented A3/A6 reply** rather than a guessed CAN routing,
frame-timing or security failure. This does not solve the
normal-mode gate or certify XC90 V8 MY2009.

See [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4)
and [existing P2 read-only capture research](p2-public-capture-followup.md).

No ECU/security authorization, firmware write, adapter registration,
driver install, replay fixture or public Virtual Car build.
