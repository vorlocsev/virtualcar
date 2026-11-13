# Original VIDA 2014D Core/UI managed IL: static ReadVin call graph

This finding is based on original owner-private
\`VIDA-ReadVIN-dotnet-bridge.zip\` (3 ZIP entries; CRC OK).
Analysis was **static**: inspected PE/CLR metadata and CIL method
bodies as bytes, without loading or executing any owner DLL.
The owner's original DLLs and raw IL dumps are **not committed**.

## Exact installed assemblies

- \`Diagnostics\Core.DLL\`: **94,208 bytes**, SHA256
  \`F7E73E59CD64923D6BB34E17883ECCDC29FA7C47E0B22AF86FC97A32E87E7F9E\`;
  original FileVersion \`2.0.5394.27551\`.
- \`Diagnostics\UI.DLL\`: **1,388,544 bytes**, SHA256
  \`6A521808273DCDA07F09E9A5766E45BB5AE6AB70A6093D5DFEFE990FFB404BF2\`;
  original FileVersion \`2.0.5394.27572\`.
- Both are PE32/x86 managed assemblies with CLR
  metadata runtime \`v2.0.50727\`; ProductVersion
  \`2014D-r12025\`.

## Confirmed IL call graph: read request

Original \`UI.DLL\` method definitions:

1. \`Vcc.Vida.DiagSwdl.UI.CommToolSetting.ReadVin\`
   (\`MethodDef #321\`):
   - notifies \`Core.JavaEventHandle.ReadVinButtonClick\`,
     which is tied to \`main.jsp\` browser event
     \`CtReadVinButtonClick\`, vehicle-profile page
     \`readVehicle()\`, and the \`ReadVIN.do\` iframe
     (browser-route path observed in earlier owner file text);
   - establishes a new session, selects
     \`CommToolName\`, \`CommToolType\`, \`VirtualCarPath\`,
     creates diagnostic dependencies including
     \`VehicleConnectionProvider\`,
     \`DiagnosticVehCommServiceProvider\`,
     and \`ScriptExecutorUC\`;
   - subscribes \`UcBrowserCallback\` and calls
     \`ScriptExecutorUC.ExecuteScriptByType\` with
     **literal argument \`readvin\`**.
2. \`Vcc.Vida.DiagSwdl.UI.Diagnostics.ScriptExecutorUC.ExecuteScriptByType\`
   (\`MethodDef #1344\`) compares the type with \`readvin\`,
   then calls \`startIdentifyVehicleWF\`.
3. \`ScriptExecutorUC.CreateIdentifyVehicleWF\`
   (\`MethodDef #1337\`) instantiates
   \`Vcc.Vida.DiagSwdl.Workflow.IdentifyVehicle.IdentifyVehicleWF\`
   and assigns \`CommToolInformationWriter\`.
4. \`ScriptExecutorUC.startIdentifyVehicleWF\`
   (\`MethodDef #1347\`) subscribes
   \`IIdentifyVehicleWF.IdentifyVehicleCallback\`,
   and calls **\`IIdentifyVehicleWF.PerformIdentification\`**.

These are exact static IL references, *not* observations of
successful runtime execution. Conditional flow can affect which
branches execute.

## Confirmed IL call graph: result callback

- \`ScriptExecutorUC.identifyVehicleCallback\` (\`#1348\`)
  conditionally stores \`VIN\` to session parameters,
  then calls \`UiBase.doBrowserCallback\`.
- \`CommToolSetting.UcBrowserCallback\` (\`#322\`)
  calls \`Core.JavaEventHandle.ReadVehicleCallback\`.
- \`Core.DLL\`
  \`Vcc.Vida.DiagSwdl.Core.JavaEventHandle.ReadVehicleCallback\`
  (\`MethodDef #52\`) invokes the registered
  \`CtReadVehicleCallbackDelegate\` (marshaling to the UI
  thread when required).
- Earlier original \`main.jsp\` and
  \`vehicleprofiledwr.js\` evidence establishes the browser
  callback \`CtReadVehicleCallback(error,vin)\` →
  \`readVinCallback(vin,error)\`.

## Architecture

Original \`UI.DLL\` assembly reference includes
**\`Workflow\` version \`2.0.5394.27569\`**, where the
\`IdentifyVehicleWF\` implementation lives; it references
\`BizServices.VehicleCommProvider\`,
\`BizServices.CarCom.DB\`, \`AppServices.VehicleAccess\`,
\`AppServices.Scripting\`, \`BizServices.ScriptRepository\`,
and \`VehCom2\` (among other assemblies).

The separately observed \`Diagnostics/ReadVIN.do\` request
likely serves a browser-side flow associated with the
ReadVin button. **This alone does not establish that the
Struts action implements ECU VIN reading**; the mapped
\`Diagnostics/ReadVIN.jsp\` remained absent at the
exploded-WAR path inspected.

## Outstanding acceptance boundaries

- No implementation of
  \`IdentifyVehicleWF.PerformIdentification\` has been
  analyzed yet. No exact CEM request, B9 FB or 22 F190
  identifier, ECU selection or J2534 on-wire trace is
  established by the two original DLLs.
- No actual VIDA VIN acceptance, verified read over
  J2534, physical J2534 test or VMware exact-head CI.
- No original VIDA DLL or full disassembly is in GitHub.

**Next static-only owner step**: locate and preserve
\`Workflow.DLL\` and, if present,
\`BizServices.VehicleCommProvider.DLL\`,
\`BizServices.CarCom.DB.DLL\`, \`VehCom2.DLL\`,
\`AppServices.VehicleAccess.DLL\`,
\`AppServices.Scripting.DLL\` and
\`BizServices.ScriptRepository.DLL\` in owner-private
local evidence. Decode \`IdentifyVehicleWF\` before
inferring any transport data.
