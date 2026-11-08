# P0-VIN-06 checkpoint: isolate VIDA ReadVin EMPTYPROFILE selection windows

Date: 2026-11-08
Repository: vorlocsev/virtualcar
Source branch: `fix/p0-vida-bootstrap-getscript-window-boundaries`
Stacked base: research/p0-vida-readvin-service-catalog-static-join (Draft PR #192; pinned base `3e90a0d30d63133f489b8ce12894ac9288b6d340`)
Module implementation commit: `ff11b776fd681e61f1b70637d2801af30624e548`
Test implementation commit: `ee498a69625a14348584b99301fd6bca2e800f10`
Module Git blob SHA-1: `297f5404fa010254f5c084aaa9a581de0769e7dc`
Test Git blob SHA-1: `a955834dc2f74d5c261710415d48d90e48b17132`

## Bug and impact

Before this stage, `audit_vida_readvin_bootstrap_trace.py` opened a tracked window for `ReadVin/EMPTYPROFILE` and left it open until the next `Starting new logsession`. A later `GetScript` selection for another script or a profiled ReadVin did not close the tracked bootstrap window. Consequently, unrelated subsequent VehComm and J2534 frames could be counted as belonging to initial VIN bootstrap.

The previous `sessions_with_all_three_request_families` counter also summed the three families over an entire logsession. Two separate ReadVin bootstrap selections could falsely satisfy this **same-window** gate by contributing different request families.

## Changes

- Track all `SP: GetScript` selections. At every new selection, clear per-window request families and only track when the new script is `ReadVin` with `EMPTYPROFILE`.
- Reset tracked state and request families on `Starting new logsession`.
- Track the three known request-family declarations only within one uninterrupted selected bootstrap window.
- Count a logsession as complete only if at least one of its **individual bootstrap windows** contains all three request families; do not join across different scripts/windows.
- Preserve the existing JSON schema, counters, source limits, privacy restrictions and hard-coded **false** for actual ECU response, client VIN acceptance and replay approval.

No CAN protocol changes, J2534 emulator response changes or original VIDA data are introduced.

## Verification: eight groups

The amended source and six new Python unit tests were fetched directly from GitHub after commit. Static source assertions:
1. Independent `GetScript` selector exists: PASS.
2. Selection clears previous tracking and window state: PASS.
3. Non-bootstrap scripts turn tracking off: PASS.
4. Logsession boundaries clear window state: PASS.
5. All three request families are required in the *same* active window: PASS.
6. Aggregate completion uses per-session window flags, not entire-session family counts: PASS.
7. Privacy limits and all explicit false runtime/VIN/replay fields remain: PASS.
8. Six new cases committed (18 total tests now defined); scenario coverage spans unrelated selection, profiled ReadVin, split/repeated windows and logsession separation: PASS.

**10/10 static source assertions PASS across eight verification groups.**
**Actual Python execution of the 18 tests: NOT RUN in this stage.**
**Exact-head Windows VMware CI: NOT RUN** (owner-only workflow dispatch is not exposed by the current connector).

## Evidence limits and next gates

- No owner-private VIDA log processed by this stage. All scenarios are synthetic declarations.
- A complete three-family request window is a *log classification*, not a confirmed ECU response. Positive-looking RX is not accepted VIN.
- The selected original private ReadVin ZIP and matching catalog T111 CSV have not been validated here.
- SectorV/VDASH acceptance, physical J2534, J2534 x86 build: NOT VERIFIED.
- No binary artifact or GitHub Release published.

Next: execute the full 18-test Python module and eligible Windows CI on an immutable reviewed source SHA; only after successful verification consider merging into its stacked research base. Do not mark an experimental VIN/CEM reply as implemented from this fix.
