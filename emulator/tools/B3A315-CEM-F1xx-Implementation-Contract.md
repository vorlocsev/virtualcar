# B3A315: F1xx CEM identification contract (proposal only)

Status: **BLOCKED ON VERIFIED ECU DATA; NOT IMPLEMENTED**. This is an evidence
and implementation specification, not an OEM response, active patch, or a
request to modify user's VIDA installation, adapter, DLL, registry, or INI.
All observed samples below are from **original VIDA + virtual J2534 emulator**
sessions, not confirmed genuine ECU measurements.

## Grounded baseline

Original VIDA fresh exact action log interval: `[75494985,75759862)`, one
`IEXPLORE.EXE PID 00001130`, `2339/2339` tagged records.

- Pre-existing device Open, originating from directory currently registered
  as `J2534 Diagnostic Lab CEM Status`: A45F 24 TX / 24 positive RX;
  DD02 24 TX / 24 positive RX. No B3A274 lab generation marker in this
  portion; **not OEM verification**.
- In-window OTHER-origin Open/Close: 0 CEM service22 TX.
- In-window SELECTED-origin Open, directory currently registered as
  `J2534 Diagnostic Lab 277`: A45F 39 TX / 39 synthetic generated /
  39 positive RX; DD02 39 / 39 / 39. All 84 CEM22 TX have source logged
  ISO15765/500k/29-bit context, including F110/F114/F106 2 TX each.
  No F1xx positive RX; 6 service22 NRC31. Each NRC31 lacks DID identity
  and **must not** be separately assigned to an F1xx request without
  stronger request-response evidence.

Current registered Lab277 `virtualcar.ini`: one correct CEM29 route,
GGD lab enabled, **zero valid configured F110/F106 fixture slots**.
This current config is not historical proof.

`emulator/src/virtualcar.c` source contract:
- `load_config`: ECUCount, ECUn RequestId/ResponseId, and four optional
  `DID0..3Code/DID0..3Hex` slots. `parse_hex_blob` requires pairs of
  hexadecimal digits separated by space/tab/dash/colon/comma, caps at 192
  bytes, returns zero for invalid/empty values.
- `answer_uds`: F110 and F106 can use exact configured slots; no
  fallback invented payload; service22 otherwise `7F 22 31`.
- F114 is explicitly excluded from these generic slots. The only
  built-in synthetic F114 VIN handler requires `ecu->req==0x726`.
  The present 29-bit CEM request ID `0x18DA50F1` cannot enter it.
- `answer_ggd_cem50_lab`: B3A274 synthetic A45F/DD02 positive replies
  require ISO15765/500000, 29-bit channel flags, exact CEM request and
  response IDs, len=3, service22 and GGD opt-in enable.
  This does not authorize F1xx responses.

## Required inputs before changing J2534 emulator responses

| DID | Existing implementation | Needed independent evidence |
| --- | --- | --- |
| F110 | Generic explicit F1xx slot | Actual same-CEM positive payload, exact DID 62 F1 10, addressing, byte length, capture provenance |
| F106 | Generic explicit F1xx slot | Actual same-CEM positive payload, exact DID 62 F1 06, addressing, byte length, capture provenance |
| F114 | Reserved slot; only a different 0x726 handler exists | Authoritative evidence that 29-bit P2 CEM supports 22 F1 14, exact positive response layout, and original VIDA acceptance |

**Do not** infer OEM bytes from CarCom/GGD A45F/DD02, P3 synthetic
0x726 VIN, generic labels, T141 BlockValue F0/F5/F8, other model or
ECU, or the count of NRC31 frames. No payload or VIN is to be stored in
public PR comments or test fixtures without explicit approval and
privacy review.

## Possible future opt-in implementation (design, not code)

1. For F110/F106, use existing four `DIDnCode`/`DIDnHex` slots on
   the **specific** `ECUn` with `RequestId=18DA50F1`,
   `ResponseId=18DAF150`, only after original evidence is verified.
   Invalid or empty entries retain `7F 22 31`.
2. For F114, **if and only if** real evidence confirms a 29-bit CEM
   positive response, add an independent default-OFF, read-only,
   explicitly per-CEM fixture; never use `Vehicle.VIN` as substitute.
   Suggested new optional profile keys: `EnableCem29F114Fixture=1` and
   `DIDF114Hex=<verified raw data bytes after 62 F1 14>`.
   Naming and code are proposals and are **not** currently supported.
3. Gate any new F114 handler on exact `22 F1 14` three-byte request,
   configured ECU req=0x18DA50F1, resp=0x18DAF150, ISO15765
   protocol, 500000 bit/s, exact 29-bit ConnectFlags policy, and
   positive, bounded, validated response bytes. Do not broaden
   `ecu->req==0x726` for the existing P3 handler.
4. Let existing ISO-TP output segmentation handle legitimate long
   responses. Do not add programming/unlock or change write/erase
   service behavior. Keep `7F 22 31` for missing/invalid fixtures
   and ensure prior sessions do not leak cached responses.
5. Audit logs must distinguish **synthetic fixture-generated**
   replies from verified OEM captures. A GUI display, a CAN RX
   frame, and a real ECU-origin verified response are distinct gates.

## Required regression and acceptance gates

- Unconfigured/default-OFF 29-bit F114 remains NRC31.
- Wrong protocol, baud, flags, request ID, response ID, DID, payload
  length, malformed hex or no/duplicate CEM route do not emit a
  fabricated positive.
- Exactly one valid opt-in F114 fixture may produce
  `62 F1 14 <verified bytes>`; F110/F106 still use only their
  independent validated slots.
- Existing 0x726 P3 behavior, GGD A45F/DD02, other ECUs and negative
  service handling remain unchanged; multi-frame flow control verified.
- Synthetic/offline tests are **not** acceptance. After explicit
  approval for a new emulator build, record fresh original VIDA
  ReadVin, CEM identification fields, T111/T122 and (if relevant)
  physical adapter checks **separately**, with original screenshots
  and an anchored log; do not label untested gates PASS.

Current release gate: **BLOCKED** until verified F110/F106 and 29-bit
F114 source evidence. Original VIDA GUI CEM visibility has been observed
but VIN/identification accepted fields remain unproven.
