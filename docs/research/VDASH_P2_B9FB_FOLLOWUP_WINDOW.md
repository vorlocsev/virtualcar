# B9FB to first next TX: source-local 500/1000 ms window

Date: 2026-11-03. Virtual Car Draft PR #39, research/vdash-functional-keepalive.
No VMware or real-vehicle session.

## Current recorded evidence

The historical private SectorV MY2005 run PR30 reports 13/13 VIN/B9FB
frames at CEM target 50, followed by Hardware probes target 50/40 with
no matched replies and an approximately five-second wait on each route.
The research notes link the next D2 service A3 to subsequent text/backend
logs, but **do not verify a shared clock** from final B9FB RX to A3 TX.

Do not calculate this interval using the separate DiCE donor B9FB
record or the separate VIDA 2010D log whose J2534 WriteMsgs call fails.
Those logs belong to different sessions, software and clocks.

## New bounded auditor

emulator/tools/audit_d2_followup_window.py reads only native
Virtual Car J2534 trace context and:

1. Recognizes CB 40/50 B9 FB on D2 CAN ID 0x000FFFFE at
   corresponding 125/500 kbit/s bus.
2. Matches RX to channel/baud and known CEM RX-ID candidates.
3. Validates completed D2 transport framing and the positive B9FB echo.
4. Takes the last RX timestamp from native RX context time-us,
   never the system wall clock.
5. Finds the first next app TX, which must be from the same PID
   and uninterrupted log epoch, but may be from a different channel.
6. Computes milliseconds and reports whether the first observed
   app TX is within the following 500 and 1000 milliseconds.
7. Marks close, disconnect, clear, session-boundary and EOF outcomes
   without inferring any timeout or intentional client silence.
8. Emits only fixed output fields: no VIN, host, raw CAN frame,
   client PID, private operands or file paths.

The script never sends CAN, changes the J2534 DLL or asserts that
VDASH/SectorV accepted the CEM.

### Example

From repository root in PowerShell, with a private native J2534
capture that has matching TX/RX context metadata:

    py -3 .\emulator\tools\audit_d2_followup_window.py .\private-native-j2534.log --output "$env:TEMP\vc-b9fb-followup.json"

The output must not exist already. Review it locally before sharing.

The first next TX is classified using fixed labels: d2_a3_target_known,
d2_a3_target_unknown, d2_b9f0, d2_b9fb, d2_b9fc, d2_a6,
or other_or_unclassified_tx. A first unrelated TX takes precedence
over any A3 later in the log; this avoids rewriting source chronology.
The two timing windows concern only that first observed TX.
If the native log contains a new app-TX marker but its required context
is missing or malformed, the audit reports next_tx_unattributed and
timestamp_unverified. Such a record is neither proven silence nor a
measurable next request. No raw malformed data is exported.

The 32-bit native time-us wraps around. Elapsed values are reported
only up to 60 seconds; otherwise the clock is marked unverified.
A completed D2 sequence does not establish valid Volvo identity,
payload checksum or acceptance by a particular client version.

## Eight synthetic tests

1. A3 490ms after completed B9FB on the same channel.
2. A3 750ms later on a different channel/baud.
3. Non-D2 TX preceding a later A3.
4. A first TX after both windows.
5. An explicit read-timeout event without a next TX (not a
   verified 1000ms timeout).
6. A truncated B9FB or off-route RX.
7. Cross-PID and Close/Open epoch barriers.
8. 32-bit clock rollover plus privacy-safe CLI/no overwrite.

All assertions are offline and synthetic. Real SectorV, physical
J2534, an authentic XC90 V8 MY2009 CEM identity and any positive A3
response remain unverified. No emulator responses or release are
modified by this work.


## Native J2534 RX status gate

Source-grounded in emulator/src/virtualcar.c:
- Native DLL logs RX context channel/protocol/status/baud/time-us (BE)
  immediately before PassThruReadMsgs -> delivered using the copied
  PASSTHRU_MSG.RxStatus (near lines 1422-1430).
- The virtual J2534 layer defines 0x100 (CAN_29BIT_ID) for extended
  CAN and 0x02 (START_OF_MESSAGE) as a start indication.
- J2534 also defines 0x01 (TX_MSG_TYPE) and 0x08 (TX_INDICATION).
  An indication is not a positive CEM response even if its Data
  happens to resemble a B9FB frame.

The follow-up auditor now ignores RX records when any of the status
bits 0x01, 0x02 or 0x08 are present, but accepts 0x100. This metadata
safeguard is not an alteration of virtual CAN or J2534 behavior.

Eight synthetic regressions cover normal extended-CAN RX, each
indication bit, combinations, indication-only B9FB sequences, an
interleaved indication that must not move the last RX timestamp,
and the impossibility of inferring a complete B9FB/A3 transition
from indications alone.

## PR30 raw-log availability

Accessible Project/Library files and the current research-branch
GitHub tree do not contain a raw, single-run PR30 native log with
both the last B9FB RX context and first subsequent A3 TX context
timestamps. Existing reports such as j2534-diagnostics.json and
p2-public-capture-followup.md are summaries and research notes.

Therefore no measured A3 gap and no 500/1000 ms silence claim
is made for the actual historical PR30 SectorV run. A separate
donor DiCE capture or VIDA hardware-failure log cannot be spliced
into the PR30 timeline based on wall-clock resemblance.
