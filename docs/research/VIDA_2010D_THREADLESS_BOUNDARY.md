# VIDA 2010D legacy J2534 log: request and write-failure boundary

2026-11-03. Virtual Car draft research PR #39. Read-only. No VMware.

## Evidence introduced by the user

The pasted VIDA2010D/DiCE snippet contains an older two-bracket pattern:

    22:36:22,291 [DiagConnection ][VehCom] VehComm request: Ecu '40', Message 'B9FB'
    22:36:22,306 [J2534ChannelMana][VehCom] PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000) ...
    22:36:22,306 [J2534ChannelMana][VehCom] J2534 function:passThruWriteMsgs failed with return value:ERR_DEVICE_NOT_CONNECTED

The user-supplied text also displays the CB 40 B9 FB packet dump *after*
the API error, followed by an attempted device reopen, an
ERR_DEVICE_IN_USE, cleanup, and an attempt to access B9FB on target 50.
The example is **not** a complete successful scan and includes no
authentic positive RX data for either B9FB target. It cannot prove that
a CEM response parser rejected any bytes.

The old pattern has no thread ID. The existing
emulator/tools/audit_j2534_discovery.py intentionally binds newer,
three-bracket VIDA records [J2534ChannelMana][thread][VehCom] by
thread. We should **not** silently extend that binding to old logs
that do not contain the required identifier.

## New bounded offline tool

emulator/tools/audit_vida_2010d_boundary.py

- Recognizes only the two-bracket legacy VIDA prefixes, target 40/50
  and named B9FB, B9F0, B9FC or A3 requests.
- Distinguishes the *observed* client request, a J2534 WriteMsgs call,
  a write failure, and a matching hexadecimal TX **dump**.
- The dump is not proof that CAN data left the J2534 device.
- Allows case variants of passThruWriteMsgs in legacy error records.
- Keeps other adapter failures in a bounded allowlisted error counter.
- Reports the interval from one client request **log line** to the
  next request line. This is **not** an RX or protocol timeout.
- Refuses to correlate older two-bracket records with newer three-
  bracket entries and always reports thread_binding_verified=false.
- Does not interpret payload content, serials, VIN, identities, private
  operands or paths; output is bounded, sanitized JSON.

PowerShell invocation from the repository root:

    py -3 .\emulator\tools\audit_vida_2010d_boundary.py .\local-vida.log --output "$env:TEMP\vc-vida2010d-audit.json"

Do not upload a raw personal VIDA trace to GitHub. Keep it locally and
review the summary before sharing. Output is exclusively created and
never overwrites the input or an existing destination.

Eight tests exercise old-format B9FB + failed write, separate
Open/Ioctl failures, RX dump uncertainty, malformed dump, HTML-escaped
brackets, isolation from the modern format, missing timestamps, and
redaction/no-overwrite. Tests use only synthetic lines.

## The two supplied ECM PowerShell scripts are a separate source

The Google Drive files supplied in this conversation are:
- "Выборка данных1.ps1": ten repeated local reads of Log_file.log,
  10 independent time/value text outputs.
- "ОБработка лога VIDA_ver3.ps1": one Get-Content read filtered by
  <---, then ten E6 service/parameter patterns; concatenates sparse
  records, sorts by 12-character Time substring and creates a tab-
  delimited Log.csv despite the .csv name.

Both scripts extract values with fixed Substring(82,2) and (85,2)
offsets and use Convert.ToString with a concatenated "0x" value.
The scripts provide author-specified coefficient formulas, but no
Log_file.log sample, validated byte offset schema, or known-good output.
We cannot conclude their reported numeric results are correct without
an actual log and an independent conversion check. Their E6/ECM
parameters also do not establish a B9FB response shape.

**Do not execute either script as an automatic data source.** They are
static examples only; the new VIDA audit never runs PowerShell.

## Research conclusion

The existing MY2005 SectorV PR30 trace shows 13 B9FB frames
delivered followed by Hardware/A3 with no RX and a ~5-second timeout.
The older VIDA2010D/DiCE snippet fails earlier: the J2534 write itself
returns ERR_DEVICE_NOT_CONNECTED. These are **different clients,
different runs, and different failures**, not one causal trace.

No new positive A3 reply is synthesized, no CEM logic is modified, and
no claim of Volvo XC90 V8 MY2009 acceptance is made.

## Legacy preflight call-order evidence (not a protocol requirement)

The client-side VIDA2010D excerpt supplied in this conversation records the
following order before the unsuccessful write to CEM target 0x40:

1. PassThruConnect(88, 0x10000001, 0x20000100, 125000, 90)
2. PassThruIoctl SET_CONFIG DATA_RATA=125000, LOOPBACK=0 BIT_SAMPLE_POINT=68
3. PassThruIoctl SET_CONFIG CAN_XON_XOFF_STMIN=40
4. Start J2534 message filter ID 0 on channel 90
5. Start J2534 periodic message channelId: 90 pMsgId:0
6. PassThruWriteMsgs(90, PASSTHRU_MSG, 1, 2000)
7. ERR_DEVICE_NOT_CONNECTED (the write fails); a subsequent TX arrow dump
   **does not** mean that the device transmitted the request.

This records what VIDA logged, not proof of successful PassThruConnect,
filter installation, actual periodic transmission, required D2 segmentation,
or a normal preparation contract for all VIDA/DiCE versions.

The older plain-text sample spells the bitrate label DATA_RATA. The audit
also recognizes DATA_RATE as a spelling variant; neither spelling proves
which underlying Ioctl parameter was accepted.

The enhanced analyzer reports a nested per-attempt preflight structure:
- fixed, source-order stage names (Connect, bitrate config, STmin config,
  filter, periodic, WriteMsgs);
- whether a logged filter/periodic/write channel equals the *declared*
  Connect channel in the same chronological attempt;
- whether declared bitrate config equals the preceding Connect bitrate;
- exact comparison to the constants of **this one published sample**;
- matches_published_sample_call_order, a strictly synthetic/order-only
  indicator, not approval of a driver, vehicle or ECU result;
- separate connect_success_verified/filter_effect_verified/
  periodic_effect_verified fields, each always false.

The analyzer never exports device ID, channel ID, host path, original raw
frames, individual raw J2534 flags, or private adapter identities. All
associations stay chronological, since the source lacks thread IDs and
independent success return codes.

Eight additional synthetic tests (09–16) check the full call order,
out-of-order/missing STmin, channel mismatches, noncanonical flags/baud,
both documented spellings, out-of-range IDs and private-data exclusion.
The legacy trace is **not** bundled as a raw fixture.

### Unresolved boundary

The target read-only SectorV XC90 V8 MY2009 investigation still needs a
comparable successful-client trace identifying which exact physical or
virtual CEM response is consumed after B9FB. The historical DiCE device
disconnect does not establish a B9FB parser fault. PR30's SectorV
Hardware/A3 timeout remains a separate source and separate failure mode.
