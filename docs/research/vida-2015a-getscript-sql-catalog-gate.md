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

Owner then ran the SQL Server **static metadata-only** query
`sys.dm_exec_describe_first_result_set_for_object(OBJECT_ID(N'dbo.GetScript'),0)`
on the authorized installed VIDA instance, without executing
`GetScript`. The **first result set** was resolved as exactly
one visible column: `Ordinal=1`, `ColumnName=XmlDataCompressed`,
`SqlType=image`, `Nullable=True`, with no metadata error reported.
This is consistent with the `dbo.ScriptContent.XmlDataCompressed image`
storage column but does **not** establish which row, profile,
script type string or language the runtime procedure returns,
its execution result, or VIDA/J2534 compatibility.

The owner then ran the local-only **source classification**
probe against `sys.sql_modules` for `dbo.GetScript`
without emitting source. Output:
`DefinitionAvailable=True`, `ScriptTypeReferences=2`,
`DirectDescriptionComparison=True`,
`DirectIdComparison=False`, and
`ExplicitIntegerConversion=False`.
Regex matching of a direct `Description = @scriptType`
(or reverse) is positive. This is a **strong clue** that
`@scriptType varchar(50)` participates in a textual
Description comparison, consistent with the separate
SQL lookup label `ReadVin` (`dbo.ScriptType.Id=7`).
But the regex **does not prove** that this specific
Description belongs to `dbo.ScriptType`, is in executable
SQL rather than a comment, or that no indirect numeric
conversion exists elsewhere. `ScriptTypeReferences=2` also
includes the procedure declaration if present.
Therefore treat caller argument `ReadVin` as **candidate**,
not a verified client runtime parameter; do not conflate
SQL numeric `Id=7` and original application's numeric
enum value or `@scriptType` string.

**Next gate**: Verify the table/column relationship using
SQL metadata only, or move to authorized **offline**
VIDA-to-virtual-J2534 trace with redacted event types,
protocol IDs, timestamps, and response outcome, never VIN,
request bytes or proprietary script output. Do not execute
`GetScript`, change positive emulator replies or publish
Virtual Car releases.

Owner completed the static SQL **referenced-entities**
confirmation without invoking `dbo.GetScript`:
`sys.dm_sql_referenced_entities(N'dbo.GetScript', N'OBJECT')`
filtered on `dbo.ScriptType` returned
`ScriptTypeDependencyRows=3` and
`DescriptionDependencyRows=1`. This directly establishes
that SQL Server dependency metadata records at least one
reference to **`dbo.ScriptType.Description`** in
`dbo.GetScript`. Combined with the source-regex result
(`DirectDescriptionComparison=True`) it strongly supports,
but does NOT strictly prove, that the parameter is compared
against this same column in the active branch, nor that
VIDA supplies the candidate string `ReadVin` at runtime.
**No SQL execution, XML extraction or J2534 traffic.**

**Transition to J2534 evidence:** repository `main` README
says the Windows x86 current deliverable is a trace-only
J2534 proxy, not a full emulator; it forwards to an
owner-supplied `VirtualCarJ2534.dll` which is not in the
repository. `cmd/oneclick/main_windows.go` registers
`VirtualCar Trace VM dev26` in the **WOW6432** 32-bit
PassThruSupport.04.04 view and starts a specified SectorV
process with `VCAR_TRACE_REAL_DLL` and
`VCAR_TRACE_LOG_PATH` in that process environment.
**This OneClick workflow has not been validated for VIDA**
and may not correctly propagate environment through a
VIDA launcher or child process. Next safe operator-local
step is **read-only registry preflight** for that provider
and x86 DLL presence, without dumping `FunctionLibrary`
paths, writing registry entries, connecting to a physical
ECU or launching VIDA. Treat registration and DLL existence
as prerequisites, **not** J2534 API call or VIDA acceptance
proof. A subsequent real VIDA session needs separately
verified architecture, process environment and redacted
J2534 request/response outcome.

**Owner-local J2534 registration preflight, 2026-11-07:**
read-only Windows Registry inspection of
`HKLM\SOFTWARE\PassThruSupport.04.04\VirtualCar Trace VM dev26`
in both `Registry32` and `Registry64` yielded:
`ProviderRegistered=False`, `LibraryConfigured=False`,
`LibraryExists=False` **in both views**. This checks ONLY
this particular provider name. The library-exists result
is false because the provider did not specify a path;
**it does not establish that any DLL file is missing from
disk**, nor does it establish that there are no other
J2534 providers installed. No DLL was loaded, no
registration was changed, no VIDA/DiCE or ECU access.

**VIDA diagnostic-path caveat from Volvo documentation:**
Volvo's Vehicle Communication Tools guidance states that
VIDA supports DiCE and J2534, recommends DiCE for D2/GGD,
and that **J2534-1 cannot be used for diagnostics**;
its J2534-2 note focuses on HS/MS-CAN software download.
See https://www.volvospecialtools.com/index.cfm?event=info.dice
(Volvo Special Tools, `Vehicle Communication Tools`).
Therefore **do not equate VIDA J2534 listing with proven
D2 ReadVin diagnostic access through the generic x86
trace proxy**. Some vendors advertise VIDA-compatible
J2534 drivers, but that cannot establish support for our
unregistered generic proxy or original VIDA 2015A VIN
read workflow. A viable next step is a read-only inventory
of existing 32/64 J2534 registry providers by aggregate
counts (no paths/names) and a separate architecture-
compatibility/VIDA-tool-selection assessment before any
registration or execution. No `GetScript` execution,
physical device tests or emulator reply changes.

**Owner-local aggregate J2534 registry inventory, read-only:**
using Registry32 and Registry64 views of
`HKLM\SOFTWARE\PassThruSupport.04.04`:

| View | Providers | Configured libraries | Existing library files | CAN advertised | ISO15765 advertised |
|---|---:|---:|---:|---:|---:|
| Registry32 | 2 | 2 | 2 | 1 | 1 |
| Registry64 | 1 | 1 | 1 | 0 | 0 |

This establishes three **registry-view entries** with
three resolvable `FunctionLibrary` files across two views;
it does not establish three unique physical adapters or
three distinct DLLs. The same x86 registration might
advertise both CAN and ISO15765 or two distinct x86
registrations might advertise one each. Missing `CAN` and
`ISO15765` REG_DWORD markers in Registry64 do not prove a
provider cannot implement those protocols. Existing files
do not establish valid DLL architecture or functional
J2534 APIs, VIDA discovery or diagnostic compatibility.
The separately checked exact `VirtualCar Trace VM dev26`
provider was absent in both views. No registry changes or
vehicle I/O occurred. Next limited gate: identify provider
registry names and DLL **basenames** (no full paths),
per-provider capability flags, and file architecture using
read-only metadata. Do not register/launch/modify.

**Owner-local J2534 provider identity/PE audit, read-only:**
The three registry-view entries were mapped to actual
provider names, DLL basenames and PE header architectures:

| Registry view | Provider | DLL basename | PE Machine | CAN DWORD=1 | ISO15765 DWORD=1 |
|---|---|---|---|---|---|
| Registry32 | Drew Technologies Inc. - MongoosePro JLR | `monpj432.dll` | x86 | Yes | Yes |
| Registry32 | SETEK - DiCE | `TSDiCE32.dll` | x86 | No | No |
| Registry64 | SETEK - DiCE | `TSDiCE64.dll` | x64 | No | No |

This resolves the earlier CAN and ISO15765 aggregate flags
to **the same x86 MongoosePro JLR provider**. Both SETEK
DiCE entries are present with architecture-matching PE
headers, but their missing registry flags are not evidence
that the driver cannot perform CAN or diagnostics.
PE Machine validation establishes file architecture only,
not DLL loadability, J2534 export availability, VIDA tool
selection, or vehicle communication. The target
`VirtualCar Trace VM dev26` provider remains absent in
both views. No calls to VIDA, J2534 APIs, or hardware.

Next preferred read-only evidence: while VIDA is already
open and with **no physical DiCE/ECU connection**, inspect
whether a relevant process has loaded `TSDiCE32.dll`,
`TSDiCE64.dll`, or `monpj432.dll` using local process/module
metadata. Negative evidence is inconclusive because a DLL
may load only after communication begins; never infer
VIDA compatibility solely from installed J2534 registration.
Do not register the proxy or publish binaries.

**Owner-local passive VIDA process/module gate:**
At observation time, Windows `Get-Process` name filter
`vida|dice|vct` found `DevCtrlSV3` (PID 4644) and
`VidaMonitor` (PID 12080). System-wide `tasklist /M`
reported **no loaded process** matching any of
`TSDiCE32.dll`, `TSDiCE64.dll`, `monpj432.dll` at that
time. This is strictly a snapshot; it does NOT establish
whether the full VIDA UI or diagnostic module was active,
whether a diagnostic adapter was selected, or whether one
of these DLLs will load upon communication. A system-wide
module-name scan also cannot rule out a differently named
DiCE communication stack. The owner subsequently inspected EXE version resources,
PE headers and service-PID matching locally, without
emitting paths or command lines. Definitive host results:
- `DevCtrlSV3.exe` PID 4644: **x64**, Company `Panasonic
  Corporation`, Product/Description `Device Control
  Utility Service`, direct Win32_Service association
  `DevCtrlSV3`. This is **not** a Volvo VIDA process; remove
  it from the presumed VIDA device stack.
- `VidaMonitor.exe` PID 12080: **x86**, Company
  `Volvo Cars Corporation`, Product `VIDA`, Description
  `VidaMonitor`, **no direct Win32_Service PID match**.
  This proves a Volvo-supplied 32-bit monitor process was
  running, NOT that VIDA's diagnostic UI had selected
  any DiCE/J2534 transport.
The preceding `tasklist /M` negative results for
`TSDiCE32.dll`, `TSDiCE64.dll` and `monpj432.dll` remain
a point-in-time snapshot. No driver DLL observed loaded.
No process start/stop, hardware communication, DLL
injection/load, or adapter registry modification.

**Owner-local extended VIDA running-process inventory:**
A passive `Win32_Process` enumeration with on-disk EXE
`FileVersionInfo.CompanyName` matching Volvo, `ProductName`
matching VIDA, or EXE filename matching VIDA/DiCE found
**only** `VidaMonitor.exe`, PID `12080`, Company `Volvo
Cars Corporation`, Product `VIDA`, `HasWindow=False`
(`MainWindowHandle==0`). This corroborates the prior
identification of the **32-bit VIDA monitor** but DOES NOT
prove that no VIDA client or web UI is running: browsers,
IIS workers and generic processes can fall outside this
filter, and inaccessible EXE metadata may be omitted.
No user program or diagnostic driver was started, no
module injection, no registry writes, no hardware I/O.

**Owner-local read-only Windows service and web-host inventory**
confirmed:
- `MSSQL$VIDA` Running / Auto / PID 4952;
- `SQLAgent$VIDA` Stopped / Manual / PID 0;
- `SQLTELEMETRY$VIDA` Running / Auto / PID 11056.
No other names matched the scoped VIDA/Volvo/DiCE/IIS
(`W3SVC`, `WAS`) service filter. In the specified web-host
process-name list, the observed groups were
`iexplore.exe` 2, `java.exe` 1, `msedge.exe` 13,
`msedgewebview2.exe` 6. The output did **not** report
`w3wp.exe`, `httpd.exe`, `javaw.exe`, `tomcat.exe`,
`chrome.exe`, or `firefox.exe`. This is an idle-time
snapshot, not proof that an HTTP server is absent; process
names can differ. Neither one Java process nor two IE
processes proves association with the VIDA diagnostic UI.
The running VIDA SQL instance is consistent with prior
read-only `DiagSwdlRepository` SQL queries. A stopped
manual SQLAgent is not inherently a fault.

**Owner-local passive Java/IE/VIDA process ancestry and PE check:**
- `iexplore.exe` PID **2624**, parent `iexplore.exe`,
  PE **x86**, Microsoft Internet Explorer product,
  `VIDAHint=False`, no Windows service association.
- `iexplore.exe` PID **4216**, parent `msedge.exe`,
  PE **x64**, Microsoft Internet Explorer product,
  `VIDAHint=False`, no Windows service association.
- `java.exe` PID **4324**, parent `cmd.exe`,
  PE **x64**, Company `Oracle Corporation`, Product
  `Java(TM) Platform SE 21.0.10`, `VIDAHint=True`
  (a local regex match for `vida|volvo` in its command
  line; original command line NOT exported), no direct
  Windows service association.
- `VidaMonitor.exe` PID **12080**, parent `explorer.exe`,
  PE **x86**, Company `Volvo Cars Corporation`,
  Product `VIDA`, `VIDAHint=True`, no direct
  Windows service association.
All were gathered by inspecting metadata of already
running processes, not by launching any application.
A Java process with a VIDA/Volvo **command-line hint**
is a **candidate** component but NOT proof of diagnostic
workload, J2534 provider selection, or connection to
installed VIDA. Browser processes also remain unassigned.
The owner pasted the script a second time with no second
result table; treat only the first completed output as
evidence.

**Owner-local Java process ancestry confirmed** by
passive `Win32_Process` metadata walk:
`explorer.exe` PID **6792** -> `VidaMonitor.exe`
PID **12080** -> `cmd.exe` PID **12228** ->
`java.exe` PID **4324**. `java.exe` reported
`VIDA=True`, `Jar=True`, `Classpath=False`,
`ServerHint=False` for private command-line tests
(`vida|volvo`, `-jar`, `-cp`/`-classpath`, and
`tomcat|jetty|spring`). `cmd.exe` had all four
hints False; `VidaMonitor.exe` had VIDA True and other
hints False; `explorer.exe` had all False. Together
with earlier PE inspections: VIDA monitor is Volvo
x86, Java binary is Oracle Java 21.0.10 x64.

**Strongest finding:** Java was actually launched as a
descendant of Volvo's VIDA monitor, so it is not just an
unrelated JVM whose command line happens to mention VIDA.
This still does **not** identify the JAR's function, a
VIDA diagnostic client, any J2534 API usage, or whether
DiCE DLLs are involved. No raw command line, JAR content,
full path, URL or secrets were returned or published.

**Owner-local `-jar` argument basename inspection:**
`java.exe` PID **4324** is executing an existing absolute
`.jar` named **`jboss-modules.jar`**; `FileExists=True`,
`NameMentionsVIDA=False`. This is consistent with
**JBoss Modules**, a modular Java classloading/boot
mechanism also used by **WildFly/JBoss AS**, but does
**not** prove which application module actually starts,
whether the process is a WildFly/JBoss server, or whether
it handles VIDA diagnostics/DiCE. The prior ancestry
`VidaMonitor.exe` -> `cmd.exe` -> `java.exe` and
`VIDAHint=True`, `Jar=True` are already established.
JBoss Modules manual: https://jboss-modules.github.io/jboss-modules/manual/
WildFly example/guide:
https://docs.wildfly.org/24/Developer_Guide.html

**Owner-local passive WildFly launcher and listener check:**
The existing `java.exe` PID **4324** was still present
with original parent PID **12228**. Private command-line
flag checks yielded: `JBossModules=True`,
`ModulePathArgument=True`, `WildFlyStandalone=True`
(`org.jboss.as.standalone`), `JBossServerModule=False`,
`JBossHomeConfigured=True` (`-Djboss.home.dir=`).
`Get-NetTCPConnection` returned **3 listening TCP sockets
owned by that Java PID, all 3 on loopback addresses**
(`127.0.0.1` / `::1`). No full command line, JAR path,
addresses/port numbers or response data were printed.

This is strong evidence of **a standalone-mode WildFly/JBoss
runtime launched from the VIDA monitor ancestry**.
It is NOT evidence that the actual Volvo diagnostic
components are deployed, that any VIDA browser is currently
communicating with the server, or that Java loads DiCE/J2534
DLLs. The `JBossServerModule=False` exact marker does not
contradict the positive `WildFlyStandalone=True` launcher
marker. The 3 listeners are point-in-time loopback-only
sockets, not proven HTTP endpoints.

**Owner-local Java-loopback client connection snapshot:**
The original `java.exe` PID **4324**, parent PID **12228**,
and `org.jboss.as.standalone` command-line marker were
reconfirmed. `Get-NetTCPConnection` returned
`LoopbackListeners=3`, `EstablishedClients=0`; the script
printed `NoEstablishedClientsInSnapshot`. This is **not**
a failure or proof of absent VIDA browser connectivity:
connections may be idle or too short-lived to appear in
a single instantaneous query, and the exact service role
and listener types remain unidentified. No loopback
HTTP requests were sent; no addresses/ports, command lines,
URLs, secrets or ECU traffic were disclosed.

**Owner-local read-only WildFly deployment-folder check:**
On the verified Java x64 PID **4324** (parent 12228 and
`org.jboss.as.standalone` launcher hint),
`JBossHomeFound=True`, `ExplicitBaseFound=False`,
`BaseResolved=True`, `BaseAbsolute=True` and
`DeploymentDirectoryExists=True`. Within the default
`jboss.home.dir/standalone/deployments`, the operator
observed **3 files**, **2 directories**, with counts
`WAR=0`, `EAR=0`, `JAR=0`, `.deployed=2`,
`.failed=0`, `.isdeploying=0` among the immediate files.
Two `.deployed` scanner markers strongly suggest **two
successfully deployed items**, potentially corresponding
to two exploded directories, but no name correspondence,
application content or diagnostic functionality has been
verified. The absence of `.war`/`.ear` archives in the
root does **not** rule out exploded deployments.

A subsequent attempted rerun submitted `if` and `else`
as separate commands and returned PowerShell
`CommandNotFoundException` for `else`; that is a CLI
parsing artifact and does not invalidate the completed
first output. An earlier untrusted scan was invalidated
by the Windows PowerShell 5.1 reserved `$HOME` variable;
the new successful output uses `$jbossHomeDir`.

**Owner-local exploded EAR deployment evidence:**
A further no-write audit confirmed **2** immediate
directories under the same WildFly `standalone/deployments`
folder, **2** `.deployed` marker files and
`UnmatchedMarkers=0`. Both enumerated directories are
**`ExplodedEAR`** (directory name extension `.ear`),
**`MarkedDeployed=True`** with a matching marker,
**`HasMETAINF=True`**, **`HasWEBINF=False`**. The latter
is normal at EAR root; web `WEB-INF` belongs inside any
nested WAR modules. This establishes a consistent
scanner-marker-to-exploded-EAR-directory mapping but does
NOT prove actual currently healthy runtime deployments,
which modules they contain, VIDA diagnostic functions,
J2534/DiCE integration or GetScript caller string.
No deployment names/paths, application content, credentials
or VIN were printed or exported. No writes, hardware I/O,
process starts, registry changes or emulator releases.

**Owner-local EAR module declaration audit (read-only):**
The two exploded EARs each have a `META-INF/application.xml`
that was **successfully parsed** with DTD processing
prohibited and the XML resolver disabled. Results in
alphabetic directory order:

| EAR slot | Deployed marker | Directories | Files | Exploded WAR directories | WAR archives | JAR archives | application.xml | Web modules | EJB modules | Java modules | Connector modules |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 1 | True | 2 | 0 | 1 | 0 | 0 | Parsed | 1 | 0 | 0 | 0 |
| 2 | True | 3 | 1 | 1 | 0 | 1 | Parsed | 1 | 1 | 0 | 0 |

These are **declared XML module counts and immediate
filesystem children**, not runtime module health. EAR slot
2 includes both a web and EJB module declaration and one
root JAR file, making it a candidate for the backend role,
NOT proof of ECU diagnostics, `ReadVin`, `GetScript` or
DiCE/J2534 traffic. Both directories contain an exploded
WAR. Actual application/deployment names, XML contents,
paths and potentially sensitive parameters were not
exported or published. No J2534 calls, ECU access,
registry changes or emulator binaries.

**Owner-local exploded WAR `WEB-INF/web.xml` structural audit:**
Both EARs contain one exploded `.war` directory with
`WEB-INF` present and a **successfully parsed**
`WEB-INF/web.xml` (XML reader with DTD prohibited, external
resolver disabled and 1 MiB document cap). Only direct
`web-app` child element **counts** were exported:

| EAR slot / WAR slot | Servlets | Servlet mappings | Filters | Filter mappings | Listeners | WEB-INF | web.xml |
|---|---:|---:|---:|---:|---:|---|---|
| 1 / 1 | 1 | 1 | 0 | 0 | 0 | True | Parsed |
| 2 / 1 | 15 | 18 | 2 | 3 | 0 | True | Parsed |

The second WAR has more descriptor-declared request
handlers/filter mappings, and its enclosing EAR also
declares an EJB module (prior finding). This makes EAR
slot 2 a useful **candidate for further passive metadata
analysis**, not proof of diagnosis, SQL `ReadVin` calls,
CAN communication or usage of DiCE/J2534. Multiple servlet
mappings per servlet and multiple filter mappings are
legitimate; zero descriptor listener declarations do not
exclude annotation/programmatic registrations. No
servlet names, URL patterns, class names, XML contents,
credentials or VIN were exported. No active requests,
process changes, ECU I/O or Virtual Car releases.

**Owner-local EJB archive identity and ZIP metadata (read-only):**
The exploded EAR in sorted slot **2** has exactly one
EJB module declaration in its previously securely parsed
`META-INF/application.xml`, and exactly one direct-child
`.jar`. The archive **basename matches the declaration**
(`EJBJarMatchesDescriptor=True`). `JARReadable=True`; its
ZIP central directory contains **374 entries, 325 `.class`,
7 `.xml`, 2 `.properties`**. A file with exact entry name
`META-INF/ejb-jar.xml` is present. Regex checks against
`.class` entry **names only** reported
`DiagnosticsNameHint=True` (substring `diagnos|vehicle|readvin`)
and `J2534DiCENameHint=True` (substring
`j2534|passthru|dice`). These checks DO NOT inspect any
class bytecode, and they do NOT prove any communication or
API integration. **Important false-positive risk:** the
case-insensitive `dice` substring can occur in unrelated
class identifiers such as `indices`, and package path
matches may be unrelated to a class's purpose. No class
names, archive contents or file paths were exported; no
SQL procedure execution, network request, J2534/ECU I/O
or binaries published.

**Owner-local refined EJB JAR filename/EJB descriptor audit:**
The same verified EAR sorted slot **2** contains a JAR
with **325 `.class` entries**. The user ran a scoped
read-only central-directory filename scan with per-category
leaf-name/full-path matches and a DTD/XXE-disabled,
1 MiB-limited parse of the JAR's `META-INF/ejb-jar.xml`.
Results:

| Metric | Value |
|---|---:|
| ClassFiles | 325 |
| ReadVinPathMatches | 0 |
| ReadVinClassMatches | 0 |
| DiagnosisClassMatches | 1 |
| VehicleClassMatches | 36 |
| J2534PathMatches | 1 |
| J2534ClassMatches | **1** |
| PassThruClassMatches | 0 |
| DiCEClassMatches (stricter leaf regex) | 0 |
| EJBXMLStatus | **Parsed** |
| SessionBeans | **20** |
| EntityBeans | 0 |
| MessageDrivenBeans | 0 |

**Critical new clue:** one actual `.class` **leaf filename**
contains `J2534`, eliminating the prior concern that the
J2534 hint was only a package path or accidental `dice`
substring. However, a matching class name alone is NOT
proof that any EJB executes it or calls a J2534 driver.
Twenty session beans are declared in the EJB descriptor,
but no call graph from these beans to that class has been
established. Zero `ReadVin` filenames does not exclude
code that performs VIN identification under other names;
zero `DiCE` leaf-name regex matches does not exclude
vendor DLL use. No class names, raw XML, class bytecode,
URLs, paths, passwords, VIN or ECU data were exported.
No code execution, process/registry change or hardware I/O.

**Owner-local EJB declaration-to-class verification:**
The same verified exploded EAR sorted slot **2**,
containing a single root EJB JAR, was inspected again with
DTD/XXE-disabled parsing of its `META-INF/ejb-jar.xml`.
All **20** `<session>` nodes declare an `ejb-class`, and
**20/20** fully qualified implementation class names
resolve to existing ZIP `.class` entries in the JAR.
`BeanClassesMissing=0`, `BeansWithoutClassDeclaration=0`.
None of the 20 declared EJB class *leaf* names contains
`J2534` or `Vehicle` (`J2534SessionBeans=0`,
`VehicleSessionBeans=0`), while the full archive still
contains **1** J2534-named `.class` (`J2534ClassFiles=1`).
This is strong static structural consistency and suggests
the J2534 class is a **non-bean helper/service candidate**;
it is NOT evidence that any bean calls it or that VIDA
uses J2534 in a ReadVin diagnostic session. No class code
or methods were run, loaded, extracted or exported.

**Owner-local static J2534 `CONSTANT_Class` reference scan (completed):**
On the restarted VIDA/WildFly Java PID **12004**, a new
read-only script independently recovered the current Java
process by confirming ancestry to `VidaMonitor.exe` instead
of relying on stale PID 4324. The operator ran the script
twice, both returning identical aggregate metrics:

| Metric | Observed |
|---|---:|
| JavaPID | 12004 |
| VIDAAncestorConfirmed | True |
| EARSlot | 2 |
| J2534TargetClasses | 1 |
| TotalClasses | 325 |
| DeclaredSessionBeans | 20 |
| OtherClassesScanned | **324** |
| ClassesSkippedBySize | **0** |
| ClassParseErrors | **0** |
| ClassesReferencingJ2534 | **0** |
| SessionBeansReferencingJ2534 | **0** |
| ReferenceType | `CONSTANT_Class` |

This is a **complete scan of other classes in that one
EJB JAR for exact JVM `CONSTANT_Class` references to the
single J2534-named type**, as resolved from its ZIP entry
path. There are **no such references among 324 peers**.
This refutes a **direct class-constant dependency within
this archive** as the currently observed path, but does
NOT establish that the class is unused, that runtime
Java/J2534 integration is absent, or that VIDA never uses
it: bytecode descriptors/UTF8 metadata, reflection,
interfaces, dynamic loading and classes in other archives
have not been evaluated. `CONSTANT_Class` references also
do not prove runtime invocation when present. The parse
script did not print any class names, bytecode, proprietary
XML, paths, runtime command lines, URLs or secrets; no
network/SQL/vehicle I/O or binaries published.

**Owner-local refined `CONSTANT_Utf8` and J2534 class-header scan:**
The read-only operator script autodetected VIDA-descendant
WildFly (`JavaPID=12004`, `VIDAAncestorConfirmed=True`)
and re-opened the same EJB JAR in sorted EAR slot **2**.
Aggregate findings: `OtherClassesScanned=324`,
`ClassesSkippedBySize=0`, `ClassParseErrors=0`.
**No peer reference hints** were found:
`PeerExactInternalNameUTF8=0`, `PeerDescriptorTypeUTF8=0`,
`PeerDottedNameUTF8=0`, `PeerAnyJ2534UTF8=0`,
`SessionBeansWithExactTargetUTF8=0`.
The target J2534-named class itself parsed successfully:
`J2534TargetStatus=Parsed`, `J2534IsInterface=False`,
`J2534IsAbstract=False`, `J2534Fields=5`,
`J2534Methods=11`, `J2534NativeMethods=0`,
`J2534AbstractMethods=0`.

The negative results narrow static references **within this
single JAR**: not only are exact `CONSTANT_Class` references
absent (prior scan), but no other parsed class constant pool
contains any case-insensitive `J2534` UTF8 substring under
the script's tests. This does **not** prove the class is
dead code or absent from VIDA's actual diagnostic path;
other WAR/JAR modules, reflection and runtime factories
remain possible. Zero `native` flags on the class's own
methods does NOT exclude JNI/JNA in dependencies.
No constant pool values, class names, bytecode, paths,
URLs, passwords, VIN, ECU data or Java methods were
exported or executed; no DB/network/J2534 device I/O,
configuration/registry changes or binary publication.

**Owner-local J2534-named class role audit (v2, completed):**
After troubleshooting a previous incomplete run, the
instrumented read-only PowerShell v2 script completed with
`[VIDA] Result=OK` and `ScriptFinished`. Current WildFly
PID was **11600**, and ancestry to `VidaMonitor.exe` was
confirmed. The EJB archive in sorted EAR slot 2 yielded:

| Metric | Result |
|---|---:|
| J2534TargetStatus | `Parsed` |
| J2534Fields | 5 |
| J2534Methods | 11 |
| Constructors | 1 |
| StaticInitializers | 0 |
| GetterMethods | 5 |
| SetterMethods | 5 |
| BooleanGetterMethods | 0 |
| OtherMethods | **0** |
| NativeMethods | 0 |
| PassThruDeclaredMethods | 0 |
| ReferencedJnaFamilyClasses | 0 |
| ReferencedJavaNetClasses | 0 |
| ReferencedJavaIOClasses | 0 |
| ReferencedReflectionClasses | 0 |
| ReferencedSQLClasses | 0 |
| JnaFamilyMethodRefs | 0 |
| NativeLibraryLoadMethodRefs | 0 |
| PassThruMethodRefs | 0 |
| ConstantPoolPassThruHints | 0 |
| ConstantPoolJ2534Hints | 3 |

**Interpretation:** the exact breakdown of declared
method names (constructor + five getter + five setter)
with five fields and no other methods is **strongly
consistent with a JavaBean/DTO** representing J2534 data,
NOT an executable J2534 PassThru driver implementation.
This is a static structure-based inference, not inspection
of method bodies or proof of actual usage or runtime
behavior. Three J2534 mentions in the target class's own
constant pool can reflect its own name/types and should
not be considered evidence of external calls. All other
324 class entries in this same EJB JAR previously tested
negative for J2534 references via exact `CONSTANT_Class`
and UTF8 hints; neither scan covers other deployments.
Zero native/PassThru/JNA references in the target class
does not rule out the rest of VIDA reaching DiCE/J2534 via
a different module, factory, interface, process or DLL.

**Owner-local deployed WAR inventory (read-only, completed):**
The bounded WAR inventory script completed with
`[VIDA] Result=OK` on `JavaPID=11600`,
`VIDAAncestorConfirmed=True`, `ExplodedWARCount=2`.
It reported, in sorted EAR/WAR slots:

| Metric | EAR 1 / WAR 1 | EAR 2 / WAR 1 |
|---|---:|---:|
| WEBINFExists | True | True |
| LIBExists | False | **True** |
| LIBFiles | 0 | **31** |
| LIBJarFiles | 0 | **31** |
| LIBNativeDLLFiles | 0 | 0 |
| LIBDirectories | 0 | 0 |
| CLASSESExists | True | True |
| CLASSESImmediateClasses | 0 | 0 |
| CLASSESSubdirectories | 1 | 1 |
| WARImmediateDirectories | 2 | **12** |
| WARImmediateFiles | 0 | **3** |

The second EAR's exploded WAR therefore contains **31
first-level JAR archives under `WEB-INF/lib`**, a useful
lead beyond the earlier EJB JAR whose `J2534`-named class
was consistent with a JavaBean/DTO. Counts are immediate
children only: `CLASSESImmediateClasses=0` does **not**
exclude nested package classes; `LIBNativeDLLFiles=0`
does **not** establish absence of native DLLs elsewhere
or native libraries embedded in JARs. No content of the
31 archives has been examined in this gate. The presence
of 31 JARs does **not** establish a J2534 driver or actual
vehicle communication.

**Owner-local WAR JAR ZIP metadata gate completed:**
Operator ran `Inspect-VIDA-WARJarMetadata.ps1` successfully
(`Result=OK`, `ScriptFinished`), on verified VIDA-descendant
WildFly `JavaPID=11600`, `EARSlot=2`, `WARSlot=1`.

| Metric | Observed |
|---|---:|
| WEBINFLibJars / ReadableJars | **31 / 31** |
| JarsSkippedLarge / JarsSkippedEntryLimit / UnreadableJars | **0 / 0 / 0** |
| JarEntriesInspected | **6518** |
| ClassEntriesFound | **5872** |
| J2534ClassNameHints / PassThruClassNameHints / DiCEClassNameHints | **0 / 0 / 0** |
| DiagnosisClassNameHints / VehicleClassNameHints | **0 / 0** |
| JarsWithAdapterNameHints | **0** |
| WARExplodedClassFiles | **279** |
| WARClassTreeLimitReached | **False** |
| WARJ2534ClassNameHints / WARPassThruClassNameHints / WARDiCEClassNameHints | **0 / 0 / 0** |

The second EAR/WAR has **6151 `.class` files total across
31 first-level `WEB-INF/lib` JAR archives and exploded
`WEB-INF/classes`**. These are **class leaf-filename**
checks and ZIP central-directory inventory only. All
readable, no skips; do **not** misstate zero filename hints
as no J2534/PassThru/DICE code or no VIDA diagnostics.
The 325-class EJB root JAR from the earlier gate is a
**separate artifact**, not included in these 6151 files.
No archive was extracted, and no bytecode or class constant
pool in these 31 JARs was read in this inventory. No paths,
names of proprietary classes, endpoints, VIN or credentials
were emitted, nor device/SQL/HTTP requests sent.

**Owner-local WAR Java constant-pool hint scan (v2, completed):**
After correcting a PowerShell 5.1 `$HOME` collision in the
first version (which failed before archive I/O), the v2
read-only script completed `Result=OK`/`ScriptFinished` on
VIDA-ancestor-confirmed WildFly `JavaPID=11600`, `EARSlot=2`,
`WARSlot=1`.

| Metric | Observed |
|---|---:|
| WEBINFLibJars | 31 |
| JarsUnreadable / JarsSkippedByLimit | **0 / 0** |
| JarEntriesInspected | **6518** |
| JARClassesScanned | **5872** |
| ExplodedClassesScanned | **279** |
| ClassesSkippedByLimit / ClassParseErrors | **0 / 0** |
| JARClassesWithJ2534UTF8 / PassThruUTF8 / DiCEUTF8 / ReadVinUTF8 | **0 / 0 / 0 / 0** |
| ExplodedClassesWithJ2534UTF8 / PassThruUTF8 / DiCEUTF8 / ReadVinUTF8 | **0 / 0 / 0 / 1** |
| JarsWithAnyKeywordHints | **0** |

**Interpretation:** all **6151** `.class` files belonging
to the examined 31 second-WAR JARs and exploded class
tree were parsed in this bounded, **constant-pool-only**
keyword test. One exploded web class contains at least one
`CONSTANT_Utf8` entry matching the broad `(read.?vin)`
pattern; zero such hits were reported for the 5872 classes
in the 31 JARs. There were no `J2534`/`PassThru`/`DiCE`
UTF8 hits under the tested patterns, but **absence of
keyword matches is not absence of diagnostic code**.
The single `ReadVin` hit is a potentially useful lead
alongside the separately observed SQL `ScriptType.Description`
value `ReadVin`; **no call or dataflow between them has
been established**, and the UTF8 value might be a field,
method, type descriptor, text literal, annotation or
other metadata. No proprietary strings, filenames, paths,
VIN or scripts were printed. No Java/SQL/network/ECU
operations, deployments, registry or build changes.

**Owner-local `ReadVin`-hint structural classification (completed):**
On VIDA-descendant WildFly `JavaPID=11600` in EAR 2 / WAR 1,
`Inspect-VIDA-ReadVinClassContext.ps1` completed successfully
(`Result=OK`, `ScriptFinished`). Parsed all 279 exploded
classes with zero skipped/parse errors. One class matched
the *broad* case-insensitive `read.?vin` regex, with these
**aggregate counts**:

| Metadata category | Count |
|---|---:|
| `ClassesWithReadVinUTF8Hint` | **1** |
| `MatchedUTF8Entries` | **3** |
| `ExactReadVinUTF8Entries` | **0** |
| `MatchedStringConstants` / `MatchedClassConstants` | **0 / 0** |
| `MatchedNameAndTypeNames` / descriptors | **1 / 0** |
| `MatchedFieldRefMembers` / `MatchedMethodRefMembers` / `MatchedInterfaceMethodRefMembers` | **1 / 0 / 0** |
| `MatchedFieldDeclarationNames` / descriptors | **1 / 0** |
| `MatchedMethodDeclarationNames` / descriptors | **2 / 0** |
| `MatchedUTF8Unclassified` | **0** |

**Interpretation:** these facts are consistent with a
field/property accompanied by two declared methods, such
as a getter and setter, but the actual name, method
signatures and behavior have not been recovered. No exact
`ReadVin` UTF8 entry nor matching literal string / method
reference was found. The broad regex may have matched a
longer or modified identifier; it is **not** evidence of
a call to SQL `GetScript`, any actual VIN read or a J2534
transaction. The previously observed SQL metadata
`ScriptType.Description=ReadVin` remains a distinct fact
without a proven implementation link. This significantly
weakens treating the single WAR keyword hit as a direct
`GetScript` caller lead.

**Owner-local second-WAR SQL-caller UTF8 hint scan (completed):**
The `Inspect-VIDA-SQLCallerHints.ps1` script finished
`Result=OK`/`ScriptFinished` on VIDA-descendant WildFly
`JavaPID=11600` (EAR slot 2 / WAR slot 1). It parsed all
**5872 JAR class entries** in **31 readable JARs**, plus
**279 exploded classes**, with **0** unreadable/skipped
JARs/classes or class parsing errors; `JarEntriesInspected=6518`.

| Keyword-bearing class count | JAR | Exploded classes |
|---|---:|---:|
| `GetScript` (substring, case-insensitive) | **26** | **1** |
| `scriptType` (substring, case-insensitive) | 0 | 0 |
| `DiagSwdlRepository` (substring, case-insensitive) | 0 | 0 |
| `ReadVin` (exact UTF8 entry) | 0 | 0 |

The 26 JAR `GetScript` UTF8 hints occurred in **three
anonymous archive slots**: slot 1 = **2** classes; slot 14
= **18**; slot 19 = **6**. `JarsWithAnyKeywordHints=3`.
**Critical caveat:** source inspection of the *probe itself*
confirmed it tests `(?i)getscript` as a **substring** in
`CONSTANT_Utf8`, with NO word boundary or JVM symbolic
reference semantics. Therefore a name such as
`getScriptName` or `getScriptEngine` may count. The 27 total
classes are **not** proof that any code invokes SQL
`dbo.GetScript`, nor that the original VIDA client binds
the `@scriptType` parameter. The simultaneous zero
`scriptType` and database-name hints gives no positive
link to the separate `DiagSwdlRepository` metadata.
The earlier one broad `read.?vin` property-shaped match
also did not have an exact `ReadVin` string entry.
No method bytecode, proprietary identifiers or string
contents, paths, credentials or VIN were exported; no
Java class executed, SQL queried, HTTP/J2534/ECU requests
sent or Virtual Car builds published.

**Owner-local exact-`GetScript` JVM metadata classification (completed):**
The `Inspect-VIDA-GetScriptExactContext.ps1` operator run
finished `Result=OK`/`ScriptFinished` on descendant
WildFly `JavaPID=11600`, EAR 2 / WAR 1, 31 readable JARs,
`JarEntriesInspected=6518`, **5872 JAR classes + 279
exploded classes**, 0 skipped/unreadable/parse errors.

| Class-count metric | JAR | Exploded |
|---|---:|---:|
| Case-insensitive substring `GetScript` in UTF8 | **26** | **1** |
| Exact UTF8 entry `GetScript` | **0** | **0** |
| Longer-only substring hits | **26** | **1** |
| Exact declared method name | 0 | 0 |
| Exact `Methodref` / `InterfaceMethodref` member | 0 / 0 | 0 / 0 |
| Exact `CONSTANT_String` literal | 0 | 0 |
| `scriptType` / repository-name / exact `ReadVin` | 0 / 0 / 0 | 0 / 0 / 0 |

Anonymous JAR slot counts were identical to the broad
scan: **slot 1: 2; slot 14: 18; slot 19: 6**; every slot
had zero exact `GetScript` UTF8 entries and exact member
references. The previously reported 27 class hits are
**all longer UTF8 values**, not a class or declared method
whose UTF8 entry is exactly `GetScript`.

**Important limit:** the absence of an *exact* UTF8 value
`GetScript` does not rule out a Java `CONSTANT_String`
literal containing an entire SQL command such as
`EXEC dbo.GetScript ...`, which would be a **longer** UTF8
value, or construction of such a command at runtime. The
negative exact-name scan therefore narrows Java-symbol
claims only; it **does not refute** a possible SQL text
literal or remote call, and does not prove VIDA lacks the
stored procedure. There is still no observed original VIDA
client SQL invocation or `@scriptType` binding.

**Owner-local longer `GetScript` structural-context scan (completed):**
The operator ran `Inspect-VIDA-GetScriptLongContext.ps1` on
verified VIDA-descendant WildFly `JavaPID=11600`, EAR slot
2 / WAR slot 1; scan completed `Result=OK`/`ScriptFinished`.
All **5872 JAR classes** (31 readable JARs; 6518 ZIP entries)
and **279 exploded classes** were read with **0** skips,
unreadable JARs or parse errors.

| Class-count metric | JAR | Exploded |
|---|---:|---:|
| Has case-insensitive substring `getscript` in `CONSTANT_Utf8` | **26** | **1** |
| Has exact `GetScript` UTF8 entry / exact named method or ref | 0 | 0 |
| Has token-like longer `getscript` identifier | **26** | **1** |
| Has a `CONSTANT_String` referencing UTF8 with `getscript` | **1** | 0 |
| Has heuristic SQL-shaped `getscript` UTF8 or `CONSTANT_String` | **0 / 0** | **0 / 0** |
| Declares a longer `getscript...`-named Java method | **17** | **1** |
| References a longer `getscript...`-named Java method | **14** | 0 |
| Declares/references similarly named field | 0 / 0 | 0 / 0 |
| Contains `scriptType` / `DiagSwdlRepository` / exact `ReadVin` | 0 / 0 / 0 | 0 / 0 / 0 |

Anonymous JAR slots remain **1:2**, **14:18**, **19:6**;
all have 0 SQL-shaped UTF8/string matches under the
probe's specific regex and 0 exact member-ref matches.
The class-count method-declaration and reference categories
**may overlap**, so must NOT be summed as unique classes.
The one JAR `CONSTANT_String` with `getscript` is **not**
classified as a SQL-shaped literal by this bounded
heuristic; do not claim it is a real SQL caller.

**Interpretation:** the 27 original broad `GetScript`
hits are most consistent with **longer Java symbol names**,
not evidence of a direct stored-procedure call. The one
string-constant hit deserves only minimal weight absent
SQL syntax. The heuristic is not exhaustive; e.g. string
construction, unusual SQL syntax, other modules or remote
calls could evade it. Neither the original VIDA caller nor
its runtime `@scriptType` was observed. No class contents,
Java method bodies, names/paths, SQL text, VIN or
credentials were disclosed, and no Java/SQL/network/ECU
requests executed.

**Owner-local EJB JAR SQL/diagnostic UTF8 scan (completed):**
`Inspect-VIDA-EJBSQLHints.ps1` completed `Result=OK` and
`ScriptFinished` in the VIDA-descendant WildFly process
`JavaPID=11600`; inspected only the **one separate root
EJB JAR in sorted EAR slot 2**, not the 31 web JARs.

| Metric | Observed |
|---|---:|
| EJBJarCount | **1** |
| ClassEntriesFound / ClassesScanned | **325 / 325** |
| SessionBeansDeclared | **20** |
| ClassesSkippedByLimit / ClassParseErrors | **0 / 0** |
| ClassesWithGetScriptUTF8 / ExactGetScriptUTF8 / GetScriptStringConstant | **0 / 0 / 0** |
| ClassesWithSQLShapedUTF8 / SQLShapedStringConstant | **0 / 0** |
| ClassesDeclaringGetScriptNamedMethod / ReferencingGetScriptNamedMethod | **0 / 0** |
| ClassesWithScriptTypeUTF8 / RepositoryUTF8 / ExactReadVinUTF8 | **0 / 0 / 0** |
| ClassesWithJ2534UTF8 / PassThruUTF8 / DiCEUTF8 | **1 / 0 / 0** |
| BeansWithGetScriptUTF8 / SQLShapedUTF8 / ScriptTypeUTF8 / RepositoryUTF8 / ExactReadVinUTF8 | **0 / 0 / 0 / 0 / 0** |

The sole `J2534`-bearing class is consistent with the
previously characterized **5-field/11-method JavaBean/DTO**
member of this JAR. There are **no matching static hints
under the probe's patterns** for SQL `dbo.GetScript`,
`@scriptType` or exact `ReadVin` among 325 classes (including
20 EJB bean implementation classes). This does NOT prove
SQL or J2534 is unused: runtime query composition,
external dependencies, other modules, or clients could
implement the functionality. Across the second WAR's
6151 classes and this separate EJB JAR's 325, **6476 class
files have been scanned under varying bounded metadata
probes**, not a complete whole-VIDA code/runtime analysis.
No class bodies, proprietary identifiers, paths, scripts,
credentials, VIN or network requests were emitted or
executed. No SQL procedure execution, adapter interaction,
ECU writes, registry changes or build publication.

**Owner-local passive SQL Server ↔ VIDA/WildFly TCP peer inventory (completed):**
`Inspect-VIDA-SQLTcpPeers.ps1` finished `Result=OK` /
`ScriptFinished`. It takes a Windows process inventory and
single `Get-NetTCPConnection` snapshot, identifies local
`sqlservr.exe` and verifies WildFly Java's ancestry to
`VidaMonitor.exe`, then matches client/server `Established`
TCP tuples by reversed address/port pairs. No SQL calls,
connection attempts or packet capture were performed.

| Aggregate metric | Result |
|---|---:|
| `LocalSQLServerProcessCount` | **1** |
| `VerifiedVidaWildFlyCount` | **1** |
| `SQLTcpListeningEndpoints` | **4** |
| `SQLTcpEstablishedEndpoints` | **4** |
| `SQLTcpPeerProcessesMatched` | **1** |
| `VidaWildFlyPeerProcesses` | **1** |
| `VidaMonitorPeerProcesses` | **0** |
| `OtherOrUnclassifiedPeerProcesses` | **0** |

**Interpretation:** this establishes **a live TCP link
between a VIDA-descendant WildFly Java process and a local
SQL Server process** at the instant of the snapshot. The
four established SQL-owned **endpoints** must NOT be
represented as four SQL queries, four distinct sessions or
four separate clients. Because PID matching yields one
Java peer process, we have process-level connection
provenance, **not** database-name selection, query text,
stored-procedure invocation, SQL login identity, or
proof that `dbo.GetScript` was called with `@scriptType`.
Coverage does not include Shared Memory, Named Pipes,
remote SQL Server or activity outside the snapshot. The
SQL client may be idle or service-related. All private
IP/port/process command lines/paths, passwords, VIN and
query bodies remain unreported. No Java/SQL/HTTP/J2534/
ECU operations, registry changes, deployments or published
Virtual Car builds.

**Next bounded read-only gate:** inventory established
loopback TCP client peers of the **three previously
observed WildFly-owned listener endpoints** using a
fresh single `Get-NetTCPConnection` snapshot, outputting
only counts/categories (`VidaMonitor`, VIDA-descendant
processes, common web-browser processes, other/unknown).
Match server-side established tuples to the WildFly-owned
listeners and reverse client endpoints, without printing
addresses, ports, PIDs, URLs, names of proprietary programs
or content. This may clarify the front-end → WildFly →
SQL network topology if the front-end is connected at
snapshot time. Zero matches are inconclusive and no result
proves any specific HTTP endpoint or SQL procedure call.
Keep draft PR #172 unmerged; publish no builds.

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
