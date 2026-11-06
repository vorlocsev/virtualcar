# CURRENT | Dvinholm / Virtual Car Lab

## ACTIVE checkpoint: C#/.NET 10 + C++20, M3 completed (2026-11-06)

**Primary product Dvinholm.** Virtual Car remains its private, optional,
read-only J2534 simulation laboratory. Do not publish Virtual Car releases.

Verified milestones:
- M0 PR #71 merged b4b70f41 (C# Core lifecycle, C++ ABI declarations),
  managed migration CI #1 SUCCESS.
- M1 PR #72 merged e11a15d4 (C# SQLite catalog/backup), CI #4 SUCCESS.
- M2 PR #75 merged 0487fc1a (synthetic read-only immutable scenario
  compiler), managed CI #6 and legacy native x86 CI #619 SUCCESS.
- M3 PR #77 merged **e835fd67a75670a3f26ebd370aab946015fd814e**.
  C++20 native DLLs built separately in Windows PE32 x86 and PE32+ x64;
  exact 14 undecorated J2534 v04.04 exports, x86 stdcall and x64 ABI.
  M3 Windows loader/PE audit and eight per-architecture fail-closed
  native test groups completed successfully.
  Final managed/native CI **#10 SUCCESS**; legacy x86 J2534 regression
  **#624 SUCCESS**, VMware LAB packaging **#445 SUCCESS**.
  Initial CI #8 failed from a C++ test/build signature mismatch: the
  third/fourth arguments of PassThruStartPeriodicMsg were corrected
  throughout header/export/tests; the final CI #10 is green.
- M3 implementation and test instructions:
  docs/architecture/VIRTUALCAR-CPP-J2534-M3.md.
- Previous Native AOT J2534 PR #70 is NONFUNCTIONAL experiment, not
  the selected C++ adapter implementation.

M3 DLL: emulator/native-cpp/src/j2534_fail_closed.cpp, CMakeLists.txt,
x86/x64 .DEF export maps, exact-bitness Windows tests and PE verification.
It **cannot open channels, transmit CAN frames or imitate hardware**.
The DLL is intentionally named VirtualCarJ2534Cpp.dll to avoid replacing
the current legacy VirtualCarJ2534.dll. It has NOT been registered under
PassThruSupport, released, uploaded as a new public artifact or used by
Dvinholm. All C/Go legacy source remains as the independent parity baseline.

**NEXT STAGE M4:** implement and verify bounded native C++ CAN and
ISO15765/ISO-TP transport/filters/flow-control state and timeouts.
Compare behavior with existing C x86 reference using 6-8 distinct gates,
include 11bit/29bit addressing, RX queue atomicity, FC, STmin/deadlines,
reset generation and no cross-ECU reply leakage. Keep this synthetic and
read-only. Do not fabricate Volvo P2 CEM diagnostic responses.
M5 then adds authenticated local Named Pipe IPC to C# headless service;
M7 is actual Dvinholm x64 loader/read-only E2E acceptance.

NOT VERIFIED: functional new C++ J2534 transport, local host IPC, WinUI lab
UI, Dvinholm x64 native end-to-end, real VIDA/SectorV XC90 MY2009 identity,
physical Volvo DiCE/J2534. Successful VMware packaging is NOT guest testing.

Canonical docs:
- docs/architecture/VIRTUALCAR-CSHARP-CPP-MIGRATION.md
- docs/architecture/VIRTUALCAR-CPP-J2534-M3.md
- docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md

**Exact continuation phrase: virtual car**

Verified checkpoint: 2026-11-06.
This document is the canonical cross-chat continuation note. Re-read the
current GitHub PR/CI state before changing code; do not rely only on chat memory.

## Product and rules

- Dvinholm is the MAIN application. Target: WinUI 3 .NET 10 self-contained
  x64. Priority: CEM PIN, CEM configuration, ECU inventory and diagnostics.
- Virtual Car is an OPTIONAL private J2534/ECU simulator for Dvinholm tests,
  not a competing production diagnostic application.
- Do not publish Virtual Car releases or enable writes/programming.
- Never use synthetic/donor XC90 data as proof of OEM compatibility.
- Distinguish synthetic offline CI from Windows GUI and physical DiCE tests.

## Verified work completed

- Virtual Car PR #59 (Go labcore skeleton and SQLite v1 schema):
  https://github.com/vorlocsev/virtualcar/pull/59
  MERGED to development as e51c3397d78ad99a86bd15ced856a22066865444.
  Windows x86 CI #577 and VMware LAB packaging #417 SUCCESS.
- Virtual Car PR #62 (Stage 60A and permanent roadmap):
  https://github.com/vorlocsev/virtualcar/pull/62
  MERGED to development as 73c4f375d5775ae3ed32ba3822158a97c8e3ed27.
  Windows x86 CI #587 and VMware LAB packaging #426 SUCCESS at
  head 8cb064d923875b69dd0d90749076a61a1caec049.
  Note: earlier CI #586 failed from a test placement NameError; corrected
  in the final merge. This is not a hidden remaining failure.
- Dvinholm PR #703: lab contract documentation MERGED to main at
  558f816d2b0a4d8ef9a1daf0cede8df1ab7e3d27, head CI #5151 SUCCESS.
  https://github.com/vorlocsev/dvinholm/pull/703
- Dvinholm x64 WinUI 3 migration PR #702 remains a separate workstream:
  https://github.com/vorlocsev/dvinholm/pull/702
  Verify current status before acting; no public x64 acceptance asserted.

- Virtual Car PR #66: stage 60B-1 Go database/sql metadata boundary,
  MERGED to development as 0d0ecdeaa63e483d8c2e80b70d187780916678b3.
  Windows x86 CI #598 and VMware LAB packaging #434 SUCCESS.
  Eight synthetic Go driver tests, no real SQLite Go driver and no runtime
  J2534 change. https://github.com/vorlocsev/virtualcar/pull/66

## Actual technical state

Implemented and tested:
- Go labcore skeleton with session generations, stop/reset/selection.
- SQLite metadata schema draft: emulator/schema/0001_lab_catalog.sql.
- Python standard-library development-time SQLite repository and CLI:
  emulator/tools/lab_sqlite_repository.py
  emulator/tools/lab_db_cli.py
  Eight synthetic tests: emulator/tests/test_lab_sqlite_repository.py.
- CLI supports explicit local init and privacy-safe aggregate health;
  refuses implicit creation, overwrite, unknown migration/corrupt DB.
- No private trace, VIN, PIN, EEPROM or VIDA XML committed.

NOT IMPLEMENTED:
- Go SQLite metadata integration is implemented and tested but has not
  been connected to running J2534/IPC/ECU engine.
- Existing Go database/sql boundary is metadata-only and cannot activate a scenario.
- Hash-verified compiled scenario snapshot and runtime fixture selection.
- Named Pipe IPC, headless Go service, actual x64 J2534 DLL.
- Dvinholm real native x64 J2534 end-to-end tests.
- Authorized live VIDA/SectorV identification of target XC90 MY2009.
- Physical J2534/vehicle testing.

## Stage 60B-2 COMPLETED | Real Go SQLite (PR #68)

- https://github.com/vorlocsev/virtualcar/pull/68
- MERGED to development: 4942fb412d85c9e6e4057a7ded44542cc72e86ce
- Final Windows x86 CI #604 SUCCESS (build + native routes).
- VMware LAB workflow #438 SUCCESS (packaging/synthetic tests,
  not a performed physical J2534 or actual VMware client run).
- New Go sqlite_driver.go uses modernc.org/sqlite v1.36.3,
  locked go.mod/go.sum, fixed local SQLite v1 schema, WAL,
  migration checksums, exclusive initialization, consistent
  VACUUM INTO backup and fail-closed corruption rejection.
- Reuses stage 60B-1 labdb.Repository; both sets of eight Go
  synthetic tests execute under CI. Windows x64 no-CGO Go
  cross-build passed, but no x64 native J2534 DLL exists.
- No scenario reply enabled: Snapshot.ApprovedReadOnly=false.
- Older PR #65 was CLOSED WITHOUT MERGE as superseded by #68.
  Its original CI #597 was successful but conflicted with
  merged parallel PRs #66 and #67. No forced overwrite performed.
- No real XC90 V8 MY2009 VIN/CEM/VIDA acceptance proven.

## NEXT STAGE: 61 Scenario Compiler

1. Create canonical, immutable scenario payloads from scoped approved
   fixture bindings and exact ECU/CAN routes.
2. Verify the SHA-256 of the entire materialized snapshot.
3. Refuse missing/research-only/ambiguous Volvo CEM evidence.
4. Add 6-8 deterministic tests and preserve J2534 native regressions.
5. Never publish Virtual Car; keep Dvinholm the primary product.

Canonical roadmap:
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md

## New priority (2026-11-06): full C# / .NET 10 migration

The user requested rewriting **all Virtual Car implementation in C#**.
This decision starts after the already completed Stage 60B-2 Go SQLite
PR #68 (merge 4942fb41, CI #604 success). Previous Go stage 60B-2 is
COMPLETED historically, but new Go Stage 61+ plans are SUPERSEDED.
Keep working C/Go as parity baseline, do not delete.

New migration ADR:
docs/architecture/VIRTUALCAR-CSHARP-DOTNET10-MIGRATION.md
New pilot: PR #70, branch feature/csharp-dotnet10-migration-foundation
(CS-01). Check latest head CI before claiming build success.
Introduced: .NET 10 C# lab controller, 8 synthetic C# tests, Native AOT
J2534 ABI-only 14-export probe and x86/x64 matching loader check.
The probe returns ERR_NOT_SUPPORTED and MUST NOT be registered or shipped.
No CAN simulation, full C# SQLite, physical J2534 or Dvinholm native
integration has been completed yet.

NEXT: complete CS-01 native x86/x64 CI, then CS-02 Microsoft.Data.Sqlite.
Keep Dvinholm primary and NEVER publish Virtual Car without permission.

## Короткая фраза для продолжения в новом чате

**virtual car**

Когда пользователь пишет только эту фразу, нужно восстановить контекст
проекта по этому файлу и
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md из ветки development
репозитория vorlocsev/virtualcar, проверить актуальные PR, CI, коммиты
и продолжить первый незавершённый этап (сейчас этап CS-01, затем CS-02).

Dvinholm остаётся основным продуктом. Virtual Car используется только
как независимый тестовый стенд. Сборки и релизы Virtual Car не публиковать
без отдельного разрешения. Не выдавать синтетические испытания за
реальную совместимость CEM/J2534.
