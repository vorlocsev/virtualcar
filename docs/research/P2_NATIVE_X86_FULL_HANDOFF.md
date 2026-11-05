# One native Windows x86 J2534 process: B9FB → B9F0 → P3 F114

Research checkpoint: 2026-11-04, Virtual Car Draft PR #39,
`research/vdash-functional-keepalive`. The tests are laboratory-only.

## Purpose

The existing Python synthetic logs could independently model D2 B9FB,
B9F0 and P3 ReadDataByIdentifier, but did not establish that a *compiled
x86 virtual PassThru DLL* could deliver all of these calls during one
uninterrupted process. The new Windows PowerShell runner
`emulator/tools/verify_native_p2_p3_handoff.ps1` uses the actual x86 DLL,
calls exported J2534 functions, and verifies its responses in order.

The runner copies the DLL into a new isolated test directory, writes
an intentionally synthetic `virtualcar.ini` there, redirects local
logging to that directory and opens both a 500 kbit/s D2 CAN channel
and a 500 kbit/s ISO15765 P3 channel in **one process**.

No vehicle/ECU is contacted. The mixed P2/P3 profile is solely an
instrumented route and transport test, not a valid model-year-specific
XC90 V8 network map.

### Exact laboratory exchange

1. Verify x86 ABI, library and J2534 exports.
2. Open one J2534 device with separate D2 CAN / P3 ISO15765 channels.
3. Send `0x000FFFFE: CB 50 B9 FB` via native WriteMsgs.
4. Read 13 synthetic B9FB reply frames on `0x01200003`, exact
   D2 controls `8F,09,0A,0B,0C,0D,0E,0F,08,09,0A,0B,4F`.
5. Send `0x000FFFFE: CB 50 B9 F0`; read three synthetic
   `8F/09/4C` frames with positive F9 F0 echo on `0x01000003`.
6. Send a separate P3 ISO15765 `22 F1 14` request on `0x726`.
7. Read the virtual DLL response from `0x72E`, checking
   a reassembled `62 F1 14` response with a deliberately synthetic
   17-byte laboratory VIN `VCARLAB0000000000`. This does not
   mean any real CEM supports that data or that a client accepts it.
8. Close both channels and the J2534 device.

The lab does not introduce any security/A3/E3 fixture, PIN recovery,
programming or real vehicle identifier.

## Independent provenance and privacy gate

`emulator/tools/verify_native_p2_p3_handoff.py` reads the
**same** private x86 J2534 native log and invokes the established
three-report source-local analyzer. The verifier demands:

- exactly one closed native epoch;
- one complete positive B9FB and one next same-channel B9F0;
- independent B9FB-to-B9F0 source-clock agreement;
- one complete positive B9F0 response;
- first next application TX recognized as P3 DID read;
- one positive P3 DID transport reply on its own native channel;
- zero ambiguous/malformed native context.

The verifier emits a tiny allowlisted JSON gate with no raw RX,
VIN, DID, part number, customer data, process ID, host, or source path.
All client acceptance, ECU inventory, original XC90 identity and
physical J2534 verification flags remain `false`.

A real ISO15765 J2534 TX/RX is a variable-length native record,
**not** a malformed twelve-byte classic-CAN D2 frame. The two earlier
B9FB-only native analyzers now treat valid ISO15765 and short CAN
messages as non-D2 traffic rather than source-corruption events.
They still require the exact eight-byte D2 CAN frame for B9FB success.

### Run locally

From a trusted repository checkout in Windows PowerShell:

```powershell
.\emulator\tools\verify_native_p2_p3_handoff.ps1 `
    -DllPath "C:\path\to\VirtualCarJ2534.dll" `
    -OutputDirectory "$env:TEMP\vc-p2-p3-native-new"
py -3 emulator/tools/verify_native_p2_p3_handoff.py `
    "$env:TEMP\vc-p2-p3-native-new\SectorVVirtualCar.log" `
    --output "$env:TEMP\vc-p2-p3-handoff-gate-new.json"
```

Both output paths must not already exist. All logs stay local;
the CI artifact uploads only the gate JSON and three redacted
`prepare_p2_capture.py` reports. The original native log and
laboratory profile are not included in the evidence artifact.

## Regression scope

The new Python test `test_native_p2_p3_single_run_gate.py`
has eight synthetic, fail-closed groups: full positive sequence,
missing B9FB, missing B9F0, negative B9F0, missing P3 RX,
off-route or wrong-DID P3, wrong PID / unclosed epoch, and
privacy plus no-overwrite. The separate Windows x86 native-routes job
is the actual compiled-DLL transport test.

## Boundary of evidence

Even a fully passing single-process native test proves only that
the **emulator + its own laboratory harness** exchanged the specified
synthetic data. It does not mean that SectorV/VDASH recognized an XC90,
displayed its hardware identifiers, accepted VIN, or populated a list
of actual ECUs. Those require an independent client-side result
from one authorized read-only run with the intended software version.

No Virtual Car release, PR merge, Dvinholm change or physical ECU
operation is implied by this work.
