# VDASH 2.5.115.79 recovered IL: static call-graph audit + separate VDASH 2.0 J2534 correlation

**Analyzed:** 2026-11-02. **Evidence:** user-owned Library artifacts `VDASH_Recovered_Methods_Inventory.json` (1,869 lines, 45,719 bytes) and `VDASH_Recovered_Diagnostic_IL_Excerpts.txt` (1,154 lines, 43,143 bytes); separately an accumulated **private** J2534 text log supplied by the user, summarized below only in aggregate. Original proprietary VDASH DLLs were **not** re-executed or re-decompiled in this stage. Source archive SHA-256 recorded by inventory: `f76fa56fe07db18866db3078ec9c7187ccaab6f457a560eaa54ee9cc371808ec`. No original IL, PEs, log lines, VINs, user paths or secrets are added to this repository.

## Artifact inventory and scope

Seven recovered assemblies report **55,786** encrypted method bodies recovered in the preceding extraction (out of a previously reported 56,665), including: Frontend.exe 27,082; Core.dll 16,557; Frontend.Client.Core.dll 8,272; Client.Core.dll 2,555; Frontend.Core.dll 724; Vdash.Frontend.exe 120; Vdash.Monitor.exe 476. The accessible JSON indexes **28 selected methods**, not all 55,786. Control-flow flattening, encrypted strings, obfuscated symbols remain. The count is **not** semantic deobfuscation or a verified protocol map.

## What the recovered instructions show

| Module / MethodDef | Source-observable behavior | Limitation |
|---|---|---|
| Frontend.Client.Core / `0x0600133D PreDetect` | Handles `get_SuggestedVin`, `set_Voltage`, `set_Volvo`, `set_PreDetectResult`; cached IDataFactory.GetLastViewV2 and DataViewV2.GetValueString/GetValue wrappers are available nearby. | Exact order/paths remain obfuscated; neither source of VIN nor successful physical ECU detection follows automatically. |
| Frontend.Client.Core / `0x0600132B Detect` | `CreateCommand(0x06001329)`, `Enqueue(0x0600132C)`, `VddCommand.Wait(0x0600115B)`, `get_ResultData`, `get_Result`, `get_DataHash`, `set_DetectResult`, `set_Ecus`, ECM/DIM/ICM/PHM model construction, `Units` enumeration, `get_HardwareNumber`, `set_LoaderResult`, and `OnDetectDone`. | The presence of ECU model constructors is **not** evidence that each ECU replied or that ECU identities were accepted. Hash checking cannot be reconstructed from obfuscated branches. |
| Frontend.Client.Core / `0x0600115D VddCommand.Execute` | Stores DongleCommandExecutionResult from client/command; sets Session/Result, creates OnCheckResult polling timer, has executionEvn and waitEvn, Timeout, invokes ParseData `0x06001160`. | Result-state mappings/remote executor and exact timeouts are not established. |
| Frontend.Client.Core / `0x06001160 VddCommand.ParseData` | Inventory records four get_ResultData calls, `set_DataHash`, two RaiseEvent calls, collection Add/Remove and `DateTime.op_GreaterThan`. | The original method body is not in the accessible excerpt; cannot assert exact parsing of D2 bytes, DataViewV2 or validation rules. |
| Frontend.Client.Core / `0x0600133A GetVin`, `0x06001339 GetConfig` | GetVin uses `PreDetectResult.Vin` and fallback Volvo getter; GetConfig returns `DetectResult.Config` (nine opcodes). | Neither is evidence of direct PassThru TX. |
| Frontend.Client.Core / `0x06001337 FastDetectEcu`, `0x06001338 FastDetectEcu(out)`, `0x0600134B FastDetectEcuAsync` | In selected build: first returns 0; second clears out parameter and returns 0; async returns null. | Only those three local methods are stubs, not every possible ECU discovery path. |
| Frontend.Client.Core / `0x06001C65/66 J2534DiagnoseManager.Add/FindImplementation` | Adds implementation by `get_Device` and retrieves from `diags` using TryGetValue. | No concrete PassThru callsite or routing to the local pipe is proven. |
| Frontend.exe / `0x060065AD/AE J2534ServerClient` | Constructor calls `Vdash.Core.PipeServerClient..ctor`; the selected OnReceiveData body is `ret`. | This is not a proof that all IPC/server handling is absent. |
| Frontend.exe / `0x06002472 DetectViewModel.Model_DetectDone` | Inventory shows get_CemCommand, get_Tuning, set_ModelId, set_Header, visibility/units refresh and command notification. | UI visibility and enabled-state predicates cannot be resolved from call inventory. |
| Client.Core / `0x060002EF SendV2` | 552 decoded opcodes, **6 decoder issues**; calls Initialize, WaitForInitialize, RaiseInternetConnectionStatus, TimeSpan.FromSeconds. | Network connectivity path visible; HTTP URL, wire payload, protobuf layout and network execution semantics not verified by these excerpts. |
| Client.Core / `0x06000308 DecodeVin` | Calls `GetDataServiceV2`, `DecodeVin` plus helper methods. | This method is distinct from `VddModel.GetVin`; whether it calls a remote server in a particular flow is not proven. |
| Client.Core / `0x060003AF/B0 StartSession` | Wrapper and overload, with DateTime.Now/ToString and initialization calls. | Cannot infer the server-side session protocol from selected method calls. |

### Minimal source-constrained call graph

```text
VddModel.PreDetect → PreDetectResult → VddModel.GetVin
VddModel.Detect → CreateCommand → Enqueue → VddCommand.Wait
                                 ↳ VddCommand.Execute → DongleCommandExecutionResult
                                     ↳ OnCheckResult / executionEvn / timeout
                                     ↳ VddCommand.ParseData → ResultData / DataHash / events
                                  ↳ DetectResult → Ecus, Units, ECM/DIM/ICM/PHM
                                     ↳ DetectViewModel.Model_DetectDone → UI update
VdashClient.DecodeVin → GetDataServiceV2 / DecodeVin (exact backend call unresolved)
VdashClient.SendV2 → initialization / internet status (exact call path unresolved)
```

This is a **call relationship sketch**, not a validated single execution path. Do not equate `GetVin` with OBD VIN request, `get_CemCommand` with a physical CEM probe, or `DataHash` with a verified signature algorithm.

## Separate evidence: accumulated VDASH 2.0 Virtual Car J2534 text log

This is **not** VDASH 2.5.115.79 static IL and **not** an independent set of 1,143 vehicle sessions. The private accumulated text contains many replay/repeat attempts with older Virtual Car revisions. Filter: rows whose emitter is `vdash_u.exe` and exactly `TX (app request)`. Count: **1,143** TX lines.

| CAN request ID | TX prefix | Occurrences |
|---|---|---:|
| `000007DF` | `3E 80` | 599 |
| `000007DF` | `09 02` | 371 |
| `000007DF` | `11 81` | 3 |
| `18DB33F1` | `3E 80` | 149 |
| `18DB33F1` | `11 81` | 3 |
| `1DD01FFF` | `3E 80` | 3 |
| `1DD01FFF` | `11 81` | 3 |
| `000FFFFE` | `D8 00` | 6 |
| `000FFFFE` | `FF C8` | 6 |

The 9 groups total 1,143. Queries for `00000726`, `18DA50F1`, `000007E0`, and `000FFFFE CB/CD` yielded zero matching TX lines within this **particular accumulated file**. Thus **no observed targeted F114, A6/B9F0/B9FB/B9FC read** was identified here. Do not infer that VDASH never uses these services, nor that the exact reason it stops is known.

An older three-times-repeated local fragment shows network-probe/cleanup-like succession: `1DD01FFF 3E80/1181`; `7DF 3E80/1181`; `18DB33F1 3E80/1181`; then on `000FFFFE`, `D8 00...` and `FF C8...`. The exact semantics of `1DD01FFF` and `D8` are **unknown**. `11 81` resembles UDS ECUReset with the suppress-positive-response bit: do not simulate a physical reset or response. Existing repository source treats `FF C8` as silent reset/exit; older log labels such as 'discovery probe' do **not** establish that it is a VIN/ECU list query.

No payloads or private logs are reproduced. Counts are for **lines** and may include duplicate sessions/versions and repeat emissions; do not use them as independent transactions or response-success rates.

## Diagnostic implication for Virtual Car

- A delivered OBD `49 02 01` VIN and suppressed TesterPresent do not prove successful `DetectResult.Ecus` construction.
- The strongest remaining alternative failure boundaries: client pre-detect confirmation, command-service/session result, ResultData/DataHash acceptance, or simply no observed physical ECU probe. Cannot rank their likelihood from these static artifacts.
- Log J2534 call results/status/filters/routes/timing and UI milestones with a sanitized, single-run, version-labelled trace. Use existing offline audit tooling. Avoid TCP/TLS interception, secrets extraction, security access, changing vehicle configuration or creating unverified replies.
- Investigation should next examine the actual bodies of `CreateCommand`, `Enqueue`, `ParseData`, `OnCheckResult`, `DetectViewModel.Model_DetectDone`, and provider-side `J2534DiagnoseManager` implementation when an authorized original build is available. Do not claim their bodies exist in the selected inventory.
- Distinguish **(1) J2534 delivered**, **(2) command result received**, **(3) DetectResult parsed**, **(4) UI accepted and listed ECU** as four different verifiable events.

## Follow-up: recovered IL branch dependencies and P2 diagnostic-mode keepalive (02.11.2026)

This addition compares the **actual saved, selected method listings** to external published P2 CAN traces. The deobfuscation report indexes 28 selected methods, but the excerpt file prints only **11 MethodDef bodies**. In particular, **there is no full `VddCommand.ParseData`, `CreateCommand`, `Enqueue`, `DetectViewModel.Model_DetectDone`, or `VdashClient.SendV2` body in the excerpts**. Inventory call counts are not complete control-flow reconstructions.

### Data provenance through pre-detection

- In recovered `Frontend.Client.Core.dll` `VddModel.PreDetect` (`0x0600133D`), the excerpt shows `get_SuggestedVin` at IL_01DC, `set_Voltage` at IL_006B, `set_Volvo` at IL_0088 and `set_PreDetectResult` at IL_019A. The constructor invoked before `set_PreDetectResult` receives the Volvo model, `dongleId` and other computed locals (IL_0186–019A).
- The same excerpt calls helpers `0x06001376` and `0x06001377` at IL_009B/00BC and IL_0124/0145; the recovered inventory independently names these wrappers `IDataFactory.ToPropertyId` and `IDataFactory.GetLastViewV2`. Their paths lead to `DataViewV2.GetValueString` (`0x06001378`), `DataViewV2.GetValue` (`0x06001379`) and `Utils.TryConvertDouble` (`0x0600137A`). The presence of a `GetLastViewV2` path is evidence that **previously available views can participate**; it is not proof that a particular transaction read fresh CAN data.
- `VddModel.GetVin` `0x0600133A` invokes `get_PreDetectResult` and `get_Vin` (IL_002E–0034 and IL_0059–005F), and also has a `get_Volvo` fallback (IL_0074–0085). `VddModel.GetConfig` `0x06001339` simply reads `get_DetectResult → get_Config`.
- Thus, seeing a VIN or an initialized Volvo object in the UI is **not by itself a proof** that this run reached OEM P2 CEM identification; cached/suggested inputs and fresh J2534 responses must be distinguished. We cannot prove from the flattened CFG which source was actually chosen on a specific run.

### Command result and ECU list dependency

- `Detect` excerpt: `CreateCommand` IL_006E → `Enqueue` IL_00AF → `Wait` IL_00B5; later there are `get_ResultData` IL_00F2, `get_Result` IL_0118 and `get_DataHash` IL_013E, and a `set_DetectResult` call at IL_0184. `set_Ecus` occurs at IL_026D; various ECM/DIM/ICM/PHM objects are instantiated. **These are occurrences in a flattened method, not a proven linear path across all conditions**.
- `VddCommand.Execute` excerpt receives a `DongleCommandExecutionResult` (IL_005D–0062), writes `Session` (IL_00AB–00B0), schedules `OnCheckResult` polling (IL_0186–01B1), compares an obfuscated accessor to integer literals 2/3/4 (e.g. IL_01DC–022B and IL_02FB–0316), has `executionEvn` and `Timeout` (IL_031D–0337), and invokes `ParseData` at IL_025E.
- The numeric literals above are real, but **their mapping to the previously reported 0..5 Status enum cannot be verified solely from this excerpt**. Do not claim `3` necessarily corresponds to a named server error before resolving the accessor and enum metadata. `ParseData` is named and called, but its exact result schema/validation is **unknown**.
- The UI `DetectViewModel.Model_DetectDone` method `0x06002472` is present only in the 28-method **inventory**. It references `get_CemCommand`, `set_ModelId`, `set_Header` and `InitializeUnits`/availability routines. These are post-processing/UI operations, not direct CAN reads.

**Falsifiable alternative explanations for an empty ECU list:** (A) pre-detect was populated without a fresh OEM scan; (B) J2534 delivery occurred but a command service result was not received/accepted; (C) ResultData/DataHash processing did not construct the required ECU data; (D) a result existed but the UI's availability/list predicate excluded it. **No ranking or concrete cause can be established yet.**

### Independent external corroboration for `0x000FFFFE D8`

- In an author's contemporaneous MOTOR-TALK P2/VADIS capture, `000FFFFE D8 00 00 00 00 00 00 00` is described as an **alive message for diagnostic mode**, approximately every four seconds:
  https://www.motor-talk.de/forum/der-can-bus-im-volvo-t4420570.html?page=3
- A separate Jagrullar account (2010) documents the same `D8` as repeated keepalive before ECM read-DTC transactions:
  https://www.jagrullar.se/forum/viewtopic.php?start=36&t=48773
- Consequently, six `000FFFFE D8 00` TX lines in the **accumulated VDASH 2.0 Virtual Car lab log** should be classified **P2 diagnostic-mode keepalive candidate**, not a CEM module-identification request or evidence of a valid ECU list. The source vehicle/year and cadence do **not** prove compatibility with XC90 V8 MY2009; the six lines occur in older, repeated emulator runs.
- `FF C8` must **not** be mislabelled as CEM discovery either. The public `Volvo-CAN-Gauge/Codes.txt` labels the global `FF/C8` combination **Whole Bus Reset**:
  https://github.com/Alfaa123/Volvo-CAN-Gauge/blob/master/Codes.txt
  This is an independently written public code list, not the intercepted response of the target VDASH. The Virtual Car source already chooses intentionally silent no-physical-reset handling. Do not implement physical reset or fabricate acknowledgements.
- `11 81` corresponds in UDS byte shape to ECUReset with suppress-positive-response bit and is observed on functional addresses in the accumulated file. This is not a read-only ECU discovery request; Virtual Car must keep it inert. `1DD01FFF` remains **unattributed**.

### End-to-end acceptance gates for a single *new* anonymized test

| Gate | Required evidence | What it does *not* prove |
|---|---|---|
| G1. J2534 transport | Fresh, version-labelled PassThru TX, matching RX status, protocol/baud/flags/filter and relevant metadata, plus no queue loss | That VDASH accepted vehicle identity |
| G2. Command lifecycle | A visible new VDASH command initiated and completed with result in a permitted log/UI; not inferred from `PassThruClose` | That `ResultData` passed schema/data-hash validation |
| G3. DetectResult | Verified UI/diagnostic state confirming fresh DetectResult/ECU set; do not derive solely from presence of static `set_Ecus` | That every ECU was individually queried |
| G4. UI ECU acceptance | Explicit list of ECU items displayed by this VDASH version following the new run, with a source-bound chassis/model-year label | That all network-specific P2 features and authentic MY2009 CEM internals are supported |

**Decision logic:** If no manufacturer-specific physical TX is observed after G1, don't invent B9F0/FB/A6 packets. If there is a physical TX but no delivered RX, first inspect allowlisted route/filter/no-fixture/timeout telemetry. If delivery exists but G2–G4 fail, focus static analysis on `CreateCommand`, `Enqueue`, `ParseData` and the UI predicate. If only keepalives `3E80/D8` or reset-like `1181/FF C8` are present, classify the session as **without observed read-only ECU discovery**, not as an ECU-negative response.

### Eight bounded checks for the next evidence stage

1. Verify source archive hash and application **version**; do not mix VDASH 2.0 runtime with 2.5.115.79 static.
2. Verify exact text-log count attribution by process and call type; do not count repeated TX lines as distinct sessions.
3. Check `PreDetect` cached view vs `SuggestedVin` vs newly delivered `49 02 01` when observable.
4. Correlate `Detect` command lifecycle against timestamps/results without inventing HTTP, protobuf, or CEM wire content.
5. Classify `D8` and `3E 80` as diagnostic-mode/TesterPresent keepalive, never ECU ID; constrain `FF C8` and `11 81` to inert reset-like handling.
6. Distinguish missing physical CAN request from no fixture, filtered RX, incomplete multi-frame and client-declined result.
7. Preserve redaction by allowlist, no private VIN, binary, user paths, account/session secrets, and no proprietary IL copies in repository.
8. Verify existing offline CI; label **VMware end-to-end** and **physical J2534** untested until separately witnessed.

## Handoff

Linked to issues #37 and #4 and PR #39. No changes to emulator behavior or fixtures in this **documentation-only addition**. Original source artifacts remain private. Windows/VMware VDASH and physical J2534 were not run in this static-analysis step; neither ECU discovery nor model-year compatibility has been demonstrated. Do not merge to main or create a release.
