# Stage 45: SectorV normal-mode gate, evidence audit only

**Goal:** separate client-side frame matching, CEM hardware probing, and
normal-mode UI warnings in Issue #4. This is not a parser of `SectorV.exe`
or of the private `sectorv.log`. No SectorV implementation, client binary,
or compatible XC90 V8 MY2009 trace is committed or executed.

## Verified chronology vs. unknown predicate

From a **separate SectorV 1.1.0 MY2005 LAB** run described in PR #30 and
`docs/research/p2-public-capture-followup.md`: the client-side B9FB matcher
reported 13 observed / 13 matched / 0 ignored; later Hardware CEM target50
(HS 500 kbit/s) and target40 (LS 125 kbit/s) emitted A3 requests with
no matching RX, around 5000 and 5001 ms reported timeout intervals; the
UI showed 24 installed modules but 0 reachable, plus a normal-mode warning.
Those observations do NOT establish the exact predicate that emitted the
warning or identify a genuine XC90 V8 MY2009 session.

Earlier discussion tentatively proposed an `E3 02` reply and a 2500 ms
acceptance window. This **has not been reproduced against a verified SectorV
client binary or complete successful client trace**. It must not be treated
as an implementation contract. `A3` is listed publicly as Security Access
Mode in Volvo D2 documentation, so synthesizing a positive E3 or bypassing
authorization would add unverified, potentially unsafe behavior. The audit
therefore records any A3 RX only as `rx_seen`, never as authorization.

## Audit input: manually curated, strictly allowlisted single-run events

Run the tool on a human-reviewed, anonymized JSON summary, NOT on private
raw logs. Example is **synthetic**, not a new SectorV capture:

```json
{
  "schema_version": "virtualcar-sectorv-gate-evidence-v1",
  "client": "SectorV",
  "version": "1.1.0.0",
  "scenario": "P2_MY2005_lab",
  "run_scope": "same_client_run",
  "observations": [
    {"event":"b9fb_matcher","source":"client_log","observed":13,"matched":13,"ignored":0},
    {"event":"hardware_a3","source":"client_log","target":"50","outcome":"timeout","elapsed_ms":5000},
    {"event":"hardware_a3","source":"client_log","target":"40","outcome":"timeout","elapsed_ms":5001},
    {"event":"normal_mode_warning","source":"client_ui"},
    {"event":"ecu_reachable","source":"client_ui","count":0}
  ]
}
```

```sh
python emulator/tools/audit_sectorv_gate.py SAFE-single-run.json --output NEW-gate-audit.json
```

- The reviewer must verify that all observations belong to the same run;
  source ordering is retained, but no time synchronization between processes
  or with a separately collected J2534 log is assumed.
- Exact event names and field allowlists reject path, VIN, raw A3 operand,
  full payload, arbitrary free-text or invented E3 predicate fields.
- The output never contains identifiers, private paths, hashes, CAN payloads,
  source log lines or raw client UI text. The output file is created only
  with exclusive `x` mode; existing files are never overwritten.
- A matcher accepted 13 frames is **not** acceptance of VIN, ECU inventory
  or normal mode. `rx_seen` after an A3 probe is not proof of authorization.
- Results always keep client ECU acceptance, normal-mode predicate,
  expected E3 bytes, and security-access authorization set to `unknown`;
  `replay_approved=false`.

## Validation / prerequisites for determining the real predicate

Eight Python unit-test groups: complete B9FB matcher with timed-out
Hardware probes, matcher-only, A3 RX without authorization, partial matching,
cross-run/version rejection, privacy fields and made-up E3 rejection, invalid
counts/duplicate events, and secure exclusive CLI file creation.

To determine the exact SectorV acceptance predicate one needs either a
verified program binary/method extraction **from the same 1.1.0 client build**
plus proof that code executes in normal-mode preparation, or a matched
successful read-only client+J2534 run with the exact request/response and
observed UI transition. An E3 fragment from other cars or a generated
laboratory positive response is insufficient.

Sources:
- [Issue #4](https://github.com/vorlocsev/virtualcar/issues/4)
- [PR #30](https://github.com/vorlocsev/virtualcar/pull/30)
- [P2 public capture follow-up](p2-public-capture-followup.md)
- [P2 read-only discovery evidence](p2-readonly-discovery-evidence.md)
- [D2 opcode glossary](https://waal70blog.wordpress.com/2015/12/02/the-can-network-on-a-volvo-part-three-message-interpretation/)

No changes to `virtualcar.c`, A3/A6/B9F0, Dvinholm, main or Virtual Car releases.
