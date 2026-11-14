# B3A145: CEM 0x40, 125 kbit/s, synthetic native transport gates

## Goal and evidence

Owner's B3A138/B3A140/B3A142 investigation showed real-looking D2 discovery TX aimed at CEM address 0x40 with B9F0 and B9FB on 125000 bps. There were zero locally validated CEM_40 response fixtures and zero CEM_40 D2 delivered markers. The 13-frame CEM_50/B9FB fixture did deliver 104 historical D2 frames in a different bounded log sample, but that is neither CEM_40 nor VIDA GUI acceptance.

Public reversal of Volvo D2 and Volvo CEM confirms the families:
- CEM B9F0: ECU type / identification, but not a universal XC90 2009 OEM payload;
- CEM B9FB: Vehicle Information section; sample layouts are vehicle-dependent;
- CEM B9FC: configuration, with other-car sources not suitable for a MY2009 fixture;
- AE1B: D2 Read-DTC selector observed historically, correct CEM response not validated.

Source references:
- https://www.matthewsvolvosite.com/forums/viewtopic.php?p=629505
- https://github.com/spnda/volvo_vida_db/blob/main/scripts/d2.py
- https://github.com/MarvinParanoid/VolvoDiagToolkit/blob/main/docs/volvo-protocol.md

## What changed

Only emulator/tests/virtualcar_test.c was modified. A new host test function injects two deliberately synthetic D2 fixture structures *in test memory only*, without exporting, packaging or persisting them:
- CEM_40/B9F0: one CAN D2 frame with a structurally correct 0xCC length and trivial synthetic marker (NOT an OEM part number);
- CEM_40/B9FB: three CAN D2 frames with 8F/09/4C markers and meaningless test bytes (NOT a VIN or vehicle information).

The test saves and restores global fixtures 0, 1, 4 and the strict routing/filter/spacing settings, opens only in-memory host J2534 CAN channels, and verifies eight independent gates:

1. Strict filters with no PASS filter drop a D2 response.
2. With odd 29-bit CAN ID pass mask/pattern=1, synthetic B9F0 single frame reaches native PassThruReadMsgs on 125 kbps.
3. Synthetic B9FB three-frame stream reaches native PassThruReadMsgs in order.
4. The same CEM_40 requests on 500 kbps are rejected by strict routing.
5. An even response CAN ID is dropped by odd-ID receive filter.
6. A newer B9F0 request supersedes unread staged B9FB on the same channel.
7. B9FC stays without fixture and cannot manufacture a configuration record.
8. AE1B stays without response, whether or not the separate observer PR #346 eventually merges.

No fake vehicle identification is emitted by the distributed DLL. The test is not a procedure for connecting to a real CEM. It does not prove correct OEM response bytes, ECU identity, VIDA acceptance, actual VIDA process binding, or physical DiCE/J2534.

## Run on owner-controlled Windows source checkout

From the repository root, with clang available:

~~~powershell
clang -std=c11 -O2 -Wall -Wextra -D_CRT_SECURE_NO_WARNINGS -o "$env:TEMP\b3a145-virtualcar-host-tests.exe" emulator/tests/virtualcar_test.c emulator/src/p2core/p2_cem_router.c emulator/src/p2core/p2_ls_observer.c emulator/src/p2core/p2_vehicle_core.c emulator/src/p2core/p2_j2534_bridge.c
& "$env:TEMP\b3a145-virtualcar-host-tests.exe"
~~~

The existing self-hosted VM workflow uses this exact host test source with the same core .c dependencies. Capture the exact output marker "PASS B3A145 CEM_40: 8 synthetic transport-only host cases", process exit 0, and the exact commit SHA, not just a historical success on development.

## Acceptance boundary

- New host test cases: CODE ADDED. Execution needs native toolchain/runner and is NOT VERIFIED by PR creation.
- The active B3A135D INI/DLL has NOT been modified and remains CEM_40/B9F0=0, B9FB=0.
- Network Update screen CEM "Not responding" remains the last owner-provided original VIDA observation.
- Future genuine/synthetic-private CEM_40 profile must be separately approved, preserve VIN privacy and trace provenance, and pass actual original VIDA acceptance gates.
