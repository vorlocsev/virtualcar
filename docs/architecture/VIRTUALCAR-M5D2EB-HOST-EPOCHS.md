# M5D-2eB: owner-only repeated Host epochs (synthetic Windows integration)

This is the **second**, process-level part of M5D-2eB after PR #125's
isolated Ledger races. All diagnostic bytes are invented VCRF fixtures.
It does **not** exercise physical CAN, Volvo, SectorV, VIDA, J2534
PassThru DLL data plane, programming, PINs, or security access.

## Single native client, four independently launched C# Hosts

An owner-only VMware test creates a unique per-architecture pipe and marker
directory under RUNNER_TEMP. A retained native C++ session object survives
three sequential Host losses and performs final recovery on the fourth:

1. Host #0 authenticates and accepts a synthetic F187 read, writes
   \`round-0.ready\`; orchestrator kills **its own Process handle**.
2. Client receives a disconnected/I/O-error/timeout result, confirms no
   bytes, no ledger entries, no channels and no active session, then writes
   \`round-0.revoked\`.
3. Host #1 repeats an accepted F187 read, writes \`round-1.ready\`.
   Native client invokes its own cooperative cancellation (without a Host
   kill). It must observe precisely \`cancelled\` and complete cleanup
   before writing \`round-1.revoked\`. Host #1 exits normally.
4. Host #2 accepts an F187 read, writes \`round-2.ready\`; orchestrator
   kills its own process and waits for the same fail-closed cleanup.
5. Host #3 is new and healthy. Native client verifies the numerically
   reused test session/generation is paired with a **different creation
   FILETIME**, old channel IDs cannot be reused and the fresh synthetic
   F187 read returns only canonical invented bytes \`AB\`. GOODBYE must
   cleanly remove the last session.

Each Host PID originates from the exact retained Process object and is
communicated by a one-use marker. The native client requires the prior
revocation marker to be written *after* each pending read resolves.
All marker paths use a unique directory, and it is cleaned in \`finally\`.

## Verification and limits

- Execute **both x86 and x64** clients with the same .NET 10 Host on the
  trusted Windows VMware runner.
- Require exit code zero from each native client and the cooperative/final
  Host; killed Hosts must actually terminate. The runner must fail on
  missing timeouts, markers, executables, or cleanup.
- Keep existing 8/8 CTest per architecture, M5D-2eA five fault gates,
  64 serial synthetic reads, C# Host 17/17, Python 252 and C/Go/.NET
  checks intact.
- Negative and positive Host replies are *synthetic only*.
  This test cannot establish real XC90 MY2009 identification or any
  physical J2534/DiCE behavior.
- All workflow artifacts, releases and adapter registration stay disabled.

**Status:** source branch pending owner-only VMware validation. This is
not a claim of execution or success until its exact source SHA, x86/x64
native markers and Actions conclusion are verified.
