# B3A307 — Original VIDA ReadVin F114 → B9 FB transport route evidence

Date: 2026-11-18. Scope: **read-only** original VIDA 2014D script/CarCom evidence
and owner-original J2534 log review. This document is not ECU firmware truth,
not an OEM-attested XC90 V8 F114/B9FB response, and not VIDA GUI acceptance.

## 1. Source-backed branch condition

Owner-original `ReadVin` script `0900c8af8184c004` / `VCC-225200`,
14 XML nodes, 27 event edges, starts at `EuCD`.
The initial node uses `ReadVinComponent`, `ServiceId=100`,
GGD `22 F1 14`, ECU variant `30728270 AA` / T100 id `821`,
config `611`. On **positive** parse, XML extracts
`Records[61716].Parameters[59790].value` and invokes `AddVIN`.
On `OnNoResponse`, `OnNegativeResponse`, or `OnNoContact` it
moves to `NO_RELAY40B9FB`. The script does **not** require `22 F1 90`.

The fallback node uses D2 `B9 FB`, ECU variant `09469693  A` /
T100 id `230` (exact two spaces), with **two configurations**:
`T121_Config 240`, priority 1, logical node `40`, D2/CAN;
and `T121_Config 241`, priority 2, logical node `50`, D2/CAN.
Only after failure of both configurations does the script advance to
the separate PJB variant `08666792  F`, id `70`, config `74`,
also logical node `50` but at a different observed bus rate.
The XML has further relay and CI/K-line branches; do not collapse
all of them into CEM responses.

Evidence documents:
- `docs/research/vida-owner-readvin-script-xml-state-machine-2026-11-10.md`
- `docs/research/vida-owner-readvin-ecu-variant-service-lookup-2026-11-11.md`
- `docs/research/vida-owner-readvin-can-config-rows-d2-oncan-2026-11-11.md`
- `docs/research/vida-owner-readvincomponent-transport-il-2026-11-10.md`
(on the retained `feature/vida-redacted-evidence-summary-v1` branch).

## 2. Actual owner-original VIDA 2014D log — a single fallback sequence

Original `VIDA-KLine-B2-runtime-20261111-105658.txt`,
session beginning 10:29:50, with original full logs retained privately:

| Timestamp | VIDA active config | Transport | Actual J2534 outgoing bytes | Result |
|---|---|---|---|---|
| 10:29:50.773 | GGD CEM 611 | ISO15765=6, 500000 | `00000726 22 F1 14` | ERR_TIMEOUT |
| 10:29:51.391 | D2 CEM 240 | CAN_PS=0x8004, 125000 | `000FFFFE CB 40 B9 FB 00 00 00 00` | ERR_TIMEOUT |
| 10:29:51.989 | D2 CEM 241 | CAN=5, 250000 | `000FFFFE CB 50 B9 FB 00 00 00 00` | ERR_TIMEOUT |
| 10:29:52.570 | D2 PJB 74 | CAN=5, 500000 | `000FFFFE CB 50 B9 FB 00 00 00 00` | ERR_TIMEOUT |

The session confirms the difference between **XML fallback node** and
**ECU transport config retries**. The second `B9 FB` is still the
same ECU variant 230, not the XML PJB node. In original managed source,
`EcuVariant` lookup picks an ordered list of configs, and
`DiagnosticVehCommService` reports `Trying next ecuconfig in list`.

`0x000FFFFE` is the D2-on-CAN J2534 arbitration ID observed
in these frames. `CB` is the D2 single-frame marker in this exact
request; `40`/`50` is the logical target. These are not ISO-TP
`22 F1 14` frames. An actual positive D2 response is **not observed**
in this timeout trace.

## 3. Direct comparison with Virtual Car development

In `emulator/src/virtualcar.c`, development as inspected 2026-11-18:

- `load_config()` creates legacy `D2_40` with `baud=125000`
  and `D2_50` with `baud=500000`; there is no independent
  opt-in `D2_50_250` record keyed to original config 241.
- `process_d2()` matches recorded fixture by `target` and
  `subcommand`; in development (prior to the stacked experiment
  branch), base records do not also match by `service` because the
  recognized request is fixed to B9.
- For baseline fixture slots, bitrate equality is required only if
  `g_p2_strict_routing` is enabled; otherwise an `0x50/500k`
  fixture can be selected while the VIDA channel is `0x50/250k`.
- In strict mode, an `0x50/250k` request cannot match the
  baseline `D2_50/500k` fixture and is rejected instead.
- The telemetry label `route=\"CEM\"` for **both**
  logical addresses 40 and 50 does not establish an ECU identity:
  original ReadVin uses 50 for CEM config 241 **and** PJB config 74.

These are **source-visible routing compatibility gaps**, not proof
of the owner GUI's current failure root cause. In this particular
timeout trace, the initial F114 request itself got no response.

In the separately stacked Draft #357, the original VIDA GUI
did receive `62 F1 14` followed by 17 ASCII VIN bytes, but reported
`The VIN can not be decoded on selected Partner Group`. It did
**not** attempt B9FB in that session. Do not interpret “J2534
returned VIN bytes” as “original VIDA accepted vehicle profile”.
The 88-byte D2/PJB-derived lab record is not OEM F114 evidence
for XC90 V8 MY2009, and the 166-byte separate CEM metadata
is not proof of the exact vehicle's expected serialized record.

## 4. Implementation contract for a follow-up code change

Do **not** flip `D2_50` from 500000 to 250000: that destroys the
distinct PJB route without solving ECU ambiguity.

A future change should:
1. Key D2 response fixture by actual **wire protocol** (CAN_PS vs CAN),
   bitrate, logical target, opcode, ECU variant/config when known,
   and separately the validated response-ID/transport framing.
2. Support opt-in `CEM cfg241, 0x50/250k` **only when an
   owner-attested response fixture exists**; otherwise remain silent
   with explicit “no validated fixture” telemetry.
3. Keep PJB `0x50/500k` independent and never alias its vehicle
   information bytes into CEM config 241.
4. Keep GGD F114 and D2 B9FB as *reactive request handlers*;
   **VIDA**, not CEM, decides when a negative/timeout result
   warrants executing the fallback branch.
5. Preserve the current read-only/no-unlock/no-programming policy.
6. Require separate event evidence for response transport,
   `Output.AddVIN`, accepted GUI VIN, and ECU identification.

## 5. Minimum next tests

- Exact GGD `0x726/22F114/ISO15765/500k` classification.
- Exact D2 `40/125k/CAN_PS`, `50/250k/CAN`,
  `50/500k/CAN` remain three distinct route contexts.
- Wrong baud, CAN ID, protocol, flags or opcode do not generate RX.
- Two D2 config attempts for CEM 230 before PJB 70 in logged sequence.
- Unsupported CEM cfg241 returns “no original fixture”, not PJB RX.
- A positive GGD reply does not implicitly force a B9FB reply.
- GUI Partner Group failure is tracked independently of transport result.
- Multi-channel retries cannot leak old D2 queued frames.

**No driver/registry/VIDA database changes, no fake OEM payload,
no security operation, no workflow dispatch, no merge or release.**
This is an evidence/plan-only research update.
