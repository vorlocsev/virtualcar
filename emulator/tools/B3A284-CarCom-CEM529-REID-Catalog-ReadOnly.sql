-- B3A284: inspect only original CarCom metadata for CEM EcuVariant 529.
-- Owner-local, read-only. No VIN, payload, CompareValue, T111.definition,
-- activation of diagnostics, SQL writes, or registry modifications.
-- Run: sqlcmd -S ".\VIDA" -E -C -d CarCom -l 5 -W -s "|" -w 320 -i "<this-file>"
SET NOCOUNT ON;

PRINT 'B3A284_IDENT_METADATA_CATALOG';
SELECT TOP (150)
       t.name AS table_name,
       c.column_id AS ordinal,
       c.name AS column_name,
       ty.name AS sql_type
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id=t.object_id
JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
WHERE t.name IN ('T146_BlockMetaIDENT', 'T141_Block','T144_BlockChild')
ORDER BY t.name,c.column_id;

PRINT 'B3A284_VARIANT529_EDGE_COUNTS';
SELECT COUNT_BIG(*) AS all_edges,
       COUNT(DISTINCT e.fkT141_Block_Parent) AS distinct_parents,
       COUNT(DISTINCT e.fkT141_Block_Child) AS distinct_children,
       SUM(CASE WHEN e.fkT141_Block_Parent=1 THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END) AS root_children,
       SUM(CASE WHEN c.fkT142_BlockType=5 THEN CONVERT(bigint,1) ELSE CONVERT(bigint,0) END) AS reid_child_edges
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS c ON c.id=e.fkT141_Block_Child
WHERE e.fkT100_EcuVariant=529;

PRINT 'B3A284_VARIANT529_BLOCK_TYPE_DISTRIBUTION';
SELECT TOP (50)
       c.fkT142_BlockType AS block_type,
       t.identifier AS block_type_name,
       c.fkT143_BlockDataType AS data_type,
       dt.[name] AS data_type_name,
       COUNT_BIG(*) AS linked_child_edges
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS c ON c.id=e.fkT141_Block_Child
LEFT JOIN dbo.T142_BlockType AS t ON t.id=c.fkT142_BlockType
LEFT JOIN dbo.T143_BlockDataType AS dt ON dt.id=c.fkT143_BlockDataType
WHERE e.fkT100_EcuVariant=529
GROUP BY c.fkT142_BlockType,t.identifier,c.fkT143_BlockDataType,dt.[name]
ORDER BY linked_child_edges DESC,block_type,data_type;

PRINT 'B3A284_VARIANT529_ROOT_CHILDREN';
SELECT TOP (120)
       e.fkT100_EcuVariant AS ecu_variant,
       e.fkT141_Block_Parent AS parent_id,
       e.fkT141_Block_Child AS child_id,
       e.SortOrder AS sort_order,
       c.[name] AS child_name,
       c.fkT142_BlockType AS block_type,
       bt.identifier AS block_type_name,
       c.fkT143_BlockDataType AS data_type,
       c.[offset] AS child_offset,
       c.[length] AS child_length
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS c ON c.id=e.fkT141_Block_Child
LEFT JOIN dbo.T142_BlockType AS bt ON bt.id=c.fkT142_BlockType
WHERE e.fkT100_EcuVariant=529 AND e.fkT141_Block_Parent=1
ORDER BY e.SortOrder,e.fkT141_Block_Child;

PRINT 'B3A284_VARIANT529_REID_EDGES';
SELECT TOP (150)
       e.fkT100_EcuVariant AS ecu_variant,
       e.fkT141_Block_Parent AS parent_id,
       p.[name] AS parent_name,
       e.fkT141_Block_Child AS child_id,
       c.[name] AS child_name,
       e.SortOrder AS sort_order,
       c.fkT143_BlockDataType AS child_data_type,
       c.[offset] AS child_offset,
       c.[length] AS child_length
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS p ON p.id=e.fkT141_Block_Parent
JOIN dbo.T141_Block AS c ON c.id=e.fkT141_Block_Child
WHERE e.fkT100_EcuVariant=529
  AND (p.fkT142_BlockType=5 OR c.fkT142_BlockType=5)
ORDER BY e.fkT141_Block_Parent,e.SortOrder,e.fkT141_Block_Child;

PRINT 'B3A284_VARIANT529_NAMED_ID_CANDIDATES';
SELECT TOP (100)
       e.fkT141_Block_Child AS block_id,
       c.[name] AS block_name,
       c.fkT142_BlockType AS block_type,
       c.fkT143_BlockDataType AS data_type,
       c.[length] AS block_length
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS c ON c.id=e.fkT141_Block_Child
WHERE e.fkT100_EcuVariant=529
  AND (c.[name] LIKE '%F110%' OR c.[name] LIKE '%F114%'
       OR c.[name] LIKE '%F106%' OR c.[name] LIKE '%Identification%'
       OR c.[name] LIKE '%Diagnostic Database%' OR c.[name] LIKE '%Software%')
ORDER BY e.fkT141_Block_Child;

PRINT 'B3A284_READ_ONLY_COMPLETE';
