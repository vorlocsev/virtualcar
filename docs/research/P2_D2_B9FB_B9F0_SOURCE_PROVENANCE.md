# Volvo P2 CEM B9FB / B9F0: provenance and source-consistency gate

Research checkpoint: 2026-11-04, Virtual Car Draft PR #39.
This is a read-only **fixture audit**, not OEM ECU identification.

## Evidence supported by the supplied CEM analysis

- A published donor-era CEM 0x50 B9FB sequence has **13 D2 frames**.
  After removing one per-frame control byte: 13 × 7 = 91 bytes.
  After removing the three-byte positive echo (50 F9 FB) the donor
  example has **88 data bytes**, with a 17-character VIN candidate
  at offset **11** (relative to the bytes after that echo).
- The donor footprint has an initial binary prefix, embedded zero and
  CRLF. It is not one plain ASCII string. Treat the one-byte D2
  control prefixes as transport, not newline/text field delimiters.
- The tested donor-style chassis and candidate vehicle-type positions
  are **heuristics tied to that one sample**, not a universal OEM schema.
  A changed VIN alone can leave other donor fields inconsistent.
- The historical 0x50 B9F0 example published by vtl has **three frames**
  with controls 8F, 09, 4C and response CAN ID 0x01000003.
  Its part-number interpretation belongs to the published example,
  **not** to XC90 V8 MY2009. B9F0 bytes must not be auto-extrapolated
  to a different vehicle.

Relevant public posts:
- https://www.matthewsvolvosite.com/forums/viewtopic.php?p=573059
- https://www.matthewsvolvosite.com/forums/viewtopic.php?p=573057
- https://www.matthewsvolvosite.com/forums/viewtopic.php?p=582658

We have **not** obtained an authenticated XC90 V8 MY2009 CEM
B9FB/B9F0/FC source, a SectorV/VDASH acceptance result, or a verified
application-level checksum formula for these blocks.

## Concrete bug fixed in the importer

Before this patch, import_p2_trace.py loaded a template INI and left
its original [P2] FixtureProvenance text intact after replacing one
of the D2 sections with data from an unrelated local trace.

For example, importing a B9F0 response into a profile containing a
modified historical B9FB donor would leave an inherited
historical_public_* provenance label at the top of a **composite**
profile. That global label could be misunderstood as evidence that
B9FB and B9F0 belonged to one verified vehicle.

Every new import now resets the global value to:

  FixtureProvenance = local_composite_unverified_trace_import

The replaced section receives these fixed, local workflow-only fields:

  FixtureSourceClass = local_redaction_attempt_unverified
  FixtureIdentityVerified = 0
  FixtureApplicationIntegrity = unknown
  FixtureSingleClientRunVerified = 0

The SourceClass is instead local_private_raw_unverified when explicitly
retaining raw identifiers, or local_synthetic_vin_unverified when a
laboratory VIN is inserted. A "redaction attempt" is not a promise that
all personal identifiers, part numbers, VIN variants or checksums were
removed. Imported source logs and original profile files stay
unchanged. Output uses exclusive creation.

No new Volvo frames, VIN, ECU identifiers or B9F0 part numbers are
invented by this correction.

## Independent offline profile audit

The new auditor tools/audit_p2_d2_fixture_provenance.py examines all
six CEM fixture sections: target 0x40 / 0x50 by B9FB / B9F0 / B9FC.

It verifies each **configured** response's CAN ID framing, first-frame
positive or negative service echo, control-counter sequence,
last-frame completion, exact frame count, and expected target/opcode.
An empty fixture is reported as disabled rather than a failed
attempt to communicate with a vehicle.

It then reports only safe, fixed-category values:

- per-section target, service, expected CAN bus and frame count;
- positive/negative transport status, never accepted ECU identity;
- source-class label with arbitrary private text redacted;
- recognized **published-example shape**, not a decoded CEM part number;
- existing B9FB donor-footprint consistency flags for the known
  13-frame sample;
- warnings for inherited global historical labels, missing section
  origins and mixed-source profiles.

The source fields in the INI are **self-reported**, not cryptographic
proof. The audit therefore leaves source consistency, ECU identity,
application checksums, real XC90 V8 MY2009 identity and SectorV/VDASH
acceptance all unverified.

### Local use (review private input, share only safe JSON)

    py -3 emulator/tools/audit_p2_d2_fixture_provenance.py ^
      emulator/virtualcar-p2-historical-demo.ini ^
      --output b9f0-public-shape-safe-new.json

On PowerShell use one line instead of Windows CMD caret continuations:

    py -3 .\emulator\tools\audit_p2_d2_fixture_provenance.py .\emulator\virtualcar-p2-historical-demo.ini --output .\b9f0-public-shape-safe-new.json

The destination must not exist. Do not publish raw capture logs,
unredacted imported INI files or exact customer/ECU identifiers.

## Regression and evidence boundary

Eight synthetic/donor regression groups cover: disabled default,
published B9F0 three-frame shape, donor B9FB footprint and VIN/chassis
inconsistency, masked VIN, malformed framing/echo, negative B9F0,
mixed-source import that resets provenance, and CLI privacy/no-overwrite
plus synthetic-VIN origin.

The normal Windows x86 CI also continues the compiled-DLL native
route tests. Neither those tests nor an offline fixture-source
audit can establish that SectorV or VDASH accepted the simulated
vehicle. The next real gate remains an operator-observed single
read-only client session with sanitized J2534 evidence.
