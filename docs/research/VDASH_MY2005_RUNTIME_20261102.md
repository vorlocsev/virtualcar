# VDASH MY2005: actual Windows GUI run, 02.11.2026

Related: Issue #37 / #4, draft PR #39 and PR #41. This is a new observation
on the current Windows system, **not** a VMware guest or physical-car test.
The profile is explicitly synthetic MY2005, ECM-only, 12.5 V, RxStart enabled,
passive traffic disabled, zero CEM fixtures. It is not authentic vehicle data.

## Provenance and capture boundary

- Native DLL: PR #39 HEAD `6f16bc34b65279fd19bdcea4619d2946cc208357`,
  [CI run 41436445230](https://github.com/vorlocsev/virtualcar/actions/runs/41436445230),
  artifact merge ref `50e83a393078ea97e5f91a7bad729bada8021ec5`.
- Artifact SHA-256:
  `b0af113eb0cbfa6e5783e3229fb245584675d42dc4590b15ed51a5fca20b44e0`.
  DLL SHA-256: `6b88755863495ada3a78d964aa45d00c60608486eeed1c16729388bd3e7d7351`.
- GUI: local Frontend FileVersion **2.5.115.84**, UI brand **VDASH 2.0 - Sponsored**,
  SHA-256 `bb9153650a736e3f03ca1a4cea265d6a5692fe1123729b3169d60f9614eea0f9`.
  The UI also displays `PATCH: OK`; its meaning and the GUI copy's distribution
  provenance were not investigated. This is not a comparison with an independently
  obtained, unmodified vendor distribution.
- Native worker: `b29b7f5e90645c9b04a12d12578a154b6ee7441c7aab1865a5e19d31277fe1aa`.
  A separate direct launch printed banner **13.33.1.57** and opened a console;
  no console input was sent. The worker was stopped before the GUI launch.
- Synthetic profile SHA-256:
  `69cff86f8338156149a64421af546bd71ac250514c804a227536bc3241819943`.
  Neither the profile nor its VIN is published.

The user completed login manually. One GUI invocation included automatic
detection after login and **one controlled refresh**. The capture contains two
worker processes and 33 repeated PassThruOpen cycles; these are not 33 independent
vehicles or test runs. A live module sample directly binds **worker 1** to the
isolated DLL path/hash above. Worker 1 covers text lines 1–1406, 19 Open/19 Close,
19 VIN deliveries and 38 checked RX metadata records. Worker 2 covers lines
1407–2461, 14 Open/13 Close; its loaded module was not independently sampled.
Aggregate counts below cover both workers and must retain this limitation.

The DLL used an isolated registration and adjacent synthetic profile. Existing
global logs were allowed to append, with their original prefixes hash-checked
before extracting complete suffix lines:

| Source suffix | Bytes / lines | SHA-256 |
| --- | --- | --- |
| Native text | 277220 / 2461 | `fe6ef7eebdab09d8cc330cb4a473ca41ceeedc1743f536f3902e607e54da17c9` |
| Backend JSONL | 150513 / 594 | `3fa8240be8649a1ca2366291571d62ce70773ac665f02af57ef6b809d576828b` |

No bytes were appended before manual login. Both original prefixes remained
unchanged. The native suffix contains only the expected worker host label,
with two process instances. Backend has no PID; there is no clock-based or
row-by-row join between the two reports. Private paths, IDs, logs, screenshots,
account details and VIN remain outside Git.

## Observed client outcome

The GUI displayed **XC90 / MY2005 / B8444S / P2 / 12.5 V** for the synthetic VIN.
Both initial detection and the controlled refresh produced this warning:

> Some ECUs in the car are not able to communicate or are stuck.

Its following battery-reset recommendation was not executed. Opening ECU
diagnostics displayed **Live datalogging by ECU** with an empty ECU list.
No logging Start, Clear DTC, Emergency reboot, programming or security action
was selected. Displayed model/year are UI observations, not authentic CEM identity.

The GUI and its spawned workers were closed after capture. The monitor started
by this invocation was stopped. The previous adapter selection was restored,
the temporary registration removed, and the original registration retained.
Profile, DLL and worker file hashes remained unchanged.

## Transport result and first complete sequence

All **99 app TX** are accounted for: 33 each `0x7DF:3E80`, `0x7DF:0902`,
`0x18DB33F1:3E80`. No other TX shapes occur in this capture. All use protocol 6,
500000 baud, channel number 1; flags are `0x40` for the first two shapes and
`0x140` for the third. Channel 1 is reused after disconnect; it is not one
uninterrupted connection. No periodic firing/marker was observed, which does
not establish whether the client attempted to register a periodic message.

The following source lines refer to the extracted native suffix and **worker 1**,
whose loaded module was directly sampled:

| Line | Observation | Next observed step |
| ---: | --- | --- |
| 20 | Open | Connect attempts, including rejected pin-switching modes |
| 23 / 24 | `0x8004`, flags `0x800` / `0x900`, 125000; both status 3 | CAN/ISO15765 attempts continue |
| 53 / 54 | TX context ch1, protocol6, flags0x40, 500000 → `0x7DF:3E80` | VIN request 63/64 |
| 63 / 64 | Same transport → `0x7DF:0902` | Separate start and data RX |
| 67–69 | RX context ch1, protocol6, status2 → `0x7E8`, ID only; metadata 6/2/4/0 | Data RX 70–72 |
| 70–72 | RX context ch1, protocol6, status0 → `0x7E8`, header490201, 24 bytes; metadata 6/0/24/24 | Disconnect 73/74 |
| 85 / 86 | TX context ch1, protocol6, flags0x140, 500000 → `0x18DB33F1:3E80` | Rejected CAN_PS Connect at 88 |
| 88 | `0x8004`, flags0x900, 125000, status3 | Disconnect / Close 89–91 |

The text auditor verifies **33 VIN-shaped deliveries**, 33 separate starts and
66 metadata records; zero missing/invalid metadata, off-route RX or parse errors.
It leaves the 33 suppressed TesterPresent transactions `unverified` by design.
The PR #39 backend auditor independently reports 99 requests / 33 sessions:
33 delivered, 33 suppressed, 33 `unverified/explicit_no_response`, all app writes,
all 99 terminal events present. Queued/dequeued RX are both 66; drops, filter
drops, conflicts and invalid lines are zero. The 33 backend sessions have no
later allowlisted CEM probe after VIN TX. Full TX inventory also contains no
A3/A6/B9F0/B9FB/P3 request. This conclusion is confined to this virtual DLL capture.

There are **33 Open but 32 Close markers**: the final TesterPresent ends at EOF.
Per-request terminal evidence is complete, but not every API session has an
observed clean Close. No timestamp is joined across logs or treated as ECU time.

## Concrete compatibility gap: CAN_PS is rejected

The existing Connect auditor found 236 complete result records, zero malformed:

| Protocol / flags / baud | Result | Count |
| --- | --- | ---: |
| `0x3 / 0x1000 / 10400` | ERR_INVALID_PROTOCOL | 99 |
| CAN `0x5 / 0x900 / 500000` | OK | 3 |
| ISO15765 `0x6 / 0x800 / 500000` | OK | 33 |
| ISO15765 `0x6 / 0x900 / 500000` | OK | 33 |
| CAN_PS `0x8004 / 0x800 / 125000` | ERR_INVALID_PROTOCOL | 3 |
| CAN_PS `0x8004 / 0x900 / 125000` | ERR_INVALID_PROTOCOL | 65 |

Thus **all 68 observed CAN_PS Connect attempts were rejected**. This is a directly observed
unsupported transport boundary before any hypothetical traffic on those channels,
not a missing positive CEM fixture. It is a plausible obstacle to additional
ECU traffic, but **the causal link to the warning is unverified**. The program
may use fallbacks or require other conditions. The trace does not reveal the
missing channel's pin selection or subsequent requests after successful Connect.

Do not alias CAN_PS to CAN or infer its physical pins from 125000 baud. The next
implementation decision needs documented pin-switching semantics and an explicit
virtual-channel model; any supported read-only observation stage requires a
separate focused PR and 6–8 relevant groups. No new CEM response follows from
this result. The separate SectorV normal-mode condition remains unproven.

## Eight checks and reusable analysis

| Check | Verified result / limit |
| --- | --- |
| 1. Runtime provenance | GUI/worker/DLL/profile hashes fixed; direct module sample only for worker 1. Recovered 2.5.115.79 IL is a different evidence set. |
| 2. Native preflight | Actual x86 CI DLL passed all eight native route/ABI groups plus backend verifier in an isolated synthetic harness. |
| 3. Capture integrity | Both original prefixes and complete extracted suffixes verified; one GUI invocation, two workers, no pre-login append. |
| 4. TX/RX metadata | All 99 TX shapes enumerated; 33 start/data pairs; 66 metadata checks pass. |
| 5. Backend lifecycle | 99 roots/terminals, 66 queued/dequeued, zero conflicts/drops; final API Close missing separately. |
| 6. Connect/config | 68 CAN_PS rejects identified; DATA_RATE applied, other accepted settings do not prove physical effects. |
| 7. Client outcome | Synthetic model/year displayed, warning observed, ECU list empty. Command-result receipt and DetectResult parsing not observed. |
| 8. Restoration/privacy | Client processes closed, selection restored, temporary registration removed; raw/private artifacts outside Git. |

Used the PR #39 artifact's `tools/audit_backend_evidence.py`, PR #41's
`emulator/tools/audit_j2534_discovery.py --include-obd`, and existing
`emulator/tools/audit_j2534_connect.py`, each with a new output path.
Backend periodic roots and narrower 7DF/500k classification differ from the
text tool's scope; their totals must not be treated as interchangeable.

[Machine-readable summary](vdash-my2005-runtime-20261102.summary.json) contains
only fixed observations, hashes and aggregates. Neither auditor's client/identity
verification flag is upgraded by manually observed UI model display.
