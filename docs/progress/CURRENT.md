# CURRENT | Dvinholm / Virtual Car Lab

## ACTIVE checkpoint: C# .NET10 / C++20, M4B-2 complete (2026-11-06)

### M5A local IPC preflight, Draft PR #85 (NOT merged / NOT verified)

`feature/m5a-secure-local-ipc-preflight` introduces `VirtualCar.Service`:
Windows current-user Named Pipe, 32-byte launch-secret HELLO, bounded
LE v1 frames, session-generation validation, one-client fail-closed
KEEPALIVE/GOODBYE and eight Windows synthetic integration gate groups.
Managed CI is wired but do not claim a PASS until the latest PR checks
finish successfully. This is **not** an installed service, a production
credential-provisioning path, a functional native J2534 DLL or full M5.
The underlying old C/Go references and existing J2534 binaries are unchanged.
See docs/architecture/VIRTUALCAR-LOCAL-IPC-M5A.md and PR #85.


Dvinholm remains the PRIMARY product. Virtual Car is a PRIVATE,
optional, read-only development lab. Never publish/register Virtual
Car as a physical J2534 adapter without explicit direction.

Completed:
- M0 PR #71 C# Core and C++ ABI, CI #1 SUCCESS.
- M1 PR #72 C# SQLite v1, CI #4 SUCCESS.
- M2 PR #75 synthetic sealed scenario compiler, CI #6 SUCCESS.
- M3 PR #77 C++ x86/x64 J2534 14-export FAIL-CLOSED ABI DLLs,
  CI #10 and legacy x86 #624 SUCCESS.
- M4A PR #79 C++ bounded CAN/ISO-TP, FIFO/FC/STmin, CI #13,
  legacy x86 #628 SUCCESS.
- M4B-1 PR #81 C++ isolated J2534 ISO15765 RX, 8 synthetic ECU
  routes, exact metadata, atomic START_OF_MESSAGE pair, CI #15,
  legacy x86 #631 SUCCESS.
- **M4B-2 PR #83 MERGED**, SHA
  **49f616f3af8ed266ecd793f0718ddb0b67c9792e**:
  actual Windows x86 BLACK-BOX comparison: independently built
  original C PassThru DLL loaded via LoadLibraryExW and called via
  PassThruOpen/Connect/StartMsgFilter/WriteMsgs/ReadMsgs/Disconnect,
  compared with separately built C++20 Iso15765Rx module for eight
  identical explicitly synthetic read-only F187/F189 test traces.
  Same synthetic INI source; C++ outputs are NOT derived from old DLL
  received bytes. Compared ProtocolID/RxStatus/TxFlags/DataSize/
  ExtraDataIndex and EVERY payload byte; only dynamic microsecond
  timestamps excluded. Eight groups passed (short, long START pair,
  two ECU, two channels, broad filter, wrong FC destination,
  63-entry FIFO pair rejection, disconnect/reset state).
  Final emulator x86 CI **#638 SUCCESS** (real DLL+new code 8/8),
  managed C#/C++ CI **#21 SUCCESS**, VMware LAB packaging
  **#453 SUCCESS**. No DLL/public releases.
  Test source: emulator/native-cpp/tests/legacy_c_cpp_parity.cpp.
  Scope: docs/architecture/VIRTUALCAR-LEGACY-C-CPP-EXEC-PARITY-M4B2.md.

**EVIDENCE LIMITS:** This is actual old C J2534 DLL versus compiled
new C++ RX *module*, NOT old versus a FUNCTIONAL new J2534 DLL.
The new M3 C++ PassThru DLL still deliberately returns NOT_CONNECTED;
there is no authenticated host IPC and no J2534 CAN transport serving
Dvinholm yet. Tested trace set is synthetic ISO15765 F187/F189 only.
Not verified: full 29-bit/raw-CAN/physical bus parity, vendor
extensions, Volvo P2 CEM B9FB replies, VIN acceptance by real software,
VIDA/SectorV/VDASH client discovery, physical DiCE or actual vehicle.
VMware LAB packaging != guest application test. Preserve old C/Go.

**NEXT M5:** securely connect a .NET 10 C# headless test host to a
native C++20 J2534 DLL using local Windows Named Pipes, strict current-
user ACL, versioned bounded IPC messages, verified sealed synthetic
scenario generation IDs, channel lifecycle/fail-closed reconnect,
timeouts and backpressure, eight integration groups. Do not accept
physical devices or ECU programming. New C++ DLL must remain
fail-closed unless authentication/scenario checks succeed.

Read first: docs/architecture/VIRTUALCAR-CSHARP-CPP-MIGRATION.md,
docs/architecture/VIRTUALCAR-LEGACY-C-CPP-EXEC-PARITY-M4B2.md,
docs/architecture/DVINHOLM-VIRTUALCAR-ROADMAP.md.

Exact cross-chat continuation phrase: **virtual car**.

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
