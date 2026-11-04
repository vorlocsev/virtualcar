# P2 B9FB: donor identity coherence, not ECU acceptance

2026-11-04, Virtual Car research PR #39. Offline/read-only only.
No E3 response, physical J2534, VMware or release changes.

## Evidence from the supplied Volvo P2 CEM research note

A public historical donor example has 13 D2 response frames,
91 non-control bytes containing positive echo 50 F9 FB,
then 88 binary-safe payload bytes. A 17-character VIN/mask
occupies payload offsets 11..27; a six-digit chassis *candidate*
occupies 46..51; a three-digit model/type *candidate* occupies
41..43. The byte at offset zero is 0x57 and a NUL follows it.

These are **positions observed in one donor**. The meaning of
prefix, type and chassis lines is not a verified universal
XC90 V8 MY2009 schema. Application-level checksum unknown.

The checked-in Virtual Car donor profiles demonstrate two cases:

- virtualcar-p2-b9fb-demo.ini: the 17-byte VIN span is
  redacted with X characters. It cannot prove any VIN or
  chassis consistency.
- virtualcar-p2-b9fb-lab-vin.ini: the synthetic embedded
  VIN matches Vehicle.VIN but its last six characters
  differ from the unchanged donor six-digit chassis candidate.
  Its VIN year character A agrees with ModelYear=2010,
  but not an optionally supplied MY2009 expectation (9).
  The donor type candidate 295 does not equal the
  supplied candidate XC90 code 275. That type interpretation
  remains an unverified hypothesis, not an OEM rule.

These mismatches were already visible in the research note.
They cannot be asserted as the specific reason SectorV rejects
the vehicle, because no actual client parser verdict exists.

## New safe binary-aware report

emulator/tools/audit_p2_b9fb_coherence.py takes one local
laboratory INI and reports only bounded booleans, lengths,
known status enums and fixed mismatch labels.

First it checks frame count/indexing, exactly eight bytes per
frame, consistent CAN response ID, D2 transport ordering,
and the positive 50 F9 FB echo. Only if the **exact known
13-frame/88-byte donor footprint** matches does it examine
the candidate VIN, chassis and type offsets. Other layouts
are reported as uninterpreted, not fabricated or rejected
as impossible on a real XC90.

For a recognized footprint the tool compares the embedded
17-byte VIN with Vehicle.VIN if present, compares a six-digit
chassis candidate with its VIN suffix, compares ModelYear and
optionally --expected-year against the tenth VIN character
for year-code range 2001..2030, and optionally compares the
three-digit type candidate to --expected-type-code. All
comparisons are hypothesis checks, never authentication.

No VIN, chassis, CAN frame, response ID, part number, path,
password or unrecognized source text is copied to its JSON.
No profile or ECU response is modified. Checksum, semantic
schema, real identity and SectorV acceptance always remain
unverified.

Example, from repository root in PowerShell:

    py -3 .\emulator\tools\audit_p2_b9fb_coherence.py .\emulator\virtualcar-p2-b9fb-lab-vin.ini --expected-year 2009 --expected-type-code 275 --output "$env:TEMP\vc-b9fb-coherence.json"

The output path must be new. The resulting report is safe to
review locally, but it must not be used as a genuine XC90
MY2009 vehicle identity certificate.

## Verification

Eight Python regression groups check:
1. Original lab profile: valid transport but chassis candidate mismatch.
2. Optional expected MY2009/type275 comparisons.
3. Masked donor demo: no inferred VIN, chassis or year.
4. Mutated Vehicle.VIN and ModelYear remain independent
   from transport validity.
5. Corrupt positive echo, control order and final frame.
6. Extra/missing frames, invalid byte values and bad options.
7. No private vehicle value or path in output.
8. CLI output no-overwrite and source preservation.

A separate CI step will create one safe JSON for the existing
lab INI, not a new vehicle fixture. No A3/E3, PIN, programming,
VDASH or SectorV client acceptance is asserted.

The next decisive step remains a genuine XC90 V8 MY2009
read-only capture and the *client-side* result of decoding
the B9FB block. Only that could establish whether these
candidate fields play a role in the Hardware transition.
