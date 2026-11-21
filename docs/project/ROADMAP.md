# Dvinholm-first Virtual Car Laboratory | Development Roadmap

Updated: 2026-11-06. **Canonical tracker:** https://github.com/vorlocsev/virtualcar/issues/60

## Product rule

- **Dvinholm is the sole primary product** (.NET 10 WinUI 3; x64 migration PR #702).
- **Virtual Car is the laboratory** for Dvinholm J2534, CAN, ISO-TP, P2/CEM, synthetic ECU, CI and regression tests. Its release/versioning is independent.
- Protect Dvinholm Stable and production settings from synthetic/experimental code.
- Virtual Car should support an x86 J2534 DLL for older diagnostic clients and eventually x64 for Dvinholm; the x86 DLL cannot load in a native x64 process.
- Never infer real Volvo OEM compatibility from synthetic fixtures or transport-level success; no invented CEM responses, secrets or configuration writes.
- Do NOT publish Virtual Car builds/releases automatically. No external service exposure.

## Architecture baseline (verified on development)

- Virtual Car PR #59 merged: https://github.com/vorlocsev/virtualcar/pull/59, Go control skeleton at `emulator/control/labcore`, inert SQL schema at `emulator/schema/0001_lab_catalog.sql`, Go & Python tests, architecture document.
- Last PR #59 amended source was verified by Windows x86 CI #577 and VMware LAB packaging workflow #417; these are NOT proof of physical hardware or Dvinholm client acceptance.
- Dvinholm architecture PR #703 opened separately, docs only; Dvinholm CI #5150 SUCCESS on 2026-11-06. x64 WinUI effort PR #702 is still separate.
- The original native Virtual Car J2534 DLL is Windows x86 and C. The existing GUI is Go. SQLite is not yet part of the runtime; the SQL draft is only data model.

## Stages and acceptance gates

| Stage | Priority | Outcome / acceptance | State |
|---|---|---|---|
| 59 | Done | Go labcore foundation + SQLite schema draft + tests | MERGED |
| **60** | **P0** | Persistent progress files; local Python SQLite repository init/read/write, checksums, no overwrites; 8+ tests | IN PROGRESS (PR follows) |
| 61 | P0 | Go SQLite driver and adapter, WAL, migration journal, backup, recover/corruption paths; 8+ tests | TODO |
| 62 | P0 | Immutable scenario compiler from approved synthetic fixtures, hash-verified snapshots; no DB queries in CAN event loop; 8+ tests | TODO |
| 63 | P1 | Local authenticated Named Pipe control/data interfaces, session ACL, fail-closed restart; 8+ tests | TODO |
| 64 | P0 | Native PE32/PE32+ J2534 ABI wrappers, 14 exports, strict x86/x64 regression and timing; 8+ tests | TODO |
| 65 | P0 | Dvinholm WinUI3 x64 loads real virtual J2534 native DLL, CAN/ISO-TP/UDS/CEM read-only E2E; 8+ tests | TODO |
| 66 | P1 | Lab UI/editor, scenario/test matrix, safe history with provenance; 8+ tests | TODO |
| 67 | P1 | Manual Dvinholm Windows GUI validation and *separate* vendor DiCE/Mongoose/real CEM evidence; independent release gates | TODO |

**At every stage:** 6–8 relevant checks minimum, preferably 8; classify tests as synthetic/offline, Windows-native, VM client, physical adapter/vehicle. Green CI = source behavior gates only. Never describe hardware/real VIN/ECU success without an observed, authorized run.

## SQLite schema and data boundaries

`emulator/schema/0001_lab_catalog.sql` includes:
`schema_migrations`, `vehicle_profiles`, `can_buses`, `ecu_nodes`,
`private_artifacts`, `response_fixtures`, `scenarios`, `scenario_revisions`,
`scenario_bindings`, `test_cases`, `test_runs`, `test_events`.

Stage 60 tooling must never be automatically executed by Dvinholm.
Future Go service is the only SQLite owner; Python bootstrap tools are
offline development utilities, not the frame-processing engine.
No raw VIN/PIN/keys/EEPROM in catalog, outputs or source history.
Do not store full private traces as SQL blobs.
Use explicit provenance and immutable, hash-verified scene snapshots.

## Durable progress protocol (every chat)

1. Read `docs/project/STATUS.md`, `docs/project/NEXT_CHAT.md` and this roadmap from the **development** branch; browse open PRs/issues and CI *fresh*.
2. Confirm factual state before claiming previous work merged/tested.
3. Pick the first unblocked P0 item. Use a separate branch and PR for Virtual Car; never edit Dvinholm Stable by implication.
4. Commit small changes with tests, review the CI and record exact PR/commit/workflow outcome.
5. Update `STATUS.md` and `NEXT_CHAT.md` **as part of the same PR** so a new chat can resume from GitHub without trusting assistant memory.
6. After merge, set only the next item to IN PROGRESS. Do not leave a completed stage marked pending.
7. Document dependencies, blockers, real/manual test gaps, and which branch contains code.
8. A new conversation can start with: "Продолжи Dvinholm-first Virtual Car по github.com/vorlocsev/virtualcar/blob/development/docs/project/NEXT_CHAT.md. Сверь GitHub PR и CI."

## References

- https://github.com/vorlocsev/dvinholm/pull/702 (target WinUI3 x64)
- https://github.com/vorlocsev/dvinholm/pull/703 (Dvinholm/Virtual Car contract)
- https://github.com/vorlocsev/virtualcar/pull/59 (core + SQLite schema foundation)
- https://github.com/vorlocsev/virtualcar/issues/60 (durable milestones)
