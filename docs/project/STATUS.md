# Project Status | Dvinholm-first Virtual Car

**Updated:** 2026-11-06 (UTC labels originate from GitHub CI).
**Source of truth:** GitHub repository branches, PRs, workflow runs and this file.
**Master tracker:** https://github.com/vorlocsev/virtualcar/issues/60

## Permanent project intent

1. Dvinholm is the primary Windows diagnostic product, WinUI 3 + .NET 10, target self-contained x64.
2. Virtual Car is a separate laboratory for developing and validating Dvinholm, not a competing end-user application.
3. Control architecture: Go headless orchestration; SQLite control-plane metadata; isolated native J2534 x86/x64 shims; private in-memory CAN/ISO15765/Volvo D2 simulated network; synthetic/offline fixture provenance. Keep tested existing C x86 DLL while migrating.
4. No invented real XC90 MY2009 CEM responses, VIN/PIN/EEPROM disclosure, hardware write or automatic Virtual Car release.
5. Every improvement must be traced to a PR, tests and CI. A green offline CI is NOT proof of real VIDA/SectorV/VDASH acceptance or physical adapter tests.

## Verified merged milestones

- Stage 47 VIDA original 2015A IL boundary research: PR #55 merged.
- Stage 48 script ZIP/XML lexical tool: PR #56 merged.
- Stage 49 script metadata linkage: PR #57 merged.
- Stage 50 ScriptProvider tracing audit: PR #58 merged.
- Stage 59 Dvinholm-first architecture Go labcore and SQLite schema: PR #59 merged to `development`; Windows x86 CI #577 success, VMware LAB packaging workflow #417 success.
- Dvinholm-side ADR PR #703 is OPEN, docs-only; CI #5150 was SUCCESS when checked on 2026-11-06. Target Dvinholm x64 migration PR #702 also OPEN.

## Current stage

**Stage 60: SQLite persistence and cross-chat handoff | IN PROGRESS.**

Active branch: `feature/labdb-persistence-handoff-stage60`.
Issue: https://github.com/vorlocsev/virtualcar/issues/60.
PR: https://github.com/vorlocsev/virtualcar/pull/61 (draft until CI verification).
Source changes:
- `emulator/tools/lab_catalog.py`: explicit opt-in per-user SQLite DB bootstrap, SHA-256 journal for schema 0001, existing-db validation, read-only summary and lab-only synthetic metadata CRUD; native emulator remains independent.
- `emulator/tests/test_lab_catalog_repository.py`: 10 synthetic tests: initialization, no overwrite, path/symlink refusal, metadata round trip, CAN 11-bit bounds, FK integrity, uniqueness, checksum drift, read-only/missing DB, safe CLI output.
- `docs/project/ROADMAP.md`: milestones and acceptance rules.
- `docs/project/NEXT_CHAT.md`: detailed start-up protocol, referenced from historical root `NEXT_CHAT.md` entrypoint.
- `docs/project/LABDB-LOCAL-USAGE.md`: opt-in synthetic-only examples.
- `.gitignore`: exclude private lab databases, journals and encrypted artifacts.
No integration with Go service or J2534 DLL is claimed. Native x64 shim does not yet exist.

## Test evidence

- Earlier Stage 59: verified Windows x86 CI #577 success (including 8 Go labcore + 8 Python SQLite schema tests); this was BEFORE Stage 60.
- Stage 60 CLI+SQLite tests: PR #61 CI status must be checked at the latest HEAD before any merge claim. No local Windows GUI or real J2534 run is implied.
- Current CI and PR state may change; ALWAYS fetch fresh status on continuation.

## Blockers / truth boundaries

- Dvinholm's x64 single-app migration is separate in PR #702; main .csproj may still target x86. The Virtual Car 32-bit DLL is NOT loadable by an x64 Dvinholm process.
- SQLite per-user DB is tooling only until Stage 61 Go driver + migrator + backup/restore are implemented.
- SQLite schema has some mutable metadata parents; final sealed scenario must use a hash-verified immutable materialized artifact before execution.
- Original VIDA 2015A identity ScriptContent and target XC90 V8 MY2009 CEM response shapes remain unverified. No simulated positive reply should be interpreted as OEM-proven.

## Next exact task

1. Check PR of Stage 60 and Windows CI; correct failing tests or schema.
2. Merge into `development` ONLY if green and content review passes.
3. Update this status with merged SHA/CI, then Stage 61: implement Go SQLite driver and repository; pin modules, validate schema checksum, never query SQLite per CAN frame.
4. Maintain current progress at root `NEXT_CHAT.md`, `docs/project/STATUS.md` and `docs/project/NEXT_CHAT.md` on `development`.

**New chat quick prompt:** "Продолжи Dvinholm-first Virtual Car по `vorlocsev/virtualcar/docs/project/NEXT_CHAT.md` в ветке development, сверь GitHub PR/CI и выполни следующий P0 этап. Не публикуй Virtual Car."
