# P0 VIDA ReadVin: nearest-call-owned XML parameters

Scope: owner-authorized VIDA XML structure only, without running it.

## Provenance

Existing owner-original redacted ReadVin v2/v3 reports agree on seven
structural counts: 14 nodes, 7 ReadVinComponent, 1 VehicleIdentityOutput,
27 handlers, 27 calls, 2 AddVIN declarations and 1 SetX40Serial.
F114 is lexically present, B9FB absent in this exact XML.
All three identity method declarations have a parameter child and
an absent / unspecified disabled attribute, not runtime evidence.

A nested XML call may contain another call and its parameter. A
naive search through all descendants would misattribute a nested
child call's parameter to its enclosing AddVIN method call.

## Change

Each identity output group gains a fixed, additive JSON section
named parameter_declarations_only. Only parameter descendants whose
nearest call ancestor is the identity method call are counted.
Candidate reference matches are recognized only for attribute
local names node, ref, source and an exact match to one of the
private XML node IDs. Other attributes (name, value, class, etc.)
are never promoted merely because an attribute value equals a
node ID. A lexical reference match is not runtime binding.

This emits only fixed categorical counts:
- calls with owned parameter declarations;
- total owned parameter declarations;
- calls with reference-like attribute matching some node ID;
- subset matching a ReadVin node ID;
- calls with nonempty parameter text.

No original XML, ZIP, VIN, node IDs, parameter keys or values,
credentials, local filenames or raw CAN data appear in output.
The earlier graph-v1 fields and all false runtime/VIN/replay
flags are preserved unchanged.

## Tests and release boundary

Eight synthetic regressions cover nearest-call ownership, nested
foreign calls, unrelated attribute false matches, reference-key
matching, disabled-attribute caution, wrapped parameters,
AddVIN versus SetX40Serial separation, namespaced XML and privacy.

The standalone local binding-shape checker was separately
verified with 20/20 synthetic tests; the original redacted
cross-report comparison suite passed 11/11. Neither constitutes
Windows CI of this exact new GitHub commit.

This work is stacked on research PR #181: compare it against
the PR #181 feature branch, not development alone.
No ECU CEM behavior, D2 B9FB reply fixture, J2534 operation,
PIN, SecurityAccess, firmware or public release is changed.

## Next evidence gate

Compare privately derived categorical argument shapes to original
pinned VIDA VehicleIdentityOutput.AddVIN and SetX40Serial IL, then
investigate the reflection parameter expression evaluator.
Static XML link count cannot establish F114 bytes, a propagated
VIN string, a selected GetScript, client VIN acceptance or
an XC90 V8 MY2009 profile.
