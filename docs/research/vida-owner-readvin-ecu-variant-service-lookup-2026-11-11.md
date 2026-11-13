# Original VIDA ReadVin ECU variant/service lookup and request assembly (2026-11-11)

**Provenance and scope:** Owner-only \`VIDA-ReadVIN-EcuVariant-Service-evidence.zip\`, 8 entries, ZIP CRC OK; all five exported-file SHA256 values matched the manifest. The source SQL export was completed read-only; a recovery script only repackaged prior files. No stored procedure, .NET assembly or J2534 transport was executed. Original vendor SQL definitions, CSV rows, and binary DLL are owner-private, not committed here.

Owner provided original \`BizServices.CarCom.VehicleServices.DLL\` (94,208 bytes, SHA256 \`1735D8AC20D63A20AFE13742EA5156CCE5A5328392BD3E44D9EC3CD8AE0DBD07\`). Managed IL inspected statically.

## Exact original per-node results

The seven \`Components.ReadVinComponent\` nodes in original owner \`ReadVin\` XML, ScriptId \`0900c8af8184c004\`, were joined independently with all seven owner-original ECU lookup rows and the nine owner-original \`T110_Service_EcuVariant\` service rows. **7/7 nodes found exactly one matching original variant and the requested service.** Six unique T100 variants occur; \`09469693  A\` occurs twice.

| Original XML NodeId | Original EcuVariant (preserve whitespace) | \`T100_EcuVariant.id\` | ECU | \`ServiceId\` | Original service/mode | Original XML Identifier |
|---|---|---:|---|---:|---|---|
| \`EuCD\` | \`30728270 AA\` | 821 | \`CEM\` GGD (T101 ECU 865) | 100 | \`22\` | \`F114\` |
| \`NO_RELAY40B9FB\` | \`09469693  A\` | 230 | \`CEM\` D2 (T101 ECU 525) | 2 | \`B9\` | \`FB\` |
| \`NO_RELAY50B9FB\` | \`08666792  F\` | 70 | \`PJB\` (T101 ECU 560) | 2 | \`B9\` | \`FB\` |
| \`WITHRELAY40B9FB\` | \`09469693  A\` | 230 | \`CEM\` D2 (T101 ECU 525) | 2 | \`B9\` | \`FB\` |
| \`WITHRELAY50B9FB\` | \`9451570\` | 714 | \`CDM\` (T101 ECU 143) | 2 | \`B9\` | \`FB\` |
| \`WITHRELAY51B9F0\` | \`30887708  A\` | 693 | \`CI\` (T101 ECU 219) | 2 | \`B9\` | \`F0\` |
| \`WITHRELAY_CI_Odo\` | \`30887707  C\` | 692 | \`CI\` (T101 ECU 219) | 9 | \`A5\` / \`01\` | \`32\` |

\`T110_Service_EcuVariant\` confirms \`ServiceId 2\` for T100 IDs 70, 230, 692, 693, 714; \`ServiceId 9\` for 692, 693, 714; \`ServiceId 100\` for 821: **9 total links**. T100 \`status\` values 0/1 were observed, but their semantic meaning was **not** established. Empty gateway ID in the seven lookup rows does not rule out gateway routing in ECU transport configuration.

Original \`dbo.general_GetEcuId(@ecuIdentifier varchar(200))\` selects the T100 numeric \`id\` by \`identifier = @ecuIdentifier\`; it **does not** return J2534/CAN identifiers or select ECU protocol configuration. All exact requested variant strings have a matching original row.

## Original RequestHandler CIL and source service definitions

Original \`BizServices.CarCom.VehicleServices.DLL\`:
- \`Data.SPService.GetService\` (MethodDef 115) obtains service/mode/definition and constructs the complete service XML representation.
- \`RequestHandler..ctor\` (MethodDef 211) reads \`<request>\` elements in XML order, seeds the Service/Mode parameters and appends hex input through \`BinaryBuffer.AddHex\` (MethodDefs 8/9).
- \`RequestHandler.GetRequest\` (MethodDef 213) returns the resulting byte array.
- \`VehicleService.GetRequestHandler\` (MethodDef 370) builds this handler; \`VehicleService.ParseResponse\` (MethodDef 371) delegates to \`ResponseHandler\`.

Original owner-carried service-definition bytes had already confirmed:
- \`ServiceId 100\`: \`Service\` 8 bits and variable-length \`Identifier\`. Input \`22\` + \`F114\` generates diagnostic application payload **\`22 F1 14\`**.
- \`ServiceId 2\`: \`Service\` 8 bits and \`Identifier\` 8 bits. Input \`B9\` + \`FB\` or \`F0\` generates **\`B9 FB\`** or **\`B9 F0\`**.
- \`ServiceId 9\` has a service listing \`A5\`, mode \`01\`, XML Identifier \`32\`, but its **original \`T111_Service.definition\` has not been obtained**. \`A5 01 32\` is a candidate, **not a proven final request serialization**.

These are diagnostic application payload bytes reconstructed from original XML and static IL; **not observed on-wire J2534/ISO-TP frames**, and no arbitration TX/RX/FUNC ID can be inferred from them.

## Next exact ECU addressing dependency

Original \`BizServices.VehicleCommProvider.DLL\`:
\`DiagnosticVehCommServiceProvider.getEcuInitConfigForVariant\` (#120) calls \`ICarComRepository.GetEcuVariantData\`, reads \`EcuVariant.ConfigIds\` and creates an \`Ecu\` object.
Original \`BizServices.CarCom.DB.DLL\`:
\`CarComRepository.GetEcuVariantData\` (#58) invokes \`vadis_GetEcuVariantData(@ecuVariantId)\`;
\`CarComRepository.GetEcuConfig\` (#51) invokes **\`vadis_GetEcuInitFromConfigId(@ecuConfigId)\`**, reading protocol, node address, bus, and **CanIdTx / CanIdRx / CanIdFunc** at returned column indices 7/8/9. Therefore next owner-only read-only extraction should inspect both original procedure definitions and resolve their exact six variants' configuration IDs and CAN addresses. The two procedures have not been executed as part of this investigation.

**Acceptance boundaries still NOT TESTED:** successful \`ensureAccess\`, actual runtime selection of any specific ECU configuration, exact CanIdTx/CanIdRx/CanIdFunc, J2534 VIN read/response, original VIDA VIN acceptance inside VMware, physical adapter, exact-head CI, merge/release. Do not label these checks Passed from catalog evidence.
