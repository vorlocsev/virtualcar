# VDASH research handoff for Codex (2026-11-02)

> Status: evidence dossier and implementation task specification, **not** proof that VDASH reaches a native J2534 transport through any named managed method. This document contains conclusions from earlier authorized, offline examination; independently recheck against accessible local artifacts. Do not commit proprietary binaries, private dumps or personal identifiers.

## Target and repository boundary

- Repository: `vorlocsev/virtualcar`; branch: `development`; PR target: `development`.
- **Virtual Car is a separate project from Dvinholm.** Do not edit Dvinholm and do not publish a Virtual Car build or merge to `main`.
- Read-only simulation/observability of Volvo P2 XC90 V8 MY2009; Windows x86/J2534, CAN HS 500 kbit/s and LS 125 kbit/s. Emulator success must be verified with the actual client; unit tests only prove offline behavior.
- Respect `docs/ROADMAP.md`, `docs/PROVENANCE.md` and existing issue #4 (CEM evidence-driven diagnostics).
- The repository contains an authorized supplied v0.3.6.6 emulator source on development, but user-private donor profiles/INI, original VDASH binaries and personal captures do **not** belong in Git. Do not assume the outdated main-branch README describes development correctly.

## 1. VDASH portable 2.5.115.79: previous static findings

Reported earlier local study (to be independently verified before treating as new evidence):
- 7 .NET assemblies protected by ConfuserEx AntiTamper Normal. Static recovery reported **55,786 of 56,665** IL method bodies, but strings, names, and control flow remain partly obfuscated. Recovered IL coverage is not equivalent to a complete protocol map.
- Managed pipeline observed: `Detect` (token `0x0600132B`) → `CreateCommand` → `Enqueue` → `VddCommand.Execute` → `VdashClient.CreateOrUpdateNonDbWr` (token `0x0600038E`) → `ICrudMemory.CreateOrUpdateNonDbWr` and `CrudClient/V2ClientBase.Send` → protobuf serialization/compression/encryption → HTTP PUT.
- Command/result envelope fields: `Status`, `Session`, `Voltage`, `Data`, `Hash`. Previously enumerated status states: 0 Created, 1 Sent, 2 Executed, 3 Failed, 4 AllFailed, 5 GotResponse.
- `ParseData` is reported to interpret `DataViewV2`, and `VddDetect` builds configuration/ECU results from returned data.
- `GetVin()` reads already stored `PreDetectResult` / `Volvo.Vin`; `GetConfig()` reads `DetectResult.Config`. Neither call alone proves sending a CAN/J2534 request. Local `FastDetectEcu` was found as a stub in the analyzed path.
- **Boundary:** client→command queue→external/service executor is observed. This does **not** identify the exact P2 CEM B9FB wire request, the remote executor algorithm, or a native PassThru callsite. No verified positive P2 CEM B9FB handler was recovered from these static observations. Do not fabricate a direct method→CAN-ID mapping.

## 2. VDASH 2.0: earlier runtime observations (a DIFFERENT version)

Earlier J2534 x86 lab run reported:
- `READ_VBATT` approximately 12.5 V.
- ISO15765 OBD `09 02` request → `49 02 01` and 17-character VIN, with `START_OF_MESSAGE`; `DataSize=24`, `ExtraDataIndex=24`.
- With `EmitIsoRxStart=1`, client displayed XC90 V8 MY2005 (the synthetic/donor scenario tested). ECU list remained empty. This is **not** proof that XC90 V8 MY2009 is detected.
- After VIN, observed CAN `18DB33F1`: `3E 80` (TesterPresent with suppress-positive-response bit). No verified ECU discovery sequence afterward.
- Separate SectorV comparison (NOT a VDASH command): a 13-frame CEM `B9FB` reply was read from CEM HS address 0x50; next unsupported `CAN 500k, ID 0x000FFFFE, CF 50 A3 02 03 A5 A5 00` was observed. Do not attribute SectorV's A3 probe to VDASH.

The static 2.5.115.79 results and runtime VDASH 2.0 findings must remain two independent evidence sets.

## 3. Verified donor D2/B9FB context and limitations

A published XC70 donor sample has 13 D2 fragments; after transport reassembly, the envelope is `50 F9 FB`, followed by **88 payload bytes**. The 17-byte VIN occupies payload offsets **11..27**. Payload begins `57 00 30 66 70 28`, then CRLF-delimited ASCII fields. Byte `00` near the start means binary-safe parsing is mandatory.
- The donor sample has code `295` (XC70-like), separate chassis `198625`, and synthetic VIN `YV1CZ0002A0000001` with mismatching serial/year. It must NOT be presented as a verified XC90 V8 MY2009 fixture.
- Unknown header fields, VIN consistency requirements, and any application checksum must remain `unknown`, not guessed.
- `B9F0` (ECU identity), `B9FB` (vehicle information), `B9FC` (configuration) are distinct; the requirement for B9F0 before B9FB is **not proven**.
- `PassThruClose` by itself does not distinguish parser failure, normal close, cancel, or mode switch.
- Public context: https://www.matthewsvolvosite.com/forums/viewtopic.php?p=573059 , https://github.com/vtl/volvo-cem-cracker/blob/master/volvo-cem-cracker.ino .
- More detailed prior conclusions were supplied as `Анализ Volvo P2 CEM.txt` in ChatGPT. This file is not present in the repository; all actionable essentials are summarized here.

## 4. Codex task: analysis first, focused tooling only

1. Audit current `development` branch architecture, existing J2534 event trace/replay tests and CEM routing before changing anything. Existing issue #4 must not be duplicated.
2. Produce `docs/research/VDASH_PROTOCOL_EVIDENCE.md`: table of every claimed finding with **source/version / static vs runtime vs inferred / confidence / missing proof**; separate 2.0, 2.5.115.79, and SectorV. Preserve method tokens precisely, verify them only if a lawful local artifact is available.
3. Add or adapt an **offline, read-only VDASH trace correlation** component only if existing infrastructure does not already cover it. It should identify J2534 open/connect/config/filter/write/read/clear/close, routing, TX→RX queue boundaries, 11/29-bit arbitration IDs, timing and repeated requests; redaction by default. Avoid claim that HTTP result fields are necessarily CAN payloads.
4. Produce a minimal sanitized fixture for the OBD `09 02 / 49 02 01` VIN flow and `18DB33F1: 3E 80` observation, explicitly marked as a VDASH 2.0 scenario; no real VIN in fixtures.
5. For D2, use binary-safe reassembly and validate fragment order, lengths, echo and payload bounds. If included, use donor B9FB as a **negative identity-consistency** test, not a genuine XC90 response.
6. Investigate why VIN acceptance is followed by empty ECU list using **observed** traces only. Categorize `not_observed`, `no_fixture`, `filtered`, `timeout`, `partial`, `delivered`, `client_result_unknown`, without inventing ECU acknowledgements or a positive A3/A6 reply.
7. Any inferred remote worker, encryption, or CAN behavior must be a hypothesis with a proposed falsifying measurement. No DRM/license bypass, no vehicle security access, ECU programming, PIN operations, crypto key extraction or replay of private production secrets.
8. One focused branch/PR to `development`; **6–8 meaningful tests** and CI on PR HEAD. A passing CI is only offline verification. Report separately: confirmed offline observations, unperformed real VDASH/VMware test, unperformed physical J2534 test. **Do not merge to main or publish a build/release.**

## Acceptance checks (8)

- [ ] Current development sources and existing issue #4 reviewed; no duplicate analyzers/assumed source paths.
- [ ] Evidence matrix preserves program version and provenance, distinguishes source-derived facts from hypotheses.
- [ ] `GetVin`/`GetConfig` are not mislabeled as direct CAN requests.
- [ ] HTTP/protobuf command path not mistaken for native J2534 implementation.
- [ ] VID/ECU separation: VIN-positive scenario can end with empty ECU list without fake ECU results.
- [ ] D2 validation rejects bad sequence/truncation and reports unknown checksum without claiming proof.
- [ ] Redaction of private identifiers and strict read-only/no-wire behavior are tested.
- [ ] Relevant C/Go/Python tests and CI pass; report includes exact SHA and real-client/VMware/physical-device verification status.

## Delivery

A concise PR summary identifying what was **actually** verified versus still blocked by missing authorized samples. No release, no automatic merge, no fabricated D2/CEM responses. If proprietary VDASH binaries are unavailable inside Codex, perform repository-only research and clearly report the blocked dynamic/static confirmations rather than inventing them.
