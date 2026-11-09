# P0: CarCom InitHw hardware edge aggregate (owner-local, read-only)

## Evidence that permits this stage

The owner supplied a redacted report from the already tested
`audit_vida_carcom_schema_links.py` v2 run on the nine private VIDA exports.
It showed **six of six hardware/init column shapes present**, including:
`T136_InitHw_Profile → T161_Profile`,
`T136_InitHw_Profile → T130_Init`,
`T131_InitValue → T130_Init`,
`T131_InitValue → T132_InitValueType`,
`T121_Config → T122_Protocol`, and
`T121_Config → T123_Bus`.
`hardware_init_value_column_shape_present=true` but
`hardware_init_profile_priority_verified=false` and
`d2_baud_from_original_data_verified=false`.

These are **names of columns**, not a source table join or a known D2
bus speed. A separately reported GGD CAN configuration at 500 kbit/s
does not authorize applying that speed to D2 CEM.

## New narrow aggregate auditor

`emulator/tools/audit_vida_carcom_inithw_aggregate.py` opens only the
owner's exported `CarCom.sqlite` **copy**, with
`mode=ro&immutable=1`, `PRAGMA query_only=ON`, explicit connection
close, and fixed bounded table/column allowlists. It validates the
original export's metadata identity and counts of exactly eight tables:

`T136_InitHw_Profile`, `T161_Profile`, `T130_Init`,
`T131_InitValue`, `T132_InitValueType`, `T121_Config`,
`T122_Protocol`, `T123_Bus`.

The six source-FK / target-PK equality joins produce only:
source count, NULL FK count, unresolved FK count, unique matches,
ambiguous matches and duplicate target-key-group count.
In a separate fixed section it counts only NULL versus non-NULL cells
for `T161_Profile.folderLevel`, `T131_InitValue.initValue`,
`T132_InitValueType.name`, and `T121_Config.busRate`.
No actual setting names, bus speed numbers, private profile/ECU IDs,
source rows, VIN, CAN/response bytes, XML, ZIP, BLOB, original SQL
definitions or private source paths are emitted.

Non-NULL `busRate` only indicates a source cell is populated. It
**does not identify the protocol to which that rate belongs**, a
selected target CEM, or the priority among inherited profile settings.
The report always sets:
`hardware_init_profile_priority_verified=false`,
`d2_baudrate_verified=false`,
`may_infer_d2_rate_from_ggd=false`,
`client_vin_accepted=false`, and `replay_approved=false`.

The analyzer rejects unexpected export identity, missing/ambiguous
physical tables or columns, export row-count mismatches and source
tables over its predeclared maximum. Output creation is exclusive,
and the input database remains unchanged. Every original path and
unknown table/column name is suppressed in CLI error output.

## Owner-controlled VM procedure

**Only after a matching Windows CI run passes and the code is reviewed.**
VIDA as a graphical application is **not installed** on this guest.

From the checked-out, verified `development` source on Windows,
the owner can execute this single PowerShell line (no multiline
backtick continuation):

```powershell
$py=(Get-Content 'E:\VirtualCar\Tools\python312.path' -Raw).Trim(); & $py 'C:\actions-runner\_work\virtualcar\virtualcar\emulator\tools\audit_vida_carcom_inithw_aggregate.py' --folder 'E:\VirtualCar\VIDA-private' --output 'E:\VirtualCar\VIDA-private\p0-carcom-inithw-joins-003.redacted.json'
```

Use a new, nonexisting output name if another owner-private report
already exists. Review JSON locally and send only the allowed
aggregate categories, not a database export or original configuration.
The exact-head Windows workflow's Python tests operate solely on
synthetic SQLite and do **not** query these private copies.

## Following gate

If all six joins are structurally and referentially valid, the
next step is a **different** owner-reviewed, profile-scoped read-only
classifier that:
1. selects the correct private XC90 V8 MY2009 profile candidates using
   independently verified model/year/engine criteria;
2. determines any inherited InitHw settings using the exact chosen
   profile hierarchy and verified original branch/priority semantics;
3. distinguishes actual per-config `busRate` and hardware initialization
   from transport routing and ECU response.

The public [2014D research port](https://github.com/spnda/volvo_vida_db/blob/e2f8ee165e373360d7f7fd0e80298f68c25bc07e/scripts/carcom.py)
contains a `get_hw_settings` profile/folderLevel rule. It is
**not proof** that the original owner 2015A-derived runtime would
select the same settings. Do not invent a D2 rate or import a real
CEM B9FB reply. `B9FBFrameCount=0`, main, PR #2, public releases
and ECU/adapter binaries remain unchanged.
