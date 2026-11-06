# DVINHOLM / VIRTUAL CAR LAB | DEVELOPMENT ROADMAP

Updated: 2026-11-06. Primary product: Dvinholm. Laboratory: Virtual Car.
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
- No confirmed actual VIDA 2015A or SectorV identification of target
  XC90 V8 MY2009, no physical J2534 test, no approved release publication.

## Implementation stages

| Stage | Goal | Required gates | State |
| --- | --- | --- | --- |
| 60A | SQLite offline catalog | explicit init, checksum, migration rejection, integrity, FK, rollback, bounded metadata, symlink safety | COMPLETED, PR #62, CI #587 |
| 60B | Go-owned catalog | pinned driver, DB backup, migration, async-safe locking, bounded queries, corrupt DB refusal, sealed metadata, cancellation | NEXT |
| 61 | Scenario Compiler | exactly sourced fixtures, canonical serialization, SHA-256, sealed revision, refusal on missing evidence, bus/ECU isolation, reproducible replay, read-only policy | PLANNED |
| 62 | Go Headless Core | lifecycle, CPU/timing, queues, no SQL in RX, reset, faults, stale session rejection, cancellation, recovery | PLANNED |
| 63 | IPC control/data | Windows SID ACL, version negotiation, x86/x64, length caps, deadline, disconnect recovery, invalid IDs, event isolation | PLANNED |
| 64 | J2534 x64 adapter | 14 exports, PE32+/ABI, CAN/ISO15765, filters, FC/STmin, timeouts, reconnect, x86 coexistence | PLANNED |
| 65 | Dvinholm native E2E | real x64 DLL load, monitor+UDS, positive synthetic DID, missing fixture, cancellation, snapshots, fault injection, evidence report | PLANNED |
| 66 | Lab Control UI | profiles, ECU catalog, scenario revision, start/stop, fault scenarios, test history, RU/EN, privacy | PLANNED |
| 67 | Evidence-scoped P2 | real diagnostic traces, B9FB/B9F0 provenance, identity script, VIN validation, profile resolution, ECU inventory, missing-data fail-closed, Windows acceptance | RESEARCH BLOCKED |

## Explicit next step (stage 60B)

- Read the latest docs/progress/CURRENT.md first, then verify GitHub.
- Stage60A is merged and tested; do not repeat it or claim it provides a
  production Go SQLite driver.
- Implement Go-owned SQLite Catalog using the existing v1 schema and
  schema checksum, explicit migration, WAL/foreign keys, backup, and
  single-writer state. Review and pin the external driver/license.
- Connect metadata loading to labcore.Catalog only after a separate
  immutable scenario payload/compiler is present; metadata digest alone
  cannot authorize actual CAN replies.
- Add 6-8 Go synthetic tests, verify full Windows x86/native CI, then
  merge to Virtual Car development. x64/native E2E is still pending.
- Keep Dvinholm PR #702 x64 work separate. Never publish Virtual Car.

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
