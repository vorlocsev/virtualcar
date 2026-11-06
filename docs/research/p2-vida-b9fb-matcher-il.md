# Stage 46 | VIDA 2015A D2 B9FB matcher IL evidence (read-only)

## Source provenance and scope
Original .NET assemblies were inspected **without execution** in the user's connected Drive directory `ai/VirtualCar/Distributions/VIDA/jboss/standalone/deployments/VidaEar.ear/VidaWeb.war/Diagnostics`:

- `BizServices.DroResultFileProducer.DLL`, 65,536 bytes, SHA-256 `99ab19223e14a06cf633e28a3017f2ed41fd52a2e34c3010f9f925a67fd8a307`.
- `VehCom2.DLL`, 266,240 bytes, SHA-256 `3a08f5ff5819396e676eac8751fdb57475e8f76e20488926259993674ec97e82`.

Neither DLL nor its real embedded B9FB answer bytes or source/private identifiers are checked into GitHub. The IL references below apply to **these precise binaries**, not every VIDA version.

## 1. Vehicle-information label is not a client acceptance predicate

`BizServices.DroResultFileProducer.DLL`:
- MethodDef `0x0600004E`, `DroTest.TestWithB9FB`: loads `B9FB` and one embedded `F9FB...` test reply via `createLogItem`, builds a test ECU list with target `0x50`, then calls `IResultFileProducer.Produce`. This is a **DRO report producer unit test**, not a successful car-connection capture.
- MethodDef `0x06000056`, `VehicleServiceInterpreter.getRequestType`: compares `String.StartsWith("B9FB")` and yields request enum `17`, named `D2_VEHICLE_INFORMATION`.
- MethodDef `0x06000057`, `VehicleServiceInterpreter.AddParsedResponse`: switch case `17` routes to general `addD2Parameters`, using CarCom `VehicleService.ParseResponse` and generic XML parameter output. This does **not** define a universal 88-byte OEM field schema or a SectorV normal-mode gate.

The embedded `F9 FB` reply is 90 service+data bytes, of which 88 follow `F9 FB`, with a documented 6-byte binary prefix and eight CRLF-separated fields. It remains an unverified sample, **not a donor-backed XC90 V8 MY2009 ECU fixture**. See the previous [B9FB evidence note](p2-b9fb-identity-shape-audit.md).

## 2. Positive D2 B9FB matching is explicit in VehCom2 IL

`VehCom2.DLL`, original MethodDef tokens:

| Method | Evidence from IL |
|---|---|
| `0x060001C8` `D2ResponseInterpreter.get_Address` | Request address = `request[0]` |
| `0x060001C9` `get_RequestService` | Service = `request[1]` |
| `0x060001CA` `get_RequestBlockOffset` | B9 block offset = `request[2]` (if present) |
| `0x060001CB` `IsPositiveResponse` | `J2534.Data[6] == request[1] + 0x40`; for service `0xB9` **also** `Data[7] == request[2]` |
| `0x060001C2` `D2onCanApplicationDICE.ReadReply` | Checks first/single-frame response ECU at `Data[5]` against request target before using `IsPositiveResponse` |
| `0x060001C3` `ParseMultipleCanFrame` | D2 type checks, first/intermediate/last handling, continuation sequence `format & 7` and increment modulo eight |

J2534 `Data` here is the **4-byte CAN ID followed by 8-byte CAN payload**. For a target50 B9FB reply, the recognized initial CAN payload is `8F 50 F9 FB ...`. If positive service is `F9` but the echoed block offset is `FC`, it **must not** satisfy a pending `B9FB` read. A matching `F9FB` from another ECU target is rejected by the separate address check.

This matcher rule is narrower than full vehicle identity. It does not validate the VIN, model year, configuration, physical CEM variant, or client normal-mode acceptance.

## 3. Regression mapping and limits

`emulator/tests/test_vida_b9fb_match_contract.py` adds **8 purely synthetic Python test groups** against the existing `import_p2_trace.validate_response`:
1. Correct 13-frame positive echo, fabricated 88-byte zeros.
2. Correct single-frame echo for target 40 and 50.
3. Wrong B9 block offset on single-frame reply.
4. Wrong B9 block offset on multi-frame reply.
5. Wrong positive service on both formats.
6. Wrong ECU target on both formats.
7. Missing final, wrong continuation counter, premature final.
8. Mixed CAN response IDs and negative B9 preservation without positive promotion.

These tests **do not load VIDA DLLs in CI**. They check that Virtual Car's read-only importer retains selected transport boundaries established by an independently inspected original assembly. The imported data are fake and remain unapproved for ECU replay.

**Unverified:** the exact application checksum/length schema for other CEMs, the normal-mode acceptance predicate in SectorV, any physical DiCE or genuine XC90 V8 MY2009 read. `main`, Dvinholm and published Virtual Car builds must remain untouched.

Drive source: [VIDA Diagnostics](https://drive.google.com/drive/folders/1eLtPQXF7m0wRuzyAgMEnDnVs0LvoqyTC).
