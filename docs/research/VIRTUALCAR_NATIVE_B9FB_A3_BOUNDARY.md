# Native Windows x86 boundary: synthetic B9FB delivery then unanswered A3

Date: 2026-11-03. Branch research/vdash-functional-keepalive,
draft PR #39. The program under test is the actual Windows x86
VirtualCarJ2534.dll, **not SectorV/VDASH**, not a physical DiCE and
not a real XC90 V8 MY2009 CEM. VMware is not involved.

## Why this additional check was needed

Existing native verify_native_routes.ps1 checks missing B9FB fixture
and zero RX for an unsupported profile. Host C tests do validate
13-frame B9FB queues and separately test A3 no-response metadata,
but those are not a single native x86 J2534 session with the
B9FB-to-A3 boundary.

The historical private PR30 SectorV run reported a completed
13/13 B9FB read and later A3 on CEM 50 and CEM 40 with no RX.
The exact client acceptance condition and delay from the final
B9FB RX to A3 TX remain unverified without the original single-run
client/native trace. This test intentionally does **not** assert
either a real-client time gap or OEM Hardware completion.

## Implementation

- emulator/tools/verify_native_b9fb_a3.ps1: isolated Windows
  PowerShell x86 runner using J2534 P/Invoke.
- emulator/tools/verify_native_b9fb_a3.py: strict metadata-only
  verifier reusing audit_backend_evidence.py.
- emulator/tests/test_verify_native_b9fb_a3.py: eight synthetic
  failure-injection cases.
- .github/workflows/emulator.yml: after the existing native route
  test, run this test on Windows x86 DLL and upload *only* a
  privacy-safe audit JSON.

The runner creates a fresh isolated directory and never modifies
Windows registry, installed J2534 drivers, actual vehicle profiles
or the native runner's other isolated test. Its temporary
configuration declares B9FB CEM50 response ID 0x01200003 and
13 D2 frames with the standard D2 control-byte sequence. The
frame body is **synthetic zero-filled data**; it contains no VIN
or authenticated model/software/hardware number. It is valid
for the simulator's D2 framing gate, not for real vehicle identity.

## Eight native gates

1. 32-bit process/ABI, expected PassThru exports.
2. HS 500k + LS 125k J2534 channel setup.
3. B9FB request TX accepted by native x86 WriteMsgs on CEM50.
4. Exactly 13 sequential CAN RX records delivered with correct
   29-bit response ID, D2 control bytes, data sizes and RX flags.
5. No additional HS data and no leakage into LS after B9FB.
6. A3 CEM50 accepted by WriteMsgs, then ReadMsgs times out;
   no synthetic E3 reply is produced.
7. A3 CEM40 on LS likewise times out with no E3 reply.
8. A3 CEM40 sent on HS and an unconfigured B9FB CEM40
   remain silent; independent backend analysis distinguishes
   unsupported_bus from missing_profile.

The backend verifier checks one synthetic session, **exactly five**
ordered client J2534 writes, 13 queued + 13 dequeued B9FB frames,
no drops, four subsequent no-RX transactions, and exact service,
target, protocol/baud/channel and terminal reason. An extra
response, missing frame, mismatched bus, wrong route, changed
classification, truncated log or invalid JSON fails closed.

## Interpretation limits

- "Delivered" means the virtual DLL returned CAN frames through
  J2534 PassThruReadMsgs. It does NOT mean SectorV parsed/accepted
  the VIN or identified any ECU.
- ReadMsgs timeout after A3 is an expected outcome of the
  deliberately incomplete emulator, not proof that the real
  hardware procedure times out after that exact duration.
- No E3 response, security handshake, PIN, key, protected-memory
  access, coding, ECU writing or programming is implemented.
- Native source timestamps cannot be joined to the missing
  PR30 client raw-log timeline. No 500-1000 ms inference for
  the historical run is made.
- No physical J2534 or VMware tests were performed; CI passing
  verifies only the isolated synthetic Windows x86 scenario.

The existing zero-fixture native audit remains unchanged. PR #39
stays Draft and no Virtual Car release is published.
