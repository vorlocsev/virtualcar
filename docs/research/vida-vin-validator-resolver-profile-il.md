# Offline VIDA 2014D-derived 2015A: VIN validation and SQL vehicle-profile boundary

Date: 2026-11-07. P0 discovery research. No actual diagnostic
attempt, VIN, SQL call or ECU reply was executed. The owner's
separately provided **BizServices.VehicleResolver.DLL** was
inspected *locally* using bounded CLR MethodDef/MemberRef call
inspection, with original SHA-256:
`31d107b0ca13ae22a2c2f3893c76d38550ac3ce160648d07888866ddafe46720`
(32 MethodDef rows). The proprietary binary and its IL body are
**not** committed.

## Identity string, VIN validation and vehicle profile are different gates

The previous source audit demonstrated that
`VehicleIdentityOutput.AddVIN` stores a string,
`SetX40Serial` may overwrite the same string and sets a
separate X40 flag, and `VehicleAccess.IdentifyVehicle`
constructs `VehicleIdentity(identity, !IsX40)`
after executing a ReadVin script. The actual executed
script remains unknown.

A *different original assembly*, `BizServices.VehicleResolver.DLL`,
contains a **separate** VIN-to-vehicle lookup service:

| MethodDef | Source-verified static call edges | Interpretation limit |
| --- | --- | --- |
| `0x06000015` `VehicleResolverService.ResolveVin` | Calls `VinValidator.IsValidVIN`, `ResolveOverriddenVin` and another `ResolveVin` overload | Establishes validation and alternate resolution **code paths**, not which path ran or the validator's actual rules |
| `0x06000016` `ResolveOverriddenVin` | Uses `SessionManager.ISessionManager.get_UserId`, `StoredProcedureHelper`, a SQL reader and builds vehicle value objects | A user/context-sensitive **database path exists**, but the selected overrides and actual database content are unknown |
| `0x06000017` second `ResolveVin` overload | Uses `StoredProcedureHelper`, SQL parameter setters/reader and constructs `VehicleModelVO`, `ModelYearVO`, `ComplexVehicleId`, `EngineVO`, `TransmissionVO`, `VehicleVO` | Vehicle model/year/engine/gearbox information can be returned from the resolver; no target MY2009 row has been observed |
| `0x06000019` / `0x0600001A` `ProfileFromVin` overloads | Call `ResolveVin`, `CreateVehicleProfile`, and reference `VehicleProfile.Empty` | Profile creation and empty-profile fallback are **separate** from raw VIN string receipt |
| `0x06000018` `CreateVehicleProfile` | Calls `profileFromComponents`, `String.IsNullOrEmpty`, `VehicleProfile.Empty`, constructs `VehicleProfile` and sets its `Vehicle` | No guarantee a profile is available even after a valid-looking identifier |
| `0x0600001B` `profileFromComponents` | Performs SQL lookup using composite-vehicle, engine and transmission properties; includes a `RemoveTransmission` fallback path | Profile aggregation may consider engine/transmission, but selected rows/order and correctness remain unknown |
| `0x0600001C` `GetAggregateProfileString` | Comma-separated profiles and another SQL helper/reader | More profile expansion is possible; does not prove specific ECU inventory |
| `0x0600001E` `ResolveProfile` | Condensed-profile SQL lookup, SQL reader and vehicle value-object reconstruction | This is yet another profile resolution path, not observed in a target session |

### Two strict caveats

1. The above are **direct method-call edges in the original code**.
   The *entire* sequence from `VehicleAccess.IdentifyVehicle`
   through `VehicleResolverService.ResolveVin` was **not** proven
   as one call stack or actual session. Treat it as **separate
   readiness gates**, not as one guaranteed synchronous pipeline.
2. The presence of `VinValidator.IsValidVIN` proves a validator
   is called on one code path. Its internal implementation was
   not supplied here, so no 17-character/checksum/manufacturer
   rule is claimed. Earlier `VehicleIdentity` constructor's
   CR/LF trimming is not itself equivalent to VIN validation.

## Eight local source-only regression assertions: 8/8 PASS

1. Exact private `BizServices.VehicleResolver.DLL` SHA-256.
2. `ResolveVin` references `VinValidator.IsValidVIN`.
3. `ResolveVin` includes overridden and overloaded resolver branches.
4. `ResolveOverriddenVin` references session user context and SQL reader.
5. SQL `ResolveVin` overload builds all five vehicle object categories.
6. Both `ProfileFromVin` overloads call `ResolveVin`,
   `CreateVehicleProfile` and `VehicleProfile.Empty`.
7. `CreateVehicleProfile` includes `profileFromComponents`,
   null/empty test and empty-profile alternative.
8. `profileFromComponents` consults composite vehicle,
   engine/transmission properties and a transmission fallback.

All eight were executed locally against the original DLL without
loading it into .NET or connecting to SQL. These are **static
assertions**, not test coverage of the actual VIN validator
implementation or Windows/VMware end-to-end behavior.
No source binary, tokens with proprietary data, raw log lines,
real VIN, script IDs, SQL strings or customer profile rows enter Git.

## Relevant negative evidence from an additional supplied log

A separately supplied `server.log` (1116 lines, 120357 bytes)
is primarily a **JBoss/WildFly/Undertow startup/hosting log**.
Within this bounded excerpt, there are **zero literal**
`GetScript`, `ReadVin`, `DiagSwdlRepository` or
`J2534` matches. This **does not** show that the
application never fetched a script: the trace level,
component, logging destination, session and time period
differ from the diagnostic `VIDA.log`.
Do not join these two logs as a single client execution.

The owner's original database `DiagSwdlRepository` file,
its live `GetScript` rows, and selected `ReadVin` XML
were **not found** in the currently accessible Drive
attachments (filename and indexed-text discovery only).

## Next falsifiable acceptance gates

1. An authorized **offline 2014D-derived VIDA 2015A** session
   needs to show `GetScript(ReadVin=4)` lookup, selected
   script identity and actual XML event graph *privately*.
2. Trace separately actual `ReadVinComponent` service choice,
   J2534 channel TX/RX, `VehicleIdentityOutput` result,
   the returned `IsX40` flag and any client identity acceptance.
3. If the client resolves a VIN, determine whether
   `VinValidator` and `ResolveVin` report a vehicle and
   `ProfileFromVin` produces a non-empty profile.
   Never use a database-expected ECU as proof of live ECU RX.
4. Observe alive/not-alive/not-in-config ECU sets in the
   same authorized read-only run, with model-year-specific
   configuration evidence.
5. Do not invent CEM A3/E3/A6/B9FB replies, require
   SecurityAccess/PIN, change ECU coding, upload OEM XML
   or VIN, or publish Virtual Car builds.

The audited stage establishes more **conditional code paths**.
It does not validate XC90 V8 MY2009 detection in VIDA,
SectorV, VDASH or a real DiCE/J2534 session.
