# ADR VC-002: Virtual Car migration to C#/.NET 10 and native C++20

Status: APPROVED BY USER (2026-11-06); implementation is incremental.
Primary product: Dvinholm. Virtual Car is an independent test laboratory.
This ADR supersedes the *technology choice* in prior Go-core roadmaps; it
does not rewrite recorded historical PR/CI results.

## Final stack

| Layer | Technology | Responsibilities |
| --- | --- | --- |
| Dvinholm client | Existing WinUI 3 / .NET 10, target Windows x64 | Normal production J2534 API, no test-only dependency |
| VirtualCar.J2534.Native | Native C++20 DLLs, separate x86 and x64 builds | Exact PassThru 04.04 ABI/exports, channels, filters, bounded queues, timeouts, flow-control metadata, lifecycle |
| VirtualCar.Transport.Native | Native C++20 | Critical hot-path CAN, ISO15765 / ISO-TP, monotonic scheduler, bounded frame dispatch; measured parity with existing C code |
| VirtualCar.Core | C# / .NET 10 | Scenario activation, session generations, ECU graph, fault-injection control, test scheduling and immutable scenario snapshots |
| VirtualCar.Storage | C# / Microsoft.Data.Sqlite 10.0.14 | Single-writer SQLite repository, scenario revisions, provenance, test runs, backups |
| VirtualCar.Service | C# / .NET 10 self-contained Windows x64 | Local Named Pipe data/control endpoints, lifecycle, event aggregation |
| VirtualCar.Control | C# / WinUI 3 | Private RU/EN lab profiles, ECU editor, scenario editor, test results |
| VirtualCar.Tests | C#/.NET + native C++ test executable | 6-8 groups per stage, native J2534 ABI, deterministic offline replay |

Dvinholm must not link against Virtual Car assemblies; its only integration
contract is the industry-standard native J2534 DLL. A Windows x86 client
cannot load a Windows x64 DLL: two separate C++ binaries must connect to
one x64 .NET headless test service through local IPC. Do not use C++/CLI.

## IPC boundary

Local-only Windows Named Pipes with explicit current-user/security ACL.
Separate control and J2534 data pipes. Authenticated session/generation IDs
in every event. Bounded frame and message lengths, bounded RX queues,
monotonic clocks, timeouts, filtering and cancellation.
No network listener, no database calls in the CAN hot path. Native client
must not request scenario swaps or test-run administration.

## Source-of-truth and preservation

- Existing emulator/src/ C x86 J2534 DLL and emulator/control Go GUI are
  kept as the baseline until **parity has been independently measured**.
- Existing emulator/schema/0001_lab_catalog.sql remains SQLite v1 source
  of truth. C# storage must migrate/verify it, not invent a new schema.
- Existing Go labcore/sqlite and Python analysis tools remain as legacy
  reference code; Go is not a dependency of the future .NET distribution.
- Original research tools, VIDA/ECU evidence notes and tests are kept.
  Do not translate them into newly asserted MY2009 ECU compatibility.
- No virtual-car public releases, no real vehicle programming, Security
  Access, PIN retrieval, immobilizer changes, or private data commits.
- Baseline: old Windows x86 J2534 behavior and CI #604 / VMware package
  #438 (prior to migration); these do NOT prove actual x64 DLL function.

## Revised work breakdown

M0 (this PR): C# .NET 10 pure lifecycle core and 8 tests; C++20
    ABI header and compile-time test, new isolated .NET/C++ CI. No
    existing J2534 binaries or runtime source changed.
M1: C# SQLite catalog using Microsoft.Data.Sqlite v10.0.14 and original
    SQL v1 schema. Explicit version/checksum, WAL, foreign keys,
    transactional migration, secure backup, no automatic overwrite.
M2: C# immutable scenario compiler: canonical bytes/SHA-256,
    verified route and source evidence, no fabricated positive CEM.
M3: C++ x86/x64 J2534 native DLL skeleton with actual 14 exports and
    fail-closed PassThru behavior, ABI/loader tests in both bitnesses.
M4: C++ native CAN/ISO15765/ISO-TP and J2534 filter/FC/timing parity
    against existing reference C host and real Windows x86 J2534 tests.
M5: C# Windows headless service + secure two-pipe IPC, bounded queues,
    generation reset, timeout, crash recovery and fault injection.
M6: C# WinUI 3 lab UI (separate from Dvinholm), scenario editor, RU/EN,
    test history, provenance, no Settings dependency on Dvinholm.
M7: Full Dvinholm x64 J2534 E2E through C++ PE32+ DLL, cross-check old
    x86 clients, read-only snapshot/DID/ECU scenarios and Windows GUI.
M8: Retire Go/C implementation ONLY when parity matrix and real
    Windows client acceptance are green and explicitly reviewed.

Every stage requires:
- 6-8 distinct synthetic/ABI automated gates,
- a focused PR on Virtual Car development,
- green new and existing CI; x64 test evidence separately identified,
- an updated docs/progress/CURRENT.md and this ADR,
- no published Virtual Car release.

## Stage M0 acceptance gates

1. Core cannot open a session before scenario activation.
2. Source is strictly synthetic and read-only; no real ECU permissions.
3. Snapshot SHA-256 is calculated from actual bytes and rechecked.
4. Scenario switch/reset blocked while sessions are active.
5. Stale session tokens are rejected after reset/replacement.
6. Cancellation or preparation error leaves no active scenario.
7. Bounded session count and concurrency-safe lifecycle.
8. Stop/shutdown invalidates sessions even when native runtime faults.

Native C++ ABI checks independently validate: J2534 data structure
layout, 32-bit message fields, exported call signature types and
endianness-independent exact field sizes. This does NOT yet build a
working J2534 C++ DLL or prove its real Windows loading.

## Next-chat trigger

The phrase **virtual car** means: read
  emulator/../docs/progress/CURRENT.md,
  docs/architecture/VIRTUALCAR-CSHARP-CPP-MIGRATION.md
and the current branch/pr/CI; continue the first incomplete C#/C++
migration milestone. Dvinholm remains the primary product.
