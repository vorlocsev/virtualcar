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
- Go SQLite Catalog driver with migration transaction/backup.
- Hash-verified compiled scenario snapshot and runtime fixture selection.
- Named Pipe IPC, headless Go service, actual x64 J2534 DLL.
- Dvinholm real native x64 J2534 end-to-end tests.
- Authorized live VIDA/SectorV identification of target XC90 MY2009.
- Physical J2534/vehicle testing.

## Stage 60B | Go SQLite Catalog (PR #65)

- Repository: https://github.com/vorlocsev/virtualcar/pull/65
- Go package: emulator/control/labdb/catalog.go; tests:
  emulator/control/labdb/catalog_test.go (eight synthetic Go cases).
- Pinned modernc.org/sqlite v1.36.3, Go 1.23 (pure Go / no CGO);
  exact transitive checksums are committed in go.mod and go.sum.
- SQLite schema is the SAME existing schema/0001_lab_catalog.sql.
- Functions: explicit Initialize/Open, version/SHA-256 migration checks,
  integrity, foreign keys, bounded profile and sealed descriptor reads,
  consistent WAL backup with VACUUM INTO.
- Critical: returned Snapshot.ApprovedReadOnly is ALWAYS false.
  Neither Dvinholm nor Virtual Car may activate database responses
  before a stage 61 snapshot compiler validates actual content.
- Windows x86 CI #594 SUCCESS, including Linux Go tests/vet,
  native-route x86 regression, and unchanged existing C DLL;
  VMware LAB packaging #430 SUCCESS.
- This checkpoint is in PR #65. Check GitHub for its latest
  head and MERGED status, plus newer CI, before claiming completion.
- No headless Go service, named pipes, x64 J2534 DLL or
  physical vehicle/VIDA acceptance has been implemented.
- An older draft PR #61 overlaps completed 60A. Do not
  substitute or merge it without reviewing differences.

## NEXT STAGE: 61 (Scenario Compiler), only AFTER PR #65 merged

1. Build canonical, immutable scenario payloads from approved lab
   fixture bindings and exact ECU/bus route metadata.
2. Verify the SHA-256 of the complete materialized snapshot artifact.
3. Preserve synthetic/private provenance; do not fabricate MY2009
   CEM replies, never treat metadata hash as runtime evidence.
4. Connect verified payloads to labcore activation only when
   the current session generation, bus, target and revision match.
5. Add 6-8 deterministic offline tests for route conflicts, missing
   evidence, read-only restrictions, interleaved ECU requests,
   partial multi-frame responses and cancellation.
6. CI + Windows native E2E remain separate acceptance stages.
7. Update this checkpoint and ROADMAP with actual PR/CI evidence.

Canonical roadmap:
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md

## Короткая фраза для продолжения в новом чате

**virtual car**

Когда пользователь пишет только эту фразу, нужно восстановить контекст
проекта по этому файлу и
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md из ветки development
репозитория vorlocsev/virtualcar, проверить актуальные PR, CI, коммиты
и продолжить первый незавершённый этап (по состоянию этого файла: 60B).

Dvinholm остаётся основным продуктом. Virtual Car используется только
как независимый тестовый стенд. Сборки и релизы Virtual Car не публиковать
без отдельного разрешения. Не выдавать синтетические испытания за
реальную совместимость CEM/J2534.
