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

Subsequently, the owner executed an additional **metadata-only** query
against `DiagSwdlRepository.sys.procedures` with the same local
connection and reported exactly one visible name match:
`SchemaName=dbo`, `ProcedureName=GetScript`. This confirms
**visibility of `dbo.GetScript` in the real installed database**
for that SQL principal. A second read-only `sys.parameters` query
then confirmed exactly five input parameters in ordinal order:
`@scriptType varchar(50)`, `@profileList varchar(4000)`,
`@scriptId varchar(32)`, `@languageCode char(5)`, and
`@ecuType int` (SQL `max_length=4` bytes). All
`is_output=False`. Thus all five **names** match the original
`BizServices.ScriptRepository.DLL` call-site research, and
the installed SQL-side parameter types are now directly observed.
The `@scriptType` SQL parameter is text, **not integer**;
the `ReadVin=4` source enum alone does not prove whether the
wire-to-SQL value is `'4'`, `'ReadVin'`, or another string.

The ability to execute the procedure, its result selection, actual
`ReadVin=4` XML, accepted VIN and ECU inventory remain
**unverified**. No stored procedure executed or diagnostic
data extracted in these metadata-only queries.

An additional owner-side `sys.tables` / `sys.columns` catalog-only
query confirmed `dbo.ScriptType` has precisely two visible columns:
`Id int` (column 1, `max_length=4`) and
`Description varchar(50)` (column 2, `max_length=50`).
The `Description` type matches the declared maximum width of
`GetScript.@scriptType varchar(50)`, but equal SQL types **do not
prove the relationship**. A subsequent owner-authorized, narrowly
scoped **read-only data query** `SELECT Id, Description FROM
dbo.ScriptType WHERE Id = 4` returned exactly **`4 / CarStatus`**.
The original .NET `ValueObjects.ScriptType.ReadVin = 4` is therefore
**not an identity mapping to `dbo.ScriptType.Id = 4`**, at least in
this installed VIDA database. A subsequent owner-authorized, bounded
read-only table lookup (two `LIKE` filters on `Description`)
returned five rows, in ordinal `Id` order:

| SQL `dbo.ScriptType.Id` | `Description` |
|---:|---|
| 3 | `EcuIdentification` |
| 7 | `ReadVin` |
| 8 | `StatusIdentifier` |
| 23 | `EcuIdentificationHighSpeed` |
| 24 | `EcuIdentificationLowSpeed` |

**Now confirmed**: the installed SQL lookup row for `ReadVin`
is `Id = 7`, while `Id = 4` is `CarStatus`.
These observations do **not** establish how the original .NET enum
or `GetScript.@scriptType varchar(50)` is transformed and passed at
runtime; in particular, `'ReadVin'` is a plausible argument,
**not a confirmed runtime value**. The original caller research
refers to high/low identification scenario enum values 19 and 20;
the installed SQL rows 23 and 24 are distinct IDs and should
not be conflated with the source enum or asserted to be an
identity mapping. No procedure executed, script XML or VIN/ECU
data was read. Next gate: inspect the exact original caller's
string conversion / SQL binding, or a separately authorized
read-only live client trace, **before** changing emulator replies.

### Installed GetScript dependency-name evidence

The owner then queried **only**
`DiagSwdlRepository.sys.sql_expression_dependencies` for
`referencing_id = OBJECT_ID(N'dbo.GetScript', N'P')`, filtered
to four known object names. Four distinct names were returned
with an **empty `referenced_schema_name`** field:

- `Script`
- `ScriptContent`
- `scriptprofilemap` (case preserved exactly as returned)
- `scriptType` (case preserved exactly as returned)

This demonstrates stored dependency metadata on those four names,
not actual read/execution behavior of `GetScript`, and **not**
that all four resolve to `dbo`. Per Microsoft
[`sys.sql_expression_dependencies` documentation](https://learn.microsoft.com/en-us/sql/relational-databases/system-catalog-views/sys-sql-expression-dependencies-transact-sql),
an unqualified reference in a non-schema-bound object may report
a `NULL` referenced schema; `referenced_id` can also be `NULL`
if unresolved. Case differences in recorded names must not be
silently normalized into proof of identical objects.

The owner subsequently completed this second, metadata-only gate:
all four references resolved to concrete `dbo` tables:

| Name in procedure definition | Resolved schema/object | Local `referenced_id` | Caller-dependent | Ambiguous |
|---|---|---:|---|---|
| `Script` | `dbo.Script` | 288720081 | false | false |
| `ScriptContent` | `dbo.ScriptContent` | 685245496 | false | false |
| `scriptprofilemap` | `dbo.ScriptProfileMap` | 580197117 | false | false |
| `scriptType` | `dbo.ScriptType` | 256719967 | false | false |

SQL Server `OBJECT_SCHEMA_NAME(referenced_id)` and
`OBJECT_NAME(referenced_id)` returned the resolved names.
These object IDs are **local database metadata**, not stable
cross-installation identifiers; do not embed them in the emulator.
`is_caller_dependent=0` and `is_ambiguous=0` constrain
reference resolution only. They do not prove all four tables are
read on the `ReadVin` branch or that the requested script exists.

**Next bounded catalog-only gate:** inspect `sys.columns`
for the four resolved tables to identify candidate relational
keys and script-type columns, optionally followed by
`sys.foreign_key_columns` for recorded relationships.
Do not fetch `ScriptContent` rows or compressed XML and do
not execute `GetScript` as part of the metadata audit.
Actual runtime script selection and client identity acceptance
remain unknown.

### Owner-verified four-table catalog columns (VIDA 2015A)

The owner ran a **catalog-only** query joining `sys.tables`,
`sys.schemas`, `sys.columns` on the authorized installed
`DiagSwdlRepository`, filtering four dbo objects:

| Table | Column | SQL type | Max length | Nullable |
|---|---|---|---:|---|
| `Script` | `Id` | `char` | 16 | no |
| `Script` | `fkScriptType` | `int` | 4 | no |
| `ScriptContent` | `fkScript` | `char` | 16 | no |
| `ScriptContent` | `fkLanguage` | `int` | 4 | no |
| `ScriptContent` | `DisplayText` | `nvarchar` | 512 | no |
| `ScriptContent` | `XmlDataCompressed` | `image` | 16 | yes |
| `ScriptContent` | `checksum` | `nvarchar` | 200 | yes |
| `ScriptProfileMap` | `fkScript` | `char` | 16 | no |
| `ScriptProfileMap` | `fkProfile` | `char` | 32 | no |
| `ScriptType` | `Id` | `int` | 4 | no |
| `ScriptType` | `Description` | `varchar` | 50 | no |

`ScriptContent.column_id` skipped `3` in this installation's
output. A gap in column IDs does not establish a readable missing
column. SQL `image` metadata `max_length=16` must **not**
be interpreted as the compressed script payload size.
No XML bytes, display text, checksums, script IDs, profile IDs,
language rows, real VIN or ECU payload was retrieved.

Possible relationships: `Script.fkScriptType -> ScriptType.Id`,
`ScriptContent.fkScript -> Script.Id`, and
`ScriptProfileMap.fkScript -> Script.Id` because their names
and types align. These are **inferences**, not verified foreign
key constraints. `ScriptType.Id=7 -> ReadVin` is already
confirmed independently. The owner subsequently ran the
bounded **read-only aggregate** SQL query
`SELECT COUNT_BIG(*) AS ReadVinScriptCount FROM dbo.Script WHERE fkScriptType = 7;`
and observed **`ReadVinScriptCount = 1`** on the installed VIDA 2015A
instance. This confirms exactly one `Script` row of the SQL
`ReadVin` type in that installation; it does **not** reveal its
`Script.Id`, whether `ScriptContent` or profile mappings are present,
or which script `GetScript` returns in a real VIDA session.

The owner's subsequent read-only aggregate-only query returned
**ContentRows=17**, **LanguageVariants=17** (distinct `fkLanguage`
values across those 17 rows), and **ProfileMappings=1** for the
single SQL `ReadVin` script. These results establish stored
associated records, **not** valid or nonempty `XmlDataCompressed`
data, an XC90-specific profile or an effective runtime selection.
No language identifiers, script/profile identifiers, VIN or XML
bytes were returned.

The owner then ran the next **aggregate-only, read-only**
check using `XmlDataCompressed IS NOT NULL`,
`DATALENGTH(XmlDataCompressed)>0` and distinct
`fkLanguage` across the SQL `ReadVin` script. The four
returned values are: `ContentRows=17`,
`NonNullXmlRows=17`, `NonEmptyXmlRows=17`,
`LanguagesWithContent=17`. **All 17 content rows have a
non-NULL, nonempty binary payload**, but this is not a
successful decompression or validation of XML syntax and
does not establish any specific XC90-compatible requests.

The owner subsequently completed this **format-only SQL** gate:
all **17 of 17** payloads start with the ZIP local-file-header
magic bytes `0x504B0304` (SQL-derived classification `ZIP`).
The aggregate binary lengths range from **2603** to **2604**
bytes across the 17 language entries. These are on-disk
compressed-container lengths, not decompressed XML sizes.
This signature suggests ZIP but **does not yet establish**
that the central directory parses, that an XML entry exists,
or that any content is valid or applicable to XC90 V8.

The owner successfully carried out this **local-only ZIP read-only
in-memory** validation for the first language variant of the SQL
`ReadVin` script. The `System.IO.Compression.ZipArchive` Read
constructor succeeded and the central directory was readable:
`ZipStructureReadable=True`, `ZipBytes=2603`, `EntryCount=1`,
`DeclaredUnpackedBytes=17964`. The other 16 ZIP payloads were
not structurally opened in this test. The declared size comes
from ZIP metadata; **actual decompression, CRC, XML wellformedness,
script selection and XC90 VIN/ECU acceptance remain unverified**.

The owner then completed this local-only read-only
validation of the **same single-language** ZIP entry using
`ZipArchiveEntry.Open()` and an explicit 1 MiB limit.
Observed values: `DecompressionCompleted=True`,
`ActualUnpackedBytes=17964`, `DeclaredUnpackedBytes=17964`,
`LengthMatches=True`, and `XmlWellFormed=True`.
The .NET `XmlReader` had `DtdProcessing=Prohibit`,
`XmlResolver=$null` and a document size ceiling.
This establishes a successful full entry stream read and
well-formed XML **for one language variant only**.
It is not an independent archive CRC check, XML schema
validation, interpretation of diagnostic commands,
execution of SQL `GetScript`, or a VIDA-accepted
VIN/ECU identification.

The owner then ran a **local-only in-memory** full sweep of
all 17 SQL `ReadVin` ZIP language variants. The loop imposed
1 MiB size limits, required exactly one ZIP entry, read the
entry stream to completion, checked its declared and actual
uncompressed lengths match, and parsed with `XmlReader`
(`DtdProcessing=Prohibit`, null `XmlResolver`, bounded chars).
Reported aggregate values:
`TotalVariants=17`, `ValidZipXmlVariants=17`,
`FailedVariants=0`, `MinDecodedBytes=17964`,
`MaxDecodedBytes=17964`. This confirms all 17 variants are
readable ZIP streams containing well-formed XML with equal
uncompressed **lengths**, but **does not prove byte equality,
equivalent XML structure, schema validity, successful CRC
verification, or VIDA/ECU operational compatibility**.
No XML, diagnostics, real VIN or script/profile IDs were
exported; original SQL `GetScript` was not executed.

The owner then conducted an **in-memory-only** SHA-256
comparison of the 17 **decompressed** XML byte streams and
of a separately derived structural signature. Results:
`TotalVariants=17`, `UniqueXmlPayloads=17`,
`UniqueXmlStructures=1`. Every XML differs in bytes, but
all share the same ordering/depth of element start/end nodes,
namespace/local names, empty-element flag and sorted attribute
**names** in the owner's comparison. The comparison
**excludes text nodes and all attribute values**;
therefore it cannot establish translation-only differences
or diagnostic parameter/logic equivalence. The previous
read-only validation confirmed well-formedness and a byte
length of 17964 for each variant. No XML content, hashes,
script/profile/language IDs or VIN were exported.

The owner completed this bounded local-only structural check
for **one** of the 17 SQL `ReadVin` XML variants. The result:
`RootElement=script`, `ElementCount=182`,
`AttributeCount=764`, `MaxElementDepth=6`,
`XmlWellFormed=True`. These are observed counts for one
variant. Because the previous structural signature matches
across all 17 XMLs, the same counts and depths are
**expected** for the rest, but have not been individually
reported by this specific counting step. The study has
not exported element text, attribute values, original XML,
private binary or real VIN/ECU frames.

The owner has completed the root-immediate-child
catalog-free, in-memory-only gate for one local `ReadVin`
XML variant. `XmlReader.Depth=1` yielded **two** element
names and counts: `title: 1` and `content: 1`.
The root-level sketch is therefore `script -> {title, content}`.
The separate single-line PowerShell enumeration confirmed
both items explicitly; an earlier short operator response
`1/1` must not be interpreted as *one* child overall.
Names suggest a heading and a main content area, but this
is only a structural inference, **not an analysis of values
or actual VIDA script execution**.

The owner next inspected immediate children of `content`
using the same local in-memory, DTD-disabled read-only XML
pass. The returned `XmlReader.Depth=2` element names and
counts are **`handlers: 1`**, **`nodes: 1`**. Combined
with the previous observation the verified XML skeleton is
`script` containing `title` and `content`, and `content`
containing `handlers` and `nodes`. **No values, text,
attribute contents or diagnostic command data were
returned.** It is plausible from names that `handlers`
contains event/response-handling constructs while `nodes`
contains execution nodes, but neither relationship is
established by the XML naming alone.

The owner completed the next local in-memory read-only
XML structural pass using `XmlReader.Depth=3`. Under the
single `content/handlers` element, it returned
**`eventhandler` = 27** and **`propertyhandler` = 6**;
under `content/nodes` it returned **`node` = 14**.
This counts **47 direct elements** at depth 3 across these
sections. It is **not** evidence that the runtime executes
47 actions, that every node targets an ECU, or that any
particular response is expected. Nothing below depth 3,
including parameter/attribute values, event names, transport
IDs, J2534 requests, XML bodies, VIN or ECU data was emitted.

The owner completed the `XmlReader.Depth=4` local-only
metadata gate twice, with identical aggregate output:
`handlers/eventhandler/call = 27`,
`handlers/propertyhandler/set = 6`,
`nodes/node/extension = 12`, and
`nodes/node/property = 70`.
That is **115** XML elements at depth 4, not 115
confirmed diagnostic commands or requests. Combined with
previously measured depths 0–3 (`1 + 2 + 2 + 47`),
**167** of the measured **182** XML elements are accounted
for; **15** remain at depths 5–6. Terms `call`, `set`,
`extension`, and `property` are element names only:
we have NOT seen values, function bindings, original
script instructions, message IDs, VIN or ECU frames.

The owner completed the depths 5 and 6 XML structural
count for **one** previously loaded local `ReadVin` ZIP:
`Depth=5: get = 3, parameter = 3`, and
`Depth=6: getbyid = 3, getbyname = 6`. Total deeper
XML elements = **15** (`DeepElementsTotal=15`). The
complete per-depth element count is now **1, 2, 2, 47,
115, 6, 9** for depths **0–6**, summing to **182**,
consistent with the previously reported `ElementCount=182`,
`AttributeCount=764`, `MaxElementDepth=6`.
No XML text, attribute values, script code, ECU message bytes,
or original proprietary XML/binary were exported. Names
`get`, `parameter`, `getbyid`, `getbyname` do not establish
SQL calls, CAN requests, VIN read behavior, or real
execution.

**Completed structural metadata gate.** Shift focus away
from adding more XML tree counts to independent evidence:
1. Establish how the **original VIDA caller** obtains/selects
   SQL `GetScript` with runtime string `@scriptType` (SQL
   numeric ID 7 alone does not establish the caller string).
2. Obtain **redacted, read-only virtual J2534 trace** from
   an authorized offline VIDA-to-virtual-adapter session,
   verifying actual request routing/timeouts before any
   emulator replies are asserted as accepted.
3. Keep hard safety boundaries: no VIN or sensitive data,
   no proprietary complete script output, no `GetScript`
   execution without separate approval, no physical ECU
   writes, no positive emulator reply changes or releases.
Draft PR #172 remains a research/helper change, not
VIDA interoperability proof.




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
