# CURRENT | Dvinholm / Virtual Car Lab

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
- Go SQLite driver registration, database opening, migration transaction/backup.
- Existing Go database/sql boundary is metadata-only and cannot activate a scenario.
- Hash-verified compiled scenario snapshot and runtime fixture selection.
- Named Pipe IPC, headless Go service, actual x64 J2534 DLL.
- Dvinholm real native x64 J2534 end-to-end tests.
- Authorized live VIDA/SectorV identification of target XC90 MY2009.
- Physical J2534/vehicle testing.

## NEXT STAGE: 60B-2 (real Go SQLite driver, migration and backup)

1. Verify and pin modernc.org/sqlite and aligned libc/go.sum compatible with the
   target Windows x64 self-contained service. Review licenses and CI builds.
2. Enforce exact migration checksum, foreign keys, bounded file paths, WAL,
   single-writer transactions and database backups.
3. Connect the existing Go labdb metadata boundary to the pinned driver,
   retaining the explicit read-only descriptor contract; consider a guarded
   labcore.Catalog only after stage61 scenario materialization.
   NEVER treat metadata SHA as payload verification.
4. Implement canonical materialized snapshot content SHA-256 verification
   in stage 61 before permitting read-only scenario activation.
5. Add 6-8 Go tests for missing DB, migrations, corruption, private content
   isolation, scenario revisions, concurrency, cancellation, fail closed.
6. Run CI and submit/merge a dedicated PR to development. Do not publish.

Canonical roadmap:
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md

## Architecture decision: full C# rewrite (2026-11-06)

The user explicitly requests rewriting Virtual Car entirely in C#.
This **supersedes** the planned Go SQLite driver stage 60B-2;
stage 60B-2 was never completed. Keep old Go/C as regression references.
The main product is still Dvinholm, and Virtual Car remains test-only.

ACTIVE BRANCH: feature/csharp-dotnet10-migration-foundation
C# roadmap and compatibility investigation:
docs/architecture/VIRTUALCAR-CSHARP-DOTNET10-MIGRATION.md

CS-01 files introduced (PR/CI to be verified):
- dotnet/src/VirtualCar.Core/ (C# 10/.NET 10 lab controller)
- dotnet/tests/VirtualCar.Core.Smoke/ (eight synthetic gates)
- dotnet/src/VirtualCar.J2534.AbiProbe/ (nonfunctional Native AOT ABI DLL)
- dotnet/tests/VirtualCar.J2534.AbiSmoke/ (x86/x64 export and load checks)
- .github/workflows/csharp-migration.yml (new isolated CI)
No x64 J2534 functionality, real SQLite C# driver, WinUI 3 Control UI
or actual vehicle runtime is represented as complete by these files.

NEXT: check CS-01 PR and CI, repair failures; then CS-02 C# SQLite.
Do not publish Virtual Car. Do not delete C/Go before verified parity.

## Короткая фраза для продолжения в новом чате

**virtual car**

Когда пользователь пишет только эту фразу, нужно восстановить контекст
проекта по этому файлу и
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md из ветки development
репозитория vorlocsev/virtualcar, проверить актуальные PR, CI, коммиты
и продолжить первый незавершённый этап (по состоянию этого файла: CS-01, затем CS-02).

Dvinholm остаётся основным продуктом. Virtual Car используется только
как независимый тестовый стенд. Сборки и релизы Virtual Car не публиковать
без отдельного разрешения. Не выдавать синтетические испытания за
реальную совместимость CEM/J2534.
