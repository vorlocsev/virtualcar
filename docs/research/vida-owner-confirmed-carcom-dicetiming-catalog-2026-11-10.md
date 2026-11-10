# Original VIDA SQL: owner-confirmed CarCom and DiceTiming catalog

Evidence origin: owner PowerShell / System.Data.SqlClient commands executed against
running VIDA instance on 2026-11-10. These are original object names and exact
column names **without anonymization**. They are not synthetic fixtures.

## Confirmation and boundaries

- SQL Server: local instance .\VIDA.
- Owner previously confirmed CarCom and DiceTiming are ONLINE, both with
  snapshot_isolation_state_desc = OFF. Do not turn snapshot isolation on as
  part of evidence collection.
- CarCom: 52 visible tables. Owner's FK catalog query returned
  **80 foreign-key column mappings**. This is a count of mappings,
  not an independently established count of distinct FK constraints.
- DiceTiming: 5 visible tables; MessageTiming and TimeoutAndResend
  inspected to the column level.
- The PowerShell console truncated the TargetTable/TargetColumn
  columns of the original FK listing. FK constraint names and source
  columns were readable, but a complete, exact target metadata table
  still needs to be retrieved without console truncation.
- Owner has **not yet supplied actual record values** from original
  ECU Profile, InitHw, Service or DiceTiming tables.

## Verified CarCom columns and declared FK names

T161_Profile contains id, identifier, folderLevel, description, title,
fkT162_ProfileValue_Model, fkT162_ProfileValue_Year,
fkT162_ProfileValue_Engine, fkT162_ProfileValue_Transmission,
fkT162_ProfileValue_Body, fkT162_ProfileValue_Steering,
fkT162_ProfileValue_Market, fkT162_ProfileValue_ControlUnit,
fkT162_ProfileValue_ChassisFrom and fkT162_ProfileValue_ChassisTo.

T162_ProfileValue contains id, identifier, description,
fkT163_ProfileValueType.

T136_InitHw_Profile contains exactly fkT130_Init and fkT161_Profile;
FK names observed:
- FK_T136_Init_Profile_T130_Init
- FK_T136_Init_Profile_T161_Profile

T130_Init contains id and fkT133_InitCategory.
T131_InitValue contains id, fkT130_Init, fkT132_InitValueType,
initValue and sortOrder.

T100_EcuVariant contains id, fkT101_Ecu, fkT101_Ecu_Gateway,
identifier, status and inheritance.

T110_Service_EcuVariant contains fkT111_Service, fkT100_EcuVariant
and nullable fkt130_Init_Timing_Service. FK names observed:
- FK_T110_Service_EcuVariant_T100_EcuVariant
- FK_T110_Service_EcuVariant_T111_Service
- FK_T110_Service_EcuVariant_T130_Init_Timing_Service

T111_Service contains id, fkT122_Protocol, service, mode,
serviceName, modeName, description, definition (SQL image),
type, status and fkt130_Init_Timing_Service_Default.
FK names observed:
- FK_T111_Service_T122_Protocol
- FK_T111_Service_T130_Init_Timing_Service_Default

T160_DefaultEcuVariant: FK names observed:
- FK_T160_DefaultEcuVariant_T100_EcuVariant
- FK_T160_DefaultEcuVariant_T161_Profile

Those constraints establish **schema-level linkage** from
Profile through InitHw_Profile to Init and from EcuVariant
through Service_EcuVariant to Service. They DO NOT prove
that any real XC90 V8 Profile selects any specific InitHw,
ECU variant or Service. Joining records and evaluating the
VIDA runtime profile-selection logic remains separate work.

## Verified DiceTiming columns

dbo.MessageTiming:
MessageTimingID int, P1max int, P3min int, P4min int, Comment char.

dbo.TimeoutAndResend:
TimeoutAndResendId int, Timeout int, Resend int, Comment char.

Actual values, units, ordering, protocol association,
cross-database access from CarCom, and runtime applicability
are **not yet verified**. Do not assume the time units are ms.

## Next read-only owner queries

Run against the **actual original SQL Server** in owner VMware.
The following statements are read-only; preserve all original
identifier and text values. Export resulting rows to owner-private
files outside the Git repository, never paste real private secrets
into public PR comments.

Find model/year/engine profile values and the original
XC90 / V8 candidate profile keys:

~~~sql
SELECT TOP (80)
    p.id, p.identifier, p.title, p.description,
    m.identifier AS ModelIdentifier,
    m.description AS ModelDescription,
    y.identifier AS YearIdentifier,
    e.identifier AS EngineIdentifier,
    e.description AS EngineDescription,
    (SELECT COUNT(*) FROM dbo.T136_InitHw_Profile h
      WHERE h.fkT161_Profile = p.id) AS LinkedInitHwCount,
    (SELECT COUNT(*) FROM dbo.T160_DefaultEcuVariant v
      WHERE v.fkT161_Profile = p.id) AS LinkedDefaultEcuCount
FROM dbo.T161_Profile p
LEFT JOIN dbo.T162_ProfileValue m ON m.id = p.fkT162_ProfileValue_Model
LEFT JOIN dbo.T162_ProfileValue y ON y.id = p.fkT162_ProfileValue_Year
LEFT JOIN dbo.T162_ProfileValue e ON e.id = p.fkT162_ProfileValue_Engine
WHERE p.identifier LIKE '%XC90%'
   OR p.title LIKE '%XC90%'
   OR p.description LIKE '%XC90%'
   OR m.identifier LIKE '%XC90%'
   OR m.description LIKE '%XC90%'
   OR e.identifier LIKE '%V8%'
   OR e.description LIKE '%V8%'
   OR e.identifier LIKE '%B8444S%'
ORDER BY p.id;
~~~

This query is **candidate discovery only**, not a guaranteed
complete XC90/V8 profile set. Values may be stored as numeric
codes instead of visible XC90/V8 text. An empty set does not
prove there is no corresponding original profile.

After obtaining a real profile ID, enumerate original linked
initialization values without guessing mappings:

~~~sql
SELECT h.fkT161_Profile AS OriginalProfileId,
       h.fkT130_Init AS OriginalInitId,
       i.fkT133_InitCategory AS OriginalInitCategoryId,
       v.fkT132_InitValueType AS OriginalValueTypeId,
       v.initValue AS OriginalInitValue,
       v.sortOrder AS OriginalSortOrder
FROM dbo.T136_InitHw_Profile h
JOIN dbo.T130_Init i ON i.id = h.fkT130_Init
LEFT JOIN dbo.T131_InitValue v ON v.fkT130_Init = i.id
WHERE h.fkT161_Profile = @OwnerChosenProfileId
ORDER BY h.fkT130_Init, v.sortOrder, v.id;
~~~

The parameter must be bound, not interpolated as SQL. This
is **all original values**, not an anonymized profile; it
does not itself prove which runtime init action occurs.

Read the original DiceTiming values separately:

~~~sql
SELECT TOP (100) MessageTimingID, P1max, P3min, P4min,
       RTRIM(Comment) AS Comment
FROM dbo.MessageTiming ORDER BY MessageTimingID;

SELECT TOP (100) TimeoutAndResendId, Timeout, Resend,
       RTRIM(Comment) AS Comment
FROM dbo.TimeoutAndResend ORDER BY TimeoutAndResendId;
~~~

The Service definition field uses SQL image. Before exporting
raw binaries, inspect read-only sizes and the original service
labels, not speculative decoding:

~~~sql
SELECT TOP (60) id, fkT122_Protocol, service, mode,
       serviceName, modeName, fkt130_Init_Timing_Service_Default,
       DATALENGTH(definition) AS DefinitionBytes
FROM dbo.T111_Service
ORDER BY id;
~~~

## Acceptance gates

- Verified: owner SQL service running; catalog object names, columns
  and listed FK names; DiceTiming field names.
- Pending: full untruncated FK target columns, actual CarCom rows,
  actual DiceTiming rows, service image format, profile matching,
  InitHw inheritance, inter-database lookup, D2 timing units,
  GetScript/ReadVin runtime and accepted VIN.
- Not checked: physical J2534, VMware exact-head CI for PR #317.
