# B3A45: bounded original VIDA + VirtualCar J2534 log evidence

This is a **read-only evidence collector** for a single owner-controlled interval.
It does not start VIDA, load a PassThru DLL, connect to a vehicle, send messages,
modify Registry32, or assert a successful VIN. All raw logs remain on the
owner's Windows/VMware guest. Do not upload them or the private baseline.

## Why two sources?

The PR #319 x86 VirtualCar native DLL derives its log path by calling
\`GetTempPathA\` **in the client process**, then appends
\`SectorVVirtualCar.log\`. This can differ from the temp path used by a
separate admin PowerShell, and it is distinct from the original VIDA
\`C:\Vida\System\Log\Diagnostics\VIDA.log\`.

Earlier B3A38 compared only VIDA.log; unchanged original-client diagnostic
markers cannot rule out activity in the native VirtualCar log. The two-file
baseline is strictly a **before/after append window**, not process attestation.
If a client used a different temporary directory or a different log file,
this audit will miss it. No source auto-discovery is attempted.

## Operator-only example (run inside same Windows guest)

Use a reviewed checkout or CI artifact containing this script and its sibling
\`audit_j2534_connect.py\`. Confirm both log paths locally before running.

~~~powershell
$private = Join-Path $env:LOCALAPPDATA 'VirtualCar\OwnerPrivate\B3A45'
$vida = 'C:\Vida\System\Log\Diagnostics\VIDA.log'
$virtual = Join-Path $env:TEMP 'SectorVVirtualCar.log'
$script = 'emulator\tools\audit_vida_j2534_session_window.py'
$baseline = Join-Path $private 'baseline.private.json'
$report = Join-Path $private 'delta-categorical.json'

py -3 $script baseline --vida-log $vida --virtual-log $virtual --private-baseline $baseline
~~~

Do **not** copy these example paths to another VM without verification. Do not
change provider registration or the original VIDA installation to create a
matching trace. With real J2534 devices / vehicle physically disconnected and
an explicitly selected, verified virtual-only B3A7 provider, the owner may
separately run one voluntary read-only original VIDA GUI observation.

Afterwards:

~~~powershell
py -3 $script delta --vida-log $vida --virtual-log $virtual --private-baseline $baseline --output $report
~~~

Both output files must be new. Repeating a Delta with a different new output
is a *cumulative* interval since the original baseline, not a fresh session.
Re-baseline explicitly before another attempt. Historical-prefix mutation,
truncation, rotation, partial lines and more than 16 MiB of appended bytes
are not treated as valid evidence.

## Evidence boundaries

- Original VIDA markers are **literal matches**, not proof of J2534 calls.
- VirtualCar lifecycle, Connect/SET_CONFIG and TX/RX marker counts are more
  specific to a native library logger but are not automatically attributable
  to the VIDA GUI or to any particular operator attempt.
- Host classes \`iexplore\`, \`java\`, \`vidamonitor\` and \`other\` describe
  logger text only. PIDs, original host paths, raw lines, VIN and CAN bytes
  never enter the output report.
- \`PassThruReadMsgs -> delivered\` can describe generated virtual frames.
  \`LOCAL ACK ONLY (NO BUS/ECU TX/RX)\` is never ECU confirmation.
- No evidence in either file proves original VIDA accepted VIN or that
  synthetic B9FB matches a real XC90 V8 MY2009.
- Even a matching filesystem DLL SHA does not attest to loaded memory.
- This tool does not replace the original VIDA GUI observation, and does not
  read or export the user-owned private diagnostic data beyond local counts.

The output explicitly sets driver selection, loaded-DLL confirmation,
physical ECU RX and accepted VIN to false/unverified; those gates require
independent, consented evidence. Related: Issues #4 and #326.
