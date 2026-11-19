# B3A7 | VIDA 2014D FIVE_BAUD_INIT ABI observer

Status: **code prepared / original VIDA B3A7 NOT TESTED**. B3A6 exact-tested baseline: `edc6d876036cb002f1d9b7e680472e78cf3cfe3a` (separately saved as immutable evidence).

## Source-based observation

Original VIDA 2014D in B3A6 issued `FIVE_BAUD_INIT` (J2534 Ioctl 4) at 18:18:08.351 for ISO9141 channel ECU address 0x51, then sent `83 51 13 B9 F0` and waited for replies after the unsupported init. Twenty 5000-ms K-Line ReadMsgs calls ultimately timed out, and upstream CAN/D2 also had missing validated ECU responses. This **does not** prove that bypassing init can identify a car.

The SAE J2534-1 FIVE_BAUD_INIT ABI requires `SBYTE_ARRAY` input with `NumOfBytes=1`, `BytePtr[0]=target`, and output with a capacity of at least 2 ECU key bytes. Reference: [J2534 Ioctl documentation](https://www.scandoc.org/en/develop/j2534/pt_ioctl.html); SAE J2534-1 section 7.4.5.

## Code in this stage

- Separate `[Diagnostics] EnableVidaFiveBaudObserverLab=1`, **default 0** and effective only alongside `EnableVidaIso9141Lab=1`.
- Observes channel/protocol/baud/`FIVE_BAUD_MOD`, InputPtr/OutputPtr presence, successfully copied `SBYTE_ARRAY` structures, input count, output buffer **capacity**, and the original one-byte target address if valid.
- Windows x86 safely probes caller-owned memory through `ReadProcessMemory`. Invalid pointers are reported unavailable, not dereferenced. No raw pointer addresses and **no output keyword bytes** are logged.
- Leaves existing `PassThruIoctl(... FIVE_BAUD_INIT ...)` response **ERR_NOT_SUPPORTED**. No output memory mutation, created ECU keywords, K-Line RX, hardware pins, or VIN.
- Other J2534 behavior, B3A6 ACK gate and original untouched VIDA are independent.

## Eight host C regression groups (added, execution PENDING)

1. Default-off and prior error parity.
2. Original `0x51` and output capacity observed; no write to output.
3. Null input.
4. Null output.
5. Invalid input count/null data and insufficient output capacity, unchanged response.
6. CAN rejection and peer channel isolation.
7. No RX/periodic/keyword side effects.
8. Reconnect, opt-out and legacy parity.

## Acceptance criteria / next tests

- Run full host C regression with new B3A7 markers.
- Build Windows x86 DLL including the new `ReadProcessMemory` kernel32 import and run a **native x86** J2534 test, checking ABI and status parity. Host tests alone are insufficient.
- Only then use a **new isolated LAB adapter** in VMware with original VIDA and original, **unredacted** logs. Collect B3A7 exact target and output-capacity evidence in the same original VIDA PID, and keep the B3A6 tested DLL separate.
- Original VIDA/ECU VIN acceptance remains **NOT PROVEN**, and CAN/D2 fixture work remains separate. Keep PR Draft; no merge/release or OEM data replacement.
