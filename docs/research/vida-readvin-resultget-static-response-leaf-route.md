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
