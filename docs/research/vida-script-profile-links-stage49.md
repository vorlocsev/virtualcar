# Stage 49 | VIDA script-profile relationship boundaries

## Findings supported by static/open source evidence

Stage 47 found in the user's original VIDA 2015A DLLs that
VehicleAccess.IdentifyVehicle runs RunIdentifyVehicleScript with a temporarily
empty VehicleProfile, then consumes VehicleIdentityOutput. No direct B9FB
mapping or selected ECU is proven by that method alone.

Independent public research scripts show a relational path in *2014D*:
- carcom.dbo.T161_Profile.identifier is compared with
  DiagSwdlRepository.dbo.ScriptProfileMap.fkProfile;
- ScriptProfileMap.fkScript joins DiagSwdlRepository.dbo.Script.id;
- ScriptContent.fkScript joins Script.id, and fkLanguage differentiates content.

Sources:
- https://github.com/Tigo2000/Volvo-VIDA/blob/main/scripts/Export-ScriptsToXML.ps1
- https://github.com/spnda/volvo_vida_db/blob/main/sql/extract_scripts.ps1

The user's VIDA 2015A installation log showed DiagSwdlRepository *attached*
but does not verify the running database instance, schema, any XML content,
nor the model-specific identification script.

IMPORTANT: The empty-profile IdentifyVehicle entry point may select a global
identification script independently from model-specific ScriptProfileMap.
A mapped script after vehicle identification must not be mistaken for the
initial identity script without verified call-site and runtime evidence.

## Local metadata-only export, not full VIDA database

Use only with your own authorized local installation. The following SQL
statements are SELECT-only and intentionally omit binary XML, VIN, vehicle
configuration, SQL credentials, names and other fields.

Run them locally through an authorized SQL client, producing three small
CSV files with the *exact* header names and order below:

Script.csv
    SELECT CONVERT(nvarchar(80), id) AS id
    FROM [DiagSwdlRepository].[dbo].[Script];

ScriptProfileMap.csv
    SELECT CONVERT(nvarchar(80), fkProfile) AS fkProfile,
           CONVERT(nvarchar(80), fkScript) AS fkScript
    FROM [DiagSwdlRepository].[dbo].[ScriptProfileMap];

ScriptContent.csv
    SELECT CONVERT(nvarchar(80), fkScript) AS fkScript,
           CONVERT(nvarchar(80), fkLanguage) AS fkLanguage
    FROM [DiagSwdlRepository].[dbo].[ScriptContent];

Do NOT select XmlDataCompressed or export a complete table. Keep all CSV
files private and outside the repository. The tested query column names
come from the two public projects, not an independent live 2015A schema
inspection. If a column/table differs, stop rather than silently remapping.

## Tool

    python emulator/tools/audit_vida_script_profile_links.py PRIVATE-METADATA --output SAFE-profile-links.json

An OPTIONAL exact private profile selector can be added. The selector is not
written to the report:

    python emulator/tools/audit_vida_script_profile_links.py PRIVATE-METADATA --profile-key LOCAL_PROFILE_KEY --output SAFE-selected-profile.json

The tool reads only exact minimal header shapes, rejects malformed fields,
large files, directory symlinks, and attempts to overwrite existing reports.
It emits counts of scripts, mappings, languages, duplicate rows, broken
referential joins, and the optional profile's connected scripts. No original
row values or SQL/server/host paths are written. Use a local access-controlled
folder for any safe report; aggregate counts alone are not a proof of privacy.

Both metadata and profile IDs can still be sensitive when retained locally:
**do not upload the input CSV files, original XML, VINs or credentials**.

## Interpretation

- A script/profile mapping = possible database relationship only.
- A ScriptContent language row = content record exists, NOT successful XML parse.
- A profile's missing mapped content = incomplete exported metadata, not proof
  that VIDA would fail at runtime.
- An observed B9FB frame = transport, not script selection.
- An AddVIN token = lexical occurrence, not a reachable code path.
- Valid VIN/profile mapping and actual ECU inventory must be verified separately.
- A client UI outcome cannot be inferred from database metadata.

This stage does not change emulator C/J2534 behavior, add a CEM fixture, unlock
an ECU, or publish a release. The eight synthetic regression groups are in
emulator/tests/test_audit_vida_script_profile_links.py.

## Next real evidence gate

The exact VIDA 2015A RunIdentifyVehicleScript selection must be resolved
by analyzing the ScriptObjectProvider/IRunScriptService call chain and the
actual authorized SQL/XML scripts, then matching client-observed sequence
B9FB / B9F0 / identity / ECU identification in one read-only run.

## Optional Windows PowerShell metadata export

A new SELECT-only local helper performs the three exact queries without
dumping XmlDataCompressed, original scripts, VIN or credentials:

    & .\emulator\scripts\Export-VidaScriptMetadata.ps1 -ServerInstance 'YOUR_SQL_INSTANCE' -OutputDirectory 'C:\PRIVATE-VIDA-METADATA'

Only run on a trusted workstation where you have SQL SELECT authorization.
The Windows PowerShell SqlServer module (Invoke-Sqlcmd) is a prerequisite;
this helper never installs it. It refuses a destination under the Git repo
and will not overwrite an existing output directory. It does not validate
whether VIDA 2015A matches the 2014D column names: a query error requires
manual schema inspection rather than a fallback or altered SQL.

The emitted CSV contains internal script/profile keys and stays PRIVATE.
Only the audited count-only JSON output may be reviewed for further sharing.
