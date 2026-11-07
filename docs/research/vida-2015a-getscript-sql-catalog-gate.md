# VIDA 2015A GetScript: catalog-only signature audit (P0)

Date: 2026-11-07. Scope: authorized **read-only** investigation of the
owner's original VIDA 2015A SQL metadata, **not** the execution or extraction
of the vehicle-identification script.

## What the original binary establishes

Static inspection of the owner's original, private
`BizServices.ScriptRepository.DLL` (SHA-256
`f046b5fa3c8d3487fc05aa1140ac3c4ef1880eef5251c8c46b1c3d73f45a6bca`)
identifies `ScriptProvider.GetFromDb` (MethodDef `0x0600001E`)
calling the stored-procedure helper with the literal name `GetScript`.

There are **eight SetParameter calls** but only **five unique names** in the
examined IL: `@scriptType`, `@profileList`, `@scriptId`,
`@languageCode`, `@ecuType`. Some setters are on alternative paths.
Eight calls **do not prove** eight SQL parameters. A CLR caller's names
do **not** independently establish the actual SQL procedure signature.

The original `ValueObjects.ScriptType` enum has `ReadVin=4`, and
`RunIdentifyVehicleScript` requests this type with an empty profile
via the five-argument `IScriptProvider.GetScript` path. Separately,
HS/LS ECU-identification scenarios use types 19 and 20.
See [the merged original IL note](vida-2015a-carcom-gateway-source-boundary.md).

The original binary does **not** provide the installed database schema,
procedure body, selected XML, VIN parser condition, completed client
connection, or accepted CEM identity. None of those has been claimed.

### Original IL: parameter-value branches (independent static check)

Further **local source-only** verification of the original unmodified
`BizServices.ScriptRepository.DLL`, SHA-256
`f046b5fa3c8d3487fc05aa1140ac3c4ef1880eef5251c8c46b1c3d73f45a6bca`,
and original `AppServices.Scripting.DLL`, SHA-256
`c5f092eddceac8b9eb583fb9a54536d482402a64797bd3597fd0cc6b387f3b7f`,
establishes these **conditional .NET caller branches**:

1. `RunIdentifyVehicleScript` uses script type **4** and a
   no-ECU-context engine; the five-argument `GetScript`
   calls `GetOneScriptFromDb`.
2. `GetFromDb` distinguishes a **null profile** from a
   supplied `VehicleProfile`: for a supplied profile it calls
   `get_Profiles` and `Strings.CommaSeparate`; the other
   branch supplies a null/DBNull-like SQL placeholder.
   `VehicleProfile.Empty` is an actual object in the
   identity call. Do **not** assume the resulting SQL string
   until its original runtime values are observed.
3. The *script ID* follows **nonempty/empty conditional
   branches**, rather than unconditionally being a literal
   empty string in the stored-procedure request.
4. ECU type uses a **-1 sentinel** versus an explicitly
   boxed integer. This influences SQL call parameters; it
   is **not** an ECU response value.
5. The SQL reader tests `HasRows`. With no rows it can
   raise `ScriptMissingException`; this is a *lookup
   failure*, not a negative CAN response, no-ignition state,
   or failed VIN semantic validation.
6. `GetOneScriptFromDb` returns the **first XML in the
   returned array**, or null if the array is empty.
   Consequently, a table count does **not** determine
   which XML the procedure returned first. Its `ORDER BY`
   or actual selection policy has **not been established**.
7. For returned binary script content, `GetZippedScriptXml`
   invokes SQL binary extraction, decompression and XML
   parsing. Whether the selected XML is the right
   `ReadVin` script is not proven by these method calls.

**Eight local IL consistency assertions: 8/8 PASS.** They verify
the two pinned DLL hashes, type-4 call, five-argument handoff,
first-or-null return, profile branch, script-ID branch,
ECU-type sentinel and SQL/ZIP/XML/exception path.
The assertions were executed **offline**; no VIDA process,
SQL connection, script body, vehicle or J2534 call was
executed. No original binary or IL body has been committed.

These findings describe the existing original **2014D-derived
offline VIDA 2015A** code path. A literal `VIDA2014D`
log release marker is not evidence of an unrelated or
incompatible diagnostic engine; see
[release/session provenance](vida-supplied-logs-2014d-session-provenance.md).

## New local tool: fixed metadata-only SQL SELECT

`emulator/scripts/Inspect-VidaGetScriptSchema.ps1` uses a trusted,
already-installed `Invoke-Sqlcmd` and *only* catalog views:

- `sys.procedures` / `sys.schemas`: whether **dbo.GetScript**
  is visible to the current SQL principal.
- `sys.parameters`: total visible parameters and presence of
  the five **fixed literal** names, with SQL types reduced to
  `text`, `integer`, `boolean`, `identifier`,
  `xml`, `other`, `unavailable`.
- `sys.tables` / `sys.schemas`: visibility of the four
  expected table names `Script`, `ScriptType`,
  `ScriptProfileMap`, `ScriptContent`.

It never selects table rows or queries `XmlDataCompressed`, and
**does not execute any stored procedure**, run a vehicle
diagnostic request, change a database, modify a driver, load original
VIDA DLLs or create a reply fixture. It does not emit server name,
credentials, paths, XML, query text, VIN, profile or script IDs.
It writes one new UTF-8 categorical JSON file **outside Git** using
exclusive `FileMode.CreateNew`.

### Authorized Windows invocation

From the project root in Windows PowerShell 5.1 or a compatible PowerShell:

```powershell
# Create this private folder yourself before running the helper.
# The example instance comes from the provided components.config.xml;
# verify it matches the actual authorized SQL instance.
& .\emulator\scripts\Inspect-VidaGetScriptSchema.ps1 `
    -ServerInstance '(local)\VIDA' `
    -OutputFile 'C:\VIDA-private\GetScript-catalog-01.json'
```

### Local VIDA SQL certificate trust (explicit opt-in)

On the owner's separate VIDA 2015A Windows 11 LTSC machine, the SQL
named instance is `.\VIDA`: `MSSQL$VIDA` and `SQLBrowser`
were running. The owner's interactive, read-only
`Invoke-Sqlcmd -TrustServerCertificate` returned
`Connected=1`, and the `DiagSwdlRepository` database
was `ONLINE` with `HAS_DBACCESS=1`. This verifies only the
SQL endpoint and database access; **GetScript catalog and
ReadVin execution have not been observed**.

Microsoft SqlServer module v22 defaults to checking the SQL TLS
certificate chain. A local SQL installation with an untrusted
self-signed certificate can reject login *after* successfully finding
the server. The helper now accepts the optional
`-TrustServerCertificate` switch for explicit, owner-authorized
**local** instances only (e.g. `.\VIDA`, `(local)\VIDA`,
`localhost\VIDA`). Without the switch, normal certificate
verification remains enabled. It rejects a nonlocal
`-ServerInstance` when the switch is supplied and never changes
the SQL Server TLS settings or system certificate trust store.

On the authorized VIDA host only, after copying the repository to
`C:\VirtualCar-VIDA` and creating a private directory:

```powershell
Set-ExecutionPolicy -Scope Process RemoteSigned -Force
Import-Module SqlServer -ErrorAction Stop
New-Item -ItemType Directory -Path 'C:\VIDA-private' -Force | Out-Null
& 'C:\VirtualCar-VIDA\emulator\scripts\Inspect-VidaGetScriptSchema.ps1' `
    -ServerInstance '.\VIDA' `
    -TrustServerCertificate `
    -OutputFile 'C:\VIDA-private\GetScript-catalog-01.json'
```

Use a **new filename** on each attempt, because the helper refuses to
overwrite existing private output. No raw script XML, SQL body, VIN
or database connection string should be uploaded to GitHub.
The helper still queries **catalog metadata only** and cannot
establish which `ReadVin=4` XML VIDA actually selects.

The SqlServer module must already be installed from a trusted source;
the helper does not install dependencies. Use existing authorized Windows
authentication, or pass a secure in-memory `PSCredential` if necessary.
Do **not** paste credentials or a real connection string into GitHub.

If the file or output folder already exists, or is inside the repository,
the helper stops without overwriting it. Review local outputs before
sharing. A metadata-only summary can still reveal properties of a
specific system; treat it as private until reviewed.

### Interpret results conservatively

`procedure_visibility=visible_dbo_GetScript` means that procedure
metadata is visible to this SQL account. It **does not prove** the
procedure works, the application calls it, or it returns a `ReadVin`
XML script. `not_visible_or_absent` explicitly combines lack
of permission and possible nonexistence; do not call it "missing".

Likewise, `table_metadata_visibility` describes only visibility,
not compatible data, populated scripts or server activity. The script
always outputs:

- `runtime_readvin_script_selected=unknown`
- `b9fb_to_vin_mapping=unknown`
- `xc90_v8_my2009_identity_accepted=unknown`
- `replay_approved=false`

Microsoft explicitly documents the permission-dependent behavior of SQL
catalog views: [metadata visibility configuration](https://learn.microsoft.com/en-us/sql/relational-databases/security/metadata-visibility-configuration).
The `dbo` schema remains a **working parameter-lookup assumption**.
The updated helper checks the procedure name across **all SQL-visible
schemas**, without exporting any schema names. It separately counts
visible non-`dbo` candidates and classifies a sole, ambiguous, or
missing/hidden result. Only the `dbo` candidate's **five parameters**
are classified; an alternate schema's signature is not inferred.
SQL default-schema resolution, app principal, permissions, selected
script and even whether any candidate is called by VIDA remain
**unknown**. Zero visible procedures still does not prove absence.

## Fix: prevent a false absence when GetScript uses a non-dbo schema

The original catalog helper only counted `dbo.GetScript`. That is
insufficient to distinguish *not present in dbo* from *not present in
any visible schema*. In an offline VIDA installation with modified
SQL ownership or an account whose default schema is not `dbo`, this
could send investigation in the wrong direction.

The updated **fixed, read-only SELECT** adds two catalog-only counts:
`AnySchemaProcedureVisibleCount` and
`NonDboProcedureVisibleCount`. It does not query procedure bodies
or table rows, returns no real schema names, and does not use
dynamic SQL, `EXEC`, or `sp_helptext`.

The JSON includes:

- `visible_getscript_any_schema_count`: all procedures named
  `GetScript` visible to the current SQL principal.
- `visible_getscript_non_dbo_schema_count`: such visible
  procedures **outside** `dbo`.
- `getscript_schema_visibility_category`: one of
  `single_visible_dbo`,
  `multiple_visible_schemas_including_dbo`,
  `single_visible_non_dbo`,
  `multiple_visible_non_dbo_schemas`,
  `no_visible_getscript_or_insufficient_permissions`.
- `parameter_scope=dbo_GetScript_only_if_visible`:
  `@scriptType`, `@profileList`, `@scriptId`,
  `@languageCode`, `@ecuType` still describe
  **only** the visible `dbo` procedure. They **must not**
  be attributed to any discovered non-`dbo` procedure.

The helper also rejects contradictory aggregate counts.
A non-`dbo` candidate is **not** automatically the actual
procedure the VIDA application calls; SQL execution
context/default schema may select another object.
A zero count means **not visible or absent to this
SQL principal**, never proven database corruption.

Six new cross-platform source-safety regression groups
verify all-schema catalog-only selection, dbo-only parameter
scope, consistency guard, distinct ambiguity categories,
output privacy and no VIN acceptance promotion.
The pre-existing 8 tests (including an optional
**PowerShell syntax parse, without running the script**) remain.
Expected Python suite: **330**, pending exact-SHA
Windows VMware validation; no authorized live SQL
connection has been attempted during this step.

## Eight regression gates and limitations

Eight new cross-platform **source-level** Python tests check: fixed
catalog-only query, no procedure/DML/table-data query, exact five
expected parameter names, unknown-or-hidden reporting, no sensitive
identity fields, exclusive output guard, no false VIN/ECU acceptance
and explicit type-classification safeguards.

Local `python -m unittest discover` on the new eight tests:
**8/8 PASS**. These checks do **not** execute Windows PowerShell,
connect to SQL Server, validate output from a live database or
authenticate the real VIDA client. A full Windows VMware test on the
**exact feature SHA** is needed before code promotion.

## Next real evidence gate

1. Confirm whether `dbo.GetScript` and the five names/types are
   visible in the actual authorized VIDA 2015A instance.
2. If not visible, check principal permissions and actual schema
   **locally**, not by asserting database damage.
3. If visible, independently inspect the parameter metadata to
   understand how the client passes `ReadVin=4`; no SQL
   stored-procedure execution is needed for this step.
4. Only with a separately authorized **read-only** VIDA diagnostic run,
   establish whether the selected script requests CEM B9FB/B9F0/A6,
   whether it obtains a `VehicleIdentityOutput`, and whether
   VIN resolution/ECU identification succeed. Keep raw logs local.
5. No security access, CEM PIN, programming, coding, hardware bus
   transmissions, synthetic positive ECU replies or Virtual Car releases.

**Research-only**, no changes to C/J2534 emulation. This is not
proof of end-to-end VIDA compatibility with XC90 V8 MY2009.
