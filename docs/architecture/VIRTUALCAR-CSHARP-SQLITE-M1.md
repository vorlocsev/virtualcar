# Migration M1: C# / .NET 10 SQLite catalog

Status: IMPLEMENTATION PR (not released). Source schema remains
emulator/schema/0001_lab_catalog.sql, unchanged.

## Technical decision

- C# uses Microsoft.Data.Sqlite version 10.0.14 (NuGet, MIT).
  https://www.nuget.org/packages/Microsoft.Data.Sqlite/10.0.14
- Embedded original SQL v1 bytes are SHA-256 verified against
  the schema_migrations journal. No silent v1-to-v2 migration.
- SQLite is owned by the C# control plane only. Native C++ J2534
  adapters will not open the DB or query SQL per CAN frame.
- One SqliteConnection and one serialized SemaphoreSlim per catalog
  instance. WAL + synchronous=FULL + foreign_keys=ON + quick_check.
- Create requires a new .db path and an already existing local folder;
  Open refuses a missing, oversized, corrupted or wrong-version DB.
- Backup uses SqliteConnection.BackupDatabase, the SQLite online backup
  protocol, instead of copying just the .db file while WAL is active.
- Only catalog metadata is exposed. No raw VIN/PIN, private trace,
  EEPROM, donor IDs or J2534 diagnostic payloads in return values.
- Sealed database revision still has SnapshotBytesVerified=false and
  RuntimeApproved=false. Scenario compiler M2 must independently
  materialize, validate and hash the entire read-only payload before
  making it visible to the C# runtime.
- No C++ transport changes in M1; preserve current x86 C emulator and
  Go control as parity baselines until migration M8.

## Eight regression groups

1. Initialize and reopen exactly schema v1; verify empty database.
2. Missing database cannot be auto-created; create refuses overwrite.
3. Modified v1 migration SHA-256 cannot be silently accepted.
4. Synthetic profile metadata listing has no secret field.
5. Sealed revision remains non-runtime-approved metadata.
6. WAL-compatible SQLite backup contains committed data; no overwrite.
7. Corrupted database, SQL injection-shaped selectors and bounds fail.
8. Cancellation prevents creation, concurrent health and disposed state.

These are synthetic offline SQLite tests on Linux and Windows. They do
not prove actual Windows x86/x64 C++ J2534, accepted vehicle identity,
real ECU capabilities, original VIDA behavior or physical DiCE support.

## Next stages

M2: compile and verify immutable scenario bytes, route consistency,
provenance and source-scoped synthetic-only responses (no fabricated CEM).
M3: native C++20 x86/x64 J2534 DLL with 14 correct exported methods.
M4: C++ CAN/ISO-TP hot-path parity and deadlines.
M5: local secure Named Pipe server in .NET 10.
M6: WinUI 3 private lab control UI.
M7: Dvinholm x64 native E2E, then M8 old backend retirement gates.

No Virtual Car builds or releases are published automatically.
Exact new-chat trigger: virtual car.
