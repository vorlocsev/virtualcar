# B9 request classification must match the native executable path

Research checkpoint: 2026-11-04. Virtual Car PR #39, Draft.
Windows x86 virtual J2534 PassThru DLL, read-only lab emulator.

## Confirmed source-code discrepancy

The native `process_d2` handler recognizes B9 FB, F0 and FC
read requests only when the classic CAN request payload begins
with `CB`, continues with a target byte, `B9` and a supported
subcommand. It does not implement a B9 replay for requests
beginning with `CA` or `CF`.

Before this checkpoint, `backend_probe_name` labeled the
payloads `CA 50 B9 FB` and `CF 50 B9 FB` as `D2_50_B9FB`
even though `process_d2` would not execute the read. The
pure P2 CEM observer `p2_cem_classify` likewise labeled those
prefixes as a recognized B9FB request. These were **misleading
research metadata**, not fabricated ECU RX frames.

This matters when analyzing SectorV run #188, which reported
A3 before B9FB but did not include the underlying TX J2534
channel identity. A mistaken `D2_50_B9FB` probe label would
increase confidence in a recognized read command without
evidence that the simulator actually executed it.

## Conservative correction

- `emulator/src/virtualcar.c`: `backend_probe_name` now
  emits `D2_[40|50]_B9F0/FB/FC` only for `CB` requests
  with a complete target, service and subcommand.
- `emulator/src/p2core/p2_cem_router.c`: its read-only
  request observer follows that same classification rule.
- `process_d2`, the underlying CAN reply implementation,
  *has not been changed*. Unsupported forms still produce
  no ECU response and no positive E3 authorization reply.
- A3/A6 CEM probe rules are unchanged; no conclusions
  about authentic security access are implied.
- The existing B9E0 research-only candidate remains a
  separate observation, **not** an implemented B9E0 reply.

## Eight regression cases

The native C regression in `emulator/tests/virtualcar_test.c`
covers the following independent request classifications:

1. CB 50 B9 FB: known B9FB probe on CEM50.
2. CB 40 B9 FB: known B9FB probe on CEM40.
3. CB 50 B9 F0: known B9F0 probe, not B9FB.
4. CB 40 B9 FC: known B9FC probe, not B9FB.
5. CA 50 B9 FB: no recognized B9FB read.
6. CF 50 B9 FB: no recognized B9FB read.
7. Truncated CB 50 B9: no recognized B9FB read.
8. CB 50 B9 FB on unrelated CAN ID 0x555:
   not a D2 CEM request.

Two additional read-only PassThruWriteMsgs checks send CA and
CF B9 forms to the actual simulator path. Each must have no
B9FB `probe_classified` event, one `unhandled_request`
terminal event and zero PassThruReadMsgs results.

These tests prevent misleading `probe_classified` metadata;
they **do not** establish that SectorV accepted VIN, parsed
hardware identifiers, or entered any authenticated CEM state.

## Remaining evidence gap

For a real XC90 V8 MY2009 SectorV capture we still need
a continuous source-local J2534 log identifying channel and
bitrate for each TX, plus the separate client-side verdict
following B9FB and A3. B9FB transport delivery and the
correct classification of its request are necessary checks
but not proof of SectorV's Hardware stage completion.

No physical J2534, VMware or real CEM write was exercised.
No Virtual Car release is published; PR #39 remains Draft.
