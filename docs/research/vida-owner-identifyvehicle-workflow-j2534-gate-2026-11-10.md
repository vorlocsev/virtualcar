# Owner VIDA 2014D original managed DLLs: IdentifyVehicle workflow and J2534-2 gate

Source: owner-private \`VIDA-ReadVIN-workflow-evidence.zip\` (7 DLLs, README.txt, manifest.csv). The archive CRC and each original DLL SHA256/length were verified **against the owner's manifest**. This is **static .NET metadata and CIL analysis only**; no original vendor binaries, full decompilation or SQL row data are committed.

Relevant exact original artifact SHA-256:
- \`Workflow.DLL\`: \`BA78B669EFEA360887D333353451E9411E82004E368B356F74200D8FCB427EBD\` (372,736 bytes, version 2.0.5394.27569).
- \`AppServices.VehicleAccess.DLL\`: \`3BCAAC2CE2DBE0B986A1C8588BBE3D75FE579BB41BB1EADA759CCDB7214545A0\`.
- \`AppServices.Scripting.DLL\`: \`C5F092EDDCEAC8B9EB583FB9A54536D482402A64797BD3597FD0CC6B387F3B7F\`.
- \`BizServices.ScriptRepository.DLL\`: \`F046B5FA3C8D3487FC05AA1140AC3C4EF1880EEF5251C8C46B1C3D73F45A6BCA\`.
- \`VehCom2.DLL\`: \`3A08F5FF5819396E676EAC8751FDB57475E8F76E20488926259993674EC97E82\`.

## Verified static ReadVin implementation path

\`UI.DLL\` previously established \`CommToolSetting.ReadVin\` →
\`ScriptExecutorUC.ExecuteScriptByType("readvin")\` →
\`IIdentifyVehicleWF.PerformIdentification\`.

1. \`Workflow.DLL\` type \`Vcc.Vida.DiagSwdl.Workflow.IdentifyVehicle.IdentifyVehicleWF\` is original TypeDef #56. \`PerformIdentification\` (MethodDef #542) constructs \`WorkerThread.CreateCommToolWorker\` with literal thread name \`IdentificationThread\`; it registers the \`startIdentification\` method and starts the worker.
2. \`startIdentification\` (MethodDef #541, IL 532 bytes) calls \`IVehicleAccess.IdentifyVehicle\` at IL_00a3 after CAN-MS checks; handles \`VehicleIdentity.IsIdentityVin\` with distinct X40 and no-response/error callbacks.
3. \`AppServices.VehicleAccess.DLL\` \`VehicleAccess.IdentifyVehicle\` (#237) saves/clones current \`VehicleProfile\`, sets \`VehicleProfile.Empty\`, invokes \`IRunScriptService.RunIdentifyVehicleScript\`, retrieves \`VehicleIdentityOutput.GetIdentity()\`, creates \`VehicleIdentity\`, and restores the profile in a \`finally\` handler. VIN read is therefore launched in a no-profile context before ECU-specific profile selection; no inference of any on-wire CAN message follows.
4. \`AppServices.Scripting.DLL\` \`RunScriptService.RunIdentifyVehicleScript\` (#113) passes **ScriptType numeric value 4** and an empty profile into the script-engine resolver, runs \`IScriptEngine.RunScript\` and casts \`GetOutput\` to \`VehicleIdentityOutput\`. The **enum label** for \`ScriptType(4)\` is not established without the original \`ValueObjects.DLL\`.
5. \`BizServices.ScriptRepository.DLL\`: \`ScriptProvider.GetScript\` uses \`ScriptType.ToString()\`; \`ScriptProvider.GetFromDb\` (#30) invokes an original stored procedure named **\`GetScript\`**, sets **\`@scriptType\`**, **\`@profileList\`**, **\`@scriptId\`**, **\`@languageCode\`**, **\`@ecuType\`**, and receives binary data. \`GetZippedScriptXml\` (#31) calls \`ZIP.DecompressString\` then \`XmlDocument.LoadXml\`. Disk \`.xmlds\` and smart-tool script sources are alternate code paths. The original \`DiagSwdlRepository\` database name appears in source metadata, but the live procedure and specific script content have not yet been inspected.

## Exact J2534 ReadVin eligibility (do not overstate)

In \`IdentifyVehicleWF.startIdentification\`:
- IL_0053 checks \`CurrentCommTool.IsJ2534\`. If false, IL_0058 branches to the identification call.
- If J2534, IL_0060 checks \`IVehicleAccess.IsCanMsSupported\`. True branches to identification.
- **Only J2534 AND NOT CAN-MS-supported** invokes \`IdentifyVehicleCallback("error.lblNoReadOut,information.noReadOutUsingJ2534", "", commTool)\` and returns early, with exact log string \`ReadVIN blocked for J2534 users\`. This is **not a blanket J2534 ban**.

\`BizServices.VehicleCommProvider.DLL\` \`CurrentCommTool\`: \`CommToolType=0\` is J2534, \`1\` DiCE, \`2\` VirtualCT (exact IL of getters).

\`VehCom2.DLL\` \`J2534ChannelManager.CheckIfMsCanIsSupported\` (#755) checks:
- for \`CommToolType=1\` (DiCE): immediate true;
- otherwise \`CreateChannel(protocol=5, baudrate=125000, flags=256)\`, \`TryClose\`, then \`CreateChannel(protocol=6, baudrate=125000, flags=0)\`, \`TryClose\`; log labels are \`CAN_PS\` and \`ISO15765_PS\`; a caught exception returns false.
- \`J2534ChannelManager.OpenDevice\` stores the result in \`_isMsCanSupported\`. \`IsCanMsSupported\` opens the device and returns that field. \`VirtualCT.DiagConnection.IsCanMsSupported\` (#1792) returns true.

**Acceptance implications for Virtual Car virtual J2534:** test channel setup/teardown for both J2534-2 pin-switching protocols at 125 kbit/s before expecting VIDA ReadVin workflow acceptance; retain real diagnostics/trace evidence, not hardcoded success claims. The user's virtual J2534 implementation has **not** been tested against this check in this analysis.

## Next owner-private evidence

Read-only query of \`DiagSwdlRepository\` system metadata for \`GetScript\` (definition, parameters, table columns), and original \`ValueObjects.DLL\` / \`BizServices.Scripting*.DLL\` to resolve enum, source script contents and engine behavior. Do **not execute** unknown SQL stored procedures to investigate effects or publish original proprietary scripts, SQL bodies, or DLLs.

**Not established:** actual owner VIN .xmlds/SQL script bytes, D2 B9FB or GGD 22F190 selection, CEM request IDs, working original VIDA readout, VMware exact-head CI, physical J2534 or release/merge.
