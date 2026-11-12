# B3A22: VIDA UDS29 ECU observer-only route (read-only lab)

Scope: `emulator/src/virtualcar.c`, `emulator/tests/virtualcar_test.c`. PR #319 stays Draft. This is **not** a verified XC90 V8 ECU identity or response fixture.

## Evidence
Windows B3A21 validated 19 synthetic J2534 WriteMsgs, 19 empty ReadMsgs, 14 `missing_profile`, 1 CEM and 4 `UNHANDLED`. Original VIDA automatic ReadVIN remains NOT PROVEN. Its request-only B3A17/B3A18 inventories contain 206 UDS requests (199 SID22, 7 SID19), 197 distinct (target,DID) keys, and 78 Volvo D2 requests, including 7 CEM B9FB. There is no original ECU RX proof.

### Why configured ECU reply generation is dangerous
Existing `answer_uds()` can synthesize VIN `0x62 F1 90`, other IDs, and default negative `0x7F 22 31` or `0x7F 19 11` responses. Adding a captured `18DAxxF1` request ID to an ordinary emulator ECU profile would wrongly make those bytes look like vehicle replies. The request-only inventory cannot justify those values or response IDs.

### Opt-in
In an **isolated synthetic lab** ECU section, `ObserverOnly=1` permits address matching while preventing **all** UDS ECU replies. This is an opt-in per ECU, default `0`, not enabled by prior B3A7 profiles. The ECU `ResponseId` is not used while observer-only. Existing response behavior with `ObserverOnly=0` is unchanged.

Example synthetic lab INI (existing private VIDA profile must remain untouched):
```ini
[Vehicle]
ECUCount=1
[ECU0]
RequestId=18DA10F1
ObserverOnly=1
```
This is **not** a request to install the new DLL or to assign a guessed response CAN ID. Use only isolated process and INI. Keep original VIDA logs and VIN private and byte-exact.

### Native regression gate
Six real host C requests targeting configured `18DA10F1` are checked: SID22 `D91A`, SID22 `F190`, SID19, tester present SID3E, diagnostic session SID10, and protected SID2E. Each must have exactly one `ECU_OTHER` route selection, one no_response terminal, no queued RX and an empty PassThruReadMsgs. The existing configured P3 CEM F114 reply remains exercised first to verify no global reply disable.

**Not accepted yet:** exact-HEAD Windows host regression, PE32 DLL build with 14 exports, native 32-bit DLL test and the original VIDA GUI acceptance remain separate gates. No fake OEM data, security access, EEPROM changes, flashing or original vehicle writes.
