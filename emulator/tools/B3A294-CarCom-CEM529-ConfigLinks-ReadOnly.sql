-- B3A294: original VIDA CarCom exact CEM 529 -> T120 -> T121 config links.
-- Owner-local, strictly read-only. No payloads, VIN, BLOBs, SQL DML, ECU commands.
-- This investigates whether candidate config 541 (GGD/500000/29) is assigned
-- to variant 529, and whether any 125000/250000 configurations are also linked.
SET NOCOUNT ON;

PRINT 'B3A294_T120_COLUMN_SCHEMA';
SELECT c.column_id AS ordinal, c.name AS column_name, ty.name AS sql_type
FROM sys.columns AS c
JOIN sys.types AS ty ON ty.user_type_id = c.user_type_id
WHERE c.object_id = OBJECT_ID(N'dbo.T120_Config_EcuVariant')
ORDER BY c.column_id;

PRINT 'B3A294_CEM529_ALL_CONFIG_LINKS';
SELECT TOP (100)
       v.fkT100_EcuVariant AS variant_id,
       ev.identifier AS variant_identifier,
       v.fkT121_Config AS config_id,
       cfg.fkT122_Protocol AS protocol_id,
       p.identifier AS protocol_identifier,
       cfg.fkT123_Bus AS bus_id,
       bus.name AS bus_name,
       cfg.busRate AS bus_rate_stored,
       cfg.addressSize AS address_size_stored,
       cfg.canIdTX AS can_id_tx,
       cfg.canIdRX AS can_id_rx,
       cfg.canIdFunc AS can_id_func,
       cfg.canIdUUDT AS can_id_uudt,
       cfg.physicalAddress AS physical_address,
       cfg.functionalAddress AS functional_address,
       cfg.canAddress AS can_address,
       cfg.commAddress AS comm_address,
       cfg.fkT121_Config_Gateway AS gateway_config_id
FROM dbo.T120_Config_EcuVariant AS v
JOIN dbo.T100_EcuVariant AS ev ON ev.id=v.fkT100_EcuVariant
JOIN dbo.T121_Config AS cfg ON cfg.id=v.fkT121_Config
LEFT JOIN dbo.T122_Protocol AS p ON p.id=cfg.fkT122_Protocol
LEFT JOIN dbo.T123_Bus AS bus ON bus.id=cfg.fkT123_Bus
WHERE v.fkT100_EcuVariant=529
ORDER BY cfg.id;

PRINT 'B3A294_VARIANT529_CONFIG_COUNTS_AND_RATES';
SELECT cfg.busRate AS bus_rate_stored,
       cfg.addressSize AS address_size_stored,
       cfg.fkT122_Protocol AS protocol_id,
       COUNT_BIG(*) AS linked_config_rows
FROM dbo.T120_Config_EcuVariant AS v
JOIN dbo.T121_Config AS cfg ON cfg.id=v.fkT121_Config
WHERE v.fkT100_EcuVariant=529
GROUP BY cfg.busRate,cfg.addressSize,cfg.fkT122_Protocol
ORDER BY cfg.busRate,cfg.addressSize,cfg.fkT122_Protocol;

PRINT 'B3A294_CONFIG541_ASSIGNED_VARIANTS';
SELECT TOP (100)
       v.fkT100_EcuVariant AS variant_id,
       ev.identifier AS variant_identifier,
       ev.fkT101_Ecu AS ecu_id,
       v.fkT121_Config AS config_id
FROM dbo.T120_Config_EcuVariant AS v
JOIN dbo.T100_EcuVariant AS ev ON ev.id=v.fkT100_EcuVariant
WHERE v.fkT121_Config=541
ORDER BY v.fkT100_EcuVariant;

PRINT 'B3A294_OTHER_VARIANTS_SAME_ECU802_CONFIGS';
SELECT TOP (120)
       ev.id AS variant_id,
       ev.identifier AS variant_identifier,
       cfg.id AS config_id,
       cfg.busRate AS bus_rate_stored,
       cfg.addressSize AS address_size_stored,
       cfg.fkT122_Protocol AS protocol_id,
       p.identifier AS protocol_identifier,
       cfg.canIdTX AS can_id_tx,
       cfg.canIdRX AS can_id_rx
FROM dbo.T100_EcuVariant AS ev
JOIN dbo.T120_Config_EcuVariant AS v ON v.fkT100_EcuVariant=ev.id
JOIN dbo.T121_Config AS cfg ON cfg.id=v.fkT121_Config
LEFT JOIN dbo.T122_Protocol AS p ON p.id=cfg.fkT122_Protocol
WHERE ev.fkT101_Ecu=802
ORDER BY ev.id,cfg.id;

PRINT 'B3A294_READ_ONLY_COMPLETE';
