# Offline VIDA 2014D / 2015A: reported version and session attribution

Date: 2026-11-07. Linked to [P0 Issue #4](https://github.com/vorlocsev/virtualcar/issues/4).
Source: three **different** owner-provided files, locally read without
uploading source logs or copying credentials, driver paths, profile keys,
or VIN. The logged release marker is an observation, **not a diagnostic-engine compatibility boundary**.

## Primary-source correction

The supplied `VIDA.log` explicitly prints **`VIDA release: VIDA2014D`**
in its sessions dated **2026-09-25** and **2026-09-26**.
**Important user-supplied build context:** the local offline VIDA
**2015A is a modification/repackaging of the VIDA 2014D diagnostic
software family**. Its embedded release label can remain `VIDA2014D`.
A previous claim that the literal 2014D log marker made these logs
unusable as evidence for the user's 2015A-labeled installation was
**incorrect and is superseded here**.

Independent community accounts also describe offline 2015A builds
as modified VIDA 2014D, sometimes with differing SQL VIN/profile
data. Context sources:
[Diagnostic Laptops](https://diaglaptops.com/wp/2021/07/29/theres-two-versions-of-vida/),
[Volvo4Life](https://www.volvo4life.es/threads/proyecto-modificar-vida-para-que-soporte-v60cc-2016.94787/).
This **does not prove bit-identical DLLs or databases** in every
installation. For exact IL, XML and SQL behavior, the hash and
runtime-selected configuration still matter.

Specific, separately sourced observations:

| Source | Observed, source-bound statement | Does NOT establish |
| --- | --- | --- |
| `VIDA.log` (Sep 2026; declares 2014D, compatible with a 2015A-labeled offline build) | CarCom `vadis_GetHwSettings` lookup, `DiagSwdlRepository` `GetSWDLSupportedVehicleModels` and `GetNavImage` mentions | `GetScript(ReadVin)` returned an XML, or a VIN was accepted |
| Same `VIDA.log` | SQL login/open error names **`ImageRepository`**, in the call chain for `VehicleImageProvider.GetImage` | Failure of `DiagSwdlRepository.GetScript`; this is a **different database** |
| Same `VIDA.log` | One `Loading J2534 driver:` log entry | Successful `PassThruOpen`, `PassThruConnect`, CAN TX/RX, DiCE compatibility, or correct CEM route |
| `VidaMonitor.log` (Oct 29, 2026) | Monitor sees `DiagSwdlRepository`, CarCom and other named database instances; reports `VIDA started OK` | That an authorized `ReadVin` procedure ran, which VIDA release the client used, or a database principal can read every object |
| `db_attach_log.txt` (installation log, no cross-session proof) | An `ImageRepository` database attach entry and several orphaned-user login remapping events, including for `DiagSwdlRepository` | That the **September** `ImageRepository` SQL error was fixed, or that these attach actions preceded/followed a particular diagnostic session |

### Local exact-category counts, source files not exported

| Source | Fixed-marker observations |
| --- | --- |
| `VIDA.log` (79 lines) | 4 exact `VIDA2014D` release declarations; 0 `VIDA2015A`; 4 session headers; 0 `SP: GetScript`; 1 `ImageRepository` login error; 1 J2534 driver load attempt; 1 CarCom `vadis_GetHwSettings` |
| `VidaMonitor.log` (45 lines) | 2 `Found database DiagSwdlRepository`; 2 `VIDA started OK` |
| `db_attach_log.txt` (64 lines) | 1 `DiagSwdlRepository attached`; 1 `ImageRepository attached`; 7 generic orphaned-user fix summaries reporting one user updated |

The date-separated and installer observations remain **independent**.
One or more of these logs may be incomplete; zero matches means
**not present in the supplied excerpt**, not that an operation never
occurred at any time in the installation.

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
  `VIDA release: VIDA2015A` **literal diagnostic log markers**,
  rather than inferring a different engine or incompatible protocol.
  Both can belong to a 2014D-derived offline build family.
  This grouping is for auditing source provenance, **not** for
  denying applicability to the user's VIDA 2015A-labeled installation.
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

1. A 2014D *marker* is counted literally, without assuming a different diagnostic engine from offline 2015A.
2. Explicit 2015A ReadVin triplet remains just script chronology.
3. New session resets prior thread's incomplete triplet.
4. Release change also resets pending state.
5. `ImageRepository` SQL error is **not** silently attributed
   to `GetScript`.
6. Driver-loading event is **not** accepted J2534 connection.
7. Unknown/2014D/2015A sources remain separately counted.
8. Inexact release text cannot spoof a literal marker; CLI remains
   redacted and refuses to overwrite an output JSON.

The eight new groups extend the existing sixteen
`test_audit_vida_script_selection.py` tests to **24**.
The full Python test suite is expected to grow from **292 to 300**.
**Expected**, not verified Windows VM result before the exact
feature-SHA run. No physical adapter/VIDA runtime tests performed.

## Next authorized evidence gate

Run the already-merged `Inspect-VidaGetScriptSchema.ps1`
against the user's authorized active **2014D-derived VIDA 2015A** SQL Server instance, **catalog
metadata only**, not the stored procedure body or private XML.
Separately obtain one continuous read-only diagnostic session
with its **literal declared VIDA release marker**, effective connection mode,
actual GetScript(ReadVin) lookup/fetch/run, and J2534 connection
outcomes. The requested live **2015A-labeled offline installation's** ReadVin identity/XML and
XC90 V8 MY2009 accepted VIN/ECU remain **unknown**.

No modification of the emulator's diagnostic response,
J2534 DLL, VIDA installation, original SQL, ECU firmware
or publication of Virtual Car binaries.
