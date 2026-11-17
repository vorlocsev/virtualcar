-- B3A285: original CarCom CEM 529 structural metadata and completeness audit.
-- No SQL writes, ECU commands, BLOB payloads, CompareValue values, or VIN.
-- Read-only owner-local, execute on the already installed CarCom database.
-- This query does NOT interpret T141.length/offset units as bytes or bits.
SET NOCOUNT ON;

PRINT 'B3A285_IDENT_METAOBJECT_CATALOG';
SELECT TOP (100)
       o.name AS object_name,
       o.type_desc AS object_type,
       SCHEMA_NAME(o.schema_id) AS schema_name
FROM sys.objects AS o
WHERE o.name LIKE '%BlockMetaIDENT%' OR o.name LIKE 'T146%'
ORDER BY o.name,o.type_desc;

PRINT 'B3A285_IDENT_SYNONYMS';
SELECT TOP (100)
       s.name AS synonym_name,
       SCHEMA_NAME(s.schema_id) AS schema_name,
       s.base_object_name AS referenced_object
FROM sys.synonyms AS s
WHERE s.name LIKE '%BlockMetaIDENT%' OR s.name LIKE 'T146%'
ORDER BY s.name;

PRINT 'B3A285_VARIANT529_CEM_ROOT_BLOCKS';
SELECT TOP (100)
       e.fkT100_EcuVariant AS ecu_variant,
       e.fkT141_Block_Child AS block_id,
       b.[name] AS block_name,
       b.fkT142_BlockType AS block_type,
       b.fkT143_BlockDataType AS data_type,
       b.[offset] AS stored_offset,
       b.[length] AS stored_length,
       (SELECT COUNT_BIG(*) FROM dbo.T144_BlockChild AS child
        WHERE child.fkT100_EcuVariant=529
          AND child.fkT141_Block_Parent=e.fkT141_Block_Child) AS child_edge_count,
       (SELECT COUNT_BIG(*) FROM dbo.T150_BlockValue AS bv
        WHERE bv.fkT141_Block=e.fkT141_Block_Child) AS value_rows,
       (SELECT COUNT_BIG(*) FROM dbo.T148_BlockMetaPARA AS mp
        WHERE mp.fkT100_EcuVariant=529
          AND mp.fkT141_Block=e.fkT141_Block_Child) AS meta_para_rows
FROM dbo.T144_BlockChild AS e
JOIN dbo.T141_Block AS b ON b.id=e.fkT141_Block_Child
WHERE e.fkT100_EcuVariant=529
  AND e.fkT141_Block_Parent=1
  AND b.fkT142_BlockType=5
ORDER BY e.fkT141_Block_Child;

PRINT 'B3A285_VARIANT529_FC_CHILDREN_SUMMARY';
SELECT COUNT_BIG(*) AS fc_child_count,
       MIN(child.[offset]) AS min_offset,
       MAX(child.[offset]) AS max_offset,
       MAX(CAST(child.[offset] AS bigint)+CAST(child.[length] AS bigint)) AS max_end_offset_plus_length,
       MIN(child.[length]) AS min_length,
       MAX(child.[length]) AS max_length,
       MIN(edge.SortOrder) AS min_sort,
       MAX(edge.SortOrder) AS max_sort,
       COUNT(DISTINCT child.[offset]) AS distinct_offsets
FROM dbo.T144_BlockChild AS edge
JOIN dbo.T141_Block AS child ON child.id=edge.fkT141_Block_Child
WHERE edge.fkT100_EcuVariant=529 AND edge.fkT141_Block_Parent=293867;

PRINT 'B3A285_VARIANT529_FC_LAST_FIELDS';
SELECT TOP (35)
       edge.SortOrder AS sort_order,
       edge.fkT141_Block_Child AS block_id,
       b.[name] AS field_name,
       b.[offset] AS stored_offset,
       b.[length] AS stored_length,
       b.fkT143_BlockDataType AS stored_data_type
FROM dbo.T144_BlockChild AS edge
JOIN dbo.T141_Block AS b ON b.id=edge.fkT141_Block_Child
WHERE edge.fkT100_EcuVariant=529 AND edge.fkT141_Block_Parent=293867
ORDER BY edge.SortOrder DESC, edge.fkT141_Block_Child DESC;

PRINT 'B3A285_VARIANT529_B9FB_B9F0_FC_STRUCTURE';
SELECT parent.id AS parent_id,
       parent.[name] AS parent_name,
       parent.[length] AS parent_stored_length,
       COUNT(edge.fkT141_Block_Child) AS child_count,
       MIN(child.[offset]) AS min_child_offset,
       MAX(CAST(child.[offset] AS bigint)+CAST(child.[length] AS bigint)) AS max_child_end
FROM dbo.T141_Block AS parent
LEFT JOIN dbo.T144_BlockChild AS edge
       ON edge.fkT100_EcuVariant=529
      AND edge.fkT141_Block_Parent=parent.id
LEFT JOIN dbo.T141_Block AS child ON child.id=edge.fkT141_Block_Child
WHERE parent.id IN (293867,293990,293992,294031,294033,294035)
GROUP BY parent.id,parent.[name],parent.[length]
ORDER BY parent.id;

PRINT 'B3A285_READ_ONLY_COMPLETE';
