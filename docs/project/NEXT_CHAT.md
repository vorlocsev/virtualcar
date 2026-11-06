# NEXT CHAT | Dvinholm-first Virtual Car

Read this at the start of EVERY new chat, even when the user writes only
"далее", "продолжи" or "continue". Do not assume a previous chat's draft
commits or CI claims still describe the latest GitHub state.

## Zero ambiguity

PRIMARY PRODUCT: https://github.com/vorlocsev/dvinholm
LAB/TEST REPOSITORY: https://github.com/vorlocsev/virtualcar
LAB DEVELOPMENT BRANCH: `development`
TRACKER: https://github.com/vorlocsev/virtualcar/issues/60
CURRENT STATUS: `docs/project/STATUS.md`
ROADMAP: `docs/project/ROADMAP.md`
ARCHITECTURE: `docs/architecture/VIRTUALCAR-CORE-SQLITE-V1.md`
DVINHOLM ADR: https://github.com/vorlocsev/dvinholm/pull/703
DVINHOLM x64: https://github.com/vorlocsev/dvinholm/pull/702

## Startup procedure for the next assistant

1. Read STATUS, ROADMAP, this file, current code and relevant open PR.
2. Check GitHub PRs and workflow jobs *live*, do not guess versions or merge.
3. Identify the first unfinished P0 gate; work on it rather than producing
   another generic research summary.
4. Make a small, tested implementation in a dedicated branch/PR, ideally 8
   regression checks. Check CI; explain physical hardware/Windows GUI gaps.
5. Update STATUS and NEXT_CHAT **in the same PR/commit** before merge so
   progress survives a new conversation.
6. If CI is green and change isolated/approved, merge into development.
   NEVER automatically release Virtual Car or silently modify Stable.
7. If CI is not green, keep PR open and record exact error/next operation.
8. Restore from GitHub rather than relying on ChatGPT memory summaries alone.

## Stage 60 state at creation

- Architecture foundation #59 merged, Go `labcore`, inert schema 0001.
- New branch `feature/labdb-persistence-handoff-stage60`: added explicit
  developer-only SQLite bootstrap (Python stdlib) and ten tests, plus
  persistent roadmap/status/handoff files. Check PR and CI for final state.
- Stage 61 must implement production-quality **Go** SQLite driver/repository
  on top of the existing Go core; Python script is a bootstrap/testing tool,
  not an acceptable permanent CAN-path database dependency.
- No Go service, Named Pipes, x64 native J2534 bridge, or Dvinholm end-to-end
  runtime integration yet. No real CEM/VIN acceptance has been proven.

## What to develop, in priority order

1. Go SQLite driver + controlled migrations/backup/rollback; integration tests.
2. Immutable, provenanced scenario snapshot compiler and in-memory ECU fabric.
3. Local, current-user control API and safely bounded J2534 data pipe.
4. x86/x64 ABI shims; native DLL load from Dvinholm target x64.
5. Dvinholm native J2534 E2E (8 gates: load/connect/filter/timing/ISO-TP/UDS/
   CEM unknown-fail-closed/cancel & disconnect).
6. Lab scenario control UI, safe test-result indexing and reports.

For concrete gates consult ROADMAP.md rather than inventing requirements.

## Data safety and evidence

- No real VIN, PIN, EEPROM, OEM proprietary responses, raw private VIDA XML,
  full private diagnostic logs or unauthorized ECU payloads into git or CI.
- Use synthetic fixture labels and record provenance in every test.
- No GUI acceptance claim without Windows GUI run; no physical J2534 claim
  without explicit hardware test; no successful VIDA/SectorV identity claim
  without observed real client result.
- Never mutate real ECU hardware as part of Virtual Car testing.

## User continuation prompt

"Продолжи Dvinholm-first Virtual Car по
https://github.com/vorlocsev/virtualcar/blob/development/docs/project/NEXT_CHAT.md .
Проверь STATUS, ROADMAP, Issue #60, PR и CI, обнови журнал прогресса и
выполни следующий этап. Virtual Car не публикуй."
