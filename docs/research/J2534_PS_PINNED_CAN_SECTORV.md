# J2534-2 switchable CAN/ISO15765 lab channels (SectorV pre-connect)

## Real SectorV evidence boundary (2026-11-05)

One operator-provided **sanitized** J2534 A-profile report showed
`sectorv` as the source family, five balanced device Open/Close cycles,
12 Connect attempts, only four successes and **no observed B9FB or P3
positive transport**. Its exact allowlisted Connect modes were:

- Standard CAN 500000: **3 OK**.
- Standard ISO15765 500000: **1 OK**.
- CAN_PS 500000: **3 invalid_protocol**.
- ISO15765_PS 500000: **1 invalid_protocol**.
- Four other Connect attempts: **invalid_protocol** with redacted
  protocol IDs or flags, which remain *unknown*. Do NOT infer their
  meaning or claim a diagnosed client rejection after B9FB.

Those four known `_PS` failures are a credible J2534 compatibility gap,
but a subsequent SectorV recognition/ECU list is **not yet observed**.

## Standards distinction and implemented limited emulation

The names `CAN_PS` (0x8004) and `ISO15765_PS` (0x8005) are
**J2534-2 switched-pin protocols**, not proprietary synonyms for 5
or 6. A successful logical `PassThruConnect` does not automatically
attach them to the HS or LS CAN network.

The emulator now accepts these two protocol IDs and preserves their
**original ID** in RX messages. Switchable channels start *unbound*;
attempting to transmit before `SET_CONFIG(J1962_PINS)` returns
`ERR_DEVICE_NOT_CONNECTED`. The caller can bind:

- `J1962_PINS` parameter `0x8001`, `0x060E`: pins 6/14 (HS),
  using 500 kbit/s in the XC90 P2 LAB.
- `J1962_PINS` `0x8001`, `0x030B`: pins 3/11 (LS),
  using 125 kbit/s in this P2 LAB.

Other physical pin selections return `ERR_PIN_INVALID`. A
`SET_CONFIG(J1962_PINS)` on an ordinary fixed-pin CAN channel
returns `ERR_NOT_SUPPORTED`. The legacy 779/no-op test setting is
**not** the standards-defined J2534-2 0x8001 option.

Switching the pins cancels old queued CAN/D2 frames and staged ISO-TP
transports **only for that channel**, just like changing its DATA_RATE.
Other channels and their filters remain intact. Pins/rate mismatches
may have a connected logical channel but cannot synthesize a Volvo
P2 CEM response on the wrong virtual network. The same logic extends
to `ISO15765_PS` with read-only synthetic P3 F114 when properly bound
to the 500 kbit/s HS laboratory route.

The separate read-only P2 observer uses a normalized CAN/ISO family
internally without changing the public J2534 protocol or claiming
any real Volvo ECU identity.

## Verified versus not yet verified

Eight host-C regressions cover pre-pin unbound write rejection,
invalid/fixed pin errors, 6/14 B9FB receive, queued old-HS cancellation
on rebind, pin/rate mismatches, 3/11 125 kbit/s LS CEM route,
independent `ISO15765_PS` F114, restored HS route and continued rejection
of the unrelated vendor protocol 0x10000001. Existing CAN/ISO and other
CEM fixture tests remain mandatory.

An additional **compiled Windows x86** native probe is included in
`emulator/tools/verify_native_p2_p3_handoff.ps1` as
`-SwitchedPinProbe`. Only an actual green workflow execution of this
new probe may be called native validation. An offline host test and
compiled DLL alone cannot prove that SectorV will select those modes
or accept a virtual XC90.

`emulator/tools/prepare_p2_client_run.py` now prioritizes
`no_virtual_adapter_connect_attempt_observed` and
`no_native_b9fb_request_observed` over *otherwise valid* multiple
Open/Close cycles. The separate lifecycle field still reports all
cycles. `connect_invalid_protocol_attempts` is counted from
allowlisted Connect status metadata, not client payload.

## Sources used for protocol semantics

- [J2534-2 switched CAN/ISO15765, multiple independent lines](https://www.scandoc.org/en/develop/j2534/pt_connect.html).
- [Open-source J2534-2 protocol constants](https://pkg.go.dev/github.com/roffe/gocan/adapter/passthru).
- [J1962_PINS value and PS channel binding example](https://device.report/m/87c8134556cd3f1614de59a78f9a605ad19af6d36ac167ef6746ca7892e34568.pdf).
- [J2534_v0404.h: J1962_PINS 0x8001](https://github.com/diamondman/J2534-PassThru-Logger/blob/master/PassThruLogger/J2534_v0404.h).

No real customer's VIN, private J2534 log, Process ID or ECU identifier
is included here. No physical J2534, diagnostic-client scan, or ECU
write/programming has been performed.
