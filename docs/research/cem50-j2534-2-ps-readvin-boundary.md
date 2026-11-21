# CEM50 J2534-2 CAN_PS / ISO15765_PS — staged native experiment

Scope: separate Volvo P2 XC90 V8 MY2009 synthetic CEM50 lab profile and new transport routing only. Public test VIN **YV1CR855691511566** is explicitly approved by the owner. This work does **not** claim genuine Volvo OEM CEM data, successful original VIDA ReadVin, ECU identity, T111 or T122.

## Reason

Original VIDA showed: `Cannot read out VIN using a J2534-1 communication tool. Please enter VIN manually.` The screenshot did not confirm the exact device selected (name truncated). Independently the installed registry entry `J2534 Diagnostic Interface CEM50` declares only `CAN=1, ISO15765=1` and the legacy DLL rejects `CAN_PS=0x8004` and `ISO15765_PS=0x8005`. Simply changing registry values before implementing an API would be false advertising.

For public J2534 constant references:
- SAE J2534 API definitions `CAN_PS=0x8004`, `ISO15765_PS=0x8005`, `J1962_PINS=0x8001`.
- Pin pair values: HS 6/14 = `0x060E`; MS 3/11 = `0x030B`.
- Volvo VIDA Help explicitly says J2534-1 is not a diagnostic device. It does **not** guarantee that J2534-2 alone permits ReadVin; an explicit runtime acceptance test is still required.

Sources: https://www.scandoc.org/en/develop/j2534/pt_ioctl_config.html and https://www.volvospecialtools.com/index.cfm?event=info.dice .

## Design (review before running)

- Default `emulator/virtualcar.ini` remains unchanged: J2534-2 PS protocols are **disabled** unless adjacent profile `[J2534_2] Enabled = 1`. The opt-in is set ONLY in `emulator/adapters/cem50/virtualcar.ini`.
- For opted-in channels, `PassThruConnect` accepts exactly `CAN_PS (0x8004)` and `ISO15765_PS (0x8005)` at 500000 or 125000 baud. Internal emulation uses CAN/ISO15765 logic; client-visible `PASSTHRU_MSG.ProtocolID` and filter/flow-control protocol fields remain the original PS IDs.
- PS channels begin **unbound**. `SET_CONFIG(J1962_PINS)` must select 6/14 at 500000 or 3/11 at 125000 before TX. Invalid pin pairs return `ERR_PIN_INVALID`, speed mismatch `ERR_INVALID_BAUDRATE`, pin changes on an already bound channel `ERR_CHANNEL_IN_USE`. Batch validation occurs before mutation, not in partial order.
- No passive or scheduled transmissions on unbound PS channels. The old classic CAN/ISO15765 routes and tests must remain unchanged.
- CEM50 B9FB 13-frame synthetic response is bound to 500000 and verified only on the 6/14 virtual HS path; 3/11 at 125000 does not leak the fixture. No real hardware or CAN output.
- Periodic TX, FC filters and RX message identifiers are kept consistent with the selected PS ProtocolID. Software download, SecurityAccess, J2534 programming voltage, ignition states, and unverified ECU replies are not implemented.

## Explicit gate status

1. [x] The owner confirmed the independent **legacy CAN** x86 CEM50 B9FB native test: 13/13 delivered, and development CI #44871560856 SUCCESS at exact SHA `e86ff1f0ec7e02c7bcdc2c512003c3f5c450414f`.
2. [ ] New PS source code compiled in a clean Windows x86 build.
3. [ ] New PS C host tests executed in native legacy suite and reviewed on exact PR head.
4. [ ] Separate x86 DLL PS: `PassThruConnect(CAN_PS/ISO15765_PS)`, atomic pins, external PS RX ID, strict filter/flow-control, 13/13 B9FB.
5. [ ] Review a new **side-by-side** PS J2534 registration/installer. Existing `C:\ProgramData\J2534-CEM50` and Registry32 key `J2534 Diagnostic Interface CEM50` must not be overwritten.
6. [ ] Prove exact provider selected in original VIDA (expanded dropdown), observed `PassThruOpen/Connect`, actual TX/RX, and removal or persistence of the J2534-1 warning.
7. [ ] Only after the above: independent original VIDA `ReadVin`, ECU recognition, and T111/T122, each with direct evidence.

## Review boundaries

This branch does **not** modify Windows J2534 registry entries, the installed original VIDA, SQL Server BaseData, or physical adapters. Do not merge to persistent VMware CI before the untrusted branch has been evaluated outside that runner. `main`, releases and pre-existing J2534 registrations remain untouched.

The code exercises a **limited and opt-in** J2534-2 pin-selectable CAN experiment, not the whole J2534-2 standard or a proven VIDA-compatible device.
