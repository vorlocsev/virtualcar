# Virtual Car P2: mixed-origin D2 fixture replay is opt-in

Research date: 2026-11-04. Scope: Draft PR #39 only.
**Read-only laboratory control; it does not authenticate real Volvo CEM data.**

## Problem

A B9FB or B9F0 trace imported from a local capture may coexist in
virtualcar.ini with inherited B9FB/B9F0/B9FC frames from a different
donor. The importer already marks such profiles:
FixtureProvenance = local_composite_unverified_trace_import

Previously the compiled J2534 DLL would validate framing and then
stage these mixed-source frames as replies to CEM requests, with no
acknowledgment that the source relationship was unknown.

## New default

For a profile with precisely that importer-generated provenance marker,
all D2 replay slots (including optional D2_Node slots) are disabled at
DLL initialization unless the operator changes the **resulting output**
profile to contain:

    [P2]
    FixtureProvenance=local_composite_unverified_trace_import
    AllowCompositeReplay=1

Only the literal string 1 unlocks the lab. Values 0, 01, 0x1, 2,
blank, or an absent option do not.

The importer ALWAYS writes AllowCompositeReplay=0 on a new output file.
It removes case-variant inherited entries first, including
allowcompositereplay=1, because Windows INI lookups are not case-sensitive.
This also overrides a template whose previous operator enabled replay.

When the lock is active, the DLL logs only a redaction-friendly count:
"P2 unapproved composite D2 fixtures disabled (count, BE)".
It does not print VIN, donor part number or raw captured frame data.
J2534 connection and the independent synthetic P3 UDS read path remain
available for separate transport diagnostics.

The **default virtualcar.ini** has AllowCompositeReplay=0 and zero
B9FB frames; it remains a read-only synthetic lab starter. Existing
untagged synthetic fixtures and historical public examples are not
silently reclassified as verified or authenticated. This is a
workflow safeguard for a precisely tagged importer output, not a
security boundary against someone who deliberately edits the file.

## What an operator can and cannot conclude

The new audit_p2_d2_fixture_provenance.py output distinguishes:
- stored D2 fixture framing, which is only an INI assertion;
- importer_composite_marker_observed;
- explicit_lab_opt_in_observed;
- stored_d2_fixtures_blocked_without_opt_in;
- per-fixture replay_allowed_by_profile_gate.

Even with opt-in=1, application checksum semantics, CEM identity,
vehicle model year and SectorV/VDASH client acceptance remain unverified.
A profile can contain 13 donor-style B9FB frames and three donor-style
B9F0 frames without these belonging to the same actual XC90.

This gate does NOT prohibit a human from intentionally replaying a
mixed-origin profile for a controlled read-only experiment. The
opt-in simply prevents accidentally using a newly imported composite
as if it were a coherent vehicle capture.

## Testing

Eight host C regression gates exercise six basic D2 fixture slots
plus an optional node, blocked/no-op and explicit opt-in cases,
unknown/historical and untagged labels, metadata preservation, and
real native CAN silence after the guard.

Python import regressions verify old AllowCompositeReplay=1 and
case-variant aliases are reset to one canonical 0. The offline
provenance auditor reports saved frames as blocked until a separate
manual opt-in is present.

The Windows x86 native-routes CI executes the **compiled DLL twice**
in separate isolated laboratory processes. The baseline synthetic
B9FB -> B9F0 -> P3 chain must complete. The importer-tagged
CompositeLocked variant must suppress B9FB/B9F0 yet preserve
independent synthetic P3 F114 read-only transport. All native
raw logs remain in runner TEMP; only allowlisted JSON is published.

No real SectorV/VDASH process, authentic XC90 V8 MY2009 CEM,
physical adapter, programming, PIN or security access is involved.
