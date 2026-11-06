# M4B-1: Strict J2534 ISO15765 RX metadata and multi-ECU isolation

Status: feature PR, **not** proof of J2534/CAN/VIDA interoperability.
Dvinholm is the main product. Virtual Car is a private optional,
read-only diagnostic simulation lab; do not publish Virtual Car releases.

## Source-derived, testable legacy C behavior

Inspected `emulator/src/virtualcar.c` on `development`:

- `enqueue_status` assigns `ProtocolID=6` for ISO15765,
  `RxStatus=0x100` for extended CAN IDs and `RxStatus=0x2`
  for `START_OF_MESSAGE`.
- The first 4 `Data[]` bytes are the RX CAN ID, **big-endian**;
  regular `DataSize=4+UDS_length`, regular
  `ExtraDataIndex=DataSize`.
- The indication `START_OF_MESSAGE` is `DataSize=4` and
  `ExtraDataIndex=0`, then the complete synthetic UDS response.
- `Timestamp` is a wrapping 32-bit value in **microseconds**.
- In strict mode a segmented response must have one exact
  `FLOW_CONTROL_FILTER` with full 4-byte RX CAN ID mask and
  the correct physical request CAN ID. Broad filters cannot grant
  segmented responses.
- If fewer than **two free FIFO slots** remain, the start indication
  and complete response must be dropped **atomically**.

These facts are verified as *source-derived fixtures* in the new tests.
They are not yet black-box output captures from a running old DLL.
Do not label them full old/new executable parity.

## Implementation M4B-1

- `emulator/native-cpp/include/virtualcar/isotp_rx.hpp`
  and `src/isotp_rx.cpp` implement a separate isolated
  ISO15765 RX-only compatibility queue.
- Supports up to 8 synthetic ECU request/response CAN routes on one
  bitrate, max 24 strict flow filters, 64 bounded RX messages,
  4095 payload bytes and reject-on-overlap CAN ownership.
- Exact J2534 `PASSTHRU_MSG` layout defined by M0/M3, no custom
  reinterpret casts. 32-bit microsecond timestamp wrap and
  11-/29-bit status flag. Single-frame-sized replies are one
  assembled ISO15765 message, larger replies may be a 2-message
  indication + payload pair.
- The queue always reserves both entries before a 2-message
  delivery, never enqueues a half-pair, and counts the dropped
  *logical response*. Reset invalidates pending queue, route and
  filter selections, plus session generation.
- Only synthetic read-only UDS service reply 0x62 is accepted,
  with length 3..4095. The upper C# M2 SHA-256 scenario compiler
  still owns actual source approval and bytes verification.
- A partial masked response filter may enable a synthetic short
  response but never an >7 byte segmented response; cross-ECU
  overlapping filters and route ID collisions are refused.
- No SQLite/CAN network calls, no physical DiCE, no IPC; the
  existing C++ J2534 DLL still **returns not connected**. The new
  `Iso15765Rx` class is not linked into any functional adapter.

## Eight regression groups

1. 11-bit/29-bit CAN validation, bitrate, eight-route bound.
2. Flow filter mask overlap, ownership and wrong ECU refusal.
3. Expected J2534 ISO15765 single RX metadata, CAN ID byte order.
4. 29-bit flag and wrapping microsecond timestamp.
5. Atomic `START_OF_MESSAGE` + complete response under FIFO exhaustion.
6. Broad filter allows short reply but not segmented response.
7. Two synthetic ECU routes retain separate CAN IDs and owner labels.
8. Reject security/write replies, oversized payload, reset old generation.

These tests run under Linux g++ with `-Werror -pedantic`, and
both Windows MSVC Win32 and x64 CMake/ctest. Legacy x86 C-emulator
regression suite remains an independent CI gate.

## M4B-2 remains necessary

- Actual **black-box same-input old C x86 vs new C++ x86/x64**
  executable comparisons, with normalized timestamps.
- Actual strict ISO15765 multi-route transport and flow filters in
  a functional J2534 DLL, not just the isolated test queue.
- FIFO cancellation/race/clock rollover under load and multi-channel
  lifecycle, then M5 secure local Named Pipes C# host.
- No asserted Volvo P2 CEM D2/B9FB ECU responses, PIN, SecurityAccess,
  OEM acceptance or actual physical adapter tests.

Cross-chat continuation phrase: **virtual car**.
