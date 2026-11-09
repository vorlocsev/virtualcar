# VIDA P0: owner-private CarCom T111/T122 schema preflight (read-only)

**Status:** source-only tool and synthetic tests; private VMware dataset has NOT
been queried by this new tool. The previously completed
[VIDA Offline Catalog workflow #42704142299](https://github.com/vorlocsev/virtualcar/actions/runs/42704142299)
verified 9/9 SQLite copy hashes/integrity and counted 269 tables, but it
did **not** extract any actual T111/T122 schema links or join source rows.

## Purpose and evidence limitation

The actual offline VIDA installation has no runnable VIDA diagnostic GUI in
the guest. In the same owner VM, copied SQLite exports are kept privately under
`E:\VirtualCar\VIDA-private` with corresponding manifest files.

This metadata-only tool determines which **expected** fixed table names and
column names are present in the existing exporter catalogs, before anyone
attempts original CarCom row joins or assumes a vehicle profile.

- CarCom candidate tables: `T111_Service`, `T122_Protocol`,
  `T110_Service_EcuVariant`, `T100_EcuVariant`, `T101_Ecu`,
  `T160_DefaultEcuVariant`, `T161_Profile`.
- DiagSwdlRepository: `ScriptType`, `Script`, `ScriptContent`,
  `ScriptProfileMap`.
- BaseData: only export identity, overall table/column counts.
- Candidate edge-shape booleans are based on fixed column names from
  previous *research hypotheses*. They are not foreign-key referential
  integrity checks, actual joins, runtime `GetScript` selection,
  known `ReadVin` service bytes, matching VIN, or an XC90 V8 MY2009
  ECU/vehicle profile.

## Commands for the trusted owner-local Codex session

Use a **new output filename**, from a reviewed checkout of the corresponding
GitHub commit. Within the guest Windows PowerShell (VIDA itself is NOT needed):

```powershell
py -3 .\emulator\tools\audit_vida_carcom_schema_links.py `
    --folder 'E:\VirtualCar\VIDA-private' `
    --output 'E:\VirtualCar\VIDA-private\p0-carcom-schema-001.redacted.json'
```

The script opens exactly three immutable local SQLite **copies** with
`mode=ro&immutable=1` and `PRAGMA query_only=ON`. Its SQL statements are
limited to `_vida_meta`, `_vida_tables`, and `_vida_columns`.
It cannot access the raw CarCom/Script user rows, original XML/ZIP, VIN,
CAN payloads or original SQL definitions.

The output contains **only fixed allowlisted** table/column names,
source row counts already present in export metadata, column counts and
six *candidate* edge-shape booleans. Unknown source table/column identifiers
are never emitted. An ambiguous fixed name in multiple SQL schemas,
repeated column, invalid exporter identity, or missing database fails closed.
Report output is exclusive and cannot be written into the Git checkout.

**Review even this redacted local JSON before copying aggregate categories to
Issue #4. Do not upload the private original databases, manifests, SQL, VIN,
XML/ZIP, or local source profile IDs.** This tool does not assert the source
copies are an atomic cross-database SQL snapshot.

## Verification and next gate

Eight fully synthetic regression groups verify expected links, absent tables,
missing columns, duplicate schema names, duplicate columns/export identity,
missing/incorrect DB, private-name redaction and exclusive output/no source
modification. Run `python -m unittest discover -s emulator/tests -p
'test_vida_carcom_schema_links.py' -v` before auditing private copies.

**Next gate only after actual owner-local report:** decide which fixed schema
matches, then independently design/review a bounded, read-only referential join
without exporting original row values or silently using guessed column names.
A metadata-only result does not justify adding a CEM `B9FB` response,
`F114`, VIN acceptance or ECU presence. Keep `B9FBFrameCount=0`,
`main`, draft PR #2, and published releases unchanged.
