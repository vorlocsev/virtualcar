# VIDA 2015A CarCom and gateway selection: source evidence (2026-11-07)

## Question

For a **read-only XC90 V8 MY2009 Virtual Car** test, which layer chooses
the expected CEM/ECU inventory, CAN bus, gateway and response parser?
A DiCE/J2534 transport read does not establish VIDA vehicle acceptance.
This note distinguishes the owner's original VIDA **2015A** assemblies
and XML from a separately inspected public **VIDA 2014D** research port.
It contains **no original VIDA code, private XML, VIN, ECU response,
credentials, path or data from a physical car**.

## Original VIDA 2015A evidence: STATIC, no program execution

The files below were obtained from the owner's authorized VIDA
Diagnostics directory and inspected as PE/CLR string metadata and
bounded XML. SHA-256 is retained to prevent version conflation.
Original bytes remain private and are NOT uploaded to this repository.

| Original component | SHA-256 | Observed static metadata |
| --- | --- | --- |
| components.config.xml | ec15a3aff2403730a53e64dc9df957fbca129c04060030e10a763788bb601f05 | Registers ICarComRepository, IVehicleServiceDatabase, IVehicleResolverService, IScriptProvider, IScriptEngineProvider, IDiagnosticSessionService, IVehicleInformationWF separately |
| diagnostic.config.xml | c0f5b8edba4075e43c2bd5e63d413502570522cef9e71a6dbcefb510bae89aec | AppSettings keys LogLevel, CommToolBatteryLimit, CommToolPollingFrequency; original values include LogLevel=Trace, numeric 11 and 2000, with **no verified unit or runtime application** |
| BizServices.CarCom.DB.DLL | a54117e6b2cc97c28bacf5df72f060ee8694de85291194046235bfd85a700be6 | Method names GetInitHwSettings, GetDefaultEcuVariant, GetEcuConfig, GetEcusForBus, GetBusType, GetEcuAddress, GatewayEcu, GatewayConfigId |
| BizServices.VehicleCommProvider.DLL | 763c26d195ee7324fd08d6da1bf7304e0090a7220c29ec46038ae695db5a82e5 | DiagnosticVehCommServiceProvider, GetGatewaySetting, GetGatewayConfig, get_NeedGateway, CreateEcuAddress, SetGateway; test names distinguish no gateway, gateway+CAN IDs, and gateway without CAN IDs |
| BizServices.ScriptRepository.DLL | f046b5fa3c8d3487fc05aa1140ac3c4ef1880eef5251c8c46b1c3d73f45a6bca | ScriptProvider, GetScriptsOfType, GetScript, GetValidLinksForSelected, GetFromDb, GetOneScriptFromDb, GetZippedScriptXml |
| AppServices.Scripting.DLL | c5f092eddceac8b9eb583fb9a54536d482402a64797bd3597fd0cc6b387f3b7f | RunIdentifyVehicleScript, RunEcuIdentificationScript, GetEcuIdentificationScript, GetScriptEngine, getScriptEngineNoEcuContext, GetVehCommSpecification |
| VehCom2.DLL | 3a08f5ff5819396e676eac8751fdb57475e8f76e20488926259993674ec97e82 | J2534TesterFilter, D2ResponseInterpreter, ReadReply, ParseMultipleCanFrame, BusTypeForEcu, NextBusTypeForEcu, SetGateway, IsInvokedByReadVinScript |

The original `components.config.xml` explicitly sets
`ScriptEngineProvider.TraceScript=false`. Original
`diagnostic.config.xml` has `LogLevel=Trace`. These are **two
different settings**. Their coexistence can explain why a diagnostic
log may contain method-level events but no XML script steps. It does
**not prove** which settings were applied in an actual VIDA run.
The config also references non-exported data sources and locations,
which are deliberately omitted here.

**Evidence limitation:** CLR method and test names confirm code
surface/types, not the taken branch, actual SQL procedure, XML content,
vehicle-specific gateway, authentication, live ECU, or which scripts
were selected. No implementation was executed or modified.

## Independently published VIDA 2014D research

Pinned source: [spnda/volvo_vida_db @ e2f8ee165e373360d7f7fd0e80298f68c25bc07e](https://github.com/spnda/volvo_vida_db/tree/e2f8ee165e373360d7f7fd0e80298f68c25bc07e).
The upstream repo describes its Python as a port/reconstruction
of VIDA CarCom, VehCom2 and related response handlers; it is **not
Volvo-certified** and is **not** independently tested here against
the owner's 2015A DLL implementation.

- `scripts/vin_decoder.py` uses VINDecodeModel / VINDecodeVariant
  and maps the possible vehicle to **multiple matching profiles**
  (model, year, partner group, body, engine, transmission, etc.).
  A VIN is not a complete verified ECU inventory by itself.
- `scripts/carcom.py:get_vehicle_ecus()` joins
  T161_Profile, T160_DefaultEcuVariant, T100_EcuVariant,
  T120/T121_Config, T123_Bus and T122_Protocol.
  It labels the **default ECU variants assumed before actual
  identification**, not observed answers from a vehicle.
- The same function exposes source config fields for CAN IDs,
  physical/functional/comm addresses, busRate, addressSize,
  gateway configuration and diagnostic/timing init references.
  Those fields are distinct; one CEM node address does not define
  every transport and gateway route.
- `get_hw_settings()` uses T136_InitHw_Profile with T130/T131/T132
  initialization values, including names for HS/LS baud,
  gateway/MECU address and a relay setting. It selects the
  most specific profile setting through ordered folderLevel.
  This is how the *research port* resolves an inherited set of
  source settings, **not** a measured 2009 CEM route.
- `scripts/d2.py` describes D2 requests on `0x000FFFFE`,
  D2 frame reassembly, source-derived low-bit tester CAN filtering
  on odd 29-bit response IDs and ECU target-byte/service matching.
  It lists a D8 keep-alive every four seconds as a research-derived
  session-keeper behavior. **These are protocol/context claims
  of that third-party port**; do not infer a compatible physical
  DiCE or that one RX proves vehicle identity.
- `scripts/filter_scripts.py` uses the **union of mapped scripts**
  from all selected vehicle profiles. It is not evidence that
  `RunIdentifyVehicleScript` used the same profile-dependent
  lookup before the vehicle was identified.

Source reference: the user's [Stage 47 original 2015A IL findings](vida-identity-ecu-boundary-il.md)
already established that `VehicleAccess.IdentifyVehicle`
temporarily selects an empty profile, calls the identity script,
then interprets `VehicleIdentityOutput`. VIN resolution and ECU
identification are separate. See also
[Stage 49](vida-script-profile-links-stage49.md) and
[Stage 50](vida-script-selection-stage50.md).

## Distinct observable states for a Virtual Car read-only laboratory

| VIDA layer | Current evidence | Still UNVERIFIED for XC90 V8 MY2009 |
| --- | --- | --- |
| Environment and DiCE/J2534 | DI bindings and known original .NET assemblies | That VIDA routes diagnostic reads through our virtual J2534 DLL |
| Vehicle profile | 2014D VIN-decoder and profile mapping | Target-specific 2015A selected profile keys and correct 2009 V8 match |
| Initial HW/physical network | GetInitHwSettings / gateway-related original method names | Exact 2015A selected bus, baud, gateway and filters |
| ECU inventory | 2014D default ECU config; original GetDefaultEcuVariant | Which modules actually responded |
| D2 transport | B9FB, B9F0, A6 framing/matcher evidence | Real validated CEM replies, normal mode, accepted identity |
| Identity output | Original 2015A RunIdentifyVehicleScript/VehicleIdentityOutput IL | Selected XML branch that sets AddVIN or SetX40Serial |
| ECU identification | Original separate GetEcuIdentificationScript path | Positive identity of any genuine MY2009 ECU |

**Do not equate 0x40/0x50 with LS/HS unconditionally.**
Service-tool documentation, specific captures and selected CarCom
profiles can give different meanings/contexts for these numbers.
A busRate, physical address, CAN arbitration ID and target/service
byte are independent variables. Original VIDA 2015A runtime selection
and vehicle provenance would be required to resolve the target.

## Eight next evidence gates (no writes or bypass)

1. Confirm the original DLL hashes and component bindings; do not copy proprietary binaries.
2. In an authorized local VIDA 2015A SQL instance, compare **read-only
   aggregate metadata** for T160/T121/T122/T123/T136/T161 with the
   public 2014D schema. Do not upload VIN, profile IDs, ECU identifiers,
   SQL connection data or original XML.
3. Verify how the empty-profile identity script is selected before VIN
   resolution; do not confuse it with later profile-linked scripts.
4. Record selected CAN/ISO15765, HS/LS baud and gateway presence as
   **separate categorical observations** in one private run.
5. Distinguish default ECU inventory from a received, properly matched
   positive ECU identity; no invented ECU replies.
6. Distinguish B9FB transport framing from vehicle identity output,
   resolver validity and the second ECU identification script.
7. Keep D2 physical reply CAN ID, odd-ID filter hypothesis,
   module address byte and positive echo as distinct matcher stages.
8. Require one authorized continuous redacted VIDA/DiCE/J2534
   **read-only** trace before asserting the precise MY2009 pathway.
   Absent evidence is recorded as unknown. No programming,
   A3 SecurityAccess, PIN, configuration write, firmware or releases.

Official platform/interface context:
[Volvo workshop requirements](https://workshopsupportguide.volvocars.biz/media/35358/VIDA-WS-Requirements-320EN20-en-GB.pdf):
VIDA recommends DiCE for D2/GGD diagnostics; J2534-1 is described
as supporting certain software download operations but not VIDA diagnostics.
This is not a statement that every DiCE or J2534 version behaves identically.

No change to emulated ECU responses, J2534 DLL, backend events or CI.
