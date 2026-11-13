# Review: `volvo-vida/volvo-vida-diagnostics` for Virtual Car

Reviewed: 2026-11-13. Target: `vorlocsev/virtualcar`, `development`, Windows x86 virtual J2534 adapter emulating the *read-only* XC90 V8 MY2009 identification path. This is a **source/applicability review**, not a captured VIDA session, original CEM response, verified vehicle profile, license clearance, or client acceptance result.

Source: <https://github.com/volvo-vida/volvo-vida-diagnostics>. The reviewed upstream is a collection of generic Python CAN, ISO-TP, UDS and J2534 building blocks. The project README explicitly limits its DBCs to selected **V40 2017** and **V60 2015** powertrain networks; it does not document a verified XC90 P2 MY2009 CEM exchange.

## Direct source findings and decision

| Reviewed file | Source-backed observation | Virtual Car decision |
| --- | --- | --- |
| [`can/interfaces/virtual.py`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/can/interfaces/virtual.py) | In-process virtual channels distribute copied frames to queues. The implementation explicitly does **not** reproduce bus arbitration/priorities or rate limiting. | Useful conceptual model for isolated tests only. **Do not** use its delivery/timestamp behavior as a DiCE or vehicle timing reference. |
| [`isotp/protocol.py`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/isotp/protocol.py), [`isotp/address.py`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/isotp/address.py) | Standard ISO 15765-2 defines Single/First/Consecutive/FlowControl PDU types, 11/29-bit and physical/functional address modes, sequence numbers, BS and STmin. | Useful for ordinary ISO-TP regression design, **not** for decoding the proprietary Volvo D2 `8F/09.../4F` fragments. Preserve separate D2 framing and its existing 13-frame B9FB gate. |
| [`isotp/errors.py`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/isotp/errors.py) | Explicit timeout, unexpected FC/CF, wrong sequence, invalid CAN payload and overflow errors. | Keep error attribution separate: ISO-TP transport failure, D2 fixture/route failure, J2534 API failure, or client application rejection. |
| [`udsoncan/j2534.py`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/udsoncan/j2534.py) | Defines J2534 client-side constants: CAN=`5`, ISO15765=`6`, `CAN_29_BIT_ID=0x100`, a `PASSTHRU_MSG` with six 32-bit metadata words plus 4128-byte data; wraps `PassThruOpen/Connect/ReadMsgs/WriteMsgs`, filters and IOCTL. | Check ABI/flag parity against `emulator/src/virtualcar.c`; the Python wrapper **loads** a PassThru DLL and is **not** a replacement virtual J2534 DLL or DiCE implementation. |
| [`udsoncan/client.py`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/udsoncan/client.py), [`udsoncan/configs.py`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/udsoncan/configs.py) | Generic ISO 14229 request/response client; its client timeout defaults are generic configuration values. | Do not infer that VIDA `ReadVin` on target P2 uses generic UDS `22 F190` or that the configured P2/P2* values are the real VIDA/DiCE timings. Resolve the actual selected VIDA service/route from the target's own evidence. |
| [`opendbc/dbc/volvo_v40_2017_pt.dbc`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/opendbc/dbc/volvo_v40_2017_pt.dbc), [`volvo_v60_2015_pt.dbc`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/opendbc/dbc/volvo_v60_2015_pt.dbc) | Model-specific, later-platform DBCs. | **Reject** as authoritative XC90 V8 MY2009 CAN ID, ECU mapping, VIN, HS/LS bus or diagnostic-response provenance. Do not import into the active emulator profile. |

The source does **not** supply: an original VIDA-selected ReadVin service graph for XC90 V8 MY2009; validated `A3`/`A6`/`B9F0` positive CEM responses; verified 13-frame XC90 B9FB; exact CEM/ECM identifiers; DiCE driver; or evidence that VIDA, VDASH or SectorV accepted a VIN. Its generic UDS and ISO-TP functionality must not be mistaken for a Volvo P2 D2 vehicle-identity implementation.

## Integration against `development`

The actual virtual J2534 source is `emulator/src/virtualcar.c`, **not** the older `main` tracing-only proxy. The existing implementation already declares `PROTO_CAN=5`, `PROTO_ISO15765=6`, `CAN_29BIT_ID=0x100`, a J2534 `PASSTHRU_MSG` layout with `Data[4128]`, and separate D2 replay profiles. Existing `emulator/tools/import_p2_trace.py::validate_response` validates D2 framing by target/opcode, CAN ID, frame length, first header, fragment order and final marker. `emulator/tools/audit_p2_b9fb_shape.py` explicitly distinguishes D2 transport validity from identity/client acceptance. **Retain** those boundaries; the external source does not warrant changing runtime replies, active INI, vehicle settings or timing defaults.

A synthetic B9FB that passes the D2 parser establishes only *framing acceptance by the test utility*. It is not proof of an OEM capture, MY2009 identity, client acceptance, or correct CAN/baud/channel provenance. The prior original VIDA run recorded six D2 B9FB requests with no delivered RX; see `NEXT_CHAT.md` B3A50–B3A54 for the limited owner-side evidence. **ReadVin and ECU identification remain NOT_VERIFIED**.

### Focused synthetic regressions

`emulator/tests/test_vida_transport_boundaries.py` checks eight meaningful groups:

1. Thirteen properly ordered synthetic D2 frames pass *transport* validation, but never vehicle-identity acceptance.
2. Standard ISO-TP SingleFrame and FirstFrame/ConsecutiveFrame examples are not silently treated as Volvo D2 B9FB.
3. An ISO-TP FlowControl frame cannot be substituted into a D2 reply.
4. D2 target `0x40/0x50` and opcode `B9F0/B9FB/B9FC` cannot be interchanged.
5. A reply mixing two response CAN IDs is rejected.
6. A D2 fragment must contain **eight raw CAN bytes**, not a short payload or a 12-byte J2534 CAN-ID-plus-frame buffer.
7. D2 sequence errors, missing final frame and wrong 13th-frame `4F` marker are rejected.
8. Unrelated raw broadcast data is not accepted as a D2 response.

These tests contain no real VIN, proprietary ECU output or third-party source code. They exercise the existing Virtual Car framing validator and shape auditor and do not execute diagnostic commands or hardware I/O. The tests **do not** prove ISO-TP behavior in the original VIDA client or physical channel timings.

## Follow-up acceptance gates

- Keep the original selected VIDA `ReadVin.ServiceId`/`Identifier` mapping tied to the same local VIDA database/version before proposing an ECU response fixture.
- On the owner's isolated VMware environment, distinguish J2534 connect, write, D2 route/baud, fixture load, RX stage/delivery, VIDA application acceptance and first ECU-identification request as **separate gates**.
- Only user-approved, provenance-labelled XC90 MY2009 capture data may become runtime response fixtures. Do not transfer V40/V60 DBC definitions or guess a positive A3/A6/B9F0 response.
- Run the full existing trusted exact-HEAD CI on `development` after reviewed integration; no source-only PR or synthetic test may be labelled a VIDA ReadVin PASS or a release gate.

## Provenance and licensing

The root [`LICENSE`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/LICENSE) is **GPL-2.0**, while its [`pyproject.toml`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/pyproject.toml) identifies Python-CAN with **LGPL-3.0-only** metadata, and [`setup.py`](https://github.com/volvo-vida/volvo-vida-diagnostics/blob/main/setup.py) identifies `udsoncan` as **MIT**. These differing package notices require per-file licensing/provenance review before any redistribution. **No code or DBC from this repository is copied into Virtual Car by this task.** The findings and tests above are independently authored and reference external files only.

Selected checked blob SHAs (for reproducibility): README `5fc348495cd86cc4dfded719888fbadbc7a12304`; ISO-TP protocol `bcbcd54ffe2231fef7d6833f5ed9662d40a10e2c`; J2534 Python wrapper `a196ba2905bf30000ebaaf6f192c1b3f7b6e6ea2`; virtual bus `ba33a6ea893798e011882797e39885e4e0e57bb6`; DBC V60 2015 `d2b58fdd016d492826bdaca58c2baf37e773fa00`.