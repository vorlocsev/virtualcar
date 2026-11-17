-- B3A282: original VIDA CarCom CEM529 / GGD F110-F106 metadata correlation.
-- Operator-only read-only SQL. No ECU interaction, no VIDA process changes.
-- Read table metadata, block references, and service definition SIZE ONLY.
-- Never extract T111_Service.definition or T150_BlockValue raw contents.
-- Expected parent database: CarCom; run with sqlcmd -d CarCom.
SET NOCOUNT ON;

PRINT 'B3A282_LINK_TABLE_COLUMNS';
SELECT t.name AS table_name,
       c.column_id AS ordinal,
       c.name AS column_name,
       ty.name AS data_type
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id=t.object_id
JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
WHERE t.name IN ('T144_BlockChild','T148_BlockMetaPARA','T150_BlockValue',
                 'T142_BlockType','T143_BlockDataType')
ORDER BY t.name,c.column_id;

PRINT 'B3A282_CEM529_READ_SERVICE22_METADATA';
SELECT v.fkT100_EcuVariant AS ecu_variant,
       s.id AS service_id,
       s.fkT122_Protocol AS protocol_id,
       s.[service] AS service_code,
       s.[mode] AS mode_code,
       DATALENGTH(s.[definition]) AS definition_bytes,
       v.fkt130_Init_Timing_Service AS variant_timing
FROM dbo.T110_Service_EcuVariant AS v
JOIN dbo.T111_Service AS s ON s.id=v.fkT111_Service
WHERE v.fkT100_EcuVariant=529 AND s.[service]='22'
ORDER BY s.id;

PRINT 'B3A282_TARGET_BLOCK_METADATA';
SELECT b.id AS block_id,
       b.fkT142_BlockType AS block_type,
       b.fkT143_BlockDataType AS data_type,
       b.[name] AS block_name,
       b.[offset] AS block_offset,
       b.[length] AS block_length,
       b.[exclude] AS excluded,
       b.[composite] AS composite
FROM dbo.T141_Block AS b
WHERE b.id IN (5055437,5055865,7956234,7983638,7991103,8083440)
ORDER BY b.id;

PRINT 'B3A282_TARGET_BLOCK_REFERENCE_COUNTS';
SELECT b.id AS block_id,
       (SELECT COUNT_BIG(*) FROM dbo.T144_BlockChild AS x
        WHERE x.fkT141_Block_Parent=b.id) AS child_edges,
       (SELECT COUNT_BIG(*) FROM dbo.T144_BlockChild AS x
        WHERE x.fkT141_Block_Child=b.id) AS parent_edges,
       (SELECT COUNT_BIG(*) FROM dbo.T148_BlockMetaPARA AS x
        WHERE x.fkT141_Block=b.id) AS meta_para_rows,
       (SELECT COUNT_BIG(*) FROM dbo.T150_BlockValue AS x
        WHERE x.fkT141_Block=b.id) AS block_value_rows
FROM dbo.T141_Block AS b
WHERE b.id IN (5055437,5055865,7956234,7983638,7991103,8083440)
ORDER BY b.id;

PRINT 'B3A282_TARGET_BLOCK_PARENT_CHILD_EDGES';
SELECT TOP (100)
       edge.fkT141_Block_Parent AS parent_id,
       parent.[name] AS parent_name,
       parent.[length] AS parent_length,
       edge.fkT141_Block_Child AS child_id,
       child.[name] AS child_name,
       child.[length] AS child_length
FROM dbo.T144_BlockChild AS edge
JOIN dbo.T141_Block AS parent ON parent.id=edge.fkT141_Block_Parent
JOIN dbo.T141_Block AS child ON child.id=edge.fkT141_Block_Child
WHERE edge.fkT141_Block_Parent IN (5055437,5055865,7956234,7983638,7991103,8083440)
   OR edge.fkT141_Block_Child IN (5055437,5055865,7956234,7983638,7991103,8083440)
ORDER BY edge.fkT141_Block_Parent,edge.fkT141_Block_Child;

PRINT 'B3A282_READ_ONLY_COMPLETE';
