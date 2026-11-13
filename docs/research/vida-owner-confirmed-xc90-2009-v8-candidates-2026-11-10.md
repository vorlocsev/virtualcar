# Owner VIDA CarCom: XC90 MY2009 V8 candidate profiles

Read-only, owner-run query on the original SQL Server **CarCom** database,
2026-11-10. This research note records original identifiers faithfully:
**no names, numeric IDs, VINs, or values were anonymized or invented**.

## Confirmed observed facts

Owner ran a SQL query selecting original \`T161_Profile\` records, joining
\`T162_ProfileValue\` for model/year/engine, counting **direct** rows
in \`T136_InitHw_Profile\` and **direct** rows in \`T160_DefaultEcuVariant\`.

The predicate was \`(m.identifier='275' OR p.title LIKE 'XC90%')\`
and \`(y.identifier='2009' OR p.title LIKE '%2009%')\`.
The result contains **349 records** for this query, not necessarily all
possible XC90 2009 records in the whole DB. All 349 emitted rows have
model \`275\`, model year \`2009\`.

- **43** records with \`EngineDescription='B8444S'\`.
- Across all **349** selected records: **335** have both
  \`DirectInitHwCount=0\` and \`DefaultEcuCount=0\`.
- Exactly **one** record has \`DirectInitHwCount=1\`:
  generic \`XC90 2009\` profile ID **163119**, original
  \`ProfileIdentifier='0b00c8af83f1a29a'\`; its
  \`DefaultEcuCount=20\`.
- All 43 V8 B8444S records have **zero direct InitHw links**.
  Exactly two V8 records have nonzero direct default ECU counts:
  - ID **163120**: \`XC90 2009 B8444S\`, original
    \`ProfileIdentifier='0b00c8af83f1a29b'\`,
    \`DefaultEcuCount=7\`.
  - ID **163191**: \`XC90 2009 B8444S TF-80SC AWD\`, original
    \`ProfileIdentifier='0b00c8af83f1a2e4'\`,
    \`DefaultEcuCount=2\`.
- Four other original V8 + TF-80SC AWD combinations illustrating
  further subdivisions: \`289697\` (L.H.D),
  \`289699\` (L.H.D Volvo Cars North America),
  \`289701\` (L.H.D Volvo Cars Europe),
  \`289702\` (R.H.D). All have zero **direct** InitHw and
  zero **direct** DefaultEcuVariant links.

These facts establish original **direct database relationships** only.
Do not concatenate or inherit those rows automatically. A real VIDA
runtime can apply profile inheritance/selection rules outside this
query, which are not established by these results. Do not treat
\`DefaultEcuCount=0\` as proof that the ECU is absent.

## Current concrete next step

Read only the original rows associated with profile IDs
\`163119\`, \`163120\` and \`163191\`, using exact table names
confirmed in the owner's catalog:

1. \`T161_Profile\`: complete original selection, including any nullable
   profile-value FK dimensions and \`folderLevel\`.
2. \`T136_InitHw_Profile\` joined to \`T130_Init\` and
   \`T131_InitValue\`: complete original direct InitHw values with
   \`sortOrder\`, no guessed inheritance.
3. \`T160_DefaultEcuVariant\` joined to \`T100_EcuVariant\`:
   complete original direct ECU variant identifiers and relationships.
4. \`T110_Service_EcuVariant\` joined to \`T111_Service\`:
   original service/protocol identifiers and \`DATALENGTH(definition)\`,
   but **do not execute the SQL \`image\` bytes as script**.
5. Full untruncated \`sys.foreign_key_columns\` metadata for
   the above relationships.
6. \`DiceTiming\` original \`MessageTiming\` and \`TimeoutAndResend\`
   rows, keeping original \`Comment\` bytes/text intact.

The first actual owner-local evidence bundle uses a PowerShell
read-only query script. Generated CSV and manifest files belong in
\`%USERPROFILE%\VIDA-original-private\` inside the user's Windows VM,
not in the public repository. The script is not an ECU programming
tool and does not require a J2534 adapter.

## Acceptance boundaries

**Confirmed:** Original SQL catalog schema and FK names, original
2009 XC90 B8444S candidate profiles, direct counts, and original
DiceTiming values in the previous owner's report.

**Still untested:** VIDA runtime algorithm for composing the
selected profile; selected ECU variant vs actual CEM/ECM;
service-definition binary format; exact GetScript/ReadVin query;
on-wire CAN/J2534 timings; successful VIN acceptance;
physical J2534; latest exact-head PR validation on VMware.

All observed user VIDA databases reported SNAPSHOT isolation OFF.
Do not \`ALTER DATABASE\` or set the user VIDA SQL database writable
for this research task.
