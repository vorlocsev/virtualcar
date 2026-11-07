# DVINHOLM / VIRTUAL CAR LAB | DEVELOPMENT ROADMAP

## Technology migration decision (2026-11-06): C#/.NET 10 + C++20

The user has selected **C#** for all managed Virtual Car components and
**C++20** for native J2534 and latency-critical CAN/ISO15765/ISO-TP.
This REPLACES the future Go-based roadmap from stage 61 onward.
Historical completed stages 60A/60B remain valid baseline evidence,
not requirements for the new architecture.

| New stage | Scope | Status |
| --- | --- | --- |
| M0 | .NET10 C# core, 8 tests, C++ ABI and isolated CI | COMPLETED, PR #71, CI #1 |
| M1 | Microsoft.Data.Sqlite / SQLite v1 migration with rollback | COMPLETED, PR #72, CI #4 |
| M2 | Canonical immutable scenario compiler, evidence gates | COMPLETED, PR #75, CI #6 |
| M3 | C++20 native x86/x64 J2534 ABI DLLs, 14 fail-closed exports | COMPLETED, PR #77, CI #10 |
| M4A | Isolated C++ CAN/ISO-TP FIFO, FC and STmin deterministic engine | COMPLETED, PR #79, CI #13 |
| M4B-1 | J2534 ISO15765 RX metadata, atomic two-entry queue, 8 ECU routes | COMPLETED, PR #81, CI #15 |
| M4B-2 | Executed x86 old C DLL vs C++ RX module, 8 synthetic trace gates | COMPLETED, PR #83, CI #638 |
| M5 | C# Host + secure Named Pipes + native C++ client | M5A/M5B/M5C-1 complete; M5C-2 PR #96 merged as 7bde901, private VMware feature #42339519459 and post-merge #42339851382 SUCCESS, native x86/x64 6/6 CTest and Host-loss/restart PASS; J2534 data plane disabled |
| M5D | Authenticated read-only synthetic CAN/ISO15765 control/data contract, bounded routing and fail-closed J2534 bridge | M5D-1/2a/2b/2c merged, post-merge VMware #42368227332 PASS (Win32/x64); M5D-2d on feature branch adds 3 deterministic Ledger replay/deadline/epoch gates (11/11 target) and native 64-request serial C++ ↔ C# stress on both x86/x64, private CI PENDING. J2534 DLL still fail-closed, no physical vehicle I/O |
| M6 | C# WinUI3 private control UI, RU/EN, test results | PLANNED |
| M7 | Dvinholm x64 native J2534 E2E + x86 client coexistence | PLANNED |
| M8 | Retire legacy Go/C ONLY after verified behavioral parity | PLANNED |

Completed source and CI evidence:
- M0: PR #71 merged b4b70f41, C#/.NET10/C++20 CI #1 passed.
- M1: PR #72 merged e11a15d4, C#/.NET10/C++20 CI #4,
  x86 J2534 #612 and VMware LAB packaging #441 passed.
- M2: PR #75 merged 0487fc1a, managed CI #6, emulator x86 #619,
  VMware LAB packaging #442 all SUCCESS. Real C# SQLite-to-scenario
  compiler, eight synthetic tests, no physical/client test.
- M3: PR #77 merged e835fd67. Windows PE32 x86 and PE32+ x64
  native C++20 J2534 DLL build, exact 14 undecorated exports, 8 per-arch
  ABI/error gates. Managed native CI #10, legacy x86 #624, VMware LAB
  packaging #445 all SUCCESS. This is a fail-closed ABI binary,
  not a functioning transport or approved physical J2534 adapter.
- M4A: PR #79 merged 3719f58b. Bounded native C++20 CAN/ISO-TP
  library tested in Win32/x64 and Linux with eight offline groups.
  Managed CI #13, legacy x86 J2534 CI #628 and VMware LAB #447
  SUCCESS. **No functional J2534 DLL integration yet**. M4B next.
- M4B-1: PR #81 merged 1786b33e. New isolated C++ J2534
  ISO15765 RX framing, exact legacy SOURCE-DERIVED metadata,
  8 synthetic multi-ECU and atomic queue tests on Linux/Win32/x64.
  C# + C++ CI #15, legacy x86 emulator #631, VMware packaging
  #448 SUCCESS. No live old/new DLL black-box parity yet.
- M4B-2: PR #83 merged 49f616f3. Independently built real C x86 DLL
  versus compiled C++20 Iso15765Rx test module with eight identical
  synthetic ISO15765 F187/F189 cases; compare all RX J2534 fields and
  bytes except dynamic timestamps. Actual x86 CI #638, managed
  migration CI #21 and VMware LAB packaging #453 SUCCESS. NOT a
  functional new C++ J2534 DLL or full original-client acceptance.
- M5A: PR #85 merged to development as 410ade408, Windows local IPC
  9/9 on private VMware #42314429323 and #42318278748.
- M5B: PR #87 source head 053e60e; private VMware #42318278748
  SUCCESS. Native C++ x86/x64 each 4/4 CTest (including 8 M5B gates),
  both architectures' wrong-server-PID and authenticated C++ ↔ C#
  HELLO/KEEPALIVE/GOODBYE checks PASS. No DLL integration or release.
- M5B CI fix: PR #89 merged to main as 84f12eb, retained .NET
  Process handle yields real Windows PowerShell 5.1 host ExitCode.
- M5C-1: PR #90 exact native source SHA 89553e3, private
  VMware #42319530476 SUCCESS, x86 5/5 and x64 5/5 CTest;
  `m5c1_bounded_session_lifecycle_8_groups` PASSED in each.
  The library remains isolated from the J2534 DLL, no data plane.
- GitHub-hosted 2-4 second failed jobs around PR #90 had no executed
  steps and no downloadable job logs; they do not establish M5C-1
  compile/test failures. Runner/account scheduling root cause unverified.
- Experimental prior Native AOT ABI probe PR #70 is nonfunctional
  and is not the user-selected C++20 production DLL.

Detailed decision: docs/architecture/VIRTUALCAR-CSHARP-CPP-MIGRATION.md.
Keep existing C/Go working until cross-language regression tests pass.
**virtual car** remains the exact cross-chat resume phrase.


Updated: 2026-11-07. Primary product: Dvinholm. Laboratory: Virtual Car.
Persistent source of truth: this repository, GitHub pull requests, CI run results.
Do not depend on ChatGPT chat memory to determine whether a task is completed.

## Governance

- Dvinholm is the deliverable: WinUI 3 / .NET 10 self-contained Windows x64,
  priority CEM PIN, CEM configuration, ECU identification and diagnostics.
- Virtual Car is a test-only independent lab; it must be optional and NEVER
  required at Dvinholm runtime.
- Virtual Car standalone release publication prohibited unless user explicitly
  changes this rule. CI artifacts are NOT published releases.
- Base work on Virtual Car development; do not modify the main/default or
  production Dvinholm Stable without a separately verified PR.
- Do not reuse anonymous synthetic or another-vehicle D2 frames as authentic
  Volvo XC90 V8 MY2009 identity/configuration evidence.
- Experimental J2534 and CAN tests are read-only: no programming, PIN secrets,
  Security Access, immobilizer work or physical hardware writes.
- 6-8 independent automated checks per stage and distinguish automated CI,
  Windows manual acceptance, and physical J2534 on actual vehicle.
- Stage progress changes ONLY when a commit/PR/CI observation backs it.

## Existing verified baseline

- Virtual Car stage47 PR #55: VIDA identity entrypoints IL boundary, merged.
- Stage48 PR #56: safe XML script audit, merged; CI #566 passed.
- Stage49 PR #57: ScriptProfileMap linkage audit, merged; CI #571 passed.
- Stage50 PR #58: ScriptProvider GetScript/Fetched/Running chronology audit,
  merged; CI #573 passed.
- Lab architecture PR #59: merged to development at e51c3397;
  Go labcore lifecycle, inert SQLite v1 schema, eight Go and eight Python
  schema test groups; Virtual Car Windows x86 CI #577 SUCCESS.
- Dvinholm PR #702: separate ongoing x64 WinUI migration; its existence
  is not proof of a public x64 release.
- Dvinholm PR #703: merged Dvinholm-first lab contract documentation
  to main as 558f816d, head CI #5151 SUCCESS.
- Virtual Car stage60A PR #62: merged to development as 73c4f375.
  The final Windows x86 CI #587 and VMware LAB #426 SUCCESS.
  Standard-library Python SQLite offline catalog, explicit migration
  checksum, no implicit schema creation/upgrades, eight synthetic tests.
- Stage60B-1 PR #66: merged at 0d0ecdea, x86 CI #598 SUCCESS.
- Stage60B-2 PR #68: merged at 4942fb41, x86 CI #604 SUCCESS,
  VMware LAB packaging #438 SUCCESS. Pinned pure-Go SQLite v1.36.3,
  WAL backup, 8 real SQLite tests, Windows x64 no-CGO build smoke.
  Conflicted earlier PR #65 closed as superseded without overwrite.
- No confirmed actual VIDA 2015A or SectorV identification of target
  XC90 V8 MY2009, no physical J2534 test, no approved release publication.

## Implementation stages

| Stage | Goal | Required gates | State |
| --- | --- | --- | --- |
| 60A | SQLite offline catalog | explicit init, checksum, migration rejection, integrity, FK, rollback, bounded metadata, symlink safety | COMPLETED, PR #62, CI #587 |
| 60B-1 | Go SQL metadata boundary | injected driver, checksum/integrity/FK checks, safe bounded metadata, eight synthetic tests | COMPLETED, PR #66, CI #598 |
| 60B-2 | Real Go SQLite driver | pinned modernc and checksums, WAL backup, migrations, bounded queries, real SQLite tests, Windows x64 build | COMPLETED, PR #68, CI #604 |
| 61 | Scenario Compiler | exactly sourced fixtures, canonical serialization, SHA-256, sealed revision, refusal on missing evidence, bus/ECU isolation, reproducible replay, read-only policy | PLANNED |
| 62 | Go Headless Core | lifecycle, CPU/timing, queues, no SQL in RX, reset, faults, stale session rejection, cancellation, recovery | PLANNED |
| 63 | IPC control/data | Windows SID ACL, version negotiation, x86/x64, length caps, deadline, disconnect recovery, invalid IDs, event isolation | PLANNED |
| 64 | J2534 x64 adapter | 14 exports, PE32+/ABI, CAN/ISO15765, filters, FC/STmin, timeouts, reconnect, x86 coexistence | PLANNED |
| 65 | Dvinholm native E2E | real x64 DLL load, monitor+UDS, positive synthetic DID, missing fixture, cancellation, snapshots, fault injection, evidence report | PLANNED |
| 66 | Lab Control UI | profiles, ECU catalog, scenario revision, start/stop, fault scenarios, test history, RU/EN, privacy | PLANNED |
| 67 | Evidence-scoped P2 | real diagnostic traces, B9FB/B9F0 provenance, identity script, VIN validation, profile resolution, ECU inventory, missing-data fail-closed, Windows acceptance | RESEARCH BLOCKED |

## Active next gate: stage 61 scenario compiler

- Stage 60A, 60B-1 and 60B-2 are merged and CI-verified.
- Current Go SQLite repository is metadata-only; no response fixture
  becomes authorized from a DB hash alone.
- Design deterministic canonical encoding for scenario snapshots
  incorporating profile revision, bus/ECU routing, fixture provenance
  and exact request/response bytes.
- Independently SHA-256 verify compiled snapshot content before labcore
  may activate synthetic, read-only ECU replies.
- Reject missing, conflicting, research-only, unknown or unsupported
  XC90 P2/CEM evidence rather than fabricating responses.
- Add 6-8 synthetic tests plus Windows x86 J2534 regression; x64
  native DLL and Dvinholm E2E remain later milestones.
- No standalone Virtual Car release or physical support claims.

## 2026-11-06: All-C# migration decision SUPERSEDES future Go phases

The user has selected C#/.NET 10 for the entire new Virtual Car lab:
core, CAN/ISO-TP, Volvo D2/ECU, scenarios, SQLite, IPC, WinUI 3 and
Native AOT J2534 x86/x64 when ABI/lifetime compatible.
Historical Go 60B-2 was completed (PR #68, CI #604). Future Go stage 61+
work is superseded, not completed. Keep old C/Go in source as parity
reference until native Dvinholm tests have passed.

Detailed staged architecture:
docs/architecture/VIRTUALCAR-CSHARP-DOTNET10-MIGRATION.md

| C# stage | Goal | State |
| --- | --- | --- |
| CS-01 | C# Core and 8 synthetic gates; native AOT 14 exports on x86/x64 | PR #70 / CI pending |
| CS-02 | C# Microsoft.Data.Sqlite repository + migrations/backups | PLANNED |
| CS-03 | C# CAN/ISO-TP parity | PLANNED |
| CS-04 | C# D2 and ECU/scenario compiler | PLANNED |
| CS-05 | .NET10 Host and named-pipe control/data channels | PLANNED |
| CS-06 | Functional C# Native AOT J2534 DLL x86/x64 | PLANNED |
| CS-07 | C# WinUI 3 Test Lab Control UI | PLANNED |
| CS-08 | Dvinholm native J2534 E2E acceptance | PLANNED |
| CS-09 | Retire C/Go ONLY after parity | PLANNED |

Do not register or distribute ABI-only probe. Native AOT DLL cannot be
unloaded with FreeLibrary, so legacy clients require separate verification.
Exact resume keyword remains **virtual car**.

## Cross-chat restoration procedure

1. Fetch this file from Virtual Car development branch.
2. Fetch docs/progress/CURRENT.md and its latest linked PR and CI.
3. Check the actual newest development commits and open PRs before acting.
4. Read Dvinholm docs/architecture/DVINHOLM-VIRTUALCAR-TESTLAB-ADR.md
   from its PR/merged branch; verify x64 PR #702 independently.
5. Work on the highest unfinished stage with 6-8 tests, create a PR.
6. Update CURRENT.md and this roadmap in the SAME PR with truthful
   outcome/CI facts. Only mark merged after GitHub confirms it.
7. Never claim background execution or future work was already completed.

## Ключевая фраза продолжения

**virtual car**

Эта короткая фраза заменяет прежний длинный запрос для возобновления
разработки между чатами. По ней следует прочитать из ветки development
файлы docs/progress/CURRENT.md и этот ROADMAP, подтвердить фактическое
состояние GitHub, выбрать следующий незавершённый этап, выполнить работу
с проверками и обновить точку продолжения.

Основной продукт: Dvinholm. Virtual Car только тестовая лаборатория,
никакой самостоятельной публикации релизов.
