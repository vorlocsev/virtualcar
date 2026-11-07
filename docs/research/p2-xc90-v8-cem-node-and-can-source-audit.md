# P0: XC90 P2 CEM node and CAN source audit (2026-11-07)

This is **service-document context only**, not a diagnostic response trace or a
protocol contract for A3/E3, A6/E6, B9F0, B9FB, VIN or SectorV normal mode.
Source sites reproduce Volvo material; original publication and equipment
provenance are not independently authenticated here.

## Evidence ledger

| Source and scope | What it supports | What it does not support |
| --- | --- | --- |
| [TJ14902 excerpt, XC90 MY2009 3.2L](https://lemon-manuals.la/Volvo/2009/XC90%20FWD%20L6-3.2L%20VIN%2098%20B6324S/Repair%20and%20Diagnosis/Powertrain%20Management/Computers%20and%20Control%20Systems/Technical%20Service%20Bulletins/Customer%20Interest/Computers%2FControls%20-%20CEM%20Download%20Interrupt%20Recovery/) | P2 CEM node **40 through MY2004**, **50 from MY2005**; P3 CEM node **726** in service-tool instructions | MY2009 **V8** raw trace, D2 reply bytes, J2534 CAN IDs, SectorV acceptance |
| [TJ14902 excerpt, XC90 AWD V8 MY2005](https://workshop-manuals.com/volvo/xc90_awd/v8-4.4l_vin_85_b8444s/relays_and_modules/relays_and_modules_accessories_and_optional_equipment/central_control_module/component_information/technical_service_bulletins/all_technical_service_bulletins_for_central_control_module/tj14902/nov/10/computers/controls_cem_download_interrupt_recovery/page_125/) | XC90 V8 **MY2005** P2 CEM node **50** contrasted with P3 **726** | Whether the exact MY2009 V8 CEM revision uses any specific CAN RX frame |
| [XC90 AWD V8 MY2005 CAN service overview](https://workshop-manuals.com/volvo/xc90_awd/v8-4.4l_vin_85_b8444s/powertrain_management/computers_and_control_systems/information_bus/component_information/description_and_operation/the_controller_area_network_%28can%29/page_8847/) | V8 HS CAN **500 kbit/s**, LS CAN **125 kbit/s**, CEM as network interface | Observed MY2009 bitrate, diagnostic request routing, a valid ECU response |
| [XC90 MY2009 wiring diagram index](https://www.manualslib.com/products/Volvo-2009-Xc90-2236351.html) | MY2009 CEM, HS/LS CAN and V8 sections exist in XC90 wiring documentation | Captured discovery session, diagnostic timing or normal-mode predicate |

## Eight research gates before any response implementation

1. Treat **target 0x50** as a documented P2 MY2005+ diagnostic-node hypothesis for XC90 V8 MY2009. **0x40** is an earlier-P2 node, or separately observed fallback, not evidence of equal modern target status.
2. Use **HS 500 / LS 125 kbit/s** as the MY2009 experimental profile. Do not adopt HS 250 from early-P2 captures.
3. Never convert service **node 50** into a 29-bit CAN arbitration ID by inference. Donor B9FB or observed IDs 0x01000003 / 0x01200003 require independent frame provenance.
4. P3 **node 726** in this service instruction denotes a **different platform**. It does not prove that a P2 MY2009 client uses 11-bit CAN 0x726 or 29-bit 0x18DA50F1.
5. These are **service** documents, not authorization captures. Do not generate positive A3/E3, guess SecurityAccess bytes, PIN, ignition state, normal-mode predicate or ECU identity.
6. B9FB **J2534 delivery**, the SectorV **13/13 frame matcher**, and **vehicle VIN acceptance** are three distinct milestones. No cross-process frame matching without shared immutable request IDs.
7. In the known MY2005 LAB run, target 50 (HS500) and target 40 (LS125) Hardware A3 probes had no matching RX; this is a **client observation**, not a measurement on MY2009 V8.
8. Only a continuous, consented, redacted **XC90 V8 MY2009** read-only client+J2534 session with channel/protocol/baud and actual UI transition can elevate a transport observation into an identity/compatibility claim.

## Practical next action

Apply the existing local privacy-safe auditors:
- emulator/tools/audit_j2534_discovery.py
- emulator/tools/audit_sectorv_gate.py
- emulator/tools/audit_p2_discovery_boundary.py

Keep source-based node/speed guidance beside their results, not as fabricated
J2534 transaction evidence. Missing full MY2009 client data means **unverified**.
See [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4) and
[p2-public-capture-followup.md](p2-public-capture-followup.md).

No source emulation changes, no captured secrets, no replay fixture, no
firmware activity, no Virtual Car packaging or release.
