-- B3A293: original VIDA CarCom CEM 529 protocol / configuration catalog.
-- Owner-local read-only. No SQL writes, VIN, BLOB, packet data or ECU actions.
-- Goal: determine whether CarCom maps protocol 7 / CEM variant 529 to a
-- bus configuration such as candidate config 541. Do NOT infer CAN baud from
-- a raw config value unless its units and association are confirmed.
SET NOCOUNT ON;

PRINT 'B3A293_RELEVANT_OBJECT_CATALOG';
SELECT TOP (100)
       t.name AS table_name,
       c.column_id AS ordinal,
       c.name AS column_name,
       ty.name AS sql_type
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id=t.object_id
JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
WHERE t.name IN ('T100_EcuVariant','T121_Config','T122_Protocol','T123_Bus',
                 'T110_Service_EcuVariant','T111_Service')
ORDER BY t.name,c.column_id;

PRINT 'B3A293_CEM529_CONFIG_REFERENCE_COLUMNS';
SELECT TOP (100)
       t.name AS table_name,
       c.name AS column_name,
       ty.name AS sql_type
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id=t.object_id
JOIN sys.types AS ty ON ty.user_type_id=c.user_type_id
WHERE c.name IN ('fkT121_Config','fkT100_EcuVariant','fkT122_Protocol',
                 'fkT123_Bus','fkT101_Ecu','fkT130_Init')
   OR c.name LIKE '%T121_Config%'
ORDER BY t.name,c.name;

PRINT 'B3A293_CEM529_VARIANT_ROW';
IF OBJECT_ID(N'dbo.T100_EcuVariant',N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.T100_EcuVariant',N'id') IS NOT NULL
   AND COL_LENGTH(N'dbo.T100_EcuVariant',N'identifier') IS NOT NULL
   AND COL_LENGTH(N'dbo.T100_EcuVariant',N'fkT101_Ecu') IS NOT NULL
BEGIN
    SELECT TOP (1)
           id AS variant_id,
           identifier AS variant_identifier,
           fkT101_Ecu AS ecu_id
    FROM dbo.T100_EcuVariant
    WHERE id=529;
END
ELSE PRINT 'B3A293_VARIANT_ROW_SCHEMA_NOT_AVAILABLE';

PRINT 'B3A293_PROTOCOL7_ROW';
IF OBJECT_ID(N'dbo.T122_Protocol',N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.T122_Protocol',N'id') IS NOT NULL
   AND COL_LENGTH(N'dbo.T122_Protocol',N'identifier') IS NOT NULL
BEGIN
    SELECT TOP (1)
           id AS protocol_id,
           identifier AS protocol_identifier
    FROM dbo.T122_Protocol
    WHERE id=7;
END
ELSE PRINT 'B3A293_PROTOCOL_ROW_SCHEMA_NOT_AVAILABLE';

PRINT 'B3A293_CONFIG541_CANDIDATE_ROW';
IF OBJECT_ID(N'dbo.T121_Config',N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.T121_Config',N'id') IS NOT NULL
   AND COL_LENGTH(N'dbo.T121_Config',N'busRate') IS NOT NULL
   AND COL_LENGTH(N'dbo.T121_Config',N'addressSize') IS NOT NULL
   AND COL_LENGTH(N'dbo.T121_Config',N'fkT122_Protocol') IS NOT NULL
   AND COL_LENGTH(N'dbo.T121_Config',N'fkT123_Bus') IS NOT NULL
BEGIN
    SELECT TOP (1)
           id AS config_id,
           busRate AS bus_rate_stored,
           addressSize AS address_size_stored,
           fkT122_Protocol AS protocol_id,
           fkT123_Bus AS bus_id
    FROM dbo.T121_Config
    WHERE id=541;
END
ELSE PRINT 'B3A293_CONFIG541_SCHEMA_NOT_AVAILABLE';

PRINT 'B3A293_BUS_OBJECT_CATALOG';
IF OBJECT_ID(N'dbo.T123_Bus',N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.T123_Bus',N'id') IS NOT NULL
   AND COL_LENGTH(N'dbo.T123_Bus',N'identifier') IS NOT NULL
   AND OBJECT_ID(N'dbo.T121_Config',N'U') IS NOT NULL
   AND COL_LENGTH(N'dbo.T121_Config',N'fkT123_Bus') IS NOT NULL
   AND COL_LENGTH(N'dbo.T121_Config',N'id') IS NOT NULL
BEGIN
    SELECT TOP (50)
           b.id AS bus_id,
           b.identifier AS bus_identifier
    FROM dbo.T123_Bus AS b
    WHERE b.id IN (SELECT c.fkT123_Bus FROM dbo.T121_Config AS c WHERE c.id=541)
      AND OBJECT_ID(N'dbo.T121_Config',N'U') IS NOT NULL
    ORDER BY b.id;
END
ELSE PRINT 'B3A293_BUS_SCHEMA_NOT_AVAILABLE';

PRINT 'B3A293_READ_ONLY_COMPLETE';
