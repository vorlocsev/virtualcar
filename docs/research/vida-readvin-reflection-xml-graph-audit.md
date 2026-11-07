# VIDA 2014D-derived offline 2015A: identity method event graph

2026-11-07. Scope: original-source IL research and a **privacy-constrained
read-only local XML graph inspector**. This does not claim that the
owner's installed `DiagSwdlRepository` returned an XML script or that
a VIN was read or accepted from an XC90 V8 MY2009.

## Original .NET mechanism: reflective event handlers, not a direct CEM-to-VIN call

Two original, locally inspected unmodified assemblies:

| Private original source | SHA-256 |
| --- | --- |
| `BizServices.Scripting.DLL` | `d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028` |
| `AppServices.Scripting.DLL` | `c5f092eddceac8b9eb583fb9a54536d482402a64797bd3597fd0cc6b387f3b7f` |

The inspected IL provides this **mechanism**, not a confirmed
runtime event or a copy of proprietary script content:

1. `RunScriptService.RunIdentifyVehicleScript` invokes
   `ScriptType.ReadVin=4` with an empty vehicle profile,
   then `IScriptEngine.RunScript` and `GetOutput`.
2. `Script.Parse` (MethodDef `0x0600066D`) builds
   nodes and event/property handlers. The original parser
   uses structural XML selectors `nodes/node`,
   `handlers/eventhandler` and `handlers/propertyhandler`.
   The node parser reads the `nodeid` attribute and the
   outer parser resolves each node's `class`.
3. `ScriptEventHandler.Parse` (`0x060006A0`) reads
   handler attributes `node` and `name`, then child
   `call` records. `EventHandlerCall.Parse`
   (`0x06000599`) reads `node`, `method`,
   `disabled`, and nested `parameter` elements.
4. `ScriptNode.GetMethods` (`0x0600008B`) uses
   `System.Type.GetMethods` and method attribute
   metadata to register callable methods. The callback
   (`0x06000074`) resolves the event handler's
   target node and method, then invokes
   `System.Type.GetMethod` and
   **`System.Reflection.MethodBase.Invoke`**.
5. `ScriptEngine.GetOutput` (`0x0600068B`) delegates
   to `Script.get_Output` (`0x06000637`), which looks
   up the special **`Output`** node in the script's
   node collection. The script node need not itself be
   the vehicle identity output type.
6. `VehicleIdentityOutput.AddVIN` and
   `SetX40Serial` are exposed as component methods.
   `ReadVinComponent.Execute` does **not directly**
   call them. Their invocation can be driven by
   script event graph links through reflection.

### Causal boundary

The mechanism explains why a static search found no direct
production `AddVIN` caller: the .NET engine can call methods
through an XML-defined event graph, by name. It **does not prove**
that the actual selected ReadVin XML contains an
`AddVIN` or `SetX40Serial` edge, which event fires,
which CAN response supplies its parameter, or that the
returned identity is valid.

The original `VehicleIdentityOutput` stores a shared
identity string with a separate `IsX40` boolean.
Consequently a script declaration to write the string
is **not** proof of accepted VIN or ECU identification.

## Eight independent local source-only checks

Executed against original SHA-pinned binaries with bounded
method-token inspection, **8/8 PASS**:

1. Both original DLL hashes.
2. Script XML node and event-handler factory path.
3. Event-handler records construct call entries.
4. Event calls parse target, method and argument records.
5. Method discovery uses reflection and attribute metadata.
6. Callback looks up a target node and invokes a method
   through `MethodBase.Invoke`.
7. `ScriptEngine.GetOutput` resolves the special output
   script node.
8. The identity output setters exist separately from
   `ReadVinComponent.Execute`.

No original binary, XML, SQL, CAN payload, VIN or
original user/device identifier was copied to GitHub.
These checks did **not** execute VIDA, SQL, J2534 or an ECU.

## Offline categorical XML graph inspector

File: `emulator/tools/audit_vida_readvin_xml_graph.py`.

It only accepts **one authorized local UTF-8 XML file**
with `<script>` root. The importer reads the structural
nodes and event-call declarations derived from the above
original method metadata; the code is original and
does not embed original VIDA script content.

The resulting JSON contains only counts of nodes,
handlers, declared calls and **candidate** identity
edges `AddVIN` or `SetX40Serial`, including:
missing/ambiguous target, a direct ReadVinComponent
source, disabled literal `true/1`, not-disabled literal
`false/0`, missing disabled attribute, or unknown literal.
It never writes XML text, script IDs, node IDs, VIN,
parameter values, source paths or device metadata.

**Important:** even an undisabled `AddVIN` declaration
**is not proof that the callback ever executed**.
Every runtime selection, callback, identity and
XC90 acceptance flag remains `false`.

Safety: max 2 MiB input, 20,000 XML elements,
96 levels deep, no DOCTYPE/ENTITY, reject UTF-16
for fail-closed scanning, reject missing/duplicate
node IDs and symlink source, refuse overwrite
of output and refuse writing private report
under the repository. The tool cannot alter VIDA
or invoke diagnostic code.

### Local use (only after obtaining authorized XML)

From the repository root:

```powershell
py -3 emulator/tools/audit_vida_readvin_xml_graph.py `
  "C:\VIDA-private\ReadVin-original.xml" `
  --output "C:\VIDA-private\ReadVin-graph-summary.json"
```

Treat both input and resulting private summary as sensitive
until locally reviewed. Do not upload original XML.
The tool is **not** an XML extraction utility.

## Eight synthetic regression tests

`emulator/tests/test_audit_vida_readvin_xml_graph.py`:
declared VIN edge without acceptance; X40 and
disabled handling; unknown/missing disabled values;
wrong target; duplicate/missing node ID; DTD and
entity rejection; bounded structure/size;
CLI redaction and exclusive-write/symlink guard.

**8/8 local synthetic tests PASS** in a separate
working directory. This is not an end-to-end
Windows/SQL/VIDA test.

Expected full Python suite becomes **308** after
previous exact-VM-verified **300** + eight tests.
Feature source must pass trusted manual Windows
VMware **at its exact HEAD SHA** before merge.
No release may be published from this research.

## Missing real evidence

The actual selected `DiagSwdlRepository.GetScript(ReadVin=4)`
XML has **not** been obtained. Therefore the XML graph tool
has only been exercised on **synthetic** specimens.
Even if the real XML contains a link, a continuous
same-session trace of callback execution and the
client-side VIN/X40 result remains necessary.
The CEM's accepted VIN and separate alive ECU list
for XC90 V8 MY2009 are still **unknown**.

No changes to emulated CEM replies, J2534 DLL,
SecurityAccess, PIN or programming functions.
