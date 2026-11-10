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
limited to `_vida_meta`, `_vida_tables`, and `_vida_columns`, including
zero-row `SELECT * ... LIMIT 0` checks of their real exporter column schemas.
This rejects malformed exports where SQLite would otherwise interpret a missing
double-quoted column identifier as a string constant.
It cannot access the raw CarCom/Script user rows, original XML/ZIP, VIN,
CAN payloads or original SQL definitions.

The output contains **only fixed allowlisted** table/column names,
source row counts already present in export metadata, column counts and
six service and six optional hardware *candidate* edge-shape booleans. Unknown source table/column identifiers
are never emitted. An ambiguous fixed name in multiple SQL schemas,
repeated column, invalid exporter identity, or missing database fails closed.
Report output is exclusive and cannot be written into the Git checkout.

**Review even this redacted local JSON before copying aggregate categories to
Issue #4. Do not upload the private original databases, manifests, SQL, VIN,
XML/ZIP, or local source profile IDs.** This tool does not assert the source
copies are an atomic cross-database SQL snapshot.

## Verification and next gate

Fifteen fully synthetic regression cases verify exporter metadata structure,
expected links, absent tables,
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


## Additive v2 gate: InitHw inheritance versus per-ECU busRate (2026-11-10)

The owner-supplied *later* offline research summary for XC90 V8 MY2009
reported 43 candidate profiles, nine direct ECU defaults across two
profiles, two CEM candidates and one ECM candidate. For GGD CEM/ECM,
the source report described CAN 500 kbit/s with 29-bit addressing, while
**the D2 CEM rows had no bus speed**. This is static catalog
classification, not proven CAN/DiCE traffic or an approved CEM fixture.

Independently published [`spnda/volvo_vida_db` source at pinned revision](https://github.com/spnda/volvo_vida_db/blob/e2f8ee165e373360d7f7fd0e80298f68c25bc07e/scripts/carcom.py)
documents two distinct metadata paths in its **2014D research port**:

1. `get_vehicle_ecus` joins `T120/T121_Config`, `T122_Protocol`
   and `T123_Bus`; a `T121_Config.busRate` is per configuration and
   can be absent. It is not a universal D2 speed.
2. `get_hw_settings` joins `T136_InitHw_Profile` through
   `T130_Init` / `T131_InitValue` / `T132_InitValueType` and
   `T161_Profile.folderLevel`. Its research implementation chooses
   higher folder level (more specific) settings when multiple profiles
   supply the same setting. **This does not independently prove the
   exact owner 2015A installation selected those inherited values.**

The schema preflight tool now emits `schema_version=...-v2` and
an additional *separate* six-element `hardware_edge_shape_candidates`
array, alongside the original six `edge_shape_candidates` (unchanged).
It only checks fixed allowlisted table and column **names** in the
three exporter catalog tables, never source data or the user's
actual `InitHw` setting values. Key safety flags:

- `hardware_init_value_column_shape_present`: true only if all
  four `T136/T130/T131/T132/T161` edge column shapes exist and
  `folderLevel`, `initValue`, and `name` are present. **Only
  source shape, not any live value or effective precedence.**
- `hardware_init_profile_priority_verified=false`.
- `d2_baud_from_original_data_verified=false`.
- `d2_baud_inferred_from_ggd_forbidden=true`.

This deliberately does **not** merge the GGD 500 kbit/s finding into
the D2 CEM row, or treat `0x50` as a bus-speed selector.
Missing expected tables/columns are simply flagged as not present,
while ambiguous duplicate fixed table names or columns fail closed.

### Owner-only next schema experiment

Run a separately reviewed commit with exact-head successful Windows CI
inside the owner-controlled guest, using a **new** private output path
because the v1 report already exists:

```powershell
$python=(Get-Content 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
& $python '.\emulator\tools\audit_vida_carcom_schema_links.py' --folder 'E:\VirtualCar\VIDA-private' --output 'E:\VirtualCar\VIDA-private\p0-carcom-hw-schema-002.redacted.json'
```

Check the working directory points to the reviewed Git checkout. The
private report contains **no actual baud, hardware-setting values,
CAN IDs, ECU addresses, VIN or private column names**. Review
it privately before publishing even summary counts.
Only after actual schema confirmation should a separately reviewed,
bounded owner-local **aggregate query** investigate inherited hardware
settings for the two candidate profiles. A `folderLevel` shape,
or a fallback algorithm in a third-party port, does not establish
the original VIDA client selected that profile. Initial
`ReadVin=4` runs against `VehicleProfile.Empty`; lack of direct
target-profile `ScriptProfileMap` linkage must not on its own
be categorized as a failed VIN read.

### Empty-column exporter inventory gate (2026-11-10)

The legacy preflight now rejects any listed user table with zero catalog
columns, including unknown/private table names. A valid source table cannot
be silently represented as present with no column metadata. Synthetic test
20 exercises one missing T111_Service column inventory. The synthetic
fixture gives otherwise-hintless tables a private placeholder column so
source metadata is structurally realistic. The full cross-tool suite
passed 73/73 locally; original 2015A VIDA SQL Server remains untested.

**All work remains read-only, original outputs private, and
`B9FBFrameCount=0` unchanged. No physical J2534, GUI VIDA,
SecurityAccess, coding, ECU programming or Virtual Car Release.**

## Hardened exporter catalog gates (2026-11-10)

The older CarCom schema preflight now follows the same metadata-only safety
boundary as the unified VIDA analyzer already on `development`:

- Verify that each allowlisted `_vida_meta`, `_vida_tables` and
  `_vida_columns` catalog object is an ordinary table in SQLite `main`.
  A malicious or malformed `VIEW` or virtual/FTS table fails closed before
  the first exporter catalog `SELECT`.
- Verify actual zero-row cursor column names, not SQLite's permissive
  double-quoted-string fallback when a referenced column does not exist.
- Reject `-wal`, `-shm` and `-journal` sidecars before opening the
  exported file with `immutable=1`. Incomplete, uncheckpointed single-file
  exports must not be presented as a complete metadata inventory.

19/19 synthetic tests passed locally on Linux/Python 3.13.5, including four
new fail-closed tests. Combined with the current unified analyzer's 20 tests,
39/39 passed and `compileall` succeeded on the exact reviewed Git blobs.
This does **not** verify Windows Python 3.12, original VIDA 2015A SQL
Server/SQLite contents, ReadVin selection, VIN acceptance, hardware
J2534, or VMware CI against the eventual merged `development` SHA.

