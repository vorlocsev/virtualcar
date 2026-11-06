# M4A | Isolated C++20 CAN / ISO-TP transport engine

Status: implementation review. This is **NOT** a functioning J2534 adapter.
Dvinholm is the primary product, Virtual Car is an optional private lab.
No Virtual Car builds or releases may be published.

## Source contract and old C reference

Before implementing the new engine, inspected the current legacy reference
`emulator/src/virtualcar.c` in `development`:

- `MAX_QUEUE=64`, `MAX_FILTERS=24` and 32-bit J2534 CAN IDs.
- `CAN_29BIT_ID=0x100`, standard CAN ID is 11-bit, extended is 29-bit.
- A multi-frame ISO-TP response requires a matching ECU Flow Control CTS,
  matching the pending request CAN ID; unrelated IDs must not grant CFs.
- Block Size 0 means unlimited CF credit; nonzero BS requires new CTS when
  credit expires. Pending credit must survive RX queue backpressure.
- Flow Control WAIT suspends a grant, OVERFLOW aborts pending response.
- Reserved STmin 0x80-0xF0 and 0xFA-0xFF are ignored; 0xF1-0xF9 represent
  100-900 microseconds. 0x00-0x7F represent milliseconds.
- Legacy code also has strict J2534 filter and ISO15765 RX
  START_OF_MESSAGE atomic admission rules not yet integrated into the
  new DLL. Full parity is a **separate M4B gate**.

## New isolated transport implementation

- `emulator/native-cpp/include/virtualcar/transport.hpp` and
  `emulator/native-cpp/src/transport.cpp`: fixed-size, allocation-free
  bounded FIFO, a single synthetic 11-bit or 29-bit ECU route, 24 filters,
  per-route PASS/BLOCK policy and cross-ID/flow control isolation.
- ISO-TP read-only reply serializer for at most 4095 bytes: padded
  Single Frame, First Frame and Consecutive Frames with 4-bit SN wrap.
- Explicit CTS/WAIT/OVERFLOW, BS credit, reserved STmin rejection,
  STmin per-frame ready timestamps and cross-block spacing preservation.
- Separate FC deadline in microseconds. Unrelated CAN/Flow Control
  messages never extend it. Bounded queue backpressure does not
  consume a pending CF, deadline or sequence number.
- Reset increments session generation, clears queued frames, ISO-TP
  pending state and filters. No database lookups and no HTTP/network.
- Pure test API `ingest_synthetic` requires an explicit caller-supplied
  frame. It does not open a socket or physical CAN/DiCE/J2534 interface.
- The M3 C++ `VirtualCarJ2534Cpp.dll` continues to return disconnected /
  unsupported for all actual PassThru operations. It is intentionally
  **not linked to a live CAN source** and must not be registered as an
  operational J2534 adapter.

## Eight deterministic synthetic gates

1. Standard/extended CAN IDs, allowed bitrates, no same request/response.
2. PASS/BLOCK filters and exact ECU ownership of Flow Control IDs.
3. 64-frame FIFO order, exhaustion and generation tags.
4. Segmented ISO-TP FF/CTS/CF reconstruction and sequence numbers.
5. Block-size credit and microsecond STmin across FC block boundaries.
6. Reserved STmin, WAIT, OVERFLOW and fail-closed flow-control handling.
7. Wrong CAN ID/unrelated messages do not prolong FC deadline.
8. 29-bit CF sequence wrap, queue saturation and reset invalidation.

Run these on Linux (host-only reference) and on Windows Win32 and x64
through the existing CMake/ctest target. Existing C x86 J2534 CI remains
independent. Passing tests prove these **synthetic engine behaviors only**,
not timing accuracy on hardware or old/new J2534 interop.

## Remaining within M4B and after

- Implement the exact J2534 pass/filter/flow-filter semantics and
  ISO15765 payload-delivery metadata, including atomic
  START_OF_MESSAGE + complete response admission.
- Add independent multi-route queue isolation (not one-route-only).
- Compare the new native x86/x64 engine against the real legacy C
  implementation under the same input traces, byte-for-byte.
- Test timing on Windows under load, rollover/cancellation, queue
  overflow accounting and Stop/Reset race behavior.
- Keep the DLL **fail closed** until M5 authentication to the
  separately verified C# Named Pipes service.
- No fabricated Volvo CEM B9FB/A3/A6 positive frames, no programming,
  PIN, SecurityAccess or active hardware transport.

Cross-chat trigger remains exactly **virtual car**.
