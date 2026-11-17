-- B3A283: determine whether CarCom GGD F110/F106 blocks belong to CEM EcuVariant 529.
-- Read-only owner-local SQL. Prints only identifiers/metadata; never reads BLOB
-- definitions, CompareValue content, VIN, firmware or physical ECU.
-- Run against the original private CarCom with sqlcmd -d CarCom.
SET NOCOUNT ON;

PRINT 'B3A283_TARGET_BLOCK_VARIANT_EDGES';
SELECT TOP (200)
       e.fkT100_EcuVariant AS ecu_variant,
       e.fkT141_Block_Parent AS parent_id,
       p.[name] AS parent_name,
       e.fkT141_Block_Child AS child_id,
       c.[name] AS child_name,
       e.SortOrder AS sort_order
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS p ON p.id=e.fkT141_Block_Parent
JOIN dbo.T141_Block AS c ON c.id=e.fkT141_Block_Child
WHERE e.fkT141_Block_Parent IN (5055437,5055865,7956234,7983638,7991103,8083440)
   OR e.fkT141_Block_Child IN (5055437,5055865,7956234,7983638,7991103,8083440)
ORDER BY e.fkT141_Block_Child,e.fkT141_Block_Parent,e.fkT100_EcuVariant,e.SortOrder;

PRINT 'B3A283_TARGET_BLOCK_VARIANT_DISTINCT_COUNTS';
SELECT q.block_id,
       COUNT(DISTINCT q.ecu_variant) AS related_variants,
       SUM(CASE WHEN q.ecu_variant=529 THEN 1 ELSE 0 END) AS edges_variant_529,
       MIN(q.ecu_variant) AS min_variant,
       MAX(q.ecu_variant) AS max_variant
FROM (
    SELECT e.fkT141_Block_Parent AS block_id,
           e.fkT100_EcuVariant AS ecu_variant
    FROM dbo.T144_BlockChild AS e
    WHERE e.fkT141_Block_Parent IN (5055437,5055865,7956234,7983638,7991103,8083440)
    UNION ALL
    SELECT e.fkT141_Block_Child AS block_id,
           e.fkT100_EcuVariant AS ecu_variant
    FROM dbo.T144_BlockChild AS e
    WHERE e.fkT141_Block_Child IN (5055437,5055865,7956234,7983638,7991103,8083440)
) AS q
GROUP BY q.block_id
ORDER BY q.block_id;

PRINT 'B3A283_CEM529_GGD_NAMED_EDGES';
SELECT TOP (100)
       e.fkT100_EcuVariant AS ecu_variant,
       e.fkT141_Block_Parent AS parent_id,
       p.[name] AS parent_name,
       e.fkT141_Block_Child AS child_id,
       c.[name] AS child_name
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS p ON p.id=e.fkT141_Block_Parent
JOIN dbo.T141_Block AS c ON c.id=e.fkT141_Block_Child
WHERE e.fkT100_EcuVariant=529
  AND (p.[name] LIKE '%F110%' OR p.[name] LIKE '%F106%'
       OR c.[name] LIKE '%F110%' OR c.[name] LIKE '%F106%')
ORDER BY e.fkT141_Block_Parent,e.fkT141_Block_Child;

PRINT 'B3A283_BLOCK_TYPE_AND_DATA_TYPE';
SELECT 'blocktype' AS source,
       CAST(t.id AS int) AS code,
       t.identifier AS label,
       t.metaTable AS detail
FROM dbo.T142_BlockType AS t WHERE t.id=5
UNION ALL
SELECT 'datatype',
       CAST(d.id AS int),
       d.[name],
       CAST(NULL AS varchar(512))
FROM dbo.T143_BlockDataType AS d WHERE d.id=50;

PRINT 'B3A283_TARGET_BLOCK_VALUE_METADATA';
SELECT TOP (100)
       v.fkT141_Block AS block_id,
       v.Id AS value_row_id,
       v.SortOrder AS sort_order,
       v.[Operator] AS compare_operator,
       DATALENGTH(v.CompareValue) AS compare_value_bytes,
       DATALENGTH(v.altDisplayValue) AS alternate_value_bytes,
       v.fkT155_Scaling AS scaling_id
FROM dbo.T150_BlockValue AS v
WHERE v.fkT141_Block IN (5055437,5055865,7956234,7983638,7991103,8083440)
ORDER BY v.fkT141_Block,v.SortOrder,v.Id;

PRINT 'B3A283_CEM529_TARGET_META_PARA_COUNTS';
SELECT m.fkT141_Block AS block_id,
       m.fkT100_EcuVariant AS ecu_variant,
       COUNT_BIG(*) AS rows_for_variant
FROM dbo.T148_BlockMetaPARA AS m
WHERE m.fkT100_EcuVariant=529
  AND m.fkT141_Block IN (5055437,5055865,7956234,7983638,7991103,8083440)
GROUP BY m.fkT141_Block,m.fkT100_EcuVariant
ORDER BY m.fkT141_Block;

PRINT 'B3A283_READ_ONLY_COMPLETE';
