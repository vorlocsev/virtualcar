# VIDA 2015A GetScript: catalog-only signature audit (P0)

Date: 2026-11-07. Scope: authorized **read-only** investigation of the
owner's original VIDA 2015A SQL metadata, **not** the execution or extraction
of the vehicle-identification script.

## What the original binary establishes

Static inspection of the owner's original, private
\`BizServices.ScriptRepository.DLL\` (SHA-256
\`f046b5fa3c8d3487fc05aa1140ac3c4ef1880eef5251c8c46b1c3d73f45a6bca\`)
identifies \`ScriptProvider.GetFromDb\` (MethodDef \`0x0600001E\`)
calling the stored-procedure helper with the literal name \`GetScript\`.

There are **eight SetParameter calls** but only **five unique names** in the
examined IL: \`@scriptType\`, \`@profileList\`, \`@scriptId\`,
\`@languageCode\`, \`@ecuType\`. Some setters are on alternative paths.
Eight calls **do not prove** eight SQL parameters. A CLR caller's names
do **not** independently establish the actual SQL procedure signature.

The original \`ValueObjects.ScriptType\` enum has \`ReadVin=4\`, and
\`RunIdentifyVehicleScript\` requests this type with an empty profile
via the five-argument \`IScriptProvider.GetScript\` path. Separately,
HS/LS ECU-identification scenarios use types 19 and 20.
See [the merged original IL note](vida-2015a-carcom-gateway-source-boundary.md).

The original binary does **not** provide the installed database schema,
procedure body, selected XML, VIN parser condition, completed client
connection, or accepted CEM identity. None of those has been claimed.

## New local tool: fixed metadata-only SQL SELECT

\`emulator/scripts/Inspect-VidaGetScriptSchema.ps1\` uses a trusted,
already-installed \`Invoke-Sqlcmd\` and *only* catalog views:

- \`sys.procedures\` / \`sys.schemas\`: whether **dbo.GetScript**
  is visible to the current SQL principal.
- \`sys.parameters\`: total visible parameters and presence of
  the five **fixed literal** names, with SQL types reduced to
  \`text\`, \`integer\`, \`boolean\`, \`identifier\`,
  \`xml\`, \`other\`, \`unavailable\`.
- \`sys.tables\` / \`sys.schemas\`: visibility of the four
  expected table names \`Script\`, \`ScriptType\`,
  \`ScriptProfileMap\`, \`ScriptContent\`.

It never selects table rows or queries \`XmlDataCompressed\`, and
**does not execute any stored procedure**, run a vehicle
diagnostic request, change a database, modify a driver, load original
VIDA DLLs or create a reply fixture. It does not emit server name,
credentials, paths, XML, query text, VIN, profile or script IDs.
It writes one new UTF-8 categorical JSON file **outside Git** using
exclusive \`FileMode.CreateNew\`.

### Authorized Windows invocation

From the project root in Windows PowerShell 5.1 or a compatible PowerShell:

\`\`\`powershell
# Create this private folder yourself before running the helper.
# The example instance comes from the provided components.config.xml;
# verify it matches the actual authorized SQL instance.
& .\emulator\scripts\Inspect-VidaGetScriptSchema.ps1 \`
    -ServerInstance '(local)\VIDA' \`
    -OutputFile 'C:\VIDA-private\GetScript-catalog-01.json'
\`\`\`

The SqlServer module must already be installed from a trusted source;
the helper does not install dependencies. Use existing authorized Windows
authentication, or pass a secure in-memory \`PSCredential\` if necessary.
Do **not** paste credentials or a real connection string into GitHub.

If the file or output folder already exists, or is inside the repository,
the helper stops without overwriting it. Review local outputs before
sharing. A metadata-only summary can still reveal properties of a
specific system; treat it as private until reviewed.

### Interpret results conservatively

\`procedure_visibility=visible_dbo_GetScript\` means that procedure
metadata is visible to this SQL account. It **does not prove** the
procedure works, the application calls it, or it returns a \`ReadVin\`
XML script. \`not_visible_or_absent\` explicitly combines lack
of permission and possible nonexistence; do not call it "missing".

Likewise, \`table_metadata_visibility\` describes only visibility,
not compatible data, populated scripts or server activity. The script
always outputs:

- \`runtime_readvin_script_selected=unknown\`
- \`b9fb_to_vin_mapping=unknown\`
- \`xc90_v8_my2009_identity_accepted=unknown\`
- \`replay_approved=false\`

Microsoft explicitly documents the permission-dependent behavior of SQL
catalog views: [metadata visibility configuration](https://learn.microsoft.com/en-us/sql/relational-databases/security/metadata-visibility-configuration).
The observed \`dbo\` schema is a **working lookup assumption**;
an empty result is not proof no \`GetScript\` procedure exists under
another schema or with different casing/collation.

## Eight regression gates and limitations

Eight new cross-platform **source-level** Python tests check: fixed
catalog-only query, no procedure/DML/table-data query, exact five
expected parameter names, unknown-or-hidden reporting, no sensitive
identity fields, exclusive output guard, no false VIN/ECU acceptance
and explicit type-classification safeguards.

Local \`python -m unittest discover\` on the new eight tests:
**8/8 PASS**. These checks do **not** execute Windows PowerShell,
connect to SQL Server, validate output from a live database or
authenticate the real VIDA client. A full Windows VMware test on the
**exact feature SHA** is needed before code promotion.

## Next real evidence gate

1. Confirm whether \`dbo.GetScript\` and the five names/types are
   visible in the actual authorized VIDA 2015A instance.
2. If not visible, check principal permissions and actual schema
   **locally**, not by asserting database damage.
3. If visible, independently inspect the parameter metadata to
   understand how the client passes \`ReadVin=4\`; no SQL
   stored-procedure execution is needed for this step.
4. Only with a separately authorized **read-only** VIDA diagnostic run,
   establish whether the selected script requests CEM B9FB/B9F0/A6,
   whether it obtains a \`VehicleIdentityOutput\`, and whether
   VIN resolution/ECU identification succeed. Keep raw logs local.
5. No security access, CEM PIN, programming, coding, hardware bus
   transmissions, synthetic positive ECU replies or Virtual Car releases.

**Research-only**, no changes to C/J2534 emulation. This is not
proof of end-to-end VIDA compatibility with XC90 V8 MY2009.
