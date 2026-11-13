# Owner VIDA 2014D: CAN-config SQL metadata + original ServiceId=9 request field order

## Source integrity and boundaries

Private owner archive \`VIDA-ReadVIN-CAN-Config-Metadata.zip\` contains **6 entries**. ZIP CRC passed, all **5/5** original file byte lengths and SHA-256 values match \`manifest.json\`; owner manifest reports \`OriginalDataAnonymized=false\`, \`ReadOnly=true\`, \`StoredProceduresExecuted=false\`. Those attributes describe the owner-local export, not independently observed execution on the VM.

The owner supplied the original bodies of \`CarCom.dbo.vadis_GetEcuVariantData(@ecuVariantId int)\` and \`CarCom.dbo.vadis_GetEcuInitFromConfigId(@ecuConfigId int)\`, original system metadata and 335-byte binary XML definition for ServiceId 9. **Original SQL source, XML bytes and CSV data are retained privately and are NOT committed.** This file records only concise analytical findings.

## CAN config source of truth (no actual CAN IDs yet)

\`vadis_GetEcuVariantData\` joins original \`T100_EcuVariant\`, \`T101_Ecu\`, \`T102_EcuType\`, \`T120_Config_EcuVariant\`, \`T121_Config\`, \`T122_Protocol\`, orders by \`Priority\`, and returns an ECU variant's candidate \`ConfigId\` and \`GatewayConfigId\`, among other fields.

\`vadis_GetEcuInitFromConfigId\` joins original \`T120_Config_EcuVariant\`, \`T121_Config\`, \`T122_Protocol\`, \`T123_Bus\`, \`T124_Net\` using \`@ecuConfigId\`. Its selected names include \`Protocol\`, \`NodeAddress\` (from \`commAddress\`), \`CanAddress\`, \`BusType\`, \`NetType\`, \`ConfigId\`, \`AddressSize\`, \`CanIdTX\`, \`CanIdRX\`, \`CanIdFunc\`, \`CanIdUUDT\`, and \`fkT121_Config_Gateway\`.

The original \`T121_Config\` metadata additionally contains \`physicalAddress\`, \`functionalAddress\`, \`priority\`, \`busRate\`, \`fkT130_Init_Diag\`, and \`fkT130_Init_Timing\`. The original SQL column types include \`canIdTX varchar(3)\`, \`canIdRX varchar(3)\`, \`canIdFunc varchar(7)\`, \`canIdUUDT varchar(508)\`: preserve leading zeros and strings, and distinguish NULL from empty.

**No actual \`T121_Config\` data rows were included in this ZIP**. Consequently, \`CanIdTX\`/\`RX\`/\`Func\`, bus selection and gateway behavior for the six original ReadVin variants remain **NOT TESTED / UNKNOWN**.

## Original ServiceId 9 definition closes request schema gap

Original \`T111_Service.definition\` for **ServiceId 9** is **335 bytes**, SHA-256 \`8A9F7CC0E52365A814677D4BEF893FA497A34BC9159A81A0D3DD051101FDC86D\`. Its binary XML defines request elements, **in exact order**:

1. \`Service\`, 8 bits.
2. \`Identifier\`, **\`type=REOFF\`**, 8 bits.
3. \`Mode\`, 8 bits.

The response defines an 8-bit \`ID9_1\` block of type \`REOFF\` and a \`Parameters\` dynamic list (type \`PARAM\`).

Previously confirmed owner-original CarCom service-link data: \`ServiceId=9\` has \`OriginalService=A5\`, \`OriginalMode=01\`. Original ScriptId \`0900c8af8184c004\` node \`WITHRELAY_CI_Odo\` has \`Identifier=32\`. Following XML order, **the expected diagnostic application payload is \`A5 32 01\`**, not the previously guessed \`A5 01 32\`. This corrects the earlier speculative ordering; exact \`REOFF\` encoding and actual sent bytes still need a request-serializer test or runtime trace. This is not evidence of J2534 frame IDs or successful VIN acceptance.

## Next owner-only read-only action

A new Windows PowerShell 5.1 **SELECT-only** collector \`VIDA-ReadVIN-CAN-Config-Rows-ReadOnly.ps1\` has been created, not run in the owner's VM. It directly queries all \`T120_Config_EcuVariant\` links and \`T121_Config\` data for **original six variant IDs: 70, 230, 692, 693, 714, 821**, retaining all config priorities; separately exports gateway-config rows and per-variant counts. It uses no stored-procedure or UDF execution, DLL execution or car connection, and saves exact original string fields plus JSON null preservation. Any exported raw SQL table contents remain owner-private and should not be uploaded to the public repository.

**Still not passed:** actual CAN IDs, config priority runtime selection, J2534-2 CAN-MS probe in virtual adapter, original VIDA VIN acceptance, physical J2534, exact-head CI, merge/release.
