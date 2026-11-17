-- B3A297: original VIDA CarCom service 22 / CEM529 DID-to-block mapping triage.
-- OWNER-LOCAL, STRICTLY READ-ONLY. No definition bytes, T150 values, VIN,
-- proprietary payloads, firmware, ECU/J2534 commands, or SQL DML exposed.
--
-- Context:
--   CEM variant 529 -> config 541 GGD 500k 29-bit (T120 confirmed).
--   Shared service id 100 is '22 Read Data By Identifier'; 363 definition bytes.
--   F0 roots (293990 and 294035), F5 root 294031 and F8 root 294033
--   have metadata, but NONE is proven to equal UDS F110/F114/F106.
-- 
-- A binary marker occurrence inside opaque T111.definition is only a
-- HEURISTIC presence check. Absence also does NOT exclude dynamic mapping.
-- UTF-16LE with 0x00 bytes is intentionally not probed using CHARINDEX;
-- Microsoft SQL Server documents a Windows-collation 0x0000 limitation.
SET NOCOUNT ON;

PRINT 'B3A297_SHARED_SERVICE22_USAGE';
SELECT TOP (15)
       e.fkT100_EcuVariant AS variant_id,
       s.id AS service_id,
       p.identifier AS protocol_label,
       s.[service] AS service_code,
       DATALENGTH(s.definition) AS definition_bytes
FROM dbo.T110_Service_EcuVariant AS e
JOIN dbo.T111_Service AS s ON s.id=e.fkT111_Service
LEFT JOIN dbo.T122_Protocol AS p ON p.id=s.fkT122_Protocol
WHERE e.fkT100_EcuVariant IN (529,2055,2725,3044)
  AND s.id=100
ORDER BY e.fkT100_EcuVariant;

PRINT 'B3A297_SERVICE22_BINARY_MARKER_HEURISTICS';
;WITH DefinitionData AS (
    SELECT id, CONVERT(varbinary(max),definition) AS b
    FROM dbo.T111_Service
    WHERE id=100
)
SELECT id AS service_id,
       DATALENGTH(b) AS definition_bytes,
       CASE WHEN CHARINDEX(0xF110,b)>0 THEN 1 ELSE 0 END AS be_f110_present,
       CASE WHEN CHARINDEX(0x10F1,b)>0 THEN 1 ELSE 0 END AS le_f110_present,
       CASE WHEN CHARINDEX(0xF114,b)>0 THEN 1 ELSE 0 END AS be_f114_present,
       CASE WHEN CHARINDEX(0x14F1,b)>0 THEN 1 ELSE 0 END AS le_f114_present,
       CASE WHEN CHARINDEX(0xF106,b)>0 THEN 1 ELSE 0 END AS be_f106_present,
       CASE WHEN CHARINDEX(0x06F1,b)>0 THEN 1 ELSE 0 END AS le_f106_present,
       CASE WHEN CHARINDEX(0x46313130,b)>0 THEN 1 ELSE 0 END AS ascii_f110_present,
       CASE WHEN CHARINDEX(0x46313134,b)>0 THEN 1 ELSE 0 END AS ascii_f114_present,
       CASE WHEN CHARINDEX(0x46313036,b)>0 THEN 1 ELSE 0 END AS ascii_f106_present
FROM DefinitionData;

PRINT 'B3A297_SERVICE_TO_BLOCK_BRIDGE_CATALOG';
-- Search for candidate *schema* bridges: tables carrying both a service
-- reference and a block reference. Does not read any table row contents.
SELECT TOP (100)
       t.name AS table_name,
       SUM(CASE WHEN c.name LIKE '%T111_Service%' THEN 1 ELSE 0 END) AS service_ref_columns,
       SUM(CASE WHEN c.name LIKE '%T141_Block%' THEN 1 ELSE 0 END) AS block_ref_columns,
       SUM(CASE WHEN c.name LIKE '%T100_EcuVariant%' THEN 1 ELSE 0 END) AS variant_ref_columns
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id=t.object_id
GROUP BY t.name
HAVING SUM(CASE WHEN c.name LIKE '%T111_Service%' THEN 1 ELSE 0 END)>0
   AND SUM(CASE WHEN c.name LIKE '%T141_Block%' THEN 1 ELSE 0 END)>0
ORDER BY t.name;

PRINT 'B3A297_IDENT_ROOT_VALUE_ROW_METADATA_ONLY';
SELECT TOP (20)
       b.id AS block_id,
       b.[name] AS block_name,
       b.[length] AS stored_length,
       COUNT_BIG(v.id) AS value_rows,
       MIN(DATALENGTH(v.CompareValue)) AS min_compare_value_bytes,
       MAX(DATALENGTH(v.CompareValue)) AS max_compare_value_bytes,
       MIN(DATALENGTH(v.altDisplayValue)) AS min_alt_display_bytes,
       MAX(DATALENGTH(v.altDisplayValue)) AS max_alt_display_bytes
FROM dbo.T141_Block AS b
LEFT JOIN dbo.T150_BlockValue AS v ON v.fkT141_Block=b.id
WHERE b.id IN (293990,294035,294031,294033)
GROUP BY b.id,b.[name],b.[length]
ORDER BY b.id;

PRINT 'B3A297_READ_ONLY_COMPLETE';
