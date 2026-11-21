# P0 | VIDA local SQL catalog gate for ReadVin storage

Status: **read-only research**. No vehicle, ECU or VIN accepted by this work.

## Newly located original database files (owner's private Drive)

A *direct db folder listing*, not a guessed filename search, exposes:
- DiagSwdlRepository_Data.MDF (2,944,335,872 bytes) and DiagSwdlRepository_log.ldf (516,096 bytes).
- CarComRT_Data.MDF (1,822,294,016 bytes).
- DiceTiming_Data.MDF (3,407,872 bytes).

The original db_attach_log.txt includes "DiagSwdlRepository attached.",
after a replacement log-file creation. The original components.config.xml
configures ScriptProvider DataSource (local)\VIDA and DatabaseInstance
DiagSwdlRepository. The supplied WildFly server.log reports
LastInstalledBaseId: VIDA2014D in the 2014D-derived offline 2015A environment.

**Not established:** whether the Drive copy is bit-identical to the locally
attached SQL database, whether the SQL principal can see all objects,
whether an XC90 V8 MY2009 ReadVin=4 XML is stored, or which version
GetScript would return. No original MDF was copied or altered.

## Safe local discovery procedure

Run only against the owner's already authorized local SQL instance.
Use a trusted checkout of this branch and trusted preinstalled
PowerShell SqlServer module (Invoke-Sqlcmd). Neither tool installs
packages, starts services, runs VIDA or executes stored procedures.

~~~powershell
$repo = "C:\VirtualCar-research" # Replace with your checkout
$private = Join-Path $env:USERPROFILE 'VIDA-private'
New-Item -ItemType Directory -Path $private -Force | Out-Null
& "$repo\emulator\scripts\Inspect-VidaGetScriptSchema.ps1" -ServerInstance '(local)\VIDA' -OutputFile (Join-Path $private 'getscript-catalog-01.json')
& "$repo\emulator\scripts\Inspect-VidaReadVinStorageSchema.ps1" -ServerInstance '(local)\VIDA' -OutputFile (Join-Path $private 'readvin-storage-catalog-01.json')
~~~

Use new output filenames per run; keep reports outside GitHub.
Both scripts SELECT exclusively from SQL catalog views.
The new helper checks five literal names: Script, ScriptType,
ScriptProfileMap, ScriptContent, ScriptCarFunction.
It exports only bounded column names, normalized type categories,
byte lengths, and nullability; actual schema names, credentials, server
address, data rows, original XML, VIN, and CAN payloads are excluded.
Output is exclusive (CreateNew) and cannot be placed in repo.

A missing catalog item means **not_visible_or_absent**:
permissions may hide tables or procedures. A visible binary/XML
column is storage metadata, NOT a selected ReadVin=4 script.
The next stage needs the catalog report first. Do not guess
ScriptContent row layout or run arbitrary SQL/procedure calls.

## Regression / acceptance boundaries

Eight local synthetic static Python gates verify fixed catalog-only SQL,
literal table allowlist, bounded output, redaction, exclusive file
creation, no stored-procedure execution, and no VIN/replay promotion.
They do NOT execute PowerShell, SQL, VIDA, J2534, or CEM.

The SectorV P0 session had 11 B9FB requests and zero B9FB RX.
The original VIDA test F9FB string does not authorize a fabricated
XC90 V8 MY2009 response. Keep B9FBFrameCount=0 and StrictRouting
unchanged. No Virtual Car release or published binaries.
