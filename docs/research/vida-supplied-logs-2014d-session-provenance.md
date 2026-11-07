# VIDA 2014D supplied-log provenance and bounded session attribution

Date: 2026-11-07. Linked to [P0 Issue #4](https://github.com/vorlocsev/virtualcar/issues/4).
Source: three **different** owner-provided files, locally read without
uploading source logs or copying credentials, driver paths, profile keys,
or VIN. **Do not label these particular logs VIDA2015A.**

## Primary-source correction

The supplied `VIDA.log` explicitly prints **`VIDA release: VIDA2014D`**
in its sessions dated **2026-09-25** and **2026-09-26**.
A prior research note referred to these supplied logs as original
VIDA **2015A** runtime logs. That attribution was incorrect.
Static analysis of separately sourced original VIDA 2015A DLLs
does **not** turn a 2014D runtime log into a 2015A capture.

Specific, separately sourced observations:

| Source | Observed, source-bound statement | Does NOT establish |
| --- | --- | --- |
| `VIDA.log` (Sep 2026; declares 2014D) | CarCom `vadis_GetHwSettings` lookup, `DiagSwdlRepository` `GetSWDLSupportedVehicleModels` and `GetNavImage` mentions | `GetScript(ReadVin)` returned an XML, or a VIN was accepted |
| Same `VIDA.log` | SQL login/open error names **`ImageRepository`**, in the call chain for `VehicleImageProvider.GetImage` | Failure of `DiagSwdlRepository.GetScript`; this is a **different database** |
| Same `VIDA.log` | One `Loading J2534 driver:` log entry | Successful `PassThruOpen`, `PassThruConnect`, CAN TX/RX, DiCE compatibility, or correct CEM route |
| `VidaMonitor.log` (Oct 29, 2026) | Monitor sees `DiagSwdlRepository`, CarCom and other named database instances; reports `VIDA started OK` | That an authorized `ReadVin` procedure ran, which VIDA release the client used, or a database principal can read every object |
| `db_attach_log.txt` (installation log, no cross-session proof) | An `ImageRepository` database attach entry and several `ASUser` orphaned-user login remapping events, including for `DiagSwdlRepository` | That the **September** `ImageRepository` SQL error was fixed, or that these attach actions preceded/followed a particular diagnostic session |

These are **not one continuous client/SQL/J2534 session**. The
Oct 29 Monitor database inventory cannot be treated as confirmation
that Sep 26 database permissions were working. No private donor identity
or ECU bytes are needed for this distinction.

The same supplied VIDA 2014D log includes `CarStatus read conditions
not correct`, but this is not evidence of a particular missing
CEM A3/A6 reply, normal-mode predicate, ignition signal or
`ReadVin` script content.

## Code: add source-version boundary to the existing trace auditor

`emulator/tools/audit_vida_script_selection.py` now:

- Counts **only exact** `VIDA release: VIDA2014D` and
  `VIDA release: VIDA2015A` declarations, not versions inferred
  from a timestamp or which DLL was inspected.
- Resets pending `GetScript → Fetched → Running` matching on
  the `Starting new logsession:` marker or a new explicit release.
  Same thread and a <30-second elapsed time across two sessions
  must **not** create a false accepted triplet.
- Counts completed `ReadVin` trace triplets separately under
  `declared_vida2014d`, `declared_vida2015a` or
  `version_unreported`. This is a count of the reported
  **client log chronology**, not VIN/ECU acceptance.
- Separately counts exact `ImageRepository` login-open errors,
  `DiagSwdlRepository` stored-procedure *mentions*,
  and `Loading J2534 driver:` attempts.
  A driver path/user login is never emitted in the report.
- Reports `actual_j2534_connection_success_verified=false`,
  `cross_file_or_cross_date_correlation_established=false`
  and retains existing unknown identity, MY2009 and replay flags.

The optional report contains fixed labels, counts and booleans only.
No raw log lines, paths, session timestamps, script IDs,
VIN, SQL users or connection strings are written.

## Eight synthetic regression groups

1. Explicit 2014D ReadVin triplet does not become 2015A.
2. Explicit 2015A ReadVin triplet remains just script chronology.
3. New session resets prior thread's incomplete triplet.
4. Release change also resets pending state.
5. `ImageRepository` SQL error is **not** silently attributed
   to `GetScript`.
6. Driver-loading event is **not** accepted J2534 connection.
7. Unknown/2014D/2015A sources remain separately counted.
8. Inexact release text cannot spoof provenance; CLI remains
   redacted and refuses to overwrite an output JSON.

The eight new groups extend the existing sixteen
`test_audit_vida_script_selection.py` tests to **24**.
The full Python test suite is expected to grow from **292 to 300**.
**Expected**, not verified Windows VM result before the exact
feature-SHA run. No physical adapter/VIDA runtime tests performed.

## Next authorized evidence gate

Run the already-merged `Inspect-VidaGetScriptSchema.ps1`
against an authorized active SQL Server instance, **catalog
metadata only**, not the stored procedure body or private XML.
Separately obtain one continuous read-only diagnostic session
with its **declared VIDA release**, effective connection mode,
actual GetScript(ReadVin) lookup/fetch/run, and J2534 connection
outcomes. The requested live **2015A** ReadVin identity/XML and
XC90 V8 MY2009 accepted VIN/ECU remain **unknown**.

No modification of the emulator's diagnostic response,
J2534 DLL, VIDA installation, original SQL, ECU firmware
or publication of Virtual Car binaries.
