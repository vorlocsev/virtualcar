# VIDA P0: exact original CLR XML argument dispatch contract

Research date: 2026-11-08. Source: the owner's **original**
BizServices.Scripting.DLL, SHA-256
d93b61b7b7524942649fd534303735dd4390af6ffee848b82e91c8e47eb5e028.
The original binary was obtained from the owner's private Drive,
hash-verified and inspected **statically**. No .NET assembly, VIDA XML,
SQL procedure, car diagnostic request or ECU firmware was executed.
Do NOT copy the original DLL, IL bodies, XML, private VIN or script
identifiers into Git.

## Original verified .NET method evidence

| Original MethodDef | Verified instruction/call consequence |
| --- | --- |
| 0x0600058F EventHandlerCall..ctor | Initialises its Enabled backing field to true |
| 0x06000599 EventHandlerCall.Parse | Reads exact XML call attributes node and method; checks **presence** of disabled through XmlAttributeCollection.get_ItemOf; if present sets Enabled=false. Uses XmlNode.SelectNodes("parameter") for direct child parameters |
| 0x06000597 EventHandlerCall.get_Enabled | Reads Enabled backing field |
| 0x0600058A CallParameter.Parse | On presence of the node attribute, sets Type=0 and reads node/property; otherwise sets Type=1 and reads value/class |
| 0x06000589 CallParameter.get_Value | Constructs a Property with constant input and calls Property.get_Value |
| 0x060006A0 ScriptEventHandler.Parse | Uses XmlNode.SelectNodes("call") for direct child calls |
| 0x06000074 ScriptNode.CallMethodCallback | Tests EventHandlerCall.get_Enabled; Type=0 resolves ScriptNode.Properties[parameter.Property].Value using parameter.Node, while Type=1 takes CallParameter.get_Value; assembles arguments and calls reflection GetMethod/MethodBase.Invoke |

The statements above are **specific to this hash-pinned 2014D-derived
offline 2015A assembly**. They are not evidence of a particular
XC90 V8 MY2009 script being selected or executed.

IMPORTANT CORRECTIONS to earlier *heuristic* XML analysis:

1. A missing disabled attribute is **Enabled=true in this parser**.
   The presence of a disabled attribute sets Enabled=false,
   **including disabled="false"**. A previously described
   "absent attribute cannot imply enabled" limitation was overly
   conservative for this particular pinned original constructor.
   Enabled by parser is still NOT callback executed.
2. Attributes ref and source are not recognized as source-node
   selectors by CallParameter.Parse. It checks the actual node
   attribute's presence, even if its value is empty.
3. A parameter *without* node is the value/class constant branch.
   A parameter *with* node is node/property reference branch.
   Neither branch alone proves the actual value or type produced.
4. SelectNodes("call") and SelectNodes("parameter") are relative
   direct-child selectors. Nested or wrapper-contained copies are
   **not** automatically promoted to parsed VIDA calls/arguments.

## Tool and verification

The new emulator/tools/audit_vida_readvin_clr_dispatch.py implements
only the above original-IL XML selection rules on one **private local**
ReadVin ZIP. Original ZIP/XML is read in memory only. It emits fixed
categorical counters for reference-vs-constant parameters, direct
calls, direct children, parser Enabled defaults and unknown node
references. It emits no literal values, node IDs, VIN, XML text or
source paths. Every runtime/vehicle/ECU/replay claim stays false.

Eight fully synthetic cases in
emulator/tests/test_audit_vida_readvin_clr_dispatch.py cover
source-property reference, value/class constants, disabled attribute
presence, nested/wrapped call exclusion, direct parameter selection,
empty node branch, X40 split and ZIP/XML/privacy/exclusive-output
validation. **8/8 Python tests PASS locally at source bytes identical
to the GitHub committed blobs**. The exact new commit's owner VMware
Windows CI has not been run.

Read-only invocation after a trusted local original ZIP exists:

    py -3 emulator/tools/audit_vida_readvin_clr_dispatch.py PRIVATE-ReadVin.zip --output PRIVATE-ReadVin-IL-Dispatch.redacted.json

Keep the original input ZIP and private output outside Git. No report
alone authorizes a synthetic VIN or a CEM replay fixture.

## Relation to existing redacted evidence

Previous original-source redacted XML summaries agree on 14 nodes,
7 ReadVinComponent, 1 VehicleIdentityOutput, 27 event handlers,
27 declared call tags, 2 AddVIN + 1 SetX40Serial declarations.
Their disabled attributes were all absent, so **if** those specific
calls were parsed by this original engine, the default Enabled flag
would be true. The reports did not record whether each of the 3
argument nodes uses node/property or value/class, nor whether the
client executed the selected script. F114 lexical presence and B9FB
lexical absence in that XML remain separate from an actual CAN
request, diagnostic response and VIN acceptance.

### Next missing evidence

Run this contract-classifier on the existing private ReadVin ZIP
or obtain a separately reviewed categorical result from the owner
VM (without publishing raw ZIP/XML). Then trace which property of
the intermediary node is referenced, using only owner-authorized
local static analysis and the original Property.get_Value code.
Verify selected runtime GetScript, actual response, and VIN
validation separately. Keep B9FBFrameCount=0 and StrictRouting=1
until genuine authorized target response evidence exists.

No Virtual Car runtime code, J2534, ECU programming or release
changed in this research step.
