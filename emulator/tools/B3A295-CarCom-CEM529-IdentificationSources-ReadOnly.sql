-- B3A295: locate metadata for CEM 529 identification roots and service 22.
-- Owner-local READ ONLY. Does not read T111.definition contents, T150 values,
-- VIN, firmware, CAN payloads, protected ECU operations, or write to CarCom.
-- Goal: distinguish CarCom F0 / F5 / F8 identification block metadata from
-- observed 29-bit UDS 22 F110/F114/F106 requests. Names alone are not
-- diagnostic DID mappings. Do not invent positive ECU response bytes.
SET NOCOUNT ON;

PRINT 'B3A295_COMPARE_ECU802_GGD_SERVICE22_LINKS';
SELECT TOP (100)
       link.fkT100_EcuVariant AS variant_id,
       s.id AS service_id,
       s.fkT122_Protocol AS protocol_id,
       p.identifier AS protocol_identifier,
       s.service AS service_code,
       s.[mode] AS mode_code,
       s.serviceName AS service_name,
       s.modeName AS mode_name,
       s.[type] AS service_type,
       s.[status] AS service_status,
       DATALENGTH(s.definition) AS definition_bytes,
       link.fkt130_Init_Timing_Service AS variant_timing_id,
       s.fkt130_Init_Timing_Service_Default AS default_timing_id
FROM dbo.T110_Service_EcuVariant AS link
JOIN dbo.T111_Service AS s ON s.id=link.fkT111_Service
LEFT JOIN dbo.T122_Protocol AS p ON p.id=s.fkT122_Protocol
WHERE link.fkT100_EcuVariant IN (529,2725,3044,2055)
  AND s.[service]='22'
ORDER BY link.fkT100_EcuVariant,s.id;

PRINT 'B3A295_CEM529_DIRECT_IDENT_ROOTS';
SELECT TOP (100)
       root.SortOrder AS sort_order,
       root.fkT141_Block_Child AS root_id,
       b.[name] AS root_name,
       bt.identifier AS root_type,
       dt.[name] AS root_data_type,
       b.[offset] AS stored_offset,
       b.[length] AS stored_length,
       (SELECT COUNT_BIG(*)
        FROM dbo.T144_BlockChild AS child
        WHERE child.fkT100_EcuVariant=529
          AND child.fkT141_Block_Parent=root.fkT141_Block_Child) AS child_count,
       (SELECT COUNT_BIG(*)
        FROM dbo.T150_BlockValue AS bv
        WHERE bv.fkT141_Block=root.fkT141_Block_Child) AS block_value_row_count
FROM dbo.T144_BlockChild AS root
JOIN dbo.T141_Block AS b ON b.id=root.fkT141_Block_Child
LEFT JOIN dbo.T142_BlockType AS bt ON bt.id=b.fkT142_BlockType
LEFT JOIN dbo.T143_BlockDataType AS dt ON dt.id=b.fkT143_BlockDataType
WHERE root.fkT100_EcuVariant=529
  AND root.fkT141_Block_Parent=1
  AND (b.[name] LIKE 'F0%' OR b.[name] LIKE 'F5%'
    OR b.[name] LIKE 'F7%' OR b.[name] LIKE 'F8%'
    OR b.[name] LIKE '%Hardware%' OR b.[name] LIKE '%Diagnostic%'
    OR b.[name] LIKE '%Software%' OR b.[name] LIKE '%Serial%')
ORDER BY root.SortOrder,root.fkT141_Block_Child;

PRINT 'B3A295_CEM529_IDENT_CHILD_METADATA';
SELECT TOP (100)
       e.fkT141_Block_Parent AS root_id,
       parent.[name] AS root_name,
       e.SortOrder AS child_order,
       e.fkT141_Block_Child AS child_id,
       child.[name] AS child_name,
       dt.[name] AS data_type_name,
       child.[offset] AS stored_offset,
       child.[length] AS stored_length
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS parent ON parent.id=e.fkT141_Block_Parent
JOIN dbo.T141_Block AS child ON child.id=e.fkT141_Block_Child
LEFT JOIN dbo.T143_BlockDataType AS dt ON dt.id=child.fkT143_BlockDataType
WHERE e.fkT100_EcuVariant=529
  AND e.fkT141_Block_Parent IN (293990,294031,294033,294035)
ORDER BY e.fkT141_Block_Parent,e.SortOrder;

PRINT 'B3A295_29BIT_ECU802_COMPARISON_IDENT_ROOTS';
SELECT TOP (120)
       e.fkT100_EcuVariant AS variant_id,
       e.fkT141_Block_Child AS root_id,
       b.[name] AS root_name,
       b.[length] AS stored_length,
       b.fkT143_BlockDataType AS stored_data_type
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS b ON b.id=e.fkT141_Block_Child
WHERE e.fkT100_EcuVariant IN (529,2725,3044)
  AND e.fkT141_Block_Parent=1
  AND (b.[name] LIKE 'F0%' OR b.[name] LIKE 'F5%'
    OR b.[name] LIKE 'F7%' OR b.[name] LIKE 'F8%'
    OR b.[name] LIKE '%Hardware%' OR b.[name] LIKE '%Diagnostic%'
    OR b.[name] LIKE '%Software%' OR b.[name] LIKE '%Serial%')
ORDER BY e.fkT100_EcuVariant,e.fkT141_Block_Child;

PRINT 'B3A295_CEM529_NAMED_F1XX_BLOCK_EDGES';
SELECT TOP (100)
       e.fkT141_Block_Parent AS parent_id,
       parent.[name] AS parent_name,
       e.fkT141_Block_Child AS child_id,
       child.[name] AS child_name
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS parent ON parent.id=e.fkT141_Block_Parent
JOIN dbo.T141_Block AS child ON child.id=e.fkT141_Block_Child
WHERE e.fkT100_EcuVariant=529
  AND (parent.[name] LIKE '%F110%' OR parent.[name] LIKE '%F114%' OR parent.[name] LIKE '%F106%'
    OR child.[name] LIKE '%F110%' OR child.[name] LIKE '%F114%' OR child.[name] LIKE '%F106%')
ORDER BY e.fkT141_Block_Parent,e.fkT141_Block_Child;

PRINT 'B3A295_READ_ONLY_COMPLETE';
