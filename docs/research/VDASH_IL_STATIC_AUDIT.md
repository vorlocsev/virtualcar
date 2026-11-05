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

## Structured IL audit / status-timer evidence (follow-up 2026-11-02)

A **generic, non-executing, read-only** audit tool and eight synthetic tests have been added to this same PR:

- `emulator/tools/audit_recovered_il.py` verifies that the declared per-MethodDef opcode counts match parsed IL lines, ties excerpt tokens to the selected method inventory, and emits a **fixed-schema allowlisted** summary only.
- `emulator/tests/test_audit_recovered_il.py` checks exact extraction, callsite presence, unknown status values, timer shape, truncated bodies, duplicate/unknown tokens, omitted priority methods and privacy. No proprietary method contents or real VIN fixtures are committed.
- For an authorized local copy (never check the two sources into this repository):

```sh
python3 emulator/tools/audit_recovered_il.py \
  --inventory "/private/VDASH_Recovered_Methods_Inventory.json" \
  --excerpts "/private/VDASH_Recovered_Diagnostic_IL_Excerpts.txt" \
  --output "/private/vdash-il-evidence.json"
```

The previously saved user Library reports were re-read and inspected **locally** without including their bytes in Git. All 11 excerpt MethodDef bodies have **exactly the declared opcode counts**, totaling **1,104 IL instructions**. The inventory has 28 selected methods, leaving **17 indexed methods without a full body in the excerpt**. This is a limitation of the selected artifacts, not of the original deobfuscation claim that it recovered 55,786 method bodies.

Additional facts from intact CIL instructions:

1. `VddModel.Detect` (MethodDef `0x0600132B`) has 511 decoded instructions, 87 call/callvirt sites and five switch constructs in the flattened CFG. It contains separate `set_DetectResult` (IL_0184), `set_Ecus` (IL_026D), `OnDetectDone` (IL_0633), `set_DeviceAvailable` (IL_0685), and both `ldc.i4.1; ret` and `ldc.i4.0; ret` terminal sequences. **We cannot prove the runtime ordering or which return path was taken** without de-flattened control flow.
2. `VddCommand.Execute` (MethodDef `0x0600115D`) has 311 instructions, 39 call/callvirt sites and three switch constructs. It stores `DongleCommandExecutionResult` in its `result` field (IL_005D..0062), invokes `ParseData` (IL_025E), and accesses `executionEvn`, `waitEvn`, `get_Timeout`, `set_Executing`, and `set_Executed`.
3. The same opaque accessor **MethodDef `0x06001178`** is called before direct equality comparisons against numeric literals **3**, **4**, and **2** respectively (IL_01E2/01E7, IL_020C/0211, IL_0301/0306). It plausibly returns an execution status, but the symbol and enum map are **not** proven. Do **not** label these branches \`Failed\`, \`AllFailed\`, etc. without confirming method/enum metadata.
4. Timer construction-shaped site IL_0186–01B1 supplies `OnCheckResult` via `TimerCallback`, the current result as state, a **1-second due time**, and `System.Threading.Timeout.InfiniteTimeSpan` as period, storing the returned object in field `timer`. The actual call at IL_01AC is still obfuscated (`0x0600117C`). Under ordinary `System.Threading.Timer(TimerCallback, object, TimeSpan, TimeSpan)` semantics, this is a single-shot timer: the InfiniteTimeSpan period disables repetition. Source: https://learn.microsoft.com/en-us/dotnet/api/system.threading.timer.-ctor . Since the wrapper and `OnCheckResult` bodies are not accessible, **neither an exact polling cadence nor a single total check can be claimed**.
5. `VddCommand.Wait` is indexed as a five-instruction method calling an obfuscated wrapper. This local method has no explicit literal timeout; `Execute` separately uses `get_Timeout` and `executionEvn`. This distinguishes the caller wait from executor completion, but does not prove that any call blocks indefinitely.
6. `PreDetect`, `Detect`, `Execute`, and \`Model_DetectDone\` must be correlated via a **new single-run, version-specific, consented trace**, not by matching only the names in recovered IL. A J2534 RX is not proof of `set_Ecus` or UI acceptance.

**Scope and access limitations:** Only the 11 existing recovered IL excerpts can be opcode-validated here; there is not enough original IL text to reconstruct `CreateCommand`, `Enqueue`, `ParseData`, `OnCheckResult` or the UI acceptance predicate. The audit script does **not** reconstruct these branches and cannot obtain protected code. One CLI output may contain only metadata/booleans/numeric comparisons, not source strings. All tests are synthetic and do not claim VDASH itself ran.

## Exact IL local provenance: DetectResult and ECU collection (2026-11-02)

The existing, private recovered IL excerpt for **VDASH portable 2.5.115.79**, module `Frontend.Client.Core.dll`, MethodDef `0x0600132B`, supports a stronger **local data-origin assertion**, without undoing the flattened control flow:

| Exact IL neighborhood | Directly supported assertion | Explicit limitation |
|---|---|---|
| IL_00F1–010C, including `get_ResultData`, a null check, an opaque generic helper and `stloc.2` | Command result data is part of the value placed in local 2, with a null/fallback path | Cannot name the data schema or prove which branch was taken |
| IL_0177–0184, `get_Volvo → ldloc.2 → newobj 0x060011BB → set_DetectResult` | The new DetectResult model is constructed from the Volvo model and local 2 | The constructor body and data acceptance criteria were not recovered |
| IL_0261–026D, `get_DetectResult → newobj 0x0600126D → set_Ecus` | The `Ecus` model is built using the already-created DetectResult | Constructor does not by itself prove individually queried ECU or non-empty list |
| IL_0285–028C, `get_DataHash → stfld dataHash` | The current command's DataHash is stored on the model | No hash algorithm, cryptographic validation or server authorization proven |
| IL_02A4–02AF and IL_04DF–04EA, `DetectResult.get_Units → GetEnumerator` | A second stage processes the DetectResult's `Units` collection | Unit enumeration need not imply real CAN transport or UI acceptance |
| IL_06BB–06BC and IL_06D0–06D1 | Both true and false return sites are present | Flattened CFG prevents attributing conditions or runtime path |

The pseudocode below describes **only adjacent IL data dependencies**, not program execution order:

```text
command.ResultData  → [nullable conversion / fallback] → local2
(Volvo, local2)     → DetectResult constructor             → model.DetectResult
model.DetectResult  → Ecus constructor                     → model.Ecus
command.DataHash    → model.dataHash
model.DetectResult  → Units enumeration / loader projections
```

### Automated independent verification

The allowlist auditor `emulator/tools/audit_recovered_il.py` now uses **(module name, MethodDef token)** as method identity, because a MethodDef token is **module-scoped**. The previously selected 28 tokens happened not to collide; however, globally keying future input by numeric token alone could silently misattribute methods from two DLLs. The tool checks 6 exact, bounded `Detect` shape predicates and retains the existing timer/status/count checks. New synthetic tests #9–16 check module-token collisions, module mismatch/missing metadata, positive constructor provenance, negative constructor/hash mutations, and explicit non-reachability of source motifs.

These predicates **do not reconstruct control-flow flattening, decrypt strings, identify the network protocol, or establish a physical CEM request**. No code, binaries, private logs, VINs, or new RX fixtures are incorporated. Two releases are **not** compared semantically: the recovered static module is VDASH portable 2.5.115.79 while earlier J2534 logs concern VDASH 2.0.

**End-to-end blocker remains:** full method bodies for `CreateCommand` (`0x06001329`), `Enqueue` (`0x0600132C`), `ParseData` (`0x06001160`), `OnCheckResult` (`0x0600115F`) and the `0x060011BB/0x0600126D` constructors, plus the `Model_DetectDone` predicate. Until they are available, claiming a specific ECU-discovery acceptance rule would be conjecture.

## Three exact direct-CIL branch edges: new negative-detect gate (2026-11-02)

The saved recovered IL listing for **portable VDASH 2.5.115.79** was independently checked with actual byte offsets (module `Frontend.Client.Core.dll`). The three edges below are **source-level conditional branches**, not an entire reconstructed flattened CFG.

| Method | Branch and computed target | Target operations | Bounded conclusion |
|---|---|---|---|
| `VddModel.GetVin`, MethodDef `0x0600133A` (47 opcodes) | `IL_0006 brfalse.s +108`; next IL_0008 + 108 = **IL_0074** | `ldarg.0; get_Volvo` | If the immediately preceding `get_PreDetectResult` null-check is false, execution enters the Volvo fallback. It does not imply a new J2534 read. |
| `VddModel.GetConfig`, MethodDef `0x06001339` (9 opcodes) | `IL_0007 brtrue.s +3`; next IL_0009 + 3 = **IL_000C** | `get_Config; ret`; fall-through `pop; ldnull; ret` | The method returns `DetectResult.Config` if the DetectResult exists; otherwise returns null. No PassThru operation occurs in the nine-instruction body. |
| `VddModel.Detect`, MethodDef `0x0600132B` (511 opcodes) | `IL_012E brfalse +1437`; next IL_0133 + 1437 = **IL_06D0** | `ldc.i4.0; ret` | **If a particular command-result-dependent predicate evaluates false, Detect directly returns false**, without following the rest of that path. |

The predicate producing the third condition is visible immediately before the branch: `ldloc.1` → `get_Result (0x0600113E)` → obfuscated generic call `0x2B000002` → obfuscated function `0x06001359` → `brfalse`. **The semantic meaning of `get_Result` codes and function `0x06001359` remains unknown**. In particular, this does *not* prove the predicate represents timeout, invalid DataHash, an absent CEM, denial by a remote server, or any other specific error.

We did not treat the existence of a false-return edge as proof that a particular runtime session took it; control-flow flattening still prevents complete reachability/probability analysis. The real body has another direct unconditional `br` from IL_0612 to the same `return false` target, whose preceding flattening dispatch has not been reconstructed. Do not conclude "false means missing ECU" from these edges.

### Regression evidence and method identity

The non-executing, allowlist-only `emulator/tools/audit_recovered_il.py` was updated to parse and check **monotonically increasing IL offsets**, then resolve only three recognized relative branch edges to existing instruction addresses. It retains (assembly, MethodDef token) identity and avoids exporting raw IL, strings, VINs or private logs. It now reports fixed-schema `recovered-il-evidence-audit-v3`. Eight **additional synthetic tests** (#17–24) include correct edges, off-by-one targets, malformed offsets, altered null arm, wrong opcode and the explicit inability to infer runtime reachability. They are synthetic checks only, and the original VDASH binary was neither run nor committed.

**Practical diagnostic implication:** For a future single, authorized VDASH 2.5.115.79 run, distinguish `PreDetectResult` cache/suggestion, the boolean return from `Detect` when observable through UI/logs, receipt and acceptance of `VddCommand.ResultData`, then construction and visibility of the `Ecus` model. This does *not* license fabricating CEM A6/B9FB replies, bypassing status checks, network interception or ECU programming. Full bodies for `0x06001359`, `CreateCommand`, `Enqueue`, `ParseData` and the `DetectResult/Ecus` constructors are still absent from selected artifacts.

## Corrected hypothesis: opaque predicate 0x06001359 is reused (2026-11-02)

**New source-grounded observation.** In the recovered IL excerpt for `Frontend.Client.Core.dll` / `VddModel.Detect` (MethodDef `0x0600132B`), `0x06001359` is called **twice**, not once, and both sites invoke the same intermediate generic MethodSpec `0x2B000002` (as printed by the extractor):

| Site | Seven-opcode input neighborhood | Subsequent branch |
|---|---|---|
| `IL_0129 call 0x06001359` | `ldloc.1; get_Result (0x0600113E); ldc.i4 2109910401; br.s 0; call 0x2B000002; call 0x06001359` | `IL_012E brfalse +1437`, direct target `IL_06D0 ldc.i4.0; ret` |
| `IL_0428 call 0x06001359` | `ldloc.s 6; get_HardwareNumber (0x06001F95); ldc.i4 1096372403; br.s 0; call 0x2B000002; call 0x06001359` | `IL_042D brtrue.s +8`, an ordinary flattened-CFG dispatch branch |

**Correction:** `0x06001359` cannot responsibly be described as a **dedicated CEM-result validator**. It is reused with at least two different sources of data: a `VddCommand.Result` value and a `Unit.HardwareNumber` value. This is consistent with an equality/comparison or another reusable predicate, but **does not establish** its signature, return semantics, decoded constants, or enum meanings. The printed constant operands are not interpreted as plaintext. The `Detect = false` edge remains genuine, yet its meaning is unknown and the runtime reachability of this branch is not established.

The **static analysis tool** now emits only two allowlisted evidence fields: `detect_shared_predicate_for_result_and_hardware_number` (true only when both exact seven-opcode local shapes are present) and `detect_shared_predicate_call_count` (an integer count, expected 2 in this excerpt). These are **method-body observations, not dynamic instrumentation**. Eight synthetic tests (#25–32) cover matching both sources, broken result/hardware getters, wrong helper/predicate, altered branch or local, plus the explicit uncertainty about semantic meaning. The normalized report format is `recovered-il-evidence-audit-v4`. Source artifacts remain private; no proprietary IL excerpt is checked into Git.

**Next missing evidence:** to discover what `0x06001359` actually does, obtain the matching original recovered assembly (with authorized user access) and inspect MethodDef body, method signature and `0x2B000002` MethodSpec/type instantiation together. Neither original recovered DLL nor full method body is in the currently accessible saved extracts. Do not guess an ECU acceptance rule, hash validation, or server error from these callsites. The current PR does not modify the emulator's J2534 response behavior, main branch or releases.

## MethodSpec metadata cross-check: one System.String generic argument (2026-11-02)

A new, externally verified fact is available **without** possession of the original recovered assembly. At both previously documented `VddModel.Detect` sites (IL_0124 and IL_0423), the saved IL excerpt prints the **same** MethodSpec operand **`0x2B000002`** with a blob that decodes to the three bytes **`0A 01 0E`**. Both are adjacent to calls to the same opaque MethodDef `0x06001359` (at IL_0129 and IL_0428 respectively).

Per **ECMA-335, sixth edition (June 2012), Partition II §§23.1.16 and 23.2.15**, a *MethodSpec* signature begins with `GENERICINST = 0x0A`, followed by a compressed generic-argument count, followed by those type signatures. The one-byte `0x01` count is exactly one; the one-byte `ELEMENT_TYPE_STRING = 0x0E` represents `System.String`. Therefore, **the printed MethodSpec is a generic-method instantiation using one System.String type argument**. Authoritative standard: https://www.ecma-international.org/wp-content/uploads/ECMA-335_6th_edition_june_2012.pdf (see II.23.2.15 and the ELEMENT_TYPE table).

This is **not** proof that the instantiated method returns `string`, decodes a constant, compares strings, validates ECUs, interprets the diagnostic status, or performs a server authorization. A generic type argument is type metadata, not a string value. The MethodSpec row's referenced base method and the bodies/signatures of `0x06001359` and the instantiated generic method remain unavailable in the 11 saved IL method bodies.

Two localized, independent observations remain:

1. `get_Result → constant → MethodSpec<string> → 0x06001359 → brfalse` leads to a direct `Detect = false` target if that source block is executed and the predicate is false.
2. `get_HardwareNumber → different constant → MethodSpec<string> → 0x06001359 → brtrue` reuses the **same MethodSpec<string> and predicate**, but the flattened CFG prevents us from naming that predicate.

### Safe automated check

The non-executing audit script now reports only the **number of adjacent MethodSpec<string> / predicate pairs** and a boolean indicating whether both expected callsites match, under fixed schema `recovered-il-evidence-audit-v5`. It uses Python's bounded `ast.literal_eval` on *bytes literals*, not `eval`, and accepts only an exact `0A 01 0E` signature. Eight **synthetic** regression checks cover alternate bytes escaping, generic arity/type/prefix mutations, missing one MethodSpec call, malformed/oversize literals, and privacy of the allowlisted output. These checks do not require or embed proprietary binary or IL snippets.

**Unblocked source requirement for stronger conclusions:** the matching recovered DLL/metadata (authorized local inspection only) must expose the MethodSpec table's underlying method token, signature, and corresponding `0x06001359` body. Only then can the expression be interpreted. Separately, body of `VddCommand.ParseData` and the `DetectResult/Ecus` constructors are needed to determine how a successful read-only command becomes a visible ECU. Do not fabricate CEM response blocks or borrow a donor's B9FB identity for an XC90 V8 MY2009.

## Execute → ParseData: two unknown result wrappers at exact IL site (2026-11-03)

A new private, independent comparison was performed against the locally
retained recovered `VDASH_Recovered_Diagnostic_IL_Excerpts.txt` and its
`.part2.txt`, plus the two halves of
`VDASH_Recovered_Methods_Inventory.txt`. **This is a check of already
recovered IL text**, not a fresh decompilation or a runtime VDASH trace.

For the `VddCommand.Execute` MethodDef `0x0600115D`, a **single contiguous
eight-instruction neighborhood** at fixed offsets is visible:

| IL offset | Instruction | What can be observed |
|---|---|---|
| `0247` | `ldarg.0` | Instance reference loaded |
| `0248` | `ldarg.0` | Instance reference loaded again |
| `0249` | `ldfld 0x04000333` | Command `result` field read |
| `024E` | `call 0x0600117A` | Unknown helper called |
| `0253` | `ldarg.0` | Instance reference loaded |
| `0254` | `ldfld 0x04000333` | Same `result` field read |
| `0259` | `call 0x0600117B` | A second unknown helper called |
| `025E` | `call 0x06001160` | `ParseData` called |

The independently saved method inventory lists **one call to each** of
`0x0600117A`, `0x0600117B`, and `0x06001160` in `Execute`. Thus
both the recovered CIL neighborhood and the call-frequency inventory
corroborate the *static staging sequence*.

This says **nothing yet** about the two helper return types, meaning of
their outputs, actual `ParseData` parameter types, reachability of the
flattened control-flow path, successful completion, command result semantics
or acceptance of a virtual ECU. In particular, the two unknown helpers
could transform or interpret the `result` object in ways that are not
available from this excerpt.

The offline auditor `emulator/tools/audit_recovered_il.py` now has two
independent allowlisted outputs:

- `execute_parse_data_two_result_wrappers_exact_static_site`: true
  only for all eight exact adjacent opcodes, tokens and IL offsets.
- `execute_parse_data_wrappers_inventory`: reports
  `three_single_calls_observed`, `counts_differ`,
  `invalid_inventory` or `unreported` for the two helpers plus
  `ParseData`. An absent call list is **unknown**, not negative evidence.

Eight synthetic mutations test the exact instruction order, helpers,
repeated result-field references, caller reference, offsets, presence
and consistency of the call inventory, malformed counts and private
symbol redaction. The repository contains no original proprietary IL text,
VIN, DLL or private archive hashes.

**Next G2 gate:** inspect the actual bodies/signatures of `0x0600117A`,
`0x0600117B` and `ParseData` in a matching original or recovered DLL,
then separately validate client-side command acceptance in a real read-only
VDASH run. Static callsite evidence alone cannot pass that gate.

## Handoff

Linked to issues #37 and #4 and PR #39. Only the read-only analysis script, synthetic tests and research documentation were added in this follow-up; no ECU behavior, fixtures or emulator responses changed. Original source artifacts remain private. Windows/VMware VDASH and physical J2534 were not run in this static-analysis step; neither ECU discovery nor model-year compatibility has been demonstrated. Do not merge to main or create a release.


## PreDetectDone vs OnDetectDone: two independent static phase anchors (2026-11-03)

A new check of the saved, authorized **VDASH portable 2.5.115.79**
`Frontend.Client.Core.dll` recovered CIL excerpts identified a separate
pre-detection completion callback and four subsequent availability refresh
calls within `Detect`. These facts are **source-location observations**,
not proof that those branches executed in a given session.

| Method | Exact MethodDef/IL site | What the source directly supports |
| --- | --- | --- |
| `VddModel.PreDetect` | `newobj 0x0600139D` at `IL_0195`, `set_PreDetectResult` at `IL_019A` | A `PreDetectResult` construction/store site receives existing model, dongle ID, and computed locals. The source does not establish fresh VIN transport. |
| `VddModel.PreDetect` | `PreDetectDone` field `0x040003CC` at `IL_01A0`; guarded `brtrue.s +6` at `IL_01A6 → IL_01AE`; `EventHandler.Invoke` at `IL_01B4` | The recovered body contains an independently guarded pre-detect completion **event invocation** after the result-store site in printed IL. This does not prove the event fired or that the result contains a valid VIN. |
| `VddModel.Detect` | `Ecus .ctor 0x0600126D` at `IL_0268`, `set_Ecus` at `IL_026D` | A separate ECU-model projection site depends on `DetectResult`, not directly on `PreDetectResult`. |
| `VddModel.Detect` | `RefreshAvailability` at `IL_05D3`, `IL_061D`, `IL_064E`, `IL_06A3` | Four distinct methods on `Dim`, `Ecm`, `Icm`, `Phm` are called from **static callsites**. There is no proof of any module being accepted. |
| `VddModel.Detect` | `OnDetectDone 0x06001343` at `IL_0633` | A different completion callback from the `PreDetectDone` event. |
| `VddModel.Detect` | `set_DeviceAvailable 0x060012F7` at `IL_0685`, immediately preceded by `ldc.i4.1` | One site sets the device-availability property to true if executed. It is not evidence of ECU visibility or a verified vehicle identity. |

**Critical caution:** The relative offsets of `OnDetectDone`,
`RefreshAvailability` and `DeviceAvailable` are **not a temporal trace**.
The method retains a control-flow-flattened switch graph. In particular,
printed `OnDetectDone` occurs between some of the refresh sites, which
must **not** be interpreted as an execution order. The exact implementations
of `RefreshAvailability` and the UI predicate remain outside the selected
recovered bodies.

**Diagnostic implication (hypothesis only):** A vehicle label/VIN may
appear after pre-detection independently of a populated ECU list. Even when
a later `Ecus` object exists, module availability and UI projection could
still be separate acceptance gates. A single new version-labelled read-only
client run must distinguish pre-detect UI event, explicit Connect, J2534
request/response delivery, command completion and a nonempty ECU list.

Implementation: the existing `emulator/tools/audit_recovered_il.py` now
reports seven allowlisted static indicators (two event/result sites plus an
aggregate phase flag; refresh-site count, DetectDone site, DeviceAvailable
site plus combined ECU/UI indicator) under
`recovered-il-evidence-audit-v6`. Eight synthetic mutation tests
(#49–56) validate site offsets/tokens, guarded branch destination, four
independent availability methods, incomplete sources and privacy.
No original vendor body, decrypted code, personal VIN, CAN frame or
authorized runtime trace is committed. No Virtual Car ECU protocol behavior
or J2534 firmware shim has been changed. Tests are not proof of VDASH
client acceptance or a real XC90 V8 MY2009 scan.


## DetectResult.Units, per-unit fields and LoaderResult: bounded G3 static audit (2026-11-03)

**Evidence:** saved, user-authorized recovered CIL excerpt from *VDASH portable 2.5.115.79*, `Frontend.Client.Core.dll`, `VddModel.Detect` MethodDef `0x0600132B`. This version is not the VDASH 2.0 client used in historical virtual-J2534 VIN observations.

### Newly distinguished source sites

| IL site(s) | CIL calls/fields | Bounded meaning |
| --- | --- | --- |
| `02A4–02B4` | `get_DetectResult → get_Units → GetEnumerator → stloc.s 5` | First static enumerator-construction site. No proof its enumerator contains data. |
| `030C–030E` | Unit-like local `6` → `get_Ecu` | An ECU property getter in a collection processing neighborhood; value and criteria unknown. |
| `0415–0417` | The same printed local `6` → `get_HardwareNumber` | Hardware-number field can participate in the branch logic. Exact semantics of shared opaque predicate `0x06001359` still unknown. |
| `04DF–04EF` | `get_DetectResult → get_Units → GetEnumerator → stloc.s 5` | **Second distinct source site** retrieving `Units`; flattened CFG does not prove two executed loops or temporal ordering. |
| `0530–0539` | Enumerator `get_Current` → local object field `0x040003D3` | A current unit-like item is staged to a local field; its decoded CLR type is not independently proven. |
| `0568–0583` | Current item, callback `0x06001387`, opaque generic MethodSpec `0x2B000023`, `set_LoaderResult` | A separate loader-result assignment motif. Neither the callback body, result type nor a successful load is established. |
| `01E2–01E9` | Command `get_Session` → model field `0x040003AA` | Session is stored in the model at a distinct static site. It does not identify a J2534 channel, HTTP session, or ECU identity without further evidence. |

**New distinction:** creating `Ecus` from `DetectResult`, enumerating `DetectResult.Units`, assigning `LoaderResult`, refreshing per-module availability, and updating UI are **different source operations**. These operations can be explained as separate potential G3/G4 failure gates, but cannot be asserted as a sequential runtime pipeline. A displayed vehicle or pre-existing engine label does not show which operations ran.

**Negative evidence boundaries:** Neither enumerator site proves positive ECU data; the local `get_Ecu` or `get_HardwareNumber` does not prove a physical ECU was queried; `set_LoaderResult` does not prove loading succeeded; no documented D2 B9F0/B9FB/B9FC-to-property mapping exists in this excerpt. Missing static motifs from an incomplete inspection must not be labeled `ECU rejected`, `CEM absent`, `VIN invalid` or `timeout`.

**Source checks:** The existing `emulator/tools/audit_recovered_il.py` gains seven allowlisted output facts (two-site count, ECU getter, hardware getter, current-item capture, loader assignment, independent session store and aggregate source-shape flag) under `recovered-il-evidence-audit-v7`. Eight synthetic tests (#57–64) mutate offsets, target tokens, current-item field, callback, independent session handling and privacy; no original proprietary CIL, customer VIN or production secrets are stored. The tests do not execute VDASH.

**Next gating evidence:** obtain legally accessible original/recovered bodies for the constructors `0x060011BB/0x0600126D`, the four `RefreshAvailability` implementations, the `get_Ecu`/`get_HardwareNumber` property types, the loader callback `0x06001387` and the UI's `Model_DetectDone` predicate. In an isolated, read-only VDASH client session, independently record (1) source/version and selected driver, (2) fresh pre-detect vs cache, (3) explicit Connect, (4) J2534 TX/RX/filters with statuses, (5) command-completion milestone and (6) actual ECU list. No CEM A3/A6/B9FB positive response should be fabricated to pass these gates.

## UI Model_DetectDone call inventory: known tokens, missing body (2026-11-03)

The saved **VDASH portable 2.5.115.79** selected-method inventory includes
`Frontend.exe` `DetectViewModel.Model_DetectDone` (MethodDef `0x06002472`,
reported **379 decoded instructions**, **0 decoder issues**). Importantly,
the user-provided selected IL *excerpt does not contain its full body*.
The inventory lists method calls, **not their order or reached branches**:

| Named call in indexed inventory | MethodDef in Frontend.exe | Bounded interpretation |
| --- | --- | --- |
| `set_ModelId` | `0x0600695B` | Model identifier may be updated in UI; actual value unknown |
| `set_Header` | `0x0600695D` | Displayed header has a setter; not proof of a freshly detected vehicle |
| `InitializeUnits` | `0x06002469` | A unit-list initializer is referenced; **body and acceptance predicate unavailable** |
| `set_DtcsRowHeight` | `0x060023C9` | UI layout property, not an ECU scan |
| `set_IsShowDtcsVisible` | `0x060023D5` | DTC visibility property, not ECU availability proof |
| `get_CemCommand` | `0x060023DC` | Command property getter only; not evidence of CEM transmission, configuration or PIN |
| `get_Tuning` | `0x060023F1` | UI/model property getter; not evidence a tuning command ran |

The earlier static `VddModel.Detect` sites called
`RefreshAvailability` on DIM/ECM/ICM/PHM methods:
`0x06001BB2 / 0x06001BBA / 0x06001BCC / 0x06001BE9`
(all in `Frontend.Client.Core.dll`). **None of these four method bodies
nor `Model_DetectDone` was included in the selected recovered IL excerpt.**
This is an **evidence-coverage limitation**, not evidence that the original
program lacks their implementations.

### New G4 coverage report

The existing static auditor reports, under
`recovered-il-evidence-audit-v8`, the number of seven exact one-count UI
call tokens indexed, presence of `InitializeUnits` and the `CemCommand`
getter, four UI projection method tokens, known instruction/decoder issue
counts, and whether corresponding full method bodies are actually present
in the selected excerpt. Its status is intentionally
`not_selected / calls_unreported / invalid_call_inventory /
partial_or_duplicate_named_calls / seven_single_calls_indexed`.
An index-only result can **never** be treated as a parsed ECU list or a
verified display predicate.

Eight additional synthetic regressions (#65–72) enforce assembly-local
MethodDef matching, missing source, partial/duplicate/malformed call
inventories, direct method-body presence distinction, and output
allowlisting. No proprietary CIL, VIN, identifiers, PIN, auth tokens or
wire payloads were stored.

**Next missing evidence:** complete authorized bodies of
`Model_DetectDone`, `InitializeUnits`, four `RefreshAvailability`
implementations, `Ecus` constructor and `DetectResult.Units` model.
In parallel obtain a fresh read-only, version-scoped VDASH UI observation
and J2534 transport audit before deciding whether transport or UI is the
blocker. Do not hard-code fabricated OEM CEM responses to satisfy presumed
UI conditions. The Virtual Car emulator and J2534 DLL were not changed.

## G4 dependency body-coverage matrix: eight provenance gates (2026-11-03)

This addition inventories **what can and cannot yet be read** from
the user-authorized *VDASH portable 2.5.115.79* extracted method selection.
It does **not** reconstruct the missing functions.

| Target | Module / MethodDef | How it is referenced | Current saved selected evidence |
| --- | --- | --- | --- |
| `Model_DetectDone` | Frontend.exe `0x06002472` | Present in selected method inventory | Indexed, body absent from 11 saved excerpts |
| `InitializeUnits` | Frontend.exe `0x06002469` | `Model_DetectDone` call inventory | Caller lists invocation; target not selected |
| `DIM.RefreshAvailability` | Frontend.Client.Core.dll `0x06001BB2` | Exact static callsite in `VddModel.Detect` | Target body not selected |
| `ECM.RefreshAvailability` | Frontend.Client.Core.dll `0x06001BBA` | Exact static callsite in `VddModel.Detect` | Target body not selected |
| `ICM.RefreshAvailability` | Frontend.Client.Core.dll `0x06001BCC` | Exact static callsite in `VddModel.Detect` | Target body not selected |
| `PHM.RefreshAvailability` | Frontend.Client.Core.dll `0x06001BE9` | Exact static callsite in `VddModel.Detect` | Target body not selected |
| `DetectResult .ctor` | Frontend.Client.Core.dll `0x060011BB` | `get_Volvo + local2` constructor motif | Target body not selected |
| `Ecus .ctor` | Frontend.Client.Core.dll `0x0600126D` | `DetectResult` constructor motif | Target body not selected |

Here **not selected** means only *absent from our limited 28-method
inventory*, not absent from the original program; **selected without
excerpt** means a method was indexed but its complete IL body was not
supplied among the 11 saved extracts. The two categories must not be
conflated. All MethodDef tokens are **assembly-scoped** and
**2.5.115.79 build-specific**.

The `recovered-il-evidence-audit-v9` output now contains an independent
`g4_dependency_coverage` object with exactly eight fixed labels. Each
shows one source evidence level (`indexed_method`, `indexed_call`,
`direct_il`, `not_observed`) and one target body coverage level
(`excerpt_present`, `selected_without_excerpt`, `not_selected`).
Only direct-CIL neighborhoods or the indexed `InitializeUnits` call
justify a reference flag; target selection/body presence is checked
independently. This is an *evidence availability map*, not a
reconstructed VDASH control-flow graph.

On the previously reviewed selected artifacts the expected coverage is
**eight distinct indexed/referenced targets, zero complete method bodies
for these targets**. The remaining gap is therefore primarily **source
acquisition and verification**, not evidence for a specific ECU rejection
rule. New synthetic tests #73–80 verify references, missing callers,
module-token collisions, presence of one complete target body,
independent refresh calls, mutation of one constructor and privacy.
No original vendor CIL excerpts, customer VINs, or read/write protocol
replies are committed.

**Do not infer** that there are exactly eight relevant methods in the
original client: this fixed shortlist is a research priority. A future
authorized recovered body could disprove the working UI-acceptance
hypothesis or reveal entirely different gates. Dynamic G4 ECU-list
acceptance must still be checked in a fresh, read-only, version-specific
VDASH UI session; current CI validates only synthetic metadata processing
and Virtual Car code.

