# Offline VIDA 2014D-derived 2015A: JBoss startup log evidence boundaries

2026-11-07. **Scope:** a private `server.log` supplied by the owner.
This is JBoss/WildFly **web-application server** evidence, not the
separate VIDA .NET script execution or J2534 CAN diagnostic log.
No raw log, credentials, paths, host names or vehicle identifiers
are included in this repository.

## Private-source inspection: two startup sessions (2026-10-29)

A local bounded read of the source (1116 lines, 120357 bytes) found
**two** separate JBoss starts, associated server-ready marker
and VIDA web application deployment. Each session shows:

| Category | Observation *per session* | Boundary |
| --- | --- | --- |
| JBoss start | 1 `WFLYSRV0049`; 1 `WFLYSRV0025` | Web server ready, not VIDA diagnostic client success |
| VIDA web application | 1 `WFLYSRV0010: Deployed "VidaEar.ear"` | Web deployment, not a VIN read |
| JDBC product | 2 `Database Product: Microsoft SQL Server` | AccessServer and BaseData connections, **not** `GetScript` |
| JNDI access server | 1 `DataSource Loaded(accessserver)` | SQL configuration is usable for that datasource only |
| JNDI base data | 1 `DataSource Loaded(BaseData)` | BaseData layer loaded, not DiagSwdlRepository |
| CarCom datasource | 1 `Bound data source [java:/jdbc/carcom]` | JNDI name bound, **not** a vehicle response |
| Database marker | 1 `LastInstalledBaseId: VIDA2014D` | Consistent with 2014D-derived offline 2015A; not binary equality |
| Login integrity | 1 `Failed to initialize WSL validation framework` and 1 `The provider self-integrity check failed.` | **WSL login/provider** error, not a CAN timeout |
| Diagnostic client tokens | 0 `GetScript`, 0 `ReadVin`, 0 `DiagSwdlRepository`, 0 `J2534` | Absence **in this server log only**; not evidence none ran elsewhere |

The first server session contains a graceful shutdown; the second
one is cut off after app initialization, so its shutdown is not
observable. The source is not a continuous CarCom/J2534 client
trace. Its negative token count is **not a negative result from
`ReadVin`**, and there is no evidence of accepted VIN or ECU.

The explicit WSL failure occurs *after* VIDA deployment at
`PreLoginAction`. Its presence suggests that the provider
self-integrity check should be investigated on the owner-controlled
installation if authentication is failing. However, without an
actual failed user login and active configuration readback,
**no direct cause, required patch or remedy is established**.
Do not bypass integrity checks or modify VIDA based on this log.

The web server reports SQL Server JDBC driver availability and
`accessserver`/`BaseData` initialization; it does not establish
a successful connection from the separate .NET script repository
client to `DiagSwdlRepository.GetScript`. See
[the SQL catalog-only inspector](vida-2015a-getscript-sql-catalog-gate.md)
for the next authorized read-only metadata step.

## Privacy-safe reusable offline analyzer

New module: `emulator/tools/audit_vida_server_startup.py`.

- Reads one *local authorized* UTF-8 text file, at most **5 MiB**.
- Splits sessions at explicit JBoss `WFLYSRV0049` markers.
- Counts a fixed allowlist of status/error strings **per session**.
- Counts literal appearances of four diagnostic terms separately.
  They are **lexical counts**, not evidence of real client API calls.
- Produces only categorical counts/booleans. No raw log lines,
  timestamps, usernames, paths, hostnames, VIN, frame IDs,
  script contents or credentials.
- Rejects symlink input, prevents output inside the Git checkout,
  and creates its report with exclusive `x` mode (no overwrite).
- Always reports `readvin_selected_or_executed_verified=false`,
  `sql_stored_procedure_executed_verified=false`,
  `j2534_pass_thru_connect_verified=false`,
  `vehicle_identity_accepted_verified=false`,
  `replay_approved=false`.

Authorized local example, with private input retained locally:

```powershell
py -3 emulator/tools/audit_vida_server_startup.py `
  "C:\VIDA-private\server.log" `
  --output "C:\VIDA-private\server-audit-summary.json"
```

The generated JSON is private metadata; review it before sharing.
There is **no** import of original VIDA libraries and **no**
query to a database, browser, J2534 device or vehicle.

## Eight synthetic test groups (local 8/8 PASS)

1. Two startups do not cross-count events.
2. JDBC product and accessserver markers do **not** claim GetScript.
3. WSL integrity error does **not** become a CAN/J2534 failure.
4. Diagnostic words are lexical mentions, never an executed script.
5. Pre-start lines are not assigned to a later session.
6. Empty/oversized input handling.
7. Sensitive synthetic text excluded from fixed JSON output.
8. Exclusive output creation, CLI redaction, symlink input rejection.

Expected Python suite on `development`: **316 tests**
(previously verified 308 + 8), subject to exact-feature Windows
VMware validation. Eight source tests were run in local Python
and the original `server.log` was inspected privately; no
Windows CI, physical DiCE, active SQL query, or real VIDA
`ReadVin` was run by this change.

## Next P0 gate

Only a continuous **diagnostic client** attempt, paired with
a read-only catalog observation of the actual authorized
`DiagSwdlRepository.GetScript(ReadVin=4)`, can distinguish
script-selection failure from CarCom/J2534 and post-response
VIN/vehicle-profile resolution. WSL web-login health is a
parallel issue unless the actual client is shown blocked by it.

Do not add synthetic positive CEM replies, access PIN/security,
alter ECU programming, publish Virtual Car builds or mistake
the web server log for DiCE/J2534 communication.
