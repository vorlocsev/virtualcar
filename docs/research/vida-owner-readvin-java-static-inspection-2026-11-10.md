# Original VIDA ReadVIN Java/JSP static inspection (owner, 2026-11-10)

## Original private evidence scope

Owner supplied \`VIDA-ReadVIN-java-static.zip\`, seven entries. ZIP
integrity passed. The evidence was produced locally by \`javap\` at
\`E:\vida\jdk\bin\javap.exe\` and read-only file inspection. The
original class, JSPs, and full disassembly remain **owner-private**,
not stored in the public repository.

The installed \`DiagnosticAction.class\` is 11,359 bytes,
SHA256 \`9FF343498BDC660D8A1FCEB1D0F5617050C51F7E06A689F6BBB629C7E399FAF2\`.
Its original fully qualified name is
\`com.ford.vcc.vida.web.action.diagnostics.DiagnosticAction\`,
extending \`org.apache.struts.action.Action\`.

## What its bytecode establishes

The \`execute(ActionMapping, ActionForm, HttpServletRequest,
HttpServletResponse)\` method:

- Logs the servlet path. It explicitly checks
  \`/Diagnostics/Diagnostics.do\` to mark diagnostic fault tracing
  active; no special check for \`ReadVIN.do\` was present.
- Obtains user, locale, subscription, vehicle specification and
  contextual session settings through
  \`com.ford.vcc.vida.web.session.SessionHandlerFactory\`.
- Populates fields in
  \`com.ford.vcc.vida.web.action.diagnostics.DiagnosticForm\`,
  diagnostic log path and local diagnostic path.
- Returns the Struts \`success\` forward.

The method
\`populateDiagnosticFormWithVehicleData(DiagnosticForm,VehicleSpecVO)\`
reads \`VehicleSpecVO.getIdList()\` and constructs a comma-separated
list of its elements for \`DiagnosticForm.setProfileId()\`.
It gets \`VehicleSpecVO.getVin()\`, falls back to
\`getDiagnosticSerialNumber()\` if the VIN string is empty, normalizes
null / literal \`undefined\` to empty, and calls
\`DiagnosticForm.setVin()\`. It also passes chassis, model, model year
and override-VIN flag.

**The class itself does not initiate CEM CAN/GGD/D2 requests, call
GetScript, or read VIN over J2534 in its inspected bytecode.**
Reading a \`VehicleSpecVO\` VIN from the session is not proof of
obtaining VIN from an ECU. The comma-separated profile-list transfer
confirms the form accepts a composite list, but does not establish
inherited ECU/service selection rules.

## Other source findings

The corresponding Struts \`success\` forward maps the
\`/Diagnostics/ReadVIN\` action to
\`/Diagnostics/ReadVIN.jsp\`. The owner-local inspection found
**no file at**
\`E:\vida\jboss\standalone\deployments\VidaEar.ear\VidaWeb.war\Diagnostics\ReadVIN.jsp\`.
A missing file at that exact path does not establish a broken
runtime or exclude another deployment/source location.

The original \`Diagnostics/LoadScript.jsp\` **does** exist. It calls
\`ScriptExec.ExecuteScript(scriptid, actions)\` and has callbacks for
\`ScriptExec::HandleScriptNavigation\`,
\`ScriptExec::NavigateIE\` and
\`ScriptExec::NavigateIEPopupWindow\`. Its script also references
\`../JavaScripts/DiagSwdl/LoadScript.js\`. This is evidence of a
**diagnostic-script execution interface**, not yet a proven edge
from \`ReadVIN.do\` to that interface.

The original \`vehicleprofiledwr.js\` triggers an iframe
\`Diagnostics/ReadVIN.do\`, then \`readVinCallback(vin,message)\`
updates VIN fields and calls \`setVin\`. Original \`main.jsp\` event
handlers connect \`CtReadVehicleCallback(error,vin)\` to
\`readVinCallback(vin,error)\` and
\`CtReadVinButtonClick()\` to \`readVehicle()\`, for
\`tab=vehicleprofile\`.

## Important gaps

1. Exact location or other registration of \`ReadVIN.jsp\`.
2. Origin, implementation and registration of \`ScriptExec\` and
   \`JavaEvent\`; which one actually initiates reading VIN.
3. \`GetScript\` query, selected CEM variant, concrete B9/22
   identifiers and actual on-wire command/response.
4. Real VIDA runtime success, VIN acceptance, VMware exact-head
   validation and physical J2534.

Next owner-local check: filename and archive-entry inventory for
ReadVIN, ScriptExec, JavaEvent and a bounded static text cross-reference
search in the deployed web app. Do not execute any Java code, invoke
diagnostics, change VIDA SQL settings or publish original vendor bytes.
