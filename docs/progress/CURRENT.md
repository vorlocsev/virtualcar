# CURRENT DEVELOPMENT CHECKPOINT | Dvinholm / Virtual Car

Last edited: 2026-11-06. This is a persistent cross-chat handoff.
Read the ROADMAP in docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md.
This checkpoint is intentionally conservative: verify GitHub before
promoting a workflow run to SUCCESS or a PR to MERGED.

## Objective

Dvinholm remains the primary product; Virtual Car is an optional,
private, read-only J2534 test laboratory. The target is x64 WinUI 3
Dvinholm connecting through a genuine x64 Virtual J2534 DLL to an
isolated Go orchestration core and SQLite scenario catalog.
Legacy x86 VIDA/SectorV/VDASH keep an x86 adapter.

## State at beginning of stage 60

Virtual Car PR #59 merged to development:
  https://github.com/vorlocsev/virtualcar/pull/59
  merge commit e51c3397d78ad99a86bd15ced856a22066865444.
  CI #577 Windows x86 SUCCESS; #417 VMware LAB packaging SUCCESS.
  Meaning: tested Go lifecycle, SQLite schema draft and existing C J2534.
  NOT: running Go core with SQLite, running actual x64 DLL or VIDA success.

Dvinholm PR #702: unified x64 WinUI migration OPEN, independently staged:
  https://github.com/vorlocsev/dvinholm/pull/702
Dvinholm PR #703: documentation-only lab interface OPEN draft:
  https://github.com/vorlocsev/dvinholm/pull/703
  Its first head CI #5150 passed; the PR head may have changed afterward.
  Recheck actual CURRENT head CI before a merge.

Current development stage: #60A, SQLite Repository offline initializer.
Current PR: https://github.com/vorlocsev/virtualcar/pull/62 (draft at creation).\nCurrent branch: feature/lab-sqlite-repository-stage60
Target base: vorlocsev/virtualcar development.
Files added in this branch:
  emulator/tools/lab_sqlite_repository.py
  emulator/tests/test_lab_sqlite_repository.py
  docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md
  docs/progress/CURRENT.md\n  emulator/tools/lab_db_cli.py\n  docs/architecture/LAB-SQLITE-REPOSITORY-STAGE60.md
No new Virtual Car releases are authorized.

## Safety and integrity

- No SQL queries per CAN frame, no simulated PIN secrets, no
  real Volvo MY2009 CEM positive response fabrication.
- Real donor captures, VIN, EEPROM and original VIDA XML stay private.
- No physical test result without physical device evidence.
- Do not merge new branch until latest relevant Windows CI green.
- GitHub is the persistent record. Chat memory may lag.

## How to resume in a NEW chat

"Продолжи проект по файлам GitHub
vorlocsev/virtualcar/docs/progress/CURRENT.md и
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md в ветке development,
проверь открытые PR/CI; далее реализуй этап 60 или следующий
незавершённый. Dvinholm главный, Virtual Car только тест-стенд,
релизы Virtual Car не публиковать."

Update this handoff as the LAST stage-60 commit using actual evidence and
the current PR number/status. If not merged, keep the branch/PR explicit;
if merged, include the verified merge SHA and latest successful CI.
