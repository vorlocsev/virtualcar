# Owner VIDA 2014D: original ReadVin ScriptType and GetScript SQL semantics

## Provenance

Owner supplied original owner-private 9-entry archive
\`VIDA-ReadVIN-GetScript-metadata.zip\`. ZIP CRC is intact;
original manifest and computed SHA-256 values agree:

| Original DLL | Bytes | SHA-256 |
|---|---:|---|
| ValueObjects.DLL | 159744 | F9F875183031B9553096D771F3F186B85D16256D63BDB4B49977EA0795BBB5C5 |
| BizServices.Scripting.DLL | 471040 | D93B61B7B7524942649FD534303735DD4390AF6FFEE848B82E91C8E47EB5E028 |

The ZIP contains SQL procedure definitions, four metadata CSVs,
these two exact DLLs, and a README. **All owner-original vendor
bytes and SQL procedure text remain owner-private** and have
NOT been copied into the repository. Nothing was executed against
the owner's live SQL by the assistant.

## Original enum (not a guess)

Original type
\`Vcc.Vida.DiagSwdl.ValueObjects.Scripting.ScriptType\`
in \`ValueObjects.DLL\`, TypeDef 96, inspected statically using
the original .NET Field/Constant metadata:
\`ReadDtc=1\`, \`ClearDtc=2\`,
\`EcuIdentification=3\`, **\`ReadVin=4\`**,
\`CarConfig=5\`, \`CarStatus=6\`,
\`ReadDtcHighSpeed=17\`, \`ReadDtcLowSpeed=18\`.

This definitively names the numeric \`ScriptType=4\` previously
observed in the IL of
\`RunScriptService.RunIdentifyVehicleScript\`.
A live row matching SQL \`ScriptType.Description='ReadVin'\`
has **not** been queried in the current ZIP; the ZIP contains only
the SQL table schema, stored procedure text and DLL enums.

## Confirmed original SQL procedure behavior

Original metadata:
\`DiagSwdlRepository.dbo.GetScript\`, created \`2004-05-04\`,
modified \`2014-10-07\`.

Parameters exactly as declared in live owner SQL:
\`@scriptType varchar(50)\`,
\`@profileList varchar(4000)\`,
\`@scriptId varchar(32)\`,
\`@languageCode char(5)\`,
\`@ecuType int\`.

The procedure resolves \`@languageId\` by \`Language.Code\`
and \`@scriptTypeId\` by \`ScriptType.Description\`,
then selects \`ScriptContent.XmlDataCompressed\`:

1. If \`@scriptId IS NOT NULL\`, returns matching script contents
   for the chosen language directly; no profile/type filtering
   is applied in this branch.
2. Otherwise, if \`@profileList IS NOT NULL\`, joins
   \`ScriptProfileMap\` and original
   \`GetValidProfilesForSelected(@profileList)\`, filters by
   ScriptType/Language, adds \`ScriptCarFunction.FunctionGroup\`
   when \`@ecuType IS NOT NULL\`, and orders by
   \`folderlevel DESC\`.
3. Otherwise (no scriptId and NULL profile list), chooses
   script content by ScriptType and Language **without a
   profile-map filter** and without explicit ordering.

The procedure selects compressed XML, not a sequence of literal
CAN frames. \`BizServices.ScriptRepository\` (prior owner evidence)
subsequently applies \`ZIP.DecompressString\` and loads XML.
The \`VehicleProfile.Empty\` value used in the previous original
\`VehicleAccess.IdentifyVehicle\` IL has **not** been proven to
serialize to SQL NULL; do not assume branch (3) is always selected.

The other original procedure \`GetSmartToolScript\` uses
\`SmartToolId\` and its own ScriptVariant/profile-map
selection; it does not establish a ReadVin invocation.

## Immediate next step and acceptance boundary

Owner-local read-only PowerShell extraction was created to
SELECT original \`ScriptType\`, \`Language\`,
\`Script\`/ \`ScriptContent\` and \`ScriptProfileMap\`
rows matching \`ReadVin\`; inspect the original SQL source
of \`GetValidProfilesForSelected\` without executing it;
and save exact compressed \`XmlDataCompressed\` bytes,
per-row SHA256 and original checksum values to an owner-private
directory. The script has **not been run in the owner's VM**.
Do not commit original content to GitHub.

Unproven: actual ScriptId(s), language mapping, original VIN XML,
the profile argument sent from an empty profile, selected ECU,
D2 B9FB / GGD 22 F190, on-wire CAN, VIDA runtime acceptance,
J2534 MS-CAN probing, physical J2534 and exact-head VMware CI.

PR remains Draft, no merge or release.


## Corrected empty-profile semantics from original Core / ScriptProvider IL
- Follow-up static analysis of the already owner-provided original `Core.DLL` found `VehicleProfile::.cctor` (MethodDef **648**): constructs the static `_empty` instance with a **single-element string[] containing literal `EMPTYPROFILE`** and condensed string **`EMPTYPROFILE`**. `VehicleProfile.get_Empty` (MethodDef **643**) returns that non-null singleton; `VehicleProfile.get_Profiles` (MethodDef **640**) returns its string array.
- Previously inspected original `AppServices.Scripting.DLL` `RunScriptService.RunIdentifyVehicleScript` (#113) passes **`VehicleProfile.get_Empty`** into `getScriptEngineNoEcuContext`. Original `BizServices.ScriptRepository.DLL` `ScriptProvider.GetFromDb` (#30), IL_00b9-00e4, sets `@profileList = DBNull.Value` **only when the profile argument is null**; otherwise it passes `VehicleProfile.get_Profiles()` through `Vcc.Vida.DiagSwdl.Util.Strings.CommaSeparate()` as `@profileList`.
- Therefore, the `ReadVin` call **does not use the null-profile branch merely because the application labels the profile "Empty"**. It supplies a non-null special profile, and likely `@profileList='EMPTYPROFILE'` (dependent on the exact `CommaSeparate` implementation). The original SQL procedure's profile-list branch invokes `GetValidProfilesForSelected(@profileList)`. Previous suspicion that null-profile SQL branch (3) was used for ReadVin was **an unproven hypothesis and should not be relied upon**.
- Next owner read-only SELECT explicitly checks original `ScriptProfileMap` for `fkProfile='EMPTYPROFILE'`, alongside all ReadVin mappings and the original function definition. No stored procedure/function execution, raw vendor bytes publication or runtime acceptance inferred.

