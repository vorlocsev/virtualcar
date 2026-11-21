# J2534 Diagnostic Interface CEM50 — XC90 V8 MY2009 (laboratory)

This is a NEW, independently registered x86 J2534 provider built from the existing development emulator DLL, with an isolated synthetic Volvo P2 CEM50 B9FB profile. It is NOT a Volvo OEM CEM image and does not prove VIDA ReadVin or ECU acceptance.

## Identity and provenance

- Registered J2534 key / display Name: J2534 Diagnostic Interface CEM50 (no "Virtual" prefix).
- Published VIN (explicitly authorized by the owner): YV1CR855691511566.
- Model year: 2009. CEM D2 target: 0x50. Request: 000FFFFE / CB 50 B9 FB; native route: J2534 CAN ProtocolID 5, 500000 bps, 29-bit; response CAN ID: 01200003.
- 13 D2 frames; exact positive service echo 50 F9 FB; nominal spacing 12 ms.
- Synthetic published historical 2005-era B9FB template. The VIN field and six-character chassis field have been changed to the owner's public chosen identity; ALL other response fields are placeholders from the donor example, not attested XC90 V8 values.
- D2 target 0x40, B9F0/B9FC, unverified passive frames and CEM 0x726 F114 are not enabled by this profile. This avoids repeating the legacy 20-byte short F114 that yielded VIDA ResultGet(59790) empty. The original VIDA may still attempt the F114 route and may or may not fall back to CEM50; do not claim acceptance without an observed run.

This owner-approved published VIN is a deliberate exception for this ONE file to the project's default policy of keeping owner identities out of the repository. Do not publish other identities, SQL captures, real ECU dumps or logs.

## Native DLL / install

A Windows PE32/x86 J2534 DLL is NOT checked in. Use the trusted, independently verified x86 emulator build from development; the installer copies it under the independent filename J2534CEM50.dll and puts this directory's virtualcar.ini beside it. The native runtime requires the literal neighboring filename virtualcar.ini internally; this is NOT the J2534 display name.

In Windows PowerShell 5.1, after reviewing the code and SHA256, run:

    $src = 'C:\path\to\trusted\x86\VirtualCarJ2534.dll'
    $hash = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
    .\Install-J2534CEM50.ps1 -SourceDll $src -ExpectedSha256 $hash

The first call is DRY_RUN_ONLY and never installs or registers. The installer also preflights all thirteen sequential D2 frames, verifies the exact 17-byte VIN at B9FB payload offset 14 and the six-byte chassis field at offset 49, and refuses duplicate or unapproved INI entries before opening Registry32. After `-Apply`, it re-reads Registry32 values before reporting success. To install, in an ELEVATED PowerShell 5.1 window:

    .\Install-J2534CEM50.ps1 -SourceDll $src -ExpectedSha256 $hash -Apply

The source path and expected hash must refer to an independently reviewed binary; computing the hash does not itself establish trust. The script checks x86 PE32, SHA256, that the registry key and destination directory do not already exist, then stages a copy to %ProgramData%\J2534-CEM50 and registers only a new Registry32 key in HKLM\SOFTWARE\PassThruSupport.04.04. On failures during creation it attempts to remove only its new key/directory. It NEVER overwrites an existing registration, the installed VIDA configuration, current J2534 DLL/INI or SQL data. If the key or folder already exists, stop and investigate rather than deleting it.

## Native x86 regression before installation

The existing `emulator/tools/verify_native_routes.ps1` provides a synthetic, isolated J2534 baseline; its `-IdentityReplay` mode uses its own older fixture, **NOT** this published CEM50 VIN or profile. Its PASS must not be reported as CEM50 B9FB validation. An exact-profile CEM50 native smoke is now included as `Verify-J2534CEM50.ps1`. It stages a COPY of the x86 DLL and this exact published INI in a NEW output folder, calls PassThruOpen/Connect/CAN WriteMsgs/13 ReadMsgs/Disconnect/Close, and compares each byte against its independently embedded expected matrix. It does not touch the registry, installed VIDA or a physical adapter. Run only with a reviewed source DLL and its full SHA256:

    $src = 'C:\path\to\trusted\x86\VirtualCarJ2534.dll'
    $sha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
    .\Verify-J2534CEM50.ps1 -DllPath $src -ExpectedSha256 $sha -OutputDirectory 'C:\Lab\CEM50-native-new'

The report `native-check.json` records the DLL digest and exact 13/13 delivery, but explicitly keeps VIDA, ECU identification and physical hardware gates false. This smoke is **prepared, not executed**, until an actual Windows x86 DLL is supplied.

## Offline gates / runtime gates

Run from repository root:

    py -3 -m unittest discover -s emulator/tests -p test_cem50_j2534_adapter.py -v

Eight synthetic offline tests verify the identity, 13-frame D2 response, published 88-byte shape, VIN/chassis consistency, silence of unrelated routes, explicit synthetic provenance, installer guardrails, and existing native CEM50 route.

Still unverified until a separately authorized owner-machine experiment: exact DLL binary provenance, correct x86 provider selection in original VIDA, 500-kbit/s CAN D2 request to target 0x50, J2534 RX of all 13 frames, VIDA ResponseHandler extraction, VIN acceptance, ECU identification and T111/T122. Original VIDA previously observed 0x726 F114 and ResultGet(59790) empty. This B9FB-only adapter is an isolated alternative, not a fix for the F114 parser.

## Recovery / removal

The installer has no automatic uninstall: when appropriate, close the diagnostic client, ensure the DLL is no longer loaded, verify the exact new Registry32 key and dedicated directory, manually export the key, then remove only the newly created J2534 Diagnostic Interface CEM50 registration and %ProgramData%\J2534-CEM50 directory. Existing J2534 Diagnostic Interface and CANPS Step6 registrations remain untouched.
