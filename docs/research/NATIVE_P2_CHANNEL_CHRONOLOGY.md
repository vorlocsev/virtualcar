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


## First later A3 without collapsing the full native session

The full synthetic native x86 audit in CI run 41760184039 contains
two B9FB requests (one complete, one deliberately unanswered) and
three separate A3 requests. A correct whole-session chronology is
therefore multiple_candidates_no_unique_pairing; this does not
invalidate a narrower **first-later-A3 observation** after the first
completed B9FB.

The v2 chronology report now includes first_completed_b9fb_to_later_a3:

- The first completed B9FB event in a single PID/native epoch is
  considered independently of overall session ambiguity.
- Select only the first **A3 request** occurring later in source
  order. It is NOT necessarily the first *application TX*: the
  independent followup audit is still needed to prove that.
- A second B9FB TX between the completed event and that A3,
  different channel, changed channel generation after Disconnect,
  different CEM target, different baud, corrupted native context,
  or unverifiable source-local clock prevents a matched/timed
  correlation.
- Only when all checks pass does the v2 report mark status
  same_channel_target_timed, with source event order numbers
  and the source-clock gap in milliseconds.
- The report continues to expose the previous conservative
  whole-session outcome and never claims ECU access or client
  VIN acceptance.

New emulator/tools/verify_native_p2_first_a3.py compares the
two already-redacted native outputs: the whole-channel chronology
and the independent first-next-TX timing audit. It requires their
first-A3 timing and channel/target results to agree, while
explicitly retaining whole-session ambiguity. A fixed, allowlisted
correlation JSON is produced; no raw native trace is uploaded.

Eight synthetic regression groups test a full multirequest session,
A3-before-B9FB, A3 during delivery, different channel/target,
channel reuse and intervening B9FB, malformed metadata and
clock bound, agreement of two independent sanitized reports,
tampering detection and output no-overwrite. These checks run
in the existing Windows x86 CI.

**Evidence boundary:** the previous native DLL-only measurement
of 0.520ms in run 41760184039 is a synthetic client/harness
measurement. Even a successful cross-report check cannot
establish the sequence or timing of historical SectorV run 188,
nor identify the correct A3/E3 security access response.


## v3 guard: unrelated app TX and RX-buffer reset

A gap between the completed B9FB and a later A3 is not necessarily
a direct transition, even on the same native channel. A complete
J2534 text log can contain another application TX (OBD, D2 B9F0,
or a different service) or a CLEAR_RX_BUFFER operation.

The v3 source-local auditor now keeps internal, bounded markers for:
- Any other recognized/unclassified **application TX** between
  completed B9FB and the first later A3, including traffic from a
  different channel in the same PID.
- Any J2534 CLEAR_RX_BUFFER log event in that interval.

Neither marker copies payload bytes, PID, host or source path into
the public chronology. When present, the first candidate is marked
intervening_other_app_tx or clear_rx_between_events and its
same_channel_target_generation_verified value remains false.
The whole-session outcome receives the equivalent explicit reason
when the session has a unique B9FB/A3 pair.

Events before the completed B9FB or after the selected first A3
do not retroactively invalidate that candidate. A prior B9FB TX
remains an independent barrier; channel generation and explicit
disconnect checks are preserved from v2.

This is a deliberately conservative ordering check. An app TX in
between could be legitimate client behavior, but it prevents a
claim that the A3 was the immediate next meaningful request.
The separate followup-window auditor is still the authority on
the **first next app TX**, not merely the first A3 service.

Eight new synthetic tests cover OBD/D2 intermediary traffic,
other channel TX, clear after and during B9FB, traffic before or
after the pair, and a different PID whose traffic must not be
spliced into the source process.

The cross-report native CI gate uses v3 and must continue to pass
unchanged synthetic x86 DLL evidence. It does not infer the
real SectorV Hardware acceptance predicate or synthesize E3.
