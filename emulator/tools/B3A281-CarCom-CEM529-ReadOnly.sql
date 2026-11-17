-- B3A281 original VIDA CarCom schema probe, owner-local, READ ONLY.
-- Run: sqlcmd -S ".\VIDA" -E -C -d CarCom -l 5 -W -s "|" -w 320 -i "emulator\tools\B3A281-CarCom-CEM529-ReadOnly.sql"
-- No writes, no VIN/dumps, no access to image definition payload.
-- The fkT100_EcuVariant=529 CEM association is owner-provided evidence.
SET NOCOUNT ON;

PRINT 'B3A281_CEM529_SERVICE_LINK_COUNT';
SELECT COUNT_BIG(*) AS linked_rows
FROM dbo.T110_Service_EcuVariant AS v
WHERE v.fkT100_EcuVariant = 529;

PRINT 'B3A281_CEM529_SERVICES';
SELECT TOP (200)
       v.fkT100_EcuVariant AS ecu_variant,
       v.fkT111_Service AS service_link,
       s.id AS service_id,
       s.fkT122_Protocol AS protocol_id,
       s.[service] AS service_code,
       s.[mode] AS mode_code,
       s.[serviceName] AS service_name,
       s.[modeName] AS mode_name,
       s.[type] AS service_type,
       s.[status] AS service_status,
       v.fkt130_Init_Timing_Service AS variant_timing,
       s.fkt130_Init_Timing_Service_Default AS default_timing
FROM dbo.T110_Service_EcuVariant AS v
JOIN dbo.T111_Service AS s ON s.id = v.fkT111_Service
WHERE v.fkT100_EcuVariant = 529
ORDER BY s.id, v.fkt130_Init_Timing_Service;

PRINT 'B3A281_T141_REFERENCING_COLUMNS';
SELECT TOP (100)
       t.name AS table_name,
       c.name AS column_name,
       ty.name AS data_type
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id = t.object_id
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE c.name LIKE '%T141%' OR c.name LIKE '%fkBlock%'
ORDER BY t.name, c.column_id;

PRINT 'B3A281_T141_POSSIBLE_IDENTIFICATION_BLOCKS';
SELECT TOP (100)
       b.id AS block_id,
       b.fkT142_BlockType AS block_type,
       b.fkT143_BlockDataType AS data_type,
       b.[name] AS block_name,
       b.[offset] AS block_offset,
       b.[length] AS block_length,
       b.[exclude] AS excluded,
       b.[composite] AS composite
FROM dbo.T141_Block AS b
WHERE b.[name] LIKE '%F110%'
   OR b.[name] LIKE '%F114%'
   OR b.[name] LIKE '%F106%'
ORDER BY b.id;

PRINT 'B3A281_READ_ONLY_COMPLETE';
