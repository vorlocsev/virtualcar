# Virtual Car development roadmap

## Confirmed test scope (dev26)

- Compile Windows x86 J2534 tracing proxy and GUI from source.
- Verify 14 exports and unchanged forwarding of calls.
- Run C99 route/classification tests and Go tests/race/vet.
- Confirm CEM A3 shape detection, B9F0/B9FB classification, channel reuse and 500/125 kbit/s routing.

## Next gated milestones

1. Import the actual independently owned `VirtualCarJ2534.dll` sources (not available in current dataset), under `src/j2534/`, after a review for hard-coded personal and proprietary data.
2. Add tests for repeated connection, CAN ID routing, filters, read timeout behavior, 13-fragment B9FB regression and source-authenticity of A3/B9F0 responses.
3. Verify CEM identification and normal mode separately; do not fabricate E3/B9F0 messages.
4. Add read-only ECM GGD model if verified for XC90 V8 MY2009 and validate the VIN/ECU discovery workflow.
5. End-to-end Windows x86/VMware testing before release; later physical J2534 testing is explicitly out-of-scope for this milestone.
6. Publish only verified artifacts after successful CI. Trace-only commits on `main` may automatically publish **prereleases** tagged `trace-dev26-<12-character SHA>` with SHA-256 checksums. Such releases are NOT finished vehicle emulators; a Stable emulator release requires independently verified implementation, Windows GUI and virtual J2534 acceptance.

Each implementation stage should aim for 6–8 meaningful checks, not long chains of micro-fixes.
