# VIDA P0: six offline CarCom joins, aggregated and privacy-bounded

The user's [previous schema report](https://github.com/vorlocsev/virtualcar/issues/4)
proved exactly **seven of seven fixed table shapes** and **six of six
expected column pairs** exist in the owner's exported CarCom schema:
T111_Service (458 rows), T122_Protocol (9), T110_Service_EcuVariant (89,615),
T100_EcuVariant (2,803), T101_Ecu (208), T160_DefaultEcuVariant (7,840),
T161_Profile (147,647). Those were catalog row counts, not completed joins.

The separate source-only tool
\`emulator/tools/audit_vida_carcom_aggregate_joins.py\` performs an actual
read-only **SQLite-equality aggregate** for those six approved edges. This
does **not** prove original SQL Server FK constraints, a selected ReadVin
script, meaningful XC90 MY2009 profile membership, real ECU availability,
CAN payloads, VIDA VIN acceptance or original car capture.

## What it does

1. Opens only owner-local \`CarCom.sqlite\` with SQLite \`mode=ro\` and
   \`immutable=1\`, then immediately enables \`PRAGMA query_only=ON\`.
2. Validates the \`_vida_meta\` identity and the \`_vida_tables\`/
   \`_vida_columns\` fixed metadata. Rejects an ambiguous fixed table,
   missing source column or source table with more than 1 million rows.
3. Looks for exact, narrow physical table names in the export (unqualified,
   \`dbo.\`, \`dbo_\` or \`dbo__\` prefix). Fails closed if none or more
   than one match. It checks the actual SQLite table's columns and row count
   against the exporter catalog before reading approved relationship columns.
4. Performs exactly the six predeclared source-FK to target-PK comparisons:
   \`T111→T122\`, \`T110→T111\`, \`T110→T100\`, \`T100→T101\`,
   \`T160→T161\`, \`T160→T100\`. Each comparison aggregates in memory/SQL
   only, with buckets: null FK, zero target matches, exactly one target
   match, multiple target matches. It also counts duplicate non-null
   target-key groups.
5. Exports **only counts, allowlisted table names, fixed booleans and static
   schema descriptors**. It never emits source values, private IDs,
   car identifiers, VIN, private table/column names, SQL definitions,
   diagnostic frame bytes, row excerpts, XML or ZIP.
6. Creates an exclusively new JSON file outside the Git checkout. It
   never modifies the owner SQLite copy or user-side manifests.

A successful report establishes referential match counts **under exported
SQLite equality and affinity semantics**. It is not an audit of SQL Server
collation semantics or a transactionally consistent capture of nine databases.

## Owner-controlled execution inside VMware

Only after code review and exact Windows CI success, use a reviewed
\`development\` checkout with Python 3.12+:

\`\`\`powershell
$python = (Get-Content "E:\VirtualCar\Tools\python312.path" -Raw).Trim()
& $python ".\emulator\tools\audit_vida_carcom_aggregate_joins.py" --folder "E:\VirtualCar\VIDA-private" --output "E:\VirtualCar\VIDA-private\p0-carcom-joins-001.redacted.json"
\`\`\`

Use the above only when PowerShell's working directory is the checked-out
repository; or replace the relative source path with that checkout's full
absolute path. Each run requires a **new** output path. Review the JSON
locally before sharing even redacted counts. Never commit it or originals.

Eight synthetic regression gates cover six-edge summaries, null/missing
links, duplicate targets, unknown name and VIN-like payload redaction,
metadata mismatch, ambiguous physical table and missing column, wrong
dataset identity/unrecognized physical mapping, output exclusivity and
Windows-safe connection cleanup.

**If physical SQLite naming differs:** do not guess a table name or
disable identity checks. Report the categorical failure and review the
exporter's physical-name mapping privately before adjusting an allowlist.

## Evidence boundaries and next direction

The original 2014D-derived 2015A ReadVin XML reported 14 nodes, seven
ReadVinComponent, two AddVIN and one SetX40Serial, and the lexical token
F114. Those remain *separate* evidence from the SQL relationships here.
The six CarCom joins cannot by themselves select one XC90 V8 MY2009
profile or prove which service builds a B9FB/F114 request.

Until a separately verified, owner-authorized, read-only vehicle source
exists, leave \`B9FBFrameCount=0\`, the emulator's strict routing, physical
J2534, VIN acceptance and ECU inventory statuses unchanged. No source
database or installed VIDA changes, no programming or SecurityAccess.
