# Volvo XC90 V8 MY2009: VIDA CarCom candidate 31296075 AA (D2 v7)

## Evidence and scope

DriveRAP diagnostic coverage lists 31296075 AA / D2 v7 for XC90 2009
B8444S. This is a catalog candidate, not an OEM capture or a specific VIN match.

The existing CarCom SQLite audit validated seven common tables and six
aggregate relationships. The new local lookup extends that research to
T120_Config_EcuVariant, T121_Config and T123_Bus. It looks up the exact
T100_EcuVariant.identifier 31296075 AA and follows T110/T111 services,
T120/T121/T122/T123 route metadata and the count of T160 default-profile
links, using only an existing owner-local CarCom.sqlite export.

The private report preserves original commAddress, busRate (including NULL),
CAN IDs, protocol, bus, service and mode; it does not guess baud from GGD.
VIN, XML, SQL, passwords, arbitrary profile identifiers and scripts are not
exported. Missing identifier means missing in this export only.

## Local Windows invocation

Use a reviewed development checkout with validated Windows CI and an existing
authorized private export. Run these commands in Windows PowerShell:

    $python = (Get-Content 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
    & $python '.\emulator\tools\audit_vida_cem_d2_variant.py' --folder 'E:\VirtualCar\VIDA-private' --output 'E:\VirtualCar\VIDA-private\cem-d2-31296075-aa-001.private.json'

Always choose a NEW output filename. The report remains outside the repository
and should be reviewed locally rather than posted to a public PR.

## Proof boundary

Metadata does not prove original VIDA selection, D2 bitrate, an installed
CEM, real E3/E6/F9 replies, security session success or VIN acceptance.
No original VIDA SQL Server, ECU, physical J2534, INI, replay or releases are
modified. The new tests use synthetic SQLite only.
