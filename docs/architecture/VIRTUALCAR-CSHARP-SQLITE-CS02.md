# Stage CS-02 | C# SQLite Repository

Stage: **implementation under review**, not a released Virtual Car component.
Goal: replace Go/Python SQLite control-plane logic with C#/.NET 10,
preserving the exact v1 schema stored in emulator/schema/0001_lab_catalog.sql.

## Implemented in this branch

- dotnet/src/VirtualCar.Storage: Microsoft.Data.Sqlite **10.0.14**,
  exact embedded canonical schema and SHA-256 migration journal.
- Explicit first creation, reject existing database overwrite,
  reject missing/unknown/corrupt DB, WAL + foreign keys.
- One connection owned by C# service, serialized writes/reads with
  SemaphoreSlim; no database queries from the J2534/CAN hot path.
- Parameterized only synthetic profile creation and bounded listing.
- Parameterized read of sealed revision metadata. **Never** promotes
  a stored SHA-256 into an approved live CAN/ECU reply.
- Online BackupDatabase API to a newly created .db path; never overwrite.
- dotnet/tests/VirtualCar.Storage.Smoke: eight real SQLite test groups
  covering migration, overwrite, corruption, safe metadata, bounds,
  read-only descriptor, backup, foreign keys, cancellation and disposal.
- New step in reusable C# CI. No virtual J2534 payloads are changed.

## Package and compatibility

Official package: https://www.nuget.org/packages/Microsoft.Data.Sqlite/10.0.14

Microsoft.Data.Sqlite is a Microsoft-maintained managed API, but SQLite
itself remains a native database engine through package dependencies.
The **application/controller/protocol logic is C#**; "all C#" does not
imply inventing a new SQL engine or eliminating the SQLite native library.

No runtime packaging for Windows x64 or C# WinUI 3 GUI is claimed here.
Native AOT for this storage component is NOT a requirement: it executes
in the out-of-process .NET 10 Host, not in the J2534 Native AOT DLL.

## Next work and caveats

- Validate CI against actual NuGet package, both C# test suites, and the
  existing C/Go native-route regression.
- Next CS-03: CAN/ISO-TP Rx/Tx/FC/timeout behavior on C#;
  use existing C reference as parity oracle.
- Later implement persistent audited editing of CAN buses and ECU nodes,
  controlled schema upgrades, separate encrypted donor artifacts and
  immutable canonical snapshot compiler before real diagnostic replay.
- No new PIN, real VIN, hardware control or invented OEM responses.
- No Virtual Car release publication. Keyword: **virtual car**.
