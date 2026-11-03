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
