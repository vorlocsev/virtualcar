# B3A332: original VIDA connection config candidate boundary

This is a read-only, source-bounded investigation. It does not execute original
VIDA, load a J2534 DLL, query SQL, alter configuration, or communicate with ECU.

## Grounded source finding

See the existing source-level study:
docs/research/vida-2015a-settings-config-selection-il.md.

The original Core.DLL resolves UseClientSettings and DiagnosticConnection
via the configured XML source. Four distinct DiagnosticConnection names
are recognized: J2534DiagnosticConnection, DiCEDiagnosticConnection,
VirtualDiagnosticConnection, NoCommConnection.

The previously inspected original diagnostic.config.xml reported
UseClientSettings=false and DiagnosticConnection=NoCommConnection.
It is UNKNOWN whether that file was selected and loaded by the VIDA process
during a ReadVin attempt. The observed text is a candidate, not a process
setting. Do not edit the installed original VIDA settings based on it.

## Explicit owner-local offline check

Select an existing authorized diagnostic.config.xml file yourself.
No location is guessed or searched. Run the tool on a private workstation:

    py -3 emulator/tools/audit_vida_connection_config_candidate.py --candidate "YOUR_SELECTED_FULL_PATH_TO_diagnostic.config.xml"

The command classifies only the value attributes of
DiagnosticConnection and UseClientSettings. It rejects DTD/entities, duplicate
keys, invalid XML, symlinks and oversized files, and prints a bounded JSON
report without XML content, path, PIN, VIN, source hash or unknown values.

A NoCommConnection result means the chosen candidate file requests that
mode; it does NOT prove any running process selected that configuration.
A J2534DiagnosticConnection result likewise does NOT prove a real
J2534 client Open, Connect, TX or RX. All runtime and acceptance proof
flags remain false, including original VIDA ReadVin and ECU identification.

## Next real acceptance gate

On an independently authorized original-client session, determine the
effective configuration URL and selected diagnostic tool separately from
the static file. Then establish RunIdentifyVehicleScript, selected GetScript,
actual J2534 client process binding, successful native TX/RX, GUI-accepted
VIN and ECU identification. Do not manufacture or copy B9FB frames.

The existing trusted VMware self-hosted runner is not an original VIDA GUI
session, and a synthetic 13-frame B9FB demonstration is not OEM source.

Previous B3A331 native x86 J2534 preflight:
PR #408 / development SHA 5bbed1009aa00fe6cce0526392c9702ed874af0e,
VMware workflow #44659890556 SUCCESS, 36/36. It verified only the virtual
DLL CAN_MS channel lifecycle. This tool and synthetic tests do not change
that evidence or mark original client VIN/ECU acceptance as complete.

No production J2534 DLL, active INI, main branch, or release changes.
