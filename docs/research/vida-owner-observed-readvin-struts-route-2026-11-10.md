# Original VIDA deployed JBoss: owner-observed ReadVIN Struts route

## Evidence scope

Owner ran a read-only PowerShell text search over
\`E:\vida\jboss\`, targeting .xml/.js/.jsp/.properties etc.
This note transcribes genuine file paths and visible matching
lines without anonymizing any original identifiers. The full
vendor files are not copied into the GitHub repository.

Observed from the owner-provided PowerShell output:

1. \`E:\vida\jboss\standalone\deployments\VidaEar.ear\VidaWeb.war\JavaScripts\vehicleprofile\vehicleprofiledwr.js\`, line **316**:
   an assignment to \`document.getElementById("readVehicleFrame").src\`
   with original target **\`Diagnostics/ReadVIN.do\`**.
2. \`...\VidaWeb.war\WEB-INF\struts-config.xml\`, line **300**:
   Struts mapping \`/Diagnostics/ReadVIN\` to
   **\`com.ford.vcc.vida.web.action.diagnostics.DiagnosticAction\`**,
   request scope and \`diagnosticForm\`.
3. \`...\VidaWeb.war\jsp\main.jsp\`, line **248**:
   callback \`document.frames['docFrame'].readVinCallback(vin, error)\`.
4. \`...\VidaWeb.war\jsp\vehicleprofile\vehicleprofile.jsp\`, line **64**:
   hidden property **\`readVinFromVehicle\`**.

Two additional large minified-jQuery hits and one artifacts-cache
hash containing \`f190\` were observed. Those are NOT evidence of
VIDA diagnostic request ID F190, a VIN DID or a B9FB command.

## Narrowly established flow

A vehicle-profile UI JavaScript element initiates a browser request
to the Struts route \`Diagnostics/ReadVIN.do\`.
The corresponding Struts XML declares a Java action handler
\`DiagnosticAction\`. Another JSP contains a \`readVinCallback\`
invocation. This is a **web routing/UI callback path**, not yet a
verified end-to-end execution sequence through the Java server,
VIDA diagnostic script selection, CEM and on-wire CAN.

\`ReadVin\`, \`ReadVIN\` and \`GetScript\` should not be conflated
without additional exact-source evidence. No specific protocol,
D2 identifier \`FB\`, UDS DID \`F190\`, or ECU CAN ID has been
confirmed by these text matches.

## Follow-up read-only owner checks

1. Print 15 lines surrounding \`struts-config.xml:300\` to inspect
   the exact action \`parameter\`, \`forward\` and method mapping.
2. Print 15–25 lines around \`vehicleprofiledwr.js:316\`
   to identify the function that triggers the iframe.
3. Print context at \`main.jsp:248\` and
   \`vehicleprofile.jsp:64\` to track callback/form data.
4. Inventory the deployed \`.class\` and JAR **entry names** (do not
   execute classes) for \`DiagnosticAction.class\` and VIN-specific
   classes under \`E:\vida\jboss\standalone\deployments\`.
5. Only after locating the actual class, inspect its method dispatch
   and the downstream implementation. Keep provenance and distinguish
   static presence from executed VIDA runtime.

All original files remain owner-local; no source JAR or class
binaries have been uploaded, published or modified by this step.
Physical J2534, VMware exact-head CI, Java diagnostic execution,
GetScript and VIN acceptance remain untested.


## Confirmed action-class file and expanded context (owner, 2026-11-10 21:27 local)

Owner successfully ran the local route/Java-class inventory. The expanded, original source text establishes:

- `vehicleprofiledwr.js:316`: `readVehicleFrame.src = "Diagnostics/ReadVIN.do"` following UI-disabling actions and progress-frame setup; `vehicleprofiledwr.js:320`: declaration `function readVinCallback(vin, message)`, with localized error handling and a VIN length check in the visible code.
- `struts-config.xml:297-302`: `/Diagnostics/LoadScript` and `/Diagnostics/ReadVIN` both map to `com.ford.vcc.vida.web.action.diagnostics.DiagnosticAction`, forwarding success to `/Diagnostics/LoadScript.jsp` and `/Diagnostics/ReadVIN.jsp`, respectively. A route mapping does not prove what method is executed.
- `jsp/main.jsp:244-257`: `document.JavaEvent::CtReadVehicleCallback(error, vin)` calls `docFrame.readVinCallback(vin,error)` only when `tab.value == 'vehicleprofile'`; `document.JavaEvent::CtReadVinButtonClick()` calls `docFrame.readVehicle()` under the same tab condition.
- `jsp/vehicleprofile/vehicleprofile.jsp:64-65`: form fields `readVinFromVehicle` and `readErrorFromVehicle`.
- **Loose, owner-installed class confirmed on disk:** `E:\vida\jboss\standalone\deployments\VidaEar.ear\VidaWeb.war\WEB-INF\classes\com\ford\vcc\vida\web\action\diagnostics\DiagnosticAction.class`. Inventory scanned 52 archive files with 0 matching inner class paths and 0 read errors; this does **not** weaken the observed loose-class evidence.

Still unproven: how Struts `DiagnosticAction` dispatches per path, the contents of either JSP, whether `JavaEvent` is an applet/COM/other bridge, downstream service/ECU selection, `GetScript`, concrete D2/GGD commands, and VIN acceptance.

Next static-only owner check: inspect `Diagnostics/ReadVIN.jsp`, `Diagnostics/LoadScript.jsp` and the located `DiagnosticAction.class` bytecode using JDK `javap`; record exact class SHA256 and disassembly in owner-private location. No class execution, SQL writes, original vendor source publication or physical J2534 test.
