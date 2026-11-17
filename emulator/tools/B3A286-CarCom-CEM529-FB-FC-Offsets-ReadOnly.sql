-- B3A286: CEM 529 original CarCom B9FB payload field map / FC offset-gap study.
-- Only reads table names, keys, offsets, lengths and data-type labels.
-- No ECU writes, SQL DML, VIN, T150.CompareValue, or T111.definition contents.
-- CarCom stored lengths may be in bits, but are kept unconverted below.
SET NOCOUNT ON;

PRINT 'B3A286_FB_FIELD_MAP';
SELECT edge.SortOrder AS sort_order,
       edge.fkT141_Block_Child AS block_id,
       child.[name] AS field_name,
       child.fkT142_BlockType AS block_type,
       bt.identifier AS block_type_label,
       child.fkT143_BlockDataType AS data_type,
       dt.[name] AS data_type_label,
       child.[offset] AS stored_offset,
       child.[length] AS stored_length,
       CONVERT(bigint,child.[offset])+CONVERT(bigint,child.[length]) AS stored_end
FROM dbo.T144_BlockChild AS edge
JOIN dbo.T141_Block AS child ON child.id=edge.fkT141_Block_Child
LEFT JOIN dbo.T142_BlockType AS bt ON bt.id=child.fkT142_BlockType
LEFT JOIN dbo.T143_BlockDataType AS dt ON dt.id=child.fkT143_BlockDataType
WHERE edge.fkT100_EcuVariant=529
  AND edge.fkT141_Block_Parent=293992
ORDER BY edge.SortOrder,edge.fkT141_Block_Child;

PRINT 'B3A286_FB_FIELD_SPAN';
SELECT COUNT_BIG(*) AS field_count,
       COUNT(DISTINCT child.[offset]) AS distinct_offsets,
       MIN(child.[offset]) AS min_stored_offset,
       MAX(CONVERT(bigint,child.[offset])+CONVERT(bigint,child.[length])) AS max_stored_end,
       SUM(CONVERT(bigint,child.[length])) AS sum_stored_lengths
FROM dbo.T144_BlockChild AS edge
JOIN dbo.T141_Block AS child ON child.id=edge.fkT141_Block_Child
WHERE edge.fkT100_EcuVariant=529
  AND edge.fkT141_Block_Parent=293992;

PRINT 'B3A286_F0_CHILD_MAP';
SELECT edge.fkT141_Block_Parent AS parent_id,
       edge.fkT141_Block_Child AS child_id,
       child.[name] AS child_name,
       child.fkT143_BlockDataType AS data_type,
       child.[offset] AS stored_offset,
       child.[length] AS stored_length
FROM dbo.T144_BlockChild AS edge
JOIN dbo.T141_Block AS child ON child.id=edge.fkT141_Block_Child
WHERE edge.fkT100_EcuVariant=529
  AND edge.fkT141_Block_Parent IN (293990,294035)
ORDER BY edge.fkT141_Block_Parent,edge.SortOrder;

PRINT 'B3A286_FC_EXPECTED_8_UNIT_SLOTS';
-- If the stated [16..1032] span were consecutive 8-unit fields, there
-- would be 128 slots. Print only exceptions (zero or duplicate fields).
;WITH Slots AS (
    SELECT CONVERT(int,16) AS stored_offset
    UNION ALL
    SELECT stored_offset+8
    FROM Slots WHERE stored_offset<1032
)
SELECT Slots.stored_offset,
       COALESCE(actual.actual_fields_at_offset,CONVERT(bigint,0)) AS actual_fields_at_offset
FROM Slots
LEFT JOIN (
    SELECT field.[offset] AS stored_offset,
           COUNT_BIG(*) AS actual_fields_at_offset
    FROM dbo.T144_BlockChild AS edge
    JOIN dbo.T141_Block AS field ON field.id=edge.fkT141_Block_Child
    WHERE edge.fkT100_EcuVariant=529 AND edge.fkT141_Block_Parent=293867
    GROUP BY field.[offset]
) AS actual ON actual.stored_offset=Slots.stored_offset
WHERE COALESCE(actual.actual_fields_at_offset,0)<>1
ORDER BY Slots.stored_offset
OPTION (MAXRECURSION 256);

PRINT 'B3A286_FC_OFFGRID_OR_NON8_FIELDS';
SELECT TOP (50)
       edge.SortOrder AS sort_order,
       edge.fkT141_Block_Child AS block_id,
       field.[name] AS field_name,
       field.[offset] AS stored_offset,
       field.[length] AS stored_length
FROM dbo.T144_BlockChild AS edge
JOIN dbo.T141_Block AS field ON field.id=edge.fkT141_Block_Child
WHERE edge.fkT100_EcuVariant=529 AND edge.fkT141_Block_Parent=293867
 AND (field.[offset]<16 OR field.[offset]>1032
      OR ((field.[offset]-16)%8)<>0
      OR field.[length]<>8)
ORDER BY edge.SortOrder;

PRINT 'B3A286_READ_ONLY_COMPLETE';
