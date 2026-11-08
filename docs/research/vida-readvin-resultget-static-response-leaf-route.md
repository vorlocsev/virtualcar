# VIDA P0: ResultGet as a possible response-tree-to-identity intermediary

Date: 2026-11-08. Authorized owner-provided original VIDA binaries
were inspected **statically**, without loading .NET assemblies,
running VIDA or exporting private XML/VIN/CAN data.

## Exact original assembly identities

- BizServices.Scripting.DLL SHA-256:
  `d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028`
- BizServices.CarCom.VehicleServices.DLL SHA-256:
  `1735d8ac20d63a20afe13742ea5156cce5a5328392bd3e44d9ec3cd8ae0dbd07`

## Verified static MethodDef chain in scripting assembly

| MethodDef | Static source behavior |
| --- | --- |
| `ResultGet.PropertySetup` 0x0600043D | Creates an `InValue` property of `PropertyClass.Response` (enum value 5). It can exist **without** a directly declared XML property |
| `ResultGet.Execute` 0x0600043F | Calls `ResultGet.setProperties` then a component event delegate |
| `ResultGet.setProperties` 0x06000440 | Enumerates direct extension `get` elements, reads destination `property` attribute, casts `InValue` to `ResponseComponent`, applies `getbyid` / `getbyname` child selectors with `key` attributes, calls `ResponseComponent.ToValue` in the leaf-value branch, conditionally converts to string, and writes to the named script `Property.set_Value` |
| `ResultGet.GetServiceId` 0x06000431 | Retrieves source properties for `InValue` and consults `IResponseHandler.GetServiceId` on a source node, if present |
| `ResultGet.GetRootPath` 0x06000432 | Retrieves source properties for `InValue` and consults `IResponseHandler.GetPath`, if present |

13/13 targeted original IL features checked locally against exact DLL
hashes: 2/2 PropertySetup, 2/2 Execute, 6/6 setProperties,
3/3 GetServiceId. `ResultGet.setProperties` selects response items
through internal `getSelectionValueById` / `getSelectionValueByName`.
The presence of `ResponseComponent.SelectNode` elsewhere does **not**
establish it is called directly here. Nor does a ToValue call guarantee
the returned object is a non-null VIN string.

The method set provides a **concrete possible** bridging mechanism:

```text
ReadVinComponent.Result : ResponseComponent
  -> candidate ResultGet.InValue : ResponseComponent
  -> ResultGet extension.get / getbyid or getbyname
  -> leaf ToValue (optional string conversion) -> ResultGet output property
  -> possible XML AddVIN(node=ResultGet, property=output)
```

The first source-property binding and second XML event graph route are
**not verified for the owner-selected actual VIDA ReadVin script**.
Previously collected owner-redacted XML reports only preserve the
role count of 6 other nodes, not their class names or parameter
values. Nothing in those reports establishes that ResultGet is
present, selected, connected, executed or returned a valid VIN.

## New bounded, privacy-safe candidate-route classifier

`emulator/tools/audit_vida_readvin_resultget_route.py` consumes ONE
private authorized ZIP and reuses the existing strict original-CLR
parsers from stacked PRs #188 and #189. Reports only categorical
counts; never writes original ZIP/XML, getby keys, node/property
identifiers, VIN, private path or CarCom response values.

It counts ResultGet node declarations, direct `InValue` properties,
direct extension/get output declarations, recognized ID/name selector
steps, **direct** script event calls from ReadVin to
`ResultGet.Execute`, and **direct** AddVIN/SetX40Serial parameters
referencing a ResultGet output property declared by get.
The original parser's `disabled` attribute **presence** disables
an event even if its literal string is `false`.

The boolean `candidate_route_lexically_present` requires **the same**
ResultGet node identifier at both sides of the apparent two-event
chain, plus parser-enabled call declarations. It does **not** prove
that `InValue` is bound to `ReadVinComponent.Result`, that a
diagnostic response exists, that XML event names match, or that
`MethodBase.Invoke` ran. Absence of a directly declared `InValue`
property is not a runtime failure: `PropertySetup` may create it.

Eleven synthetic regression groups protect:
- single-node candidate, no ReadVin event, unknown output, fake
  constant node match, `disabled="false"`, wrapped get,
  absent/different class, unknown keys, X40 vs VIN, private ZIP
  exclusive JSON and unrelated ResultGet node joins.

**32/32 synthetic Python tests PASS locally** (11 new + 13 property
class + 8 CLR dispatch). The exact GitHub file Git blob SHA1
matches the locally tested bytes:
`audit_vida_readvin_resultget_route.py` =
`0e6f847b591f41822b4fa7e33dc02602ed08c69c`;
`test_audit_vida_readvin_resultget_route.py` =
`29050ea379eb06e43fbdc0a6a610e7c8db128c4b`.

Windows VMware exact-head CI is **not yet run**. Original private
ReadVin ZIP is not present in this research environment and was
**not** passed through the new tool. Do not claim that ResultGet was
in the target selected XML or that SectorV recognizes XC90 V8.


## Verified third XML leg: propertyhandler / set

A second, independently bounded IL inspection of the **same original**
BizServices.Scripting.DLL (SHA-256 pinned above) established:

- `Script.Parse` MethodDef `0x0600066D` selects
  `handlers/propertyhandler` records under `script/content`.
- `ScriptPropertyHandler.Parse` `0x060006D3` reads
  the source attributes `node` and `name`, and selects
  immediate child `set` records.
- `PropertyHandlerSet.Parse` `0x06000600` reads
  target attributes `node` and `property`; **presence**
  of a `disabled` attribute disables the setter even when
  that attribute's text is `false`.
- `PropertyHandlerSet..ctor` `0x060005F7` initializes the
  setter's Enabled field to `true`.
- `ScriptNode.SetPropertyCallback` `0x06000072` resolves
  the source `(node, property)` in the collection, obtains
  `Property.get_Value`, selects matching propertyhandler
  records, tests setter Enabled and assigns the same object
  to the target `Property.set_Value`.

Five targeted original MethodDef checks **5/5 PASS** for these
method names, IL literals and target calls. The actual binary
was not executed; its private IL bytes are not in this repository.

The classifier therefore checks the additional direct XML
declaration analogous to:

~~~xml
<propertyhandler node="Reader" name="Result">
  <set node="Extractor" property="InValue"/>
</propertyhandler>
~~~

This markup is an invented **synthetic test example**, not an
extracted VIDA script or target XC90 observation. The new
`candidate_three_leg_route_with_property_binding_lexically_present`
requires, within one private XML script, **all three**:

1. A parser-enabled ReadVin event call to `ResultGet.Execute`.
2. A parser-enabled `ReadVin.Result` propertyhandler setter
   to the **same ResultGet's** `InValue`, from the **same
   ReadVin node** as the event.
3. A parser-enabled identity method call using that
   ResultGet node's declared `get` output property.

This is a strictly stronger candidate than the previous
`candidate_route_lexically_present`, which is retained as a
backward-compatible **two-event-only lexical** flag. The
three-leg check remains *declaration-only*: it cannot verify
callback ordering, an enabled event name, successful ECU
response, actual run of `ResultGet`, extracted string type
or the client's VIN acceptance.

Six additional fully synthetic regressions verify absent
propertyhandler, disabled setter (including literal false),
wrong target property, wrapped setter, mismatched source
ReadVin node and mismatched target ResultGet node. The
latest local combined suite **38/38 PASS** (17 ResultGet
+ 13 PropertyClass + 8 CLR dispatch). Local tested source
Git object hashes exactly match the updated GitHub files:

- route analyzer `5d1ca0564ef3bffff834bf75972a7b4d91b978e9`;
- ResultGet tests `d7dc19fb9f24360b3f190e1c54ce316fb5941847`.

Windows VMware CI for the updated **exact PR HEAD** has not
run. The owner's original private ReadVin ZIP was not
re-audited, so the third leg is still **unconfirmed in actual
selected VIDA XML** and the project must not generate a
fabricated CEM VIN reply.

## Original event-name wiring: stricter candidate gate (2026-11-08)

A further bounded read-only review of the owner's **same SHA-pinned**
original `BizServices.Scripting.DLL` identified the precise
event delegate names, not just arbitrary XML eventhandler node IDs:

- The original `ReadVinComponent` TypeDef extends `VehCommBase`,
  which declares public `MethodDelegate` fields
  `OnPositiveResponse` (FieldDef `0x040001B1`),
  `OnNoResponse`, `OnNoContact` and
  `OnNegativeResponse`. No duplicate event field is declared
  by `ReadVinComponent`.
- `VehCommBase.executeService` (MethodDef `0x06000420`)
  stores `Result` through `set_Result`, then invokes the
  `OnPositiveResponse` delegate along its positive response branch.
  It invokes separate delegate fields for the no-response and
  negative-response branches. This is a **static** branch observation,
  not an observed positive response in the target car.
- `ResultGet` declares public `OnGet` (FieldDef `0x040001BA`).
  Its `Execute` (MethodDef `0x0600043F`) calls
  `setProperties`, then invokes the `OnGet` delegate
  if non-null.
- `ScriptNode.GetEvents` (`0x0600008C`) registers
  reflected event fields by their **actual names**.
  `ScriptNode.CallMethodCallback` (`0x06000074`)
  looks up the script's `EventHandlerCollection` using the
  **source node ID AND callback event name**.
  `ScriptEventHandler.Parse` (`0x060006A0`)
  reads XML attributes `node` and `name`, not only node.

The earlier three-leg classifier (v1) tested a reader-to-ResultGet
event and ResultGet-to-identity event without checking the
XML `name` against actual delegate names. Old synthetic XML
omitted both event names, so it was a **false positive** for
original runtime dispatch reachability.

Schema v2 keeps the old weaker flags as explicitly incomplete
declarations, but
`candidate_three_leg_route_with_property_binding_lexically_present`
now also requires: `ReadVin.OnPositiveResponse -> ResultGet.Execute`,
the matching parser-enabled `ReadVin.Result -> ResultGet.InValue`
property setter, and `ResultGet.OnGet -> AddVIN/SetX40Serial`
from the **same ResultGet instance**. It exposes separate
`candidate_addvin_route_with_event_names_lexically_present`
and `candidate_x40_route_with_event_names_lexically_present`,
and retains `candidate_three_leg_without_event_name_validation_lexically_present`
for comparisons with legacy reports. Any of these flags are
**static XML declarations only**. An event may never fire and
a result may never be a valid VIN.

Five additional synthetic regressions check empty/missing event
names, `OnNoResponse` instead of positive response, wrong ResultGet
event, separate X40 output, and disabled positive-response call.
The new schema v2 files match locally tested Git blobs:
route analyzer `bce5293b7f4ca48f2df5ee2b6fc58cd8632b480b`,
22 route tests `6a8e660adb791ec6b3a236803944c3a2df44c01f`.
**43/43** total Python synthetic tests PASS locally
(22 route + 13 property-class + 8 CLR dispatch).

This evidence does NOT establish that the original owner-selected
ReadVin XML has this chain; the original private XML was not
reloaded here. No client VIN, CEM response, physical J2534
operation or ECU identity is thereby verified.

## Original MethodDef signature and Output-node shape gate (2026-11-08)

The earlier event-name-aware schema v2 still treated a callback with
**extra or missing arguments** as a plausible complete VIN route.
This is too permissive for the original SHA-pinned CLR implementation.

Six read-only checks were repeated against the owner's original
`BizServices.Scripting.DLL`, using **only CLR metadata and bounded
method IL**, without executing the DLL: **6/6 PASS**.

- The original DLL SHA-256 matched the pinned source.
- `ResultGet.Execute` (MethodDef `0x0600043F`) has instance
  method signature `void()`, requiring **0 direct XML parameters**.
- `VehicleIdentityOutput.AddVIN` (`0x0600037D`) has signature
  `void(System.String)`, requiring **exactly 1** direct argument.
- `VehicleIdentityOutput.SetX40Serial` (`0x0600037E`) also
  requires **exactly 1** `System.String` argument.
- `Script.get_Output` (`0x06000637`) contains a literal
  `Output` node lookup and uses `ScriptNodeCollection.Contains`
  and `ScriptNodeCollection.get_Item`. An identity-output
  component with another node ID is not the script's final
  output object.

The analyzer now has a **v3 schema** with two *additional* strong
candidate flags:
`candidate_addvin_route_arity_and_output_shape_lexically_present`
and
`candidate_x40_route_arity_and_output_shape_lexically_present`.
Each requires the existing strict event-name + propertyhandler
route, **0 direct parameters** on `ResultGet.Execute`,
**1 direct parameter** on `AddVIN`/X40 and
the output node ID literally `Output`.
Wrong arity or a differently named identity-output node makes
the strong candidate false. The weaker v2 event-name and
three-leg fields are retained unchanged as incomplete evidence.

The new checks do **not** validate the **type or content** of
the evaluated argument. A `ResultGet` leaf may be null,
non-string, wrong vehicle data or never execute; therefore
`identity_argument_string_type_verified=false`,
`vin_accepted_by_client=false` and all runtime/ECU/replay
flags remain false.

**7 new completely synthetic regressions** test a shape-matching
AddVIN route, one extra Execute parameter, two AddVIN parameters,
non-`Output` identity target, separate valid X40 route,
missing AddVIN parameter, and nested/wrapper-hidden argument.
The combined local Python suite is now **50/50 PASS**
(29 route + 13 property-class + 8 CLR dispatch).
Verified original binary metadata/IL: **6/6 PASS**.
The exact GitHub blob SHA1s of the code tested locally:
- route analyzer: `a36f3aa166c68749e4870dcb741bd80ddf33b2ce`;
- route tests: `b77000cc455bd9719f40e3cd59ae2d61f85cb8c4`.

This is NOT evidence that an original ReadVin XML was selected,
that any VIN was obtained, or that an actual XC90 V8 replied.
The private original ReadVin ZIP has not been processed in this
stage. Exact source Windows/VMware CI remains unrun; PR stays Draft.

## Source-backed ResultGet output-property registration gate (2026-11-08)

A new failure mode was found **in the prior synthetic fixture**:
it supplied an XML extension `get property="Decoded"` but no
corresponding directly declared ResultGet `<property name="Decoded"
class="String"/>`. The prior strict *event-name + arity + Output*
route therefore looked plausible even though the script's
`ResultGet.setProperties` later accesses its output through
`PropertyCollection.get_Item`. An extension `get` declaration
alone is **not** evidence the output property exists or has a
compatible type.

Original owner-private unmodified `BizServices.Scripting.DLL`
(SHA256 pinned above) was inspected again **without executing it**.
Independent targeted metadata/IL checks: **5/5 PASS**:

- `ScriptNode.Parse` MethodDef `0x06000089` has the immediate
  XML `property` selector and a property-registration path.
- `ResultGet.PropertySetup` `0x0600043D` explicitly registers
  `InValue` with `PropertyCollection.CreateOrUpdate`.
  This method alone does **not** establish registration of
  an arbitrary output key such as `Decoded`.
- `ResultGet.setProperties` `0x06000440` obtains `get`
  output property name, looks up `PropertyCollection.get_Item`
  and calls `Property.set_Value` on the selected output.
- `ResultGet.SetPath` `0x0600043C` has a separate
  `PropertyCollection.CreateOrUpdate` path. This may be
  used to register output properties dynamically in some flows;
  a missing direct XML declaration therefore must **not**
  be presented as proof of runtime impossibility.

The **v4 schema** adds two conservative, *stronger declaration-only*
flags to the previous v3 structural/arity flags:

- `candidate_addvin_route_direct_declared_string_output_lexically_present`
- `candidate_x40_route_direct_declared_string_output_lexically_present`

Both additionally require a directly declared, unique
`<property name="..."` with `class="String"` on the
**same ResultGet node**, matching the exact
`<extension><get property="...">` destination key
that the identity parameter references. A missing property,
non-String/unknown class, duplicate property name,
wrapper-only property or property registered on a different
ResultGet leaves the new strict gate **false**. The weaker
v3 flags remain present to preserve their distinct meaning.

This does **not** establish the actual argument's CLR
type, the success of `Property.set_Value`, event execution,
or VIN acceptance. Specifically, a false v4 flag means
**not statically established by a direct declared String
property**, not necessarily that VIDA cannot execute the script.

Eight additional *synthetic-only* regression groups test
missing direct property, unique String, Byte class, wrapper
placement, duplicate name, unrelated second ResultGet,
separate X40 and wrong property name. All **58/58** local
Python synthetic regressions PASS (37 ResultGet, 13
property-class, 8 original CLR dispatch).

The exact locally executed source Git blobs were committed
and verified in GitHub:

- route analyzer `af83516f1ba73a3276589c2aa91615e7867fc17e`;
- route tests `4a239f77653dbc6bfb8d3b9f041fbe100f41df65`.

Windows VMware CI for exact latest PR HEAD remains **unrun**.
No owner's original private ReadVin ZIP has been processed
by the v4 classifier. The privately collected redacted
v2/v3 reports do not contain these output property classes.
No runtime CEM/J2534 changes or compiled release.

## Next real evidence gate

Run only on an already authorized locally available original ReadVin
ZIP, keep the private input out of Git and publish only reviewed
categorical output. If ResultGet appears, next verify the origin of
`InValue` and the class of the `AddVIN` argument. A same-session
runtime capture is needed for actual request, ECU response, GetScript
selection and client VIN acceptance. The emulator keeps
`B9FBFrameCount=0`, no invented F114 replies, no PIN, unlock,
SecurityAccess, programming or firmware writes.

This is research-only. No CEM, J2534 or executable release changes.

## Original ResultGet.SetPath dynamic-registration contract (2026-11-08)

The owner's original **unmodified** Scripting and CarCom DLLs were
verified again by SHA-256, static MethodDef IL, FieldDef/Constant
metadata and CustomAttribute metadata: **10/10 targeted local
assertions PASS**. No original .NET method was executed.

Exact original `ResultGet.SetPath` MethodDef `0x0600043C`
has the CLR signature
`void(System.String, ResponsePath, ResponseNodeType)`.
Its behavior is **conditional on the third argument**:

| Original `ResponseNodeType` | Resulting `PropertyClass` |
| --- | --- |
| `Primitive = 7` | `String = 2` |
| All other values | `Response = 5` |

The enum value `Primitive=7` was confirmed independently from
the original CarCom DLL's FieldDef/Constant table, not inferred
from its field order. The first conditional branch in `SetPath`
checks this enum value, then calls `PropertyCollection.CreateOrUpdate`
with the matching PropertyClass. The method also selects or creates
an extension `get` element by its output `property` attribute
and invokes `ResponsePath.Save` to store the selection path.

**Important registration boundary:**

- `ResultGet.SetPath` is a **public** instance method, but in this
  original SHA-pinned scripting assembly it has **NO**
  `[Scriptable]` CustomAttribute.
- `ResultGet.Execute` **does** have `[Scriptable]`.
- `ScriptNode.GetMethods` (MethodDef `0x0600008B`) registers
  callable XML methods using reflected `GetCustomAttributes`
  and a `Scriptable` type check.
- No direct original call site for `ResultGet.SetPath` was found
  in the scripting assembly's examined IL. This is **not** proof
  that the method is never invoked by a separate owner application,
  compiled helper or reflection.

Consequently the previous v4 "direct XML String property" flag
is intentionally **only a conservative evidence category**.
A legitimate external `SetPath` call can create a String property
and corresponding extension get selector even when neither was
directly declared in the original XML. However, a synthetic XML
`<call node="Extractor" method="SetPath">...` declaration
**cannot prove that this non-Scriptable method was executable via
the original event-dispatch registry**.

Schema **v5** therefore preserves every v4 route flag and adds
fixed categorical counts of direct XML calls targeting ResultGet
`SetPath`, including the number with 3 direct parameters,
incorrect arity and presence-disabled declarations. None of
these calls is promoted to dynamic output registration evidence.

Fixed original-source fields in the redacted JSON report the
signature, `Primitive=7 -> String` and `other -> Response`
contract, `SetPath` absent / `Execute` present
`[Scriptable]` metadata, and **all dynamic invocation/runtime
success flags false**. No XML value, path, node key, VIN,
original DLL bytes or private source location is emitted.

**6 new synthetic regressions** cover source contract,
apparently valid 3-parameter but unregistered SetPath XML call,
wrong arity, `disabled="false"`, targeting an unrelated
component, and no extension get creation without an actual
external call. **64/64 local Python tests PASS**
(43 ResultGet route + 13 PropertyClass + 8 CLR dispatch).

Original-source-only categorical evidence report:
`virtualcar-vida-setpath-original-clr-static-v1`,
**10/10 PASS**. Exact GitHub route analyzer/test Git blob
SHA1s match locally executed bytes:

- Analyzer `454ec32fffe0fb3cd56a278b9358a7701dfcaa04`.
- Tests `1adcf46858457bb8bbe6ceba4a1ee070dbd38fed`.

No original private ReadVin XML ZIP or actual same-session
VIDA client/CEM VIN acceptance was inspected in this step.
No emulator J2534/CEM runtime or compiled release changed.
The exact updated GitHub PR HEAD still lacks Windows VMware CI.
