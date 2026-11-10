# VIDA ReadVinComponent: original DLL implementation and transport call boundaries (2026-11-10)

## Evidence provenance

Owner-private 6-member ZIP \`VIDA-ReadVIN-component-locator.zip\`: integrity
verified with zero corrupted entries. The original owner scan covered **146 DLLs**,
reported 20 files matching broad names, and 2 containing the literal
\`ReadVinComponent\`, with no read errors. Both private original DLL copies
passed SHA256 verification against the owner source manifest.

- Original \`BizServices.Scripting.DLL\` **471,040 bytes**, SHA256
  \`D93B61B7B7524942649FD534303735DD4390AF6FFEE848B82E91C8E47EB5E028\`.
  .NET metadata **defines**
  \`Vcc.Vida.DiagSwdl.BizServices.Scripting.Components.ReadVinComponent\`
  (TypeDef **132**, methods 1059–1062).
- \`ResourceManager.DLL\` **921,600 bytes**, SHA256
  \`8B40B9676574ADD979F62D355BAAA3939600B23E40034B9DC14A41EDF7BDF7E6\`.
  It contains the text \`ReadVinComponent\` but **does not define that type**:
  the binary-string scan alone was not sufficient evidence of implementation.

Original DLLs, proprietary XML, SQL export rows and full bytecode
disassembly remain owner-private; this GitHub document contains only
evidence-derived technical findings, no vendor binary or raw SQL body.

## Confirmed original ReadVinComponent IL

\`ReadVinComponent.PropertySetup\` (MethodDef **1060**) declares
\`CanHiSpeedValue\`, \`UseRelay\`, \`BusId\`, \`Identifier\`, and
sets the ECU selection \`Mode\` to \`EcuVariant\`.
\`ReadVinComponent.Execute\` (MethodDef **1062**, 114 IL bytes) performs:

1. Read original \`CanHiSpeedValue\` and \`UseRelay\` properties.
2. Call \`VehCommBase.setupVehComm()\` (MethodDef **1053**) and obtain
   a \`DiagnosticVehCommService\`.
3. Call \`DiagnosticVehCommService.AddParameter("Identifier", exact XML Identifier)\`.
4. Call \`DiagnosticVehCommService.SetupTester(CanHiSpeedValue, UseRelay)\`.
5. Call \`VehCommBase.executeService()\` (MethodDef **1056**).

No direct J2534 function call, arbitration ID, or hardcoded VIN
identifier is present in this \`Execute\` body.

\`VehCommBase.setupVehComm\` switches by \`EcuMode\`:
\`EcuAddress\` -> \`CreateFromEcuAddress\`;
\`EcuType\` -> \`CreateFromEcuType\`;
\`EcuVariant\` -> \`CreateFromEcuVariant\`.
Rechecked original owner-private \`ReadVin\` XML:
**all seven ReadVinComponent nodes specify \`Mode=EcuVariant\`**.
The \`EcuAddress=64\` original property of \`NO_RELAY40B9FB\`
does **not select the address-mode branch**, and \`BusId\` is declared
but not directly read by the examined \`Execute/setupVehComm/executeService\`
methods. Do not interpret XML \`BusId\` or \`EcuAddress\` as established
physical J2534 CAN identifiers.

## Exact ECU resolution and request pipeline from previously owner-provided DLLs

From original \`BizServices.VehicleCommProvider.DLL\` and
\`BizServices.CarCom.DB.DLL\` already separately examined and SHA256-verified:

- \`DiagnosticVehCommServiceProvider.CreateFromEcuVariant\`
  (MethodDef **122**) calls \`getEcuVariantId(0, ecuVariantString)\`,
  then \`getEcuInitConfigForVariant\`, \`ensureAccess\` and service construction.
- \`getEcuVariantId\` (#**128**) calls \`ICarComRepository.GetEcuId\`.
  \`CarComRepository.GetEcuId\` (#**49**) invokes original SQL stored
  procedure **\`general_GetEcuId\`** with **\`@ecuIdentifier\`**,
  caches the result and returns a numeric variant ID. If the lookup
  fails, the service provider attempts profile-specific default
  ECU resolution, which is not proof it succeeds with EMPTYPROFILE.
- \`DiagnosticVehCommService.AddParameter\` (#**148**) calls
  \`VehicleService.SetParameter\`.
  \`DiagnosticVehCommService.Execute\` (#**155**) calls
  \`VehicleService.GetRequestHandler\`,
  \`RequestHandler.GetRequest\`, constructs
  \`RequestDataVO\`, then goes through
  \`IDiagnosticConnection.SendData\` and
  \`VehicleService.ParseResponse\`.
- \`VehCommBase.executeService\` (#**1056**) dispatches
  \`OnPositiveResponse\` and relevant error events to the XML
  graph; absent/negative/no-contact behavior cannot be mapped
  to real traces without a runtime observation.

The original script's seven node values are retained exactly
in owner-local evidence; the six distinct strings that need
\`general_GetEcuId\` verification are:
\`30728270 AA\`,
\`09469693  A\`,
\`08666792  F\`,
\`9451570\`,
\`30887708  A\`,
\`30887707  C\`.
Original internal whitespace is significant and preserved.

## J2534 bridge settings established statically

In the previously original \`VehCom2.DLL\`:

- \`DiagnosticConnection.SetupTester\` (#**140**) constructs
  \`CommToolSettings\` with
  \`CanMsBaudrate=125000\`,
  \`CanHsBaudrate=CanHiSpeedValue\`,
  \`UseRelay=UseRelay\`, \`ConnectionType=0\`.
- \`J2534.DiagConnection.SetupCommTool\` (#**399**) disconnects
  and applies these speed/relay settings to \`DiagAppConnection\`.
- \`Send_GGD\` (#**392**) checks CAN-MS eligibility and chooses
  active HS/MS baudrate based on the init provider bus, then
  \`DiagAppConnection.Send\`.
- \`Send_D2onCan\` (#**393**) likewise checks CAN-MS and has an
  explicit \`IsInvokedByReadVinScript\` condition. The actual
  implementation of that named helper (#**397**) is **only**
  \`ICommToolSettingsResolver.GetCommToolSettings() == null\`,
  not a comparison against \`ScriptType.ReadVin\`.
  When true, it obtains speed from active \`DiagAppConnection\`;
  otherwise from current settings. Whether the condition is
  satisfied for the owner runtime is **not tested**.
- The CAN-MS eligibility probe at 125 kbps identified earlier
  and the readout operation's own HS/relay settings are
  **different mechanisms**.

No on-wire request IDs, ISO-TP frames or physical CAN speeds are
claimed from these properties.

## Next owner-only verification

A SELECT-only owner-local extractor was prepared (not VM-tested) to
look up each original variant in \`CarCom.T100_EcuVariant\`, check
service relationships in \`T110_Service_EcuVariant\` for services
2/9/100, and read the exact \`general_GetEcuId\` SQL definition
through \`sys.sql_modules\` **without invoking it**. It also copies
only \`BizServices.CarCom.VehicleServices.DLL\` if present,
to analyze request serialization / response parsing locally.

**Still NOT TESTED:** actual \`general_GetEcuId\` execution;
runtime selection of a specific ECU; source binary request
serialization by \`VehicleService\`; owner VIDA ReadVin acceptance,
J2534 emulation acceptance, physical J2534 and exact-head CI.
No merge or release is claimed.
