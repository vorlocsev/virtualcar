# Historical SectorV run 188: A3 before B9FB

2026-11-03. Draft PR #39. No VMware or physical adapter.

## Recovered evidence

Previously stored redacted reports were rechecked. They are derived
analyses, NOT an independently preserved raw J2534 TX/RX capture.

- d2-sectorv-report.json, analyzer 0.3.6.7-dev8-standalone:
  31 B9FB requests, 23 ordered 13-frame completions, 8 incomplete
  disconnects. Four A3 requests are reported unmatched.
- d2-sectorv-latest.json, analyzer 0.3.6.7-dev9:
  run 188 has one complete B9FB and one unmatched A3;
  reported A3-after-B9FB counts are zero.
- d2-sectorv-latest(1).json, analyzer 0.3.6.7-dev10:
  run 188 event order:
  1 run_start (window 0)
  2 can_connect_500k (window 1)
  3 a3_request (window 1)
  4 a3_unmatched (window 1)
  5 can_connect_125k (window 2)
  6 b9fb_request (window 2)
  7 b9fb_ordered_complete (window 2)
  8-11 disconnect (window 2)
  12 close (window 2).

The B9FB session separately reports route 0x50, response CAN ID
0x01200003, 13 frames delivered and 13 matching RX metadata frames.
However the report explicitly says TX channel ID is absent.
Thus a B9FB event appearing after a 125k Connect does NOT prove
that the B9FB was actually transmitted on the 125k channel. Do
not infer a physical route, security level or client parser state.

## Corrected research conclusion

In *run 188* the observed A3 request PRECEDES the completed B9FB
event and belongs to an earlier connection window. It is not a
validated post-B9FB transition or a same-channel continuation.

A separate historical SectorV client-side VIN -> Hardware trace
from PR30 reports 13 matched B9FB frames followed by Hardware/A3
with no RX. Its relationship to run 188, including exact clock
and channel linkage, is not proven. Do not merge the runs.

The prior synthetic Windows x86 DLL-only CI 41710010150 did
measure 152.763 ms from B9FB TX to its final RX and 0.943 ms
from final RX to next A3 TX. Those values are source-local
measurements of a deliberately synthetic harness, NOT the
timing of SectorV. The test uses an artificial zero-filled
B9FB payload, not a valid XC90 VIN profile.

## New historical report chronology auditor

emulator/tools/audit_sectorv_report_chronology.py accepts only the
recognized old SectorV JSON report family and emits a bounded,
allowlisted JSON summary. It distinguishes:

- A3 before a completed B9FB event;
- A3 after a completed B9FB in the same connection window, but
  without declaring TX channel or ECU acceptance proven;
- A3 after B9FB in different windows;
- missing timeline or ambiguous event multiplicity.

It verifies timeline consistency with reported counts and
13-frame session status. Contrary chronology counts are refused.
No raw VIN, CAN frame, PID, path or original log is exported.

Example command from the repo root in Windows PowerShell:

    py -3 .\emulator\tools\audit_sectorv_report_chronology.py '.\d2-sectorv-latest(1).json' --output "$env:TEMP\vc-sectorv-chronology.json"

The output filename must be new. Keep the input locally.
Eight synthetic tests check run-188 order, older aggregate
unknown chronology, same-window after-order, different-window
after-order, contradictory counters, malformed/incomplete
records, privacy filtering, and no-overwrite.

## Still needed

An uninterrupted new source-local SectorV J2534 recording with
explicit TX channel ID plus a separate client-side result
would allow a stronger audit. A source-local clock join is
not present in the historical reports. No positive E3 fixture,
VIN acceptance or ECU enumeration is claimed.

This stage does not modify Virtual Car response bytes,
simulate authorization or publish a release.
