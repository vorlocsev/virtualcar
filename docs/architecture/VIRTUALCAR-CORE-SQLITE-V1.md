# Virtual Car Lab v1 | Core, SQLite and Dvinholm-first test architecture

Status: PROPOSED / non-production foundation; 2026-11-06.
Companion contract: https://github.com/vorlocsev/dvinholm/blob/docs/virtualcar-testlab-j2534-contract/docs/architecture/DVINHOLM-VIRTUALCAR-TESTLAB-ADR.md

## Business goal and ownership

Dvinholm is the deliverable. Virtual Car is an isolated, reproducible testing
backend. The existing C J2534 DLL, Go Windows control utility and Python static
analysis remain available; they are not rewritten or disabled by this proposal.
Never publish Virtual Car releases automatically.

## Proposed layers and language decision

1. Dvinholm: the existing .NET 10 WinUI 3 app, moving to self-contained x64.
   Uses unchanged J2534 API; must work without the lab installed.
2. J2534 Data Adapters: thin, native Windows x86 and x64 DLLs. C ABI remains
   explicit; exact same 14 exported PassThru 04.04 functions and documented
   memory/calling conventions. Existing x86 code is a behavioral baseline.
   Future x64 wrapper is NOT implemented in this stage.
3. VirtualCar.Core: a future local Go x64 headless service, separate from GUI.
   One orchestration owner for each diagnostic session, immutable scenario
   revisions, stop/reset/fault scheduling, monotonic event ordering, safe output.
   A new pure Go package emulator/control/labcore supplies the START of its
   fail-closed coordination logic. No transport/IPC/SQLite driver yet.
4. ProtocolRuntime: preserve tested existing native C P2/CAN/ISO-TP logic as
   the reference; only consider isolated Rust protocol engines after measured
   parity. The orchestration service must never issue ECU write operations.
5. SQLite: lab control-plane catalog and read-only result indices, opt-in local
   per-user database; never queried per CAN frame.
6. Content-addressed private artifacts: restricted filesystem outside the
   install/git checkout. Genuine captured traces/private binary payloads
   must be encrypted (Windows user protection); a SQLite row stores only
   SHA-256 and relative encrypted path. Synthetic reply bytes may be stored
   in SQLite but must be explicitly labelled.

The target UI and CLI are clients of the same control API. They cannot bypass
scenario validation or issue diagnostic TX as root/admin. No HTTP listener.

## Execution model

    Control UI -- [control pipe] --+
                                  |
    Dvinholm -> x64 J2534 shim -- [data pipe] --> VirtualCar.Core
    VIDA/x86 -> x86 J2534 shim -- [data pipe] --> VirtualCar.Core
                                                    |
                                              ScenarioCoordinator
                                               |    |       |
                                        SessionGuard |    FaultScheduler
                                               |    |
                                       In-memory CAN Fabric
                                               |
                                        D2 / ISO-TP / ECUs
                                               ^
                                               |
                             sealed, hash-verified scenario snapshot
                                               ^
                                               |
                                 SQLite + optional private artifacts

Data-plane frame handling does not open SQLite connections. A scenario is
selected only with no live J2534 sessions, validated, materialized once,
hash-checked and activated under a new monotonically increasing generation.
Late response messages MUST match session id and generation to be delivered;
otherwise discard them and record a safe categorical drop event.

We must preserve distinct CAN 125/500 kbit/s buses and specific RX/TX IDs,
11/29-bit addressing, ISO15765 Flow Control and timing; never share a fixture
between unrelated modules. Simulation time can be deterministic in isolated
tests, but observed J2534 waits/timestamps must obey client-visible
monotonic time and the actual timeout contract.

## SQLite database v1 (proposed initial schema)

An inert migration draft is in emulator/schema/0001_lab_catalog.sql.
It must be deliberately invoked by a future migrator. No new runtime
code opens or modifies a database in this PR.

Tables and their responsibilities:
- schema_migrations: version, checksum, applied timestamp.
- vehicle_profiles: laboratory profile + provenance; NO VIN column.
- can_buses: bus identity, bitrate and identifier format per vehicle.
- ecu_nodes: ECU type, diagnostic request/response routes, protocol and off
  by default. Values are metadata, not verified Volvo CEM specifications.
- private_artifacts: restricted relative encrypted path, SHA-256 and size.
- response_fixtures: synthetic bytes OR encrypted private artifact, source,
  request hash and explicit read-only lab approval.
- scenarios / scenario_revisions / scenario_bindings: named scenario,
  revision, digest, fixture bindings; revisions sealed before running.
- test_cases: assertion type and schema-versioned expected results.
- test_runs: test case, scenario/adapter/build SHA-256, origin, status and
  failure class; physical-j2534 labelled results need an evidence digest.
- test_events: bounded structured counters only, never raw CAN or VIN.

A scenario sealing operation is a future *materialization* step: load the
allowed data, validate CAN route uniqueness, provenance, response lengths,
timings and security boundaries; emit a canonical immutable snapshot artifact
with a SHA-256. Hash it again immediately before activation. SQL triggers
protect sealed revision metadata/bindings and their referenced fixture edits.
The sample schema is NOT a complete cryptographic immutability proof for
mutable vehicle/bus/ECU rows; the materialized snapshot must supply that
guarantee. No automatic retrofit to the installed INI or old fixture format.

SQLite connection rules: journal_mode=WAL for per-user lab instance;
PRAGMA foreign_keys=ON for every connection; one serialized writer;
busy_timeout; all migrations atomic with snapshot backup through SQLite
backup API, not an unsafe copy of only the .db file while WAL is active.
Do not expose a shared SQLite file to both x86/x64 J2534 DLLs: ONLY the
controller process owns database connections. Read-only control/query
snapshots are served by its API.

Suggested per-user file location: %LOCALAPPDATA%/VirtualCar/Lab/lab.db;
encrypted artifacts in %LOCALAPPDATA%/VirtualCar/Lab/private/.
Do not use the repository root, program install folder or Dvinholm data path.

## Scenario provenance and capabilities

Each scenario, fixture and emitted test result must distinguish:
  synthetic; captured_private; research_only; unknown.
Only synthetic or explicitly approved local captured fixtures can be
activated as LAB READ-ONLY replies. Research-only observations cannot enable
a response automatically. Private captures are not shared or included in
CI/release artifacts. A scenario carrying the XC90/V8 name is not OEM-valid
by name alone. Lack of real CEM data => no fabricated B9F0/B9FB response.

Explicitly different evidence steps:
  CAN transport delivered
  != ISO-TP decoded
  != identity script selected
  != VIN accepted
  != ECU inventory accepted
  != real-vehicle support.

No Security Access/PIN enumeration, configuration programming, key/immobilizer
actions, ECU reset, write services or real hardware control in the lab.

## Local IPC v1 (design, NOT implemented)

- Named Pipe endpoints per signed-in user: control and J2534 data.
- System SID/session ACLs and least privilege, no global listener.
- Hello/protocol-version/feature negotiation and independent session ID.
- Control plane: ListProfiles, SelectSealedScenario, Reset, RunTest, Abort,
  SubscribeSafeEvents, ExportSanitizedResults.
- Data plane: Open, Connect, Start/StopFilter, Read, Write, Ioctl,
  Close, Heartbeat. One native J2534 API call maps to a bounded request.
- Bound lengths for every field, frame, queue and message; do not trust DLL
  callers. I/O deadlines, cancellation, structured failures and restart
  detection required. No raw diagnostic data in logs by default.
- On daemon death, generation mismatch, queue overflow or channel conflict:
  fail closed. Never replay stale queued frames into a new session.
- J2534 PassThruReadMsgs timeout semantics must be tested on actual x86/x64
  DLLs, including a blocking read during daemon shutdown.
- Pipe transport and performance characteristics are candidates to measure,
  not yet a demonstrated latency guarantee.

## Existing implementation vs this stage

Already existing: C x86 J2534 DLL, P2 core components, Go controller,
INI fixtures, test runners and read-only audits.
Added here:
- Go package emulator/control/labcore: pure, disconnected scenario lifecycle
  kernel with catalog/runtime interfaces, revisions, session caps, generation,
  fail-closed selection/reset/shutdown. NO database driver, pipes, ECU runtime
  or code changed in the existing DLL.
- First SQLite migration draft with foreign keys, provenance constraints,
  scenario sealing guards, bounded event vocabulary and hashed test metadata.
- Eight synthetic Go tests for the kernel and eight SQLite tests for schema.
No real VIDA/VDASH/Dvinholm process was launched during authoring.

## Delivery sequence aligned with Dvinholm

1. [This PR] Review Go core contracts, SQLite DDL and 16 synthetic tests.
2. Select and implement a Go SQLite driver, migration journal and backup
   contract; test upgrades and corrupt DB fail-closed handling.
3. Write canonical scenario compiler and synthetic/CEM evidence gate.
4. Split UI from headless Go service with local control API; C reference
   J2534 emulator is still the default until parity is proven.
5. Add x64 native J2534 adapter and registration/ABI checks for the approved
   Dvinholm x64 line. Keep x86 for legacy VIDA/SectorV/VDASH.
6. Implement the bounded data pipe, monotonic clock, FC/timer semantics and
   exact session-generation checks.
7. Dvinholm E2E automation through real native J2534 loader and virtual
   x64 adapter, including eight Dvinholm-specific read-only gates.
8. Verify Windows GUI manually; assess physical DiCE/J2534 separately.
   No inferred release or protocol compatibility from synthetic tests.

No Dvinholm production code, published Stable, PIN vault or ECU-writing code
is changed by this architecture stage.
