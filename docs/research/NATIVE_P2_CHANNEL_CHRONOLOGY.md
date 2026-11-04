# Native J2534 A3/B9FB chronology with channel attribution

2026-11-04. Virtual Car draft PR #39, read-only research. No VMware,
physical DiCE, ECU programming, PIN or fabricated A3/E3 reply.

## Why this is needed

The recovered old SectorV dev10 summary of run 188 reports A3
before B9FB and in separate connection windows, but the historic
report does not contain the TX J2534 channel ID. An earlier client
note documenting a post-B9FB Hardware phase is a *different*
piece of evidence and cannot be merged with run 188.

The *current* virtual DLL already prints:

    TX context channel/protocol/flags/baud/time-us (BE)
    TX (app request) <CAN bytes>
    RX context channel/protocol/status/baud/time-us (BE)
    PassThruReadMsgs -> delivered <CAN bytes>

These native metadata records contain the actual temporary J2534
channel IDs and timestamps, so the next genuine SectorV capture
does **not** need invented route IDs or a change to CAN responses.

## Analyzer

emulator/tools/audit_native_p2_channel_chronology.py

- Read-only: parses one native J2534 text log, never injects CAN
  responses and never executes an input trace.
- Separates PID-local sessions at initialization, Open, Close and
  explicit session boundary markers.
- Internally uses exact native TX/RX channel numbers and keeps
  channel generation across disconnect/reconnect. When the same
  numeric channel ID is reused after a disconnect, it does not
  imply one logical connection.
- Emits only per-epoch channel aliases ("ch1", "ch2"), never raw
  PIDs, hostnames, CAN payload, VIN, protected data or source path.
- Recognizes D2 CEM50/40 B9FB requests and A3 app TX from strict
  CAN context, not from a misleading client-phase label.
- Validates a completed B9FB RX sequence with existing read-only
  D2 transport structure validation on matching channel/baud
  and known reply CAN IDs, excluding TX indicators.
- Distinguishes A3 before B9FB, during B9FB delivery, after B9FB
  on the same channel+target, after B9FB on a different channel
  or target, and ambiguous duplicate candidates.
- Includes source-local timing only when a unique after-order
  sequence exists. Even then it does NOT imply client acceptance.
- Treats malformed/missing TX/RX context and ambiguous disconnect
  metadata conservatively; no same-channel attribution is
  inferred from missing metadata.

Eight synthetic test groups verify (1) A3 before B9FB on a
different channel, (2) after-order same-channel timing, (3) A3
during B9FB delivery, (4) other channel/target, (5) reused
channel after disconnect and cross-PID separation, (6) incomplete
or off-route frames and RxStatus indications, (7) malformed
metadata and private-field non-disclosure, (8) session closure
and no-overwrite CLI.

## Usage for a real SectorV experiment

1. Launch SectorV against an **isolated, read-only Virtual Car**
   profile. Never enable actual ECU writes or programming.
2. Capture the native file SectorVVirtualCar.log from the
   temporary directory of the SectorV process. Keep the raw file
   private; it can contain vehicle identifiers and diagnostic data.
3. Run locally from the repository root in PowerShell:

    py -3 .\emulator\tools\audit_native_p2_channel_chronology.py "C:\path\to\SectorVVirtualCar.log" --output "$env:TEMP\vc-p2-chronology.json"

4. Verify the redacted JSON output locally. A complete transport
   record is **not** evidence that SectorV accepted a VIN, left
   the Hardware stage, completed A3 security access or identified
   any particular ECU.
5. If the target log is truncated, missing per-TX context, or
   contains a different client PID/epoch, its events may not be
   correlated. Do not silently join it to historical summary
   run 188 or to the independent PR30 native lab.

The tool reports a process-name marker only as an observation
from the untrusted source log, never as independent proof of
the executable or model year.

The Windows x86 CI also runs this analyzer after the previous
synthetic native B9FB -> A3 session and uploads the safe report
alongside the already validated B9FB timing/backend audits.
This validates parser behavior on a real x86 DLL-generated log
but does **not** amount to a real SectorV acceptance test.

## Acceptance boundary

The following remain unverified by the evidence available now:
- Actual same-channel SectorV run-188 A3/B9FB association.
- The complete SectorV Hardware-phase state machine.
- Any authentic response E3 to A3 for XC90 V8 MY2009.
- ECU identity acceptance and read-only block enumeration.

No Virtual Car release is created, PR #39 stays Draft and the
core CEM response path is unchanged.
