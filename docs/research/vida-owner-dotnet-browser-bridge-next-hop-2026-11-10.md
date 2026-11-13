# Owner-confirmed VIDA .NET browser bridge references: ReadVIN next hop (2026-11-10)

Owner supplied a private, intact archive \`VIDA-ReadVIN-next-hop.zip\`, 2 files:
\`ReadVIN-next-hop-inventory.txt\` and \`DiagnosticForm-declarations.txt\`.
The original ZIP and vendor files are **not committed**.

## Direct static evidence (original identifiers retained)

- Original deployed \`VidaWeb.war\jsp\main.jsp:167\` embeds
  \`<object id="JavaEvent" name="JavaEvent" classid="/Vida/Diagnostics/Core.DLL#Vcc.Vida.DiagSwdl.Core.JavaEventHandle" width="0" height="0"></object>\`.
  \`main.jsp\` includes \`JavaEvent::CtReadVehicleCallback(error, vin)\`,
  \`JavaEvent::CtReadVinButtonClick()\`, and \`JavaEvent.Complete()\`.
  The callback forwards \`vin,error\` to the vehicle-profile page.
- Original \`VidaWeb.war\JavaScripts\DiagSwdl\LoadScript.js:1\` uses
  \`document.write\` to inject \`<object id="ScriptExec" classid="UI.DLL#Vcc.Vida.DiagSwdl.UI.Diagnostics.ScriptExecutorUC" width="100" height="100" codetype="application/x-msdownload">\`.
- Original \`VidaWeb.war\Diagnostics\LoadScript.jsp:37\` calls
  \`ScriptExec.ExecuteScript(scriptid, actions)\`, and has
  \`ScriptExec::HandleScriptNavigation\`, \`NavigateIE\`,
  \`NavigateIEPopupWindow\` handlers.
- Original \`DiagnosticForm.class\` declarations include separate
  fields/properties/getters/setters for \`vin\`, \`profileId\`,
  \`scriptid\` and \`actions\`. These describe Struts form data,
  **not** a diagnostic transport request.
- \`VidaWeb.war\Diagnostics\ReadVIN.jsp\` was **absent** at the
  exact path forwarded by the Struts XML mapping; \`LoadScript.jsp\`
  was present. The prior filename search did not target \`Core.DLL\`
  or \`UI.DLL\`, and therefore **does not prove those DLLs absent**.
- Owner text inventory examined 232 loose text files, reporting
  17 relevant text matches in 7 files. Archive inventory checked
  52 JAR/WAR/EAR/ZIP files by entry name, zero matching entries,
  zero read errors. It did **not** scan .NET DLL metadata or binary
  contents, nor observe a live diagnostic runtime.

## Implications and boundaries

This is an original-source **declaration of a web-to-.NET diagnostic
bridge**. Java \`DiagnosticAction\` prepares a form; the observed
web code declares browser-embedded \`JavaEventHandle\` and
\`ScriptExecutorUC\` controls. No executed event, mapped class
implementation, actual control loading, or path from \`ReadVIN.do\`
to \`ExecuteScript\` has yet been proven.

Next read-only owner check: locate \`Diagnostics\Core.DLL\` and
\`Diagnostics\UI.DLL\` in \`E:\vida\`, hash and inspect metadata/static
strings (do not execute DLLs), then inspect selected managed IL
owner-locally. Preserve all original names, do not anonymize source
IDs, and keep vendor assemblies and full source dumps out of public
GitHub.

**Not tested:** GetScript, D2 \`B9 FB\`, GGD \`22 F190\`, runtime
VIN acceptance, CEM selection, exact-head VMware CI or physical J2534.
