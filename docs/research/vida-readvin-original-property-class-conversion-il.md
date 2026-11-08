# VIDA P0: PropertyClass conversion and ReadVin argument declaration audit

Research date: 2026-11-08. Source is the owner's authorized, unmodified
BizServices.Scripting.DLL; SHA-256
d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028.
The original DLL was inspected **statically** and was never executed.
Do not commit original DLL, XML, raw VIN, CAN frames or XML attribute values.

## Verified original .NET methods and XML selectors

- `Script.Parse` MethodDef 0x0600066D selects `script`, then its
  `content` child; from the content node, it selects `nodes/node`
  and `handlers/eventhandler`. Thus script/content/nodes is
  expected structure rather than evidence of an invalid nested graph.
- `ScriptNode.Parse` MethodDef 0x06000089 selects immediate
  `property` children of a script node.
- `Property.Parse` MethodDef 0x060005DF reads the `name`,
  `class`, `type` attributes and uses `value` with
  `Property.set_Value` (with a dedicated plotter-list branch).
- `CallParameter.Parse` MethodDef 0x0600058A uses presence of
  `node` to choose `node/property`; if absent, it chooses
  the constant `value/class` branch.
- `CallParameter.get_Value` MethodDef 0x06000589 constructs
  `Property` and returns `Property.get_Value`.
- `Property.set_Value` MethodDef 0x060005DE contains 1306 IL bytes,
  an eight-case `PropertyClass` switch, conversion and error paths.

## PropertyClass enum from original FieldDef and Constant metadata

| Integer | Original enum name | Observed conversion path |
|---|---|---|
| 0 | Int | Null/empty to 0, decimal Parse, 0x hex UInt32 helper, numeric conversions |
| 1 | Double | Null/empty to 0, decimal Parse, 0x hex UInt32 helper followed by floating conversion |
| 2 | String | Null to empty; `ToString` and Double-specific formatting paths |
| 3 | PlotterlineList | Plotter list value handling |
| 4 | Byte | Null/empty to 0, decimal Parse, 0x hex Byte helper, ToByte conversion |
| 5 | Response | Response/object assignment path |
| 6 | Parameter | Parameter object handling |
| 7 | PlotterValue | Interface-specific plotter value handling |

The names **and integer constant values** above were read from
PropertyClass FieldDef/Constant metadata, and all eight switch
case targets were independently located in original setter IL.
A conversion path's presence does **not** establish that it was
taken by the actual ReadVin script, or that the result is valid VIN.
Some failure/logging paths in original Property.set_Value can contain
source value and node identification: do not share raw VIDA logs
without privacy review.

## New safe tool

`emulator/tools/audit_vida_readvin_property_classes.py` reads a
**single private local ZIP** (via the already bounded original-IL
dispatch loader). It requires the original parser's
`script/content/nodes/node` and `handlers/eventhandler`
layout. It classifies only direct identity method calls and
direct XML argument declarations:

- A parameter with `node`: look up the referenced node's
  directly declared `property` name and report the source's
  **PropertyClass bin**. Dynamic/unfound property is reported
  as `unknown_or_missing`, not rejected as a runtime failure.
- A parameter without `node`: record the constant
  `class` enumeration bin, never its literal `value`.
- Distinguishes parser-enabled declarations (no `disabled`
  attribute) from parser-disabled declarations (attribute
  present, even if its string value is `false`).

No property content, VIN, XML text, node IDs, parameter names,
original file name or source path appears in the output.
All runtime argument evaluation, reflection execution,
selected-script, ECU identification and VIN acceptance flags
remain false.

The exact bytes of the new analyzer and eight synthetic tests
are identical to GitHub source blobs. Combined with the prior
original-IL dispatch suite, **16/16 Python synthetic tests PASS
locally**. Exact-head Windows VMware CI and a run on original
private ReadVin XML have **NOT** occurred. Keep PR Draft.

Local-only example, after a trusted original ZIP is already available:

    py -3 emulator/tools/audit_vida_readvin_property_classes.py C:\VIDA-private\ReadVin-original.zip --output C:\VIDA-private\ReadVin-property-classes.redacted.json

No fresh export or manual owner action is needed for this
research stage. Do not treat a reported `String` declaration
as proof of a VIN from a CEM response, a selected GetScript,
or a successful SectorV client identity.

## Newly verified response-object boundary (same pinned original DLL)

Further source IL inspection established a crucial type boundary:

- `ReadVinComponent.Execute` MethodDef `0x06000426` calls
  `VehCommBase.setupVehComm`, uses XML-declared `Identifier`
  as a diagnostic AddParameter, applies `CanHiSpeedValue` and
  `UseRelay` to SetupTester, then calls `VehCommBase.executeService`.
- `VehCommBase.executeService` `0x06000420` invokes the
  diagnostic service's `Execute` and stores its returned
  `ResponseComponent` through `VehCommBase.set_Result`.
- `VehCommBase.set_Result` `0x0600040B` assigns the
  `Result` property with `Property.set_Value`.
  `VehCommBase.get_Result` `0x0600040A` retrieves that property
  and performs a CLR cast to `ResponseComponent`.
- The original MethodDef signatures for
  `VehicleIdentityOutput.AddVIN` `0x0600037D` and
  `VehicleIdentityOutput.SetX40Serial` `0x0600037E` are
  both `instance void (System.String)`. Thus an unmodified
  `ReadVinComponent.Result` response object must **not** be
  interpreted as a validated VIN or a string argument.
  A subsequent parsing/conversion/selection step still needs evidence.

The analyzer adds only categorical counts for source references from
`ReadVinComponent`, direct references to its `Result` property,
whether that property has XML `class=Response` or an unresolved/
different class, and references to other/missing nodes.
Unknown XML source metadata never upgrades to VIN evidence.
No raw response or actual XML parameter values are disclosed.
Output flags fix `direct_readvin_result_to_identity_string_flow_verified=false`
and `readvin_result_is_accepted_vin=false`.

Four additional synthetics cover response-object source, other
ReadVin property, missing/mismatched XML class and missing/other
component references. One further synthetic verifies the
`System.String` identity method signature evidence is never a
claim of actual conversion. With the original eight
CLR-dispatch tests the local suite is now **21/21 PASS**
(13 property-class + 8 dispatch).
The GitHub source blobs exactly match the locally tested files:
analyzer `b2ce93fafe06612232e3fe76f1be58be26a743de`;
tests `ddaea237581a0106ff10ad24d3d5c14b49ccf856`.
This is local test evidence, **not** Windows CI of the new PR head.

## Candidate response-node-to-string operations in original CarCom

A separate original owner-provided
`BizServices.CarCom.VehicleServices.DLL` has SHA-256
`1735d8ac20d63a20afe13742ea5156cce5a5328392bd3e44d9ec3cd8ae0dbd07`.
A bounded **static-only** MethodDef review finds these possible
mechanisms, not confirmed ReadVin XML calls:

| Original MethodDef | Verified static operation |
| --- | --- |
| `ResponseComponent.SelectNode` `0x060000FB` | Splits a path on `/`; each segment selects a nested response item through `getSelectionValue`, with numeric versus name-based lookup |
| `ResponseComponent.ToValue` `0x060000FA` | Casts to `ResponseLeaf` and calls virtual `ResponseLeaf.GetValue` |
| `ResponseStringLeaf.GetValue` `0x06000122` | Returns a stored string value |
| `ResponseStringLeaf.ToString` `0x06000121` | Also returns its stored string value |

The methods provide a **possible** response tree -> leaf -> string
conversion route. They do not establish which XML intermediate node
calls them or which CarCom path addresses any XC90 VIN.

Together with the pinned original scripting DLL signatures,
`AddVIN` `0x0600037D` and `SetX40Serial` `0x0600037E`
both take one `System.String` argument, while
`VehCommBase.get_Result` returns `ResponseComponent`.
The type boundary must **not** be silently collapsed into
`VIN accepted` or an emulated CEM response.

## Next gates

1. Obtain the class-only private report if it can be produced
   through authorized existing VM data without revealing ZIP/XML.
2. Resolve intermediate property producer and runtime value
   assignment by original static IL, keeping source values private.
3. Confirm same-session ReadVin selection, diagnostic request,
   received CEM response, accepted VIN and ECU identification
   separately. Keep strict read-only emulation and no fabricated
   B9FB response from inferred XML structure.

No J2534/CEM runtime changes, PIN, SecurityAccess, programming,
or compiled Virtual Car release in this PR.
