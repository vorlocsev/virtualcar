# Offline VIDA 2014D-derived 2015A: ReadVinComponent to CarCom/D2 call boundary

Date: 2026-11-07. Research-only follow-up to
[VIDA script-selection provenance](vida-supplied-logs-2014d-session-provenance.md)
and [the earlier identity-output IL audit](vida-2015a-identity-vin-x40-ecu-states-il.md).

This note documents **original static .NET IL call topology**. It does
not run VIDA, execute XML, make requests through J2534, access an ECU,
or recover script content. Original binaries were provided privately
by the owner and are **not** included in the repository.

## Three verified original DLL source identities

| DLL | SHA-256 | Relevant class/method |
| --- | --- | --- |
| `BizServices.Scripting.DLL` | `d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028` | `Components.ReadVinComponent.Execute`, `VehCommBase` |
| `BizServices.VehicleCommProvider.DLL` | `763c26d195ee7324fd08d6da1bf7304e0090a7220c29ec46038ae695db5a82e5` | `DiagnosticVehCommService` |
| `VehCom2.DLL` | `3a08f5ff5819396e676eac8751fdb57475e8f76e20488926259993674ec97e82` | `J2534.DiagConnection.Send_D2onCan` |

The following is a **statically present call topology**, not
a proven single execution trace for any VIN or model year:

```text
ReadVinComponent.Execute                        [BizServices.Scripting]
  -> VehCommBase.setupVehComm
       -> CreateFromEcuVariant / CreateFromEcuType / CreateFromEcuAddress
  -> DiagnosticVehCommService.AddParameter
  -> DiagnosticVehCommService.SetupTester
  -> VehCommBase.executeService
       -> DiagnosticVehCommService.Execute      [VehicleCommProvider]
            -> CarCom VehicleService.GetRequestHandler
            -> RequestHandler.GetRequest
            -> DiagnosticVehCommService.execute
                 -> Ecu.AvailableEcuConfigIds / PrioritizeNewConfig
                 -> sendData
            -> buildResponseSet
            -> VehicleService.ParseResponse
       -> VehCommBase.set_Result

If selected transport is D2 on CAN:
J2534.DiagConnection.Send_D2onCan                [VehCom2]
  -> VerifyCanMsSupport
  -> IsInvokedByReadVinScript
       -> ICommToolSettingsResolver.GetCommToolSettings (comparison)
  -> conditional send path, involving HS/MS baud configuration
     or initial-provider bus/retry metadata
  -> DiagAppConnection.Send
```

### Evidence about VIN versus service execution

`ReadVinComponent.Execute` (MethodDef `0x06000426`,
114 IL bytes) has direct calls to
`setupVehComm`, `AddParameter`, `SetupTester` and
`executeService`. **It does not itself directly invoke**
`VehicleIdentityOutput.AddVIN` or `SetX40Serial`.

This does **not** mean the full script never writes VIN. The
selected XML, its branches and any subsequent script
component that interprets `VehCommBase.Result` are
**not available**. The earlier original
`VehicleIdentityOutput` result mapping remains relevant,
but it must not be attributed directly to the
`ReadVinComponent.Execute` method.

### Independent ECU route and response layers

Original `VehCommBase.setupVehComm` (MethodDef
`0x0600041D`) contains distinct calls to
`IDiagnosticVehCommServiceProvider.CreateFromEcuVariant`,
`CreateFromEcuType` and `CreateFromEcuAddress`.
The method can therefore construct diagnostics from
different kinds of input; which branch the target
2015A `ReadVin` XML selects is unverified.

Original `VehCommBase.executeService` (MethodDef
`0x06000420`) invokes `DiagnosticVehCommService.Execute`
and stores a `Result`. The latter, in original
`BizServices.VehicleCommProvider.DLL` (MethodDef
`0x0600009B`), obtains a CarCom request handler,
constructs a request, invokes the service's lower
`execute`, builds a response set and calls the
CarCom `VehicleService.ParseResponse`.

The lower `DiagnosticVehCommService.execute` (MethodDef
`0x06000096`) references
`Ecu.get_AvailableEcuConfigIds`,
`Ecu.PrioritizeNewConfig` and `sendData`.
Thus **candidate configuration selection is a
separate stage from receiving and parsing an ECU reply**.
A successful J2534 RX, a script-running log event and
the parsed VIN identity are three different
acceptance gates.

### A special D2-on-CAN path is present for ReadVin

Original `VehCom2.J2534.DiagConnection.Send_D2onCan`
(MethodDef `0x06000189`) invokes
`VerifyCanMsSupport` and
`IsInvokedByReadVinScript` before
choosing among alternative `DiagAppConnection.Send`
argument paths. These paths refer separately to
`CanHsBaudrate`, `CanMsBaudrate`, current bus
metadata, and init-provider retries.

Original `IsInvokedByReadVinScript` (MethodDef
`0x0600018D`) calls
`ICommToolSettingsResolver.GetCommToolSettings`
and compares a result. This **confirms a special-case
branch exists**, but not that it was taken in a real
session, its correct target baud, physical pin
switching capabilities, or the interpretation of the
setting for a 2009 XC90 V8.

This supports the conservative interpretation of
[public 2014D fallback observations](vida-readvin-2014d-public-fallback-chronology.md):
multiple CAN/ISO15765 transport candidates can be
attempted during vehicle identification. Their
presence is *not* an instruction to hardcode
125k/250k/500k fallback as an XC90 MY2009 route.

## Eight local original-source consistency checks: 8/8 PASS

Run locally against **unmodified private original
binaries**, using a bounded CLR metadata/IL inspector,
without running any .NET code:

1. Exact SHA-256 for all three assemblies.
2. `ReadVinComponent.Execute` has all four
   diagnostic-service setup/execution calls.
3. No direct `AddVIN`/`SetX40Serial` call in
   `ReadVinComponent.Execute`.
4. `VehCommBase.setupVehComm` contains ECU variant,
   type and address factory alternatives.
5. `VehCommBase.executeService` stores a service result.
6. `DiagnosticVehCommService.Execute` uses a CarCom
   request handler and response parser.
7. Internal `execute` contains ECU candidate-configuration
   lookup/prioritization and send step.
8. `Send_D2onCan` contains a `ReadVin`-specific
   check and HS/MS baud / retry source references.

**8/8 PASS means source call topology, not tested
runtime behavior or accepted VIN.** No original DLL,
raw IL bytes, script contents, vehicle profile, PIN,
VIN, adapter identifiers or proprietary request/response
frames were committed.

## Next authorized evidence, no fabricated replies

1. Determine which `ReadVinComponent` XML node was
   actually selected by the owner's **2014D-derived
   offline 2015A** installation, via read-only
   `GetScript(ReadVin=4)` metadata and a continuous
   authorized application log.
2. Distinguish component `Execute`, selected CarCom
   request, J2534 transport and `ParseResponse`
   outcome with *same-run evidence*. Do not emit
   original payloads into the repository.
3. Observe separately whether a later script branch
   calls `VehicleIdentityOutput.AddVIN` or
   `SetX40Serial`, and whether the resolver accepts
   the identity and enumerates actual alive ECUs.
4. Keep `ImageRepository` login problems distinct
   from `DiagSwdlRepository.GetScript`.
5. No SecurityAccess/PIN, programming, fabricated
   A3/E3/A6 responses, physical driver installation,
   publication of Virtual Car builds or claims of
   XC90 V8 MY2009 success without target evidence.
