# VIDA ReadVin: redacted v2/v3 graph consistency

Research date: 2026-11-08. Read-only continuation of the owner's VIDA
ReadVin XML research. Original VIDA ZIP/XML, raw VIN, SQL MDF and
private local paths must stay outside Git.

## Existing, owner-generated source material

Two independent redacted reports were available from the actual VIDA
ReadVin XML. Graph v2 counted nodes, handlers and lexical tokens.
Topology v3 counted node roles and declared two-edge event paths.
The new consistency tool compared seven overlapping counters:

| Field | Both reports |
|---|---:|
| Nodes | 14 |
| ReadVinComponent nodes | 7 |
| VehicleIdentityOutput nodes | 1 |
| Event handlers | 27 |
| Declared calls | 27 |
| AddVIN declarations | 2 |
| SetX40Serial declarations | 1 |

All seven counters agreed. The topology v3 report observed two
declaration-only edges from some ReadVinComponent to each of
the two AddVIN and one SetX40Serial output calls; no direct
one-edge output calls were seen. The XML graph declarations DO
NOT prove code executed, callback enabled, data flowed, a VIN
was accepted, or the intended XC90 V8 profile was selected.

Independent disabled-attribute comparison also agrees for all
three identity method declarations: 3/3 calls have a parameter
child; all 3/3 have **absent/unspecified** literal disabled
attributes in both v2 and v3. No call has an explicit enabled
literal. Absence of disabled is NOT equivalent to successful
callback execution, VIN propagation or even proven enabled
status. The new cross-check reports only fixed-category counts,
not parameter names or values. It passed 11 synthetic cases,
and an owner-original source v2/v3 run with 7/7 shared counts.

F114 was present as a lexical token in the original XML; B9FB
was absent as a lexical token there. Neither establishes what a
different VIDA edition or actual car might request. The user's
publicly redacted graph counters are not evidence of ECU response
bytes, and are not committed to this PR.

## Software and local checks

- emulator/tools/audit_vida_redacted_consistency.py reads ONLY
  existing, already-redacted JSON v2 and v3 reports, each bounded
  to 128 KiB, checks explicit schemas, seven counter overlaps,
  role partitions, declared distance bins, parameter-child and disabled-attribute counts, and false runtime/VIN
  acceptance flags. Writes a NEW categorically redacted JSON
  outside the repository. No source data passthrough.
- emulator/tests/test_audit_vida_redacted_consistency.py contains
  eleven synthetic-only regression groups for agreement,
  contradiction, forged success, boolean/count type mismatch,
  invalid path partitions, partial graphs, privacy/exclusivity,
  schema and oversized-file rejection.

Usage if new v2/v3 reports exist (already done for prior reports):

~~~powershell
py -3 .\emulator\tools\audit_vida_redacted_consistency.py C:\VIDA-private\readvin-15.graph-v2.redacted.json C:\VIDA-private\readvin-15.topology-v3.redacted.json --output C:\VIDA-private\readvin-consistency.redacted.json
~~~

This tool does not run VIDA, SQL queries, CEM, J2534 or ECU
programming. No original XML/ZIP, VIN, source paths or private
metadata are published.

## Next evidence gate

Investigate exact XML parameter reference semantics along the
F114 -> ReadVinComponent -> intermediary -> AddVIN path, then
relate that to original method IL without revealing parameters
or assuming the graph executes. Runtime GetScript selection,
the actual CEM diagnostic reply and accepted VIN/profile
remain unverified. Keep B9FBFrameCount=0 until genuine,
authorized, read-only response evidence exists.

No emulator protocol or CEM behavior changed; no release
is required for this research-only PR.
