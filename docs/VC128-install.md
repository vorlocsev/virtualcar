# VC127G installation and recovery

Use a disposable or recoverable Windows VMware environment with an existing
licensed diagnostic installation. This package contains a 32-bit J2534 provider,
a native controller, and the full vehicle-specific VC124 profile. It is not a
physical adapter or a universal vehicle simulator. Clean Windows dependency
validation and 64-bit J2534 client support are not established.

## Install

1. Obtain the exact tested ZIP and its accompanying release notes, checksums,
   MIT license and license scope. Compare the ZIP SHA256 using Windows PowerShell:
   `Get-FileHash -Algorithm SHA256 -LiteralPath '<path-to-ZIP>'`.
   Expected: `2D996757E355819848522225B39AE8337F9797D31E71A6B896EA48797C1F28D8`.
2. Take a recoverable VM snapshot. Extract to a new local directory. Keep the
   EXE, DLL and INI together; do not substitute the synthetic CI fixture.
3. Close VIDA, Internet Explorer, VirtualCar and other J2534 clients. Do not
   terminate them forcibly while a diagnostic session is active.
4. Run VirtualCar.exe as administrator. For a fresh installation, confirm
   clients are closed, select Install / Connect to VIDA and confirm the prompt.
   Check registration status; close the controller before running VIDA.
5. Select J2534 Lab Adapter in VIDA and verify the vehicle, network and DTC view.
   A separate running controller is not required for the tested profile.

## Existing RC1 or incompatible installation

The controller targets `C:\Program Files (x86)\VirtualCar-VC121` and the
32-bit `PassThruSupport.04.04\J2534 Lab Adapter` registration. It refuses to
replace incompatible files. Do not install over RC1 or manually overwrite its
DLL, INI or seal. Preserve a VM snapshot, the old directory and registration;
use a controlled clean migration or a fresh VM. Removal of the owned registration
retains files. For rollback, close clients and restore the verified VM snapshot.
Do not delete unrelated J2534 entries or change DiCE x64. No blanket rollback
support for arbitrary existing installations is claimed.

## Package metadata

The original ZIP is intentionally byte-identical to the accepted package.
Its embedded README and RELEASE-INFO predate the later acceptance and owner
approval. Use the accompanying current release notes for the updated status.
The ZIP includes an unredacted vehicle-specific profile; do not use it to
represent a different physical vehicle. No original VIDA binaries or databases
are supplied by this package.
