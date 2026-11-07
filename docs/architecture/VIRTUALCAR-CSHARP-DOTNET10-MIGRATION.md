# Virtual Car C# rewrite | ADR VC-CSHARP-001

> **Historical alternative (Native AOT): superseded for critical layers.**
> The user's later explicit choice is native **C++20** for J2534 and
> timing-critical CAN/ISO15765/ISO-TP, while C#/.NET10 stays the managed
> core/storage/service/UI. The Native AOT x86/x64 PassThru DLL from PR #70
> is a nonfunctional experimental ABI canary, not the production adapter.
> Current decision: [ADR VC-002](VIRTUALCAR-CSHARP-CPP-MIGRATION.md).
> M0 PR #71 and M1 PR #72 have merged and passed CI; M2 is next.
> This older document remains as an architectural experiment record.


Status: ACCEPTED direction, implementation **IN PROGRESS**.
Date: 2026-11-06. Priority: **Dvinholm** first, Virtual Car is a lab.

## Decision

Migrate Virtual Car to **C# / .NET 10** for the emulator core, CAN/ISO-TP,
Volvo D2 read-only ECUs, control service, SQLite repository, test runner,
WinUI 3 desktop control and, if the J2534 ABI lifetime tests allow,
a Native AOT x86/x64 PassThru DLL.

Historical C (native x86 DLL), Go (old control UI and labcore) and Python
(read-only evidence audits) remain as the validated regression baseline.
Do not remove, overwrite, ship or publish the new implementation until all
relevant gates pass. The request to migrate does not certify the result.

## Native J2534 feasibility and limits

Microsoft currently documents:
- Native AOT supported on Windows x86 and x64 since .NET 9.
  https://learn.microsoft.com/dotnet/core/deploying/native-aot/
- Class libraries can publish as native shared libraries and export static
  [UnmanagedCallersOnly(EntryPoint=...)] functions, all parameters blittable.
  https://learn.microsoft.com/dotnet/core/deploying/native-aot/libraries
- Native AOT libraries **do not support unloading** by FreeLibrary.
  This is a potential incompatibility with third-party J2534 clients:
  https://learn.microsoft.com/dotnet/core/deploying/native-aot/libraries

The 14 PassThru.04.04 entrypoints need **undecorated** exports,
x86 stdcall ABI (x64 Windows calling convention), fixed-width unsigned 32-bit
values, exact PassThruMsg layout, no garbage collector pointers across ABI,
bounded RX/TX queues, thread-safe callbacks and real timeout semantics.

**The initial Native AOT DLL is just an ABI canary**:
dotnet/src/VirtualCar.J2534.AbiProbe. Every export returns
ERR_NOT_SUPPORTED, never opens a channel or returns a fake ECU reply.
It must not be installed or registered under PassThruSupport.04.04.
The matching-bitwidth test process deliberately does NOT FreeLibrary.
It proves export/load/stack correctness only if CI passes, **not** general
client compatibility with DLL unloading.

Potential fallback if Native AOT loader/lifetime parity fails: a minimal
native C ABI stub for legacy clients, with all simulator logic in C#.
This would be a narrowly documented exception, not rewriting the core
back into C. The user decision about all-C# remains the target.

## Target topology (after migration)

    Dvinholm x64  .NET 10 WinUI 3
           |
           +---- normal J2534 PassThru API ----> VirtualCar.J2534 x64
                                                  (C# Native AOT)
                                                 |
     legacy x86 diagnostics -> J2534 x86 -------+--- Named Pipe data
                                                     |
                                             VirtualCar.Host
                                           (.NET 10 x64, C#)
                                                     |
                                           VirtualCar.Core
                                        (C# state machine/timing)
                                          /       |         \
                                  CAN fabric   ECU models   Fault engine
                                                   |
                                               scenarios
                                                   |
                                          VirtualCar.Storage
                                      (Microsoft.Data.Sqlite)
                                                   |
                                       encrypted private artifacts

     VirtualCar.Control (WinUI 3 C#) ---- Named Pipe control ---- Host
     VirtualCar.Tests (C#) -> native ABI, scenarios, real Dvinholm E2E

Do not share a SQLite connection with J2534 DLLs or query SQLite per frame.
Only Host opens DB; compile scenarios to immutable versioned read-only
snapshots and SHA-256 validate materialized bytes before activation.
A database digest alone is NOT authorization to replay CAN.

## Migration sequence (supersedes Go 60B-2 work)

| Stage | Result | Exit conditions |
| --- | --- | --- |
| CS-01 | .NET 10 Core + Native AOT ABI probe | 8 core guards, x86/x64 exports and load proven in CI |
| CS-02 | C# SQLite repository | pinned Microsoft.Data.Sqlite, schema v1 migration/checksum, WAL, backups, private source guard, 8 tests |
| CS-03 | C# CAN/ISO-TP runtime | same RX/TX/frame/FC behavior as C reference, independent bus speeds, queues and timeouts |
| CS-04 | C# Volvo D2/ECU/scenario engine | evidence-scoped CEM/ECM, revision isolation, immutable fixtures, fault injection, 8 tests |
| CS-05 | .NET 10 Host and secured local IPC | per-user ACL, control/data pipe separation, bounds, deadlines, reconnection, replay prevention |
| CS-06 | Complete x86/x64 J2534 Native AOT implementation | all 14 functions with tested 04.04 structures/filters/ISO15765; native unload issue and client compatibility documented |
| CS-07 | WinUI 3 control panel | profile/ECU editor, scenario start/stop, CAN Monitor, logs and RU/EN UI |
| CS-08 | Dvinholm E2E | Dvinholm actual J2534 DLL loader x64, read-only DID, monitor, fault/reconnect, snapshot, no production writes |
| CS-09 | Retire legacy only after parity | tests for x86 legacy and x64 Dvinholm, Windows manual/VMware, no successful failures hidden |

The former Go 60B-2 path is **SUPERSEDED, NOT COMPLETED**.
Older Go/C modules remain in tree as read-only regression references
until C# parity, not as required runtime dependencies of target design.

## Stage CS-01 actually added

- dotnet/src/VirtualCar.Core: independent C# lab controller with immutable
  SHA-256 checked snapshot bytes (not just metadata), session generations,
  explicit cancellation and fail-closed replace/reset/dispose.
- dotnet/tests/VirtualCar.Core.Smoke: eight deterministic synthetic checks,
  no test NuGet dependency or real ECU.
- dotnet/src/VirtualCar.J2534.AbiProbe: non-functional Native AOT ABI DLL
  with 14 named PassThru exports; zeroes returned handles and fails closed.
- dotnet/tests/VirtualCar.J2534.AbiSmoke: matching-process 32/64-bit loader,
  exact GetProcAddress names and stdcall invocation without FreeLibrary.
- .github/workflows/csharp-migration.yml: isolated .NET 10 core and
  win-x86/win-x64 AOT compatibility gates, **no artifact distribution**.

CI is the authority for compiled/binary status, not this design document.
Do not claim these builds or Windows loaders passed until actual runs confirm.

## Provenance / security requirements

- Dvinholm product **must never depend on Virtual Car at runtime**.
- No private VIN, PIN, EEPROM, donor logs or original VIDA XML in repo.
- Synthetic data are labeled and cannot prove XC90 V8 MY2009 identity.
- Read-only path only. No programming, PIN extraction, security access,
  immobilizer, vehicle key operations, or real ECU writing.
- Unverified A3/A6/B9F0/D2 response layouts remain OFF.
- Never publish Virtual Car releases without explicit separate authorization.

## Next chat continuation

User can write exactly: **virtual car**.
Read development/docs/progress/CURRENT.md and this ADR, verify PR/CI, and
continue the next incomplete C# migration stage rather than returning to Go.
