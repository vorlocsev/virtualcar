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
2. **UPDATED after acquisition of original `Util.DLL`:**
   the exact `VinValidator.IsValidVIN` static predicate is now
   independently characterized below. Its check is weaker
   than full ISO VIN semantic validation. Earlier
   `VehicleIdentity` constructor's CR/LF trimming
   remains a separate stage.

## Newly acquired original Util.DLL: actual IsValidVIN branches

The owner-provided `Util.DLL` (114688 bytes, SHA-256
`a0ef808188bab12de429fcb4467a9ceadfbfc3747cfb68580664495550ce263d`)
contains these unmodified managed methods:

| Original MethodDef | Confirmed static IL behavior |
| --- | --- |
| `0x06000278` `VinValidator.IsValidVIN` (97 IL bytes) | Returns false for null; requires `.Length == 17`; extracts `.Substring(length-6, 6)`, calls `IsValidChassisNbr`; finally accepts any one of four `.StartsWith` prefixes `YV`, `PN`, `LV`, `LY` |
| `0x06000279` `VinValidator.IsNumeric` (29 IL bytes) | Applies `Regex.Match` with pattern `\\D`; inverts whether a non-decimal match succeeded |
| `0x0600027A` `VinValidator.IsValidChassisNbr` (23 IL bytes) | Requires suffix length six and the `IsNumeric` check |

All four `StartsWith` conditional branches target the same positive
return instruction. The remaining middle positions are not validated by
**this method**, and there is **no ISO 3779 check-digit computation or
whole-VIN character-set check inside these methods**.

The .NET `String.Length` counts **UTF-16 code units**, not necessarily
Unicode grapheme clusters; `Regex \D` by default treats Unicode
decimal digits as digits. Consequently this predicate must not be
simplified to a claim that *only* ASCII digits would pass the original
runtime. `StartsWith(string)` also uses .NET's built-in string comparison;
the source check establishes the literal prefixes, not all unusual
locale/Unicode corner cases.

**Crucial distinction:** `IsValidVIN` is only a string-shape gate in
one `ResolveVin` path. It does **not** establish that the vehicle exists
in `DiagSwdlRepository` or other VIDA databases, that any CEM frame
was received, that the XML script produced a VIN, or that VIDA accepted
the XC90 V8 MY2009 profile.

### Reproducibility: two different sets of completed checks

**9/9 local original-source IL assertions PASS** over SHA-pinned
`Util.DLL` and `BizServices.VehicleResolver.DLL`:
both hashes, unique method token/body, null/length branches,
six-character substring, numeric suffix guard, `\\D` regex,
four explicit prefixes, four positive conditional branches,
and caller from `VehicleResolverService.ResolveVin`.
No original assembly was executed or committed.

Separately, `emulator/tools/vida_vin_shape_ascii.py` is a tiny
**synthetic ASCII-only approximation**, deliberately **not** integrated
into CEM/J2534 runtime. It uses 17-character length, four initial
two-letter prefixes and six trailing ASCII digits. It intentionally
rejects all non-ASCII candidates rather than claiming exact .NET
Unicode equivalence. Its `emulator/tests/test_vida_vin_shape_ascii.py`
covers eight synthetic groups: null/type, exact length, suffix,
four prefixes, other prefixes, lowercase, unconstrained middle,
non-ASCII fail-closed. **8/8 local synthetic tests PASS.**

The supplied test strings are invented synthetic placeholders,
**not actual or accepted VINs**. A true ASCII shape result is never
equivalent to `ReadVin`, `VinValidator` client execution, SQL profile
resolution or an accepted ECU. No original VIN, raw IL, SQL,
script XML or private record was added to Git.

The expected entire Python test suite becomes **324**
(previous 316 exact-VM-verified + eight), requiring a trusted Windows
VMware run on the **exact new feature SHA** before merging.

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
