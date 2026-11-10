# Stage 50 | VIDA ScriptProvider selection chronology and identity boundary

Scope: read-only investigation of VIDA 2015A for a virtual Volvo XC90 V8 MY2009. The source of truth for actual client acceptance is a private authorized VIDA diagnostic run, **not** a public ECM example, textual token match or successful J2534 transport.

## Verified separately, do not collapse into a single success flag

1. Original user-provided VIDA 2015A IL was examined in merged Stage 47 (PR #55). VehicleAccess.IdentifyVehicle invokes RunIdentifyVehicleScript with a temporarily empty VehicleProfile, then consumes VehicleIdentityOutput; an absent/empty identity takes a VinException branch. The actual SQL/XML script selected by this entry point and its B9FB dependency remain unknown.
2. The public VIDA diagnostic log in Tigo2000/Volvo-VIDA records ScriptProvider calling DiagSwdlRepository GetScript for **VehCommSpecification** (an ECM example), then Fetched script, then Running script. This is a real published example of lookup and execution chronology, but not proof of the XC90 V8 CEM/VIN identity path.
3. A public GetVehCommSpecification/ScriptMissingException stack trace in a Matthews Volvo forum shows the nested ScriptProvider.GetFromDb -> GetOneScriptFromDb -> GetScript route. The failed VehCommSpecification selection is distinct from a CEM bus timeout, an identity-script failure, VIN validation or ECU inventory.
4. Original user Drive files VIDA.log, VidaMonitor.log and server.log were inspected for literal GetScript, ScriptProvider and RunIdentifyVehicleScript entries; none were found. These installer/server/monitor logs are not a complete VIDA diagnostic trace. Their absence proves nothing about what would happen in an authorized diagnostic run.

Public evidence:
- https://github.com/Tigo2000/Volvo-VIDA (published GetScript/Fetched/Running log, for a different vehicle)
- https://www.matthewsvolvosite.com/forums/viewtopic.php?p=671800 (VehCommSpecification error stack, another session)
- https://github.com/vorlocsev/virtualcar/blob/development/docs/research/vida-identity-ecu-boundary-il.md (original 2015A DLL IL evidence)
- https://github.com/vorlocsev/virtualcar/blob/development/docs/research/vida-script-profile-links-stage49.md (SQL metadata boundary)

## New local-only trace checker

emulator/tools/audit_vida_script_selection.py reads an authorized PRIVATE VIDA text log, validates bounded input and emits only categorical counters. It looks for an explicit ScriptProvider GetScript, a Fetched script, and a Running script, with the same thread indicator and matching script identifier *in memory only*, in chronological order within 30 s. Script identifiers, VIN, profile values, ECU IDs, raw lines, timestamps, private path and client identifiers are never copied into output. Trace thread/time matching supports only **local correlation**, not independently authenticated control flow.

Categories include generic GetScript, VehCommSpecification, fetched, running, matched triplets, mismatched identifiers, cross-thread/unpaired entries, ScriptMissingException and explicit GetVehCommSpecification exception references. A reference to RunIdentifyVehicleScript on a stack frame counts as a *mention*, not proof that its script was selected or completed. Exact selected runtime identity script, B9FB -> VIN conversion and MY2009 vehicle acceptance are **always UNVERIFIED**.

Local example with an authorized complete VIDA diagnostic trace:

    python emulator/tools/audit_vida_script_selection.py PRIVATE-VIDA-TRACE.log --output NEW-SAFE-vida-script-selection.json

The file input must be UTF-8, non-symlink and <=4MiB; no input is changed. The output must not already exist. No raw logs, XML scripts, VIN, credentials or literal ECU/script identifiers should be committed to GitHub. Before sharing even categorical counts, review the local output for disclosure-sensitive information.

## Eight regression groups

1. Matching GetScript -> Fetched -> Running is transport/runtime chronology, not VIN proof.
2. Non-VehCommSpecification lookup does not become identity evidence.
3. Mismatched fetched/running script identifiers fail correlation.
4. Cross-thread script events cannot be joined.
5. Superseded lookups and invalid 30-s windows do not silently pass.
6. ScriptMissingException, GetVehCommSpecification error and RunIdentifyVehicleScript **mention** remain separate.
7. Malformed encoding, timestamps and oversized source lines are rejected.
8. CLI reports counters only and never overwrites an existing report.

Test file: emulator/tests/test_audit_vida_script_selection.py. Local synthetic **8/8 PASS**. CI regression will execute this test automatically via existing Python unittest discovery.

## What remains unknown

- Actual RunIdentifyVehicleScript SQL/XML and its ScriptProvider query parameters in the user's original VIDA 2015A.
- Whether target XC90 V8 CEM B9FB/B9F0 is requested and accepted by VIDA.
- The precise resolver, selected vehicle profile and ECU scripts for the target MY2009.
- Real VIDA/SectorV client acceptance, physical DiCE behavior and comprehensive CEM vehicle configuration.

No J2534 code/fixture changed, no fabricated positive CEM/ECU responses, no Security Access, programming, PIN extraction or release publication. Continue only after a reliable authorized original-script/diagnostic-log observation.

## Follow-up: monotonic GetScript triplets and first unbound ReadVin (2026-11-10)

The original trace checker guarded the 30-second window relative to GetScript
but did **not** compare the time of `Running script` to the preceding
`Fetched script`. With out-of-order log timestamps it could mark a successful
triplet even though the run appeared **before** the fetch. The corrected
classifier requires `GetScript time <= Fetched time <= Running time`, on
the same trace thread and within the same log session. Out-of-order running
events have their own counter, also increment `unmatched_running_script_events`,
and clear that thread's pending correlation.

The first VIDA identify-vehicle lookup has a separate *literal request
shape* that may contain `Type: 'ReadVin'`, `Profile: 'EMPTYPROFILE,'`,
`ScriptId: ''`, and `EcuType: '-1'`. The checker now counts that complete
four-field shape, separately from the existing broad explicit EMPTYPROFILE
counter. A matching GetScript/fetch/run sequence increments a second bootstrap
shape triplet counter, not a runtime identity or vehicle profile verification.
Partial, wrong-type, cross-thread, out-of-order and missing-fetched sequences
remain non-promotable. The output never includes original field values, VIN,
script identifiers, private paths, raw log lines or timestamps.

These are synthetic event-order guards, **not evidence that the owner's VIDA
2015A actually executed ReadVin with those parameters**, nor proof of D2
bitrate, CEM replies or VIN acceptance. Real GetScript/profile selection
still requires an independently observed and authorized original diagnostic
session. Earlier test claims in this document refer to the earlier release;
the focused follow-up adds six negative/positive synthetic regression cases.


## Follow-up: clock-only midnight rollover (2026-11-10)

Original VIDA ScriptProvider log event headers contain `HH:mm:ss,fff` but
not a per-event calendar date. The previous 30-second request→fetch→run
correlator compared only same-day millisecond clock values, so a valid
trace beginning just before midnight and continuing after midnight would be
wrongly treated as an orphan fetch or unmatched run.

The clock-only classifier now accepts **one tightly bounded presumed
midnight rollover** only when the GetScript request is in the final 30 seconds
of the day and the subsequent event occurs in the first 30 seconds of the
next clock day. Both elapsed times are measured relative to the same request
and must remain within its original 30-second window; `Running script`
must be no earlier than `Fetched script` on that request-relative timeline.
A middle-of-day backwards timestamp, an overlong window, a reversed
fetch/run and a new logsession remain uncorrelatable. This does **not**
infer a reliable calendar date or permit cross-file/cross-session joins.

Two new report counters, `matched_midnight_rollover_triplets` and
`matched_read_vin_midnight_rollover_triplets`, count only fully ordered
correlations. The original report schema version, `matching_scope`
string, existing counters and all negative VIN/ECU/replay evidence flags
are unchanged. Six synthetic regression cases were added (31–36).
No real VIDA 2015A trace or original XML was examined. Even a positive
rollover counter is only log chronology, **not** proof of
`RunIdentifyVehicleScript` execution, selected XML, J2534 receipt or a
VIN accepted by the client.
