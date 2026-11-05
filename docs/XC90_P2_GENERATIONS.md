# XC90 I (P2) generation-sensitive diagnostics: evidence and routing gates

Status: research specification only. **No response fixture, ECU identity, or client acceptance is validated by this document.** No programming/security operations are authorized.

## Verified boundaries

| Vehicle variant | HS-CAN | LS-CAN | VIDA CEM node (not a CAN arbitration ID) | Diagnostic-family evidence |
| --- | --- | --- | --- | --- |
| XC90 P2 MY2003–2004 | 250 kbit/s | 125 kbit/s | `40` in TJ14902 | D2; avoid treating MY2003 as interchangeable with MY2009 |
| XC90 P2 MY2005–2006 | 500 kbit/s | 125 kbit/s | `50` in TJ14902 | D2 plus GGD introduction with B8444S V8 on HS-CAN |
| XC90 P2 MY2007–2014 | 500 kbit/s | 125 kbit/s | `50` in TJ14902 | D2/GGD coexistence; vary actual ECU family by powertrain, module and software |
| XC90 SPA MY2016+ | separate architecture | not modeled here | Not P2 | VDS; outside scope |

The MY2007 exterior facelift **is not** the protocol-change boundary. The HS-CAN change is MY2005. VIDA classifies older-platform cars with D2/GGD and XC90 MY2016+ with VDS.

* **Evidence:** Volvo diagnostic communications speed: https://charm.li/Volvo/2004/XC90%20L5-2.5L%20Turbo%20VIN%2059%20B5254T2/Repair%20and%20Diagnosis/Powertrain%20Management/Transmission%20Control%20Systems/Testing%20and%20Inspection/Scan%20Tool%20Testing%20and%20Procedures/Reading%20off%20the%20Control%20Module%20ID/
* **Evidence:** Volvo TJ14902 recovery document, VIDA node addresses: https://lemon-manuals.la/Volvo/2009/XC90%20FWD%20L6-3.2L%20VIN%2098%20B6324S/Repair%20and%20Diagnosis/Powertrain%20Management/Computers%20and%20Control%20Systems/Technical%20Service%20Bulletins/Customer%20Interest/Computers%2FControls%20-%20CEM%20Download%20Interrupt%20Recovery/
* **Evidence:** VIDA official protocol grouping: https://vidaresources.volvocars.biz/help-wbt/us/b5980760141034ddc0a801cc2958048c.htm
* **Evidence:** GGD introduced on XC90 MY2005 B8444S (HS-CAN): https://lemon-manuals.la/Volvo/2008/S80%20AWD%20V8-4.4L%20VIN%2085%20B8444S/Repair%20and%20Diagnosis/Testing%20and%20Inspection/Initial%20Inspection%20and%20Diagnostic%20Overview/Diagnosis/Diagnostic%20Versions%20and%20Communication%20Methods/

## Keep distinct namespaces in code

1. **Model year / generation**: 2003/2004 vs 2005+ P2. MY2007 facelift is presentation/ECU-variant context, not a new bus family.
2. **Electrical bus**: HS or LS, bitrate, connector pins and any diagnostic relay behavior. Physical pin routing is not implied by PassThruConnect success.
3. **J2534 ProtocolID**: CAN, ISO15765 and optional J2534-2 switched-pin variants. A successful channel allocation does not establish actual physical pin binding or client interpretation.
4. **Diagnostic message arbitration ID**: 29-bit D2 shared request (observed `0x000FFFFE`) is not a VIDA node byte.
5. **VIDA logical ECU node**: `40` (earlier P2 CEM), `50` (MY2005+ P2 CEM), `726` (P3 CEM in TJ14902). Do **not** mechanically equate the hexadecimal values of a VIDA node with CAN IDs without validated framing.
6. **Diagnostic family per ECU**: D2, GGD, P3-style UDS discovery probe, or unknown. Do not infer one from a platform label alone.
7. **Response fixtures**: source provenance and exact route must be validated separately from transport. Unknown DID or identity means `no_fixture`, never a fabricated positive answer.

In current `proxy/p2_cem_router.c`, `0x50@500000` and `0x40@125000` are paired unconditionally. That is a current *classifier rule*, not a complete generation-aware mapping. The TJ14902 model-year node change must not be translated into changing LS baud to 250000: HS/LS remain separate constraints. This classifier is passive; **do not change it or the J2534 DLL without matching tests and verified traces**.

## LAB-533 evidence: transport vs client

* Native **synthetic** Windows x86 handoff: D2 B9FB 13/13 RX, D2 B9F0 3/3 RX, P3 F114 1/1 RX; all three marked responded. Not real-client acceptance.
* Separate local client log subset: 8 Connect attempts, four successful CAN_PS/ISO15765_PS channels, two apparent native process scopes, no observed B9FB request.
* The privacy-safe read-only P3 audit identified `22 F114` at `0x726` as `delivered`, `22 F1B0` and `22 F1A3` as `explicit_missing_fixture`, and a later `22 F114` as `invalid_iso_tp_framing`. `delivered` means J2534 transport only. Do not assume all four calls belong to the same verified application process or that `0x726` belongs to an XC90 P2 CEM.
* Screenshot shows the client displaying XC90 2003 and a synthetic donor VIN. Display alone does not establish provenance of the VIN, that the scan finished, or an XC90 V8 MY2009 identity.
* Native records/fixture details remain private; none are committed here. Replay was **not** approved by the auditor.

## Proposed profile contract (schema illustration only)

```yaml
vehicle:
  platform: P2
  model: XC90
  model_year: 2009
  engine: B8444S
  variant_verified: false

buses:
  hs:
    bitrate: 500000
    obd_pins: [6, 14]
  ls:
    bitrate: 125000
    obd_pins: [3, 11]

diagnostics:
  cem_d2:
    vida_node: "50"
    shared_d2_tx_can_id: "0x000FFFFE"
    fixture_status: unverified
  cem_ggd:
    family_candidate: GGD
    request_can_id: null
    response_can_id: null
    fixture_status: unverified
  p3_probe:
    observed_request_can_id: "0x726"
    accepted_as_p2_cem: false
    fixture_status: unverified
```

No default positive reply for `22 F114`, `22 F1B0`, or `22 F1A3` should be generated from this illustration.

## Eight implementation gates

1. Profile selection: MY2003 HS250 and MY2009 HS500 are different profiles; no silent fallback.
2. Physical bus, pin binding, baud and logical node represented independently.
3. D2 `0x000FFFFE` route classification does not confuse `40`/`50` logical nodes with CAN IDs.
4. P3 `0x726` discovery remains isolated from P2 CEM, with no automatic identity response.
5. D2/GGD selection is per ECU and requires fixture provenance; unknown combinations yield `no_fixture`.
6. Synthetic 13/13 B9FB, 3/3 B9F0 and 1/1 F114 regression remains green with zero RX drops.
7. Repeat `22 F114` is checked for ISO-TP framing, filters, queue generation and inter-request contamination; do not patch the fixture until failure is localized.
8. Real client verdict separately records adapter selection, VIN source, completed ECU scan, and process/session evidence. No result is inferred from J2534 RX delivery.

## Repository scope

As of this research, `main` contains the dev26 read-only tracer and passive CEM classifier; it does **not** contain the independently built LAB-533 `VirtualCarJ2534.dll` source. This specification is not a binary update. Keep runtime changes behind a later, test-backed PR.
