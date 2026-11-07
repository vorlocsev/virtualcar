# M4B-2: executable legacy C x86 DLL vs new C++20 black-box RX parity

Status: pending independent CI result and review. This does **not**
enable the new C++ J2534 DLL, nor demonstrate VIDA, Volvo OEM identity,
Dvinholm E2E, physical DiCE, or real vehicle operation.

## Actual executable comparison (not merely source-derived)

The PR builds the **unaltered** legacy `emulator/src/virtualcar.c` as an
actual Windows x86 J2534 DLL using the existing `build-cross.sh` CI step,
then separately builds `vc_legacy_c_cpp_parity.exe` as a native Win32 MSVC
executable. The latter dynamically loads the built legacy C DLL with
`LoadLibraryExW` and invokes real `PassThruOpen`, `PassThruConnect`,
`PassThruStartMsgFilter`, `PassThruWriteMsgs`, `PassThruReadMsgs`
and `PassThruDisconnect` functions. The new independently compiled
C++20 `Iso15765Rx` module receives matching, fixed synthetic replies.

The C++20 test **does not copy the old DLL's received payloads** as input.
Independent scenario expectations come from a temporary ASCII-only
`virtualcar.ini` synthesized by the test:

- ECM A: CAN request 0x7E0, response 0x7E8,
  F187 PartNumber `LABA`, F189 Software `LAB-LONG-SYNTHETIC-ENGINE`.
- ECM B: CAN request 0x7E1, response 0x7E9,
  F187 PartNumber `LABB`, F189 Software `LAB-SW-B`.
- Strict J2534 filters ON, optional ISO15765 START_OF_MESSAGE ON.
  No passive traffic, D2/CEM frames, private VIN or hardware I/O.

Inputs to the *old C DLL* are synthetic ISO15765 J2534 writes
`22 F1 87` / `22 F1 89`; the *new C++ engine* receives the
independent matching expected positive response from the same explicit
test profile. The comparator checks ProtocolID, RxStatus, TxFlags,
DataSize, ExtraDataIndex and EVERY byte up to DataSize, normalizing
**only the dynamic microsecond timestamp**. Device/channel/filter
handles are never compared as those are dynamic.

Eight executed gate groups:
1. Short synthetic DID F187 response, one real legacy PassThru reply.
2. Long F189 read, START_OF_MESSAGE then complete response, two messages.
3. Two separate ECU CAN request/response route pairs on one channel.
4. Two channels, one filtered and one unfiltered, no cross-channel reply.
5. Broad FC response mask admits short reply but refuses segmented reply.
6. Flow filter with wrong request CAN ID suppresses long reply.
7. FIFO at 63 entries drops the two-slot START/payload pair atomically.
8. Channel disconnect/reconnect drops pending data and filter authorization.

The harness itself creates a NEW isolated directory. It copies the old
C DLL there, writes a standalone synthetic INI, sets process-local
LOCALAPPDATA/TEMP/TMP and does not touch J2534 registry entries or any
installed user profiles. The isolated logs are **not uploaded** as CI
artifacts. It prints only gate labels/statuses and an 8/8 summary.
A missing DLL, failed open/filter/transport, or mismatch makes CI fail.

## Evidence boundary

- **Actual old executable versus new compiled C++ RX module:** yes,
  but only for the eight synthetic ISO15765 patterns above.
- **New C++ DLL versus old C DLL:** no. The M3 C++ PassThru DLL is
  deliberately FAIL-CLOSED until secure host IPC; it is not involved
  in this parity harness.
- **Raw CAN ISO-TP wire frame parity:** no. This tests the reassembled
  strict ISO15765 PassThru receive contract; M4A transport timings are
  still separately simulated.
- **Multi-route different CAN bitrates, 29-bit old/new black-box,
  arbitrary vendor extensions, error codes under load:** not yet.
- **Real J2534 hardware, live vehicle, original SectorV/VDASH/VIDA
  client recognition, Volvo CEM B9FB identities:** not demonstrated.

Dvinholm remains the primary product. Keep legacy C/Go as a parity
reference until M7/M8, no Virtual Car releases.

Next after verified M4B-2: M5 secure local Windows Named Pipes between
native x86/x64 C++ J2534 boundary and C#/.NET10 headless service;
review readiness before changing the DLL's fail-closed behavior.
Resume phrase: **virtual car**.
