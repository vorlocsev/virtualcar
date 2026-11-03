# VDASH official documentation ↔ recovered-variable crosswalk (2026-11-03)

**Scope:** public D5T5 documentation reviewed 2026-11-03 versus Virtual Car's earlier, user-authorized static evidence for VDASH portable **2.5.115.79** and separate historical J2534 observations of **VDASH 2.0**. **No vendor source code/API contract** was published in the reviewed pages. This is a correlation of product concepts to privately recovered *names and IL callsites*, not a documented property schema, verified runtime trace, emulator acceptance result, or mapping to CAN commands.

**Target:** read-only Virtual Car simulation of P2 XC90 4.4 V8 MY2009. Do not edit or merge Dvinholm. No PIN/security operations, program/erase/modify commands, licensing bypass, synthetic OEM ECU acknowledgement, client binary or private VIN.

## Most consequential official findings

1. **Two UI phases.** Official *VDASH Basics* describes waiting for vehicle detection, then pressing **Connect**, then VDASH scanning and loading available modules. Thus a shown VIN is not proof of successful ECU enumeration. Source: https://d5t5.com/wiki/vdash/article-vdash-basics
2. **The right P2 platform and engine are supported at a product level.** Official VDASH information lists XC90 under P2. CEM PIN guidance expressly lists **XC90 4.4 V8** among P2 vehicles for VDASH CEM PIN decoding. This is *not* a protocol payload, hardware number, checksum or a claim of a specific MY2009 firmware variant. Sources: https://d5t5.com/article/vdash-volvo-diagnostic and https://d5t5.com/article/volvo-cem-pin-code
3. **Do not confuse distinct security concepts.** Official PIN taxonomy differentiates vehicle-configuration **CEM PIN** from immobilizer **CEM IMMO PIN**; the page excludes P2 XC90 V8 from VDASH CEM IMMO decoding while listing it for CEM configuration PIN decoding. These functions must never be taken as part of basic read-only VIN/ECU discovery. Source: https://d5t5.com/article/volvo_pin_codes_explained
4. **VDD is also a standalone device.** The manufacturer's VDD (VDASH Dongle) is OBD/GSM hardware. The presence of a managed class called `VddCommand` does *not* prove that every instance uses this separate device, nor that a class called VDD maps directly to a PassThru transport. Source: https://dev.d5t5.com/article/vdash-vdd-dongle
5. **VMware is explicitly unsupported by D5T5.** The vendor states VM/VMware/VirtualPC configurations are not allowed because of USB/DiCE stability. Therefore VMware is an independent lab environment that cannot be used as vendor-certified proof or automatically blamed for a failure. Source: https://d5t5.com/wiki/vdash/article-vdash-virtual-environment-vmware-virtualpc
6. **Generic J2534 is supported with caveats**, while DiCE/SUPER J2534 remain preferred. Official material provides x86 and x64 *driver* packages, not proof that a given diagnostic process can load a given 32-bit DLL. Source: https://d5t5.com/wiki/vdash/article-generic-j2534
7. **Version boundary:** vendor release notes list **2.5.115.81 (2026-10-16)** as newer than our recovered **2.5.115.79**. No public internal MethodDef/field-token compatibility contract exists between them. Source: https://d5t5.com/wiki/wiki/article-release-notes-vdash

## Crosswalk: public feature ↔ recovered symbols

Legend: **DOC** = directly stated public product behavior, **IL** = source-grounded in private 2.5.115.79 recovered IL/REA or summarized bounded inventory, **INFERENCE** = candidate correlation only, **RUNTIME20** = a different VDASH 2.0 lab source. A token is **module/build scoped**, not a portable API name.

| Official documentation / feature (DOC) | Recovered symbol / source (IL or Virtual Car) | Correlation and limit |
| --- | --- | --- |
| Vehicle is detected before Connect | `VddModel.PreDetect 0x0600133D`, `SuggestedVin`, `PreDetectResult`, `set_Volvo`, `get_PreDetectResult` | **INFERENCE:** plausible pre-connection model; recovered code also references saved DataViewV2. Presence of a VIN may be cached/suggested; DOC does not specify these names or local/remote data source. |
| Press **Connect** to scan and load modules | `VddModel.Detect 0x0600132B`; `CreateCommand 0x06001329`, `Enqueue 0x0600132C`, `VddCommand.Wait 0x0600115B` | **INFERENCE:** plausible connection-stage work queue. Do not equate a method call with a specific D2/UDS/CAN request. |
| Car VIN appears in the product | `GetVin 0x0600133A` reads `PreDetectResult.Vin` or `Volvo` fallback | **IL:** getter reads existing state. Not proof of fresh J2534 RX. Separate VDASH 2.0 `09 02`/`49 02 01` observation must not be attributed to this 2.5.115.79 getter. |
| Internet is required for VDASH | `Client.Core.SendV2 0x060002EF`, `StartSession 0x060003AF/B0`; previous `VdashClient.CreateOrUpdateNonDbWr` result pipeline | **INFERENCE:** consistent with online lifecycle, not proof of exact endpoint, server-side command execution, protobuf fields or login rules. |
| J2534/DiCE diagnostic hardware is required for OBD | `J2534DiagnoseManager.Add/FindImplementation 0x06001C65/66`; Virtual Car `PassThruOpen/Connect/ReadMsgs` | **INFERENCE:** hardware selection/API boundary. No exact provider implementation, native method call or mapping to managed `VddCommand` is recovered. |
| Battery/ignition requirements and voltage calibration | `PreDetect.set_Voltage`; `DongleCommandExecutionResult.Voltage` (previous envelope); Virtual Car `BatteryMv=12500` synthetic fixture | **INFERENCE:** vehicle voltage can be modeled, but no evidence these values are equivalent or that voltage alone proves ignition II. Release 2.5.114 added calibration for uncalibrated J2534. |
| Results from a diagnostic command | `VddCommand.Execute 0x0600115D`, `result 0x04000333` typed as `DongleCommandExecutionResult`, `ParseData 0x06001160` | **IL:** Execute obtains a result object and calls ParseData in a flattened CFG. Product docs do not describe `Status`, `Session`, `Data`, `Hash` structure. No completion/acceptance path proven. |
| Result staging preceding parsing | Helper `0x0600117A : (class:1349) → class:205[]`; `0x0600117B : (class:1349) → byte[]`; `ParseData : (class:205[], byte[]) → void` | **REA:** types agree with input `result` field `class:1349`; exact callsites `IL_024E`, `IL_0259`, `IL_025E`. This is *type compatibility only*, not verified DataView decoding or ECU schema. |
| Successful ECU scan populates module list | `DetectResult` `newobj 0x060011BB`, `Ecus` `newobj 0x0600126D`, `set_DetectResult`, `set_Ecus`, `DetectResult.Units` | **IL:** plausible result projection; no nonempty ECU list, CEM identity or acceptance predicate proven. `FastDetectEcu` stubs observed in selected build do not rule out other paths. |
| ECU individual refresh, engine type visible if previously detected | `DetectViewModel.Model_DetectDone 0x06002472`, `set_ModelId`, `set_Header`, `InitializeUnits`; `get_HardwareNumber` | **INFERENCE:** could map to UI refresh/cached engine data. These release-note features affirm that UI display and a fresh scan are distinct observations; do not assert code-to-button correspondence. |
| Vehicle configuration | `VddModel.GetConfig 0x06001339` reads `DetectResult.Config`, `get_CemCommand` in UI inventory | **IL/INFERENCE:** getter does not send CAN frames; neither symbol proves executing or unlocking CEM configuration. Do not equate `get_CemCommand` to `B9FC` or PIN operation. |
| Diagnostic status / abort / timeout | `get_Result`, `set_Result`, `get_Timeout`, `OnCheckResult`, `executionEvn`, `waitEvn`, opaque accessor `0x06001178` | **IL:** explicit comparisons against literals 2, 3, 4, timer callshape. Their enum mapping and runtime behavior remain *unproven*. DOC only documents a user-visible Abort action introduced in version 2.5.115.3. |
| DataHash or other result validation | `get_DataHash`, `set_DataHash`, `Detect.dataHash`; prior result envelope `Hash` | **IL:** fields/accessors exist; no proof of SHA, signature, HTTP integrity, checksum for P2 B9FB or required server validation. |
| Specific P2 CEM wire response | D2 `B9F0`, `B9FB`, `B9FC` in separate published Volvo investigations and Virtual Car fixtures | **NOT IN DOC:** no manufacturer document maps these opcodes to any of the preceding managed symbols; do not use XC70 donor B9FB as valid MY2009 XC90 identity. |

## Official release notes material to test design

- **2023-06-05 / 2.5.107:** user setting to **not automatically detect** the car immediately after login. It can change the *time at which detection is attempted*, so absence of requests on login is not an ECU negative result.
- **2023-10-12 / 2.5.114:** voltage calibration for non-calibrated J2534 hardware. Do not assume one hard-coded battery millivolt field explains acceptance.
- **2024-02-14 / 2.5.115.3:** generic J2534 support and an Abort button. A close/abort is not successful discovery.
- **2024-03-10 / 2.5.115.5:** individual ECU re-read supported. Distinguish initial ECU discovery from subsequent refresh.
- **2024-03-28 / 2.5.115.7:** basic OBD-device diagnostics added. Treat device validation separately from OEM CEM identity.
- **2025-07-11 / 2.5.115.64:** engine ECU type displayed in the car profile **if detected previously**. A model/profile field alone does not prove live detection.
- **2026-10-16 / 2.5.115.81:** ELM327 diagnostics added; this was **after** the researched 2.5.115.79, so do not ascribe any ELM discovery path to it without build-specific evidence.

## Observations, not explanations

In the historical **VDASH 2.0** virtual-J2534 lab, an OBD `09 02` request and synthesized `49 02 01` VIN response were reported, followed by a UI VIN/model view but **empty ECU list**. Later traffic included functional `3E 80`; selected accumulated logs had no source-confirmed individual P2 CEM `B9F0/B9FB/B9FC` reads. This is a *different program version* from recovered IL and a repeated lab trace, not proof that the later client's `Detect` returned false.

An older `emulator/virtualcar-vdash-lab.ini` also contains a P3 `[ECU1]` route `0x726/0x72E` and a synthetic model-year-inconsistent VIN. **Do not use that fixture as an authentic P2 XC90 V8 MY2009 identity** or silently bind it to vendor claims.

## Next read-only validation, eight gates

1. Record exact client build, x86/x64, host/VM, selected J2534 adapter, checksum of the *virtual* DLL and detect-on-login option.
2. Record separately first **pre-detect** indication (VIN/vehicle) and an explicit user **Connect** action. Record whether VIN was prepopulated/cached.
3. Inspect PassThru Open/Connect/config/filter outcomes and RX_START/data messages using existing allowlist audits. A successful J2534 Connect does not imply ECU recognition.
4. Confirm one source-labelled `09 02` ↔ `49 02 01` pair, or explicitly mark not observed. Preserve genuine timestamp and request boundaries.
5. Observe actual read-only target-specific P2 queries after Connect; classify missing/filtered/timeout/partial/delivered. Do **not** invent `B9F0/B9FB/B9FC` or acknowledge reset/security operations.
6. Capture sanitized client-facing milestones (command pending/completed, ECU refresh, ECU list display). These are not replaced by CIL callsites or `PassThruClose`.
7. Separate reported hardware/voltage, network/session lifecycle, server/result lifecycle and UI ECU presentation. Do not equate `VddCommand.Result` with J2534 API success.
8. Report acceptance only when a **new, single-run** client session and J2534 log correlate on this exact version. Host Windows is preferable for vendor-supported validation; VMware remains unsupported and physical J2534 untested.

## Sources and boundaries

Public vendor URLs:
- https://d5t5.com/wiki/vdash/article-vdash-basics
- https://d5t5.com/article/vdash-volvo-diagnostic
- https://d5t5.com/wiki/vdash/article-generic-j2534
- https://d5t5.com/wiki/vdash/article-vdash-virtual-environment-vmware-virtualpc
- https://d5t5.com/article/volvo-cem-pin-code
- https://d5t5.com/article/volvo_pin_codes_explained
- https://d5t5.com/wiki/wiki/article-release-notes-vdash
- https://dev.d5t5.com/article/vdash-vdd-dongle

Bounded internal research (private source bytes intentionally excluded):
- [VDASH_IL_STATIC_AUDIT.md](VDASH_IL_STATIC_AUDIT.md)
- [VDASH_REA_OFFLINE_WORKFLOW.md](VDASH_REA_OFFLINE_WORKFLOW.md)
- [VDASH_PROTOCOL_EVIDENCE.md](VDASH_PROTOCOL_EVIDENCE.md)
- [VDASH_RESEARCH_HANDOFF.md](VDASH_RESEARCH_HANDOFF.md)

**Research-only.** No method/enum or CLI API is declared officially by the vendor. No proof of authentic P2 MY2009 CEM, live ECU enumeration or server-side acceptance exists in this crosswalk.
