# Virtual Car roadmap (updated after dev30)

## Baseline available in development
- User-supplied VirtualCarJ2534 source v0.3.6.6 under emulator/, with observation-only P2 Vehicle Core integration.
- J2534 READ128 compatibility fix and offline regression checks.
- Configurable emulator ECU profiles, B9FB/B9FC frame replay and 142-byte F106 fixture support.
- Passive 11/29-bit CAN observation tools, early P2 source research, and read-only SavvyCAN CSV statistics.
- Privately supplied donor profile **is not** part of the repository.

## Development priorities
1. P0: Verified CEM identification for XC90 V8 MY2009. Investigate A3, A6, B9F0 and P3/29-bit routes using trusted response captures. Preserve existing B9FB replay.
2. P0: Correct J2534 transport boundaries, channel/filter identity, read/write semantics, and READ128 real-world validation.
3. P1: Read-only ECU identification including VIN and ECU topology, with per-model profiles and provenance for each DID.
4. P1: Offline CAN-state model (Off/Sleepy/Awake/Active) using *synthetic* signals and explicit model-year gates; do not interpret status frames as D2 normal-mode confirmation.
5. P1: VMware end-to-end tests with a separate adapter installation; compare J2534 diagnostics to the previously verified DLL.
6. P2: Physical J2534 testing only after emulator-only milestones, with no programming/security operations.

## PR and release gates
- Every task: one focused feature/fix branch -> PR to development; normally 6–8 meaningful checks.
- GitHub Actions must pass on the PR HEAD SHA; distinguish unit tests from real VMware/device testing.
- development -> main PR #2 currently stays in draft until end-to-end evidence is provided.
- No Stable release or merge based solely on source compilation, synthetic VIN, lab fixtures, or assumed CEM positive responses.

See [workflow](CHAT_GITHUB_WORKFLOW_RU.md) and [provenance](PROVENANCE.md).
