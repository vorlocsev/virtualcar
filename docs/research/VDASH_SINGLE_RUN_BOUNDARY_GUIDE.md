# VDASH: single-run J2534/UI observation boundary

**Lab-only, read-only.** This does not execute VDASH, extract protected code, alter ECU replies or validate a real Volvo CEM. It reconciles three *independent* sources only when the operator attests that they came from one test. Even then, **same_run_independently_verified is always false**, because the existing reports have no shared VDASH run ID.

## Motivation and source evidence

Recovered static IL for VDASH portable 2.5.115.79 references:
- VddModel.Detect → DetectResult → Ecus / Units;
- four separate RefreshAvailability callsites;
- a call to InitializeUnits in Model_DetectDone's inventory.

The actual bodies of InitializeUnits, Model_DetectDone and RefreshAvailability are missing from the available selected IL excerpts. Older, **different-version VDASH 2.0** runtime logs reported an OBD VIN header/length response but an empty ECU list. These two evidence sources must not be interpreted as one established execution trace.

The tool documents the crucial boundary:
1. J2534 Connect status is only local adapter/channel evidence.
2. OBD 09 02 / 49 02 01 delivery is only transport header/length evidence.
3. Targeted D2/P3 delivery is not a validated CEM payload or UI acceptance.
4. VDASH command completion and InitializeUnits execution are *not* observed by these Virtual Car reports.
5. The ECU list visible in the VDASH interface is a separate **operator-reported** observation.

## Collect a new private, one-client laboratory run

Use the same Virtual Car DLL and diagnostic client for a fresh short test, not an accumulated log from previous builds. Record the client version and the UI stages. VMware is outside VDASH vendor support and any tests there are experimental. Use only read-only diagnostics. Do not run PIN, SecurityAccess, CEM configuration, reset, flashing or programming.

From the repository root on Windows, generate the two **existing sanitized reports** from the local Virtual Car text log. Choose fresh output filenames because the tools never overwrite existing files.

~~~powershell
py -3 .\emulator\tools\audit_j2534_connect.py "$env:TEMP\SectorVVirtualCar.log" --output "$env:TEMP\vc-connect-report.json"
py -3 .\emulator\tools\audit_j2534_discovery.py "$env:TEMP\SectorVVirtualCar.log" --include-obd --output "$env:TEMP\vc-discovery-report.json"
~~~

The log location can vary by build; verify it locally before running. Keep the raw log private because it can contain VIN or CAN payload.

Create a local file called vdash-ui-milestones.json. The following is **an example template, not the result of a real VDASH test**:

~~~json
{
  "format": "virtualcar-vdash-ui-milestones-v1",
  "client_build": "vdash_2_0",
  "one_client_run_attested": true,
  "same_run_sources_attested": true,
  "predetect_vehicle_shown": true,
  "connect_pressed": true,
  "connect_ui_finished": true,
  "ecu_list": "empty"
}
~~~

Choose client_build from vdash_2_0, vdash_2_5_115_79, or other. Use null for unobserved boolean milestones; use empty / nonempty / unknown for ecu_list. Set both attestation fields to true **only** if you personally verified that the reports and UI note come from the same single process/session and selected adapter. No VIN, account identifiers, licence keys, URLs, file paths, screenshots, or raw payloads should be added.

Run:

~~~powershell
py -3 .\emulator\tools\audit_vdash_session_boundary.py --ui "$env:TEMP\vdash-ui-milestones.json" --connect "$env:TEMP\vc-connect-report.json" --discovery "$env:TEMP\vc-discovery-report.json" --output "$env:TEMP\vc-vdash-boundary.json"
~~~

The output copies only fixed-schema labels, counts and flags and will not overwrite an existing output file.

## Research focus labels and limitations

| Label | Narrow permissible interpretation |
| --- | --- |
| no_cross_source_conclusion | Missing source alignment attestation, multiple discovery sessions, or parse errors. No diagnosis. |
| explicit_connect_not_observed / unknown_connect_ui_action | No confirmed manual Connect click. Automatic discovery remains possible. |
| inspect_driver_or_missing_connect_log | No exact Virtual Car J2534 Connect attempt in this source. Missing log is not missing adapter proof. |
| inspect_j2534_connect_failure | Observed Connect attempt(s), zero successful local channel creations. |
| vin_delivered_no_oem_request_observed | Delivered OBD VIN header/length + empty UI, but no recognized D2/P3 request in selected source. This does not prove CEM absence, parser rejection, or permanent failure to scan. |
| inspect_command_result_and_ui_projection | Targeted D2/P3 transport delivered but ECU list reported empty. Investigate client result and UI, without asserting command/ParseData succeeded. |
| ui_list_observed_identity_unverified | User saw a nonempty ECU list. Actual XC90 V8 MY2009 compatibility is not verified. |
| more_client_transport_evidence_needed | No specific boundary justified by these reports. |

The analyzer always emits *vdash_command_completion_verified=false*, *initialize_units_execution_verified=false*, *ecu_identity_verified=false* and *xc90_v8_my2009_verified=false*. It does not compare logs by timestamps, CAN IDs or guessing a client session token. It must not be used to fabricate B9F0/B9FB/B9FC data.

Note that the synthetic virtualcar-vdash-lab.ini still combines a P2 target with a P3 route and a non-MY2009 placeholder VIN. This is **not** an authenticated XC90 V8 MY2009 fixture. No emulator CAN behavior was changed in this stage.

Eight synthetic tests cover delivered VIN, targeted reads without UI, J2534 failure, attestation/multiple-session mismatches, incomplete transport, nonempty UI, malformed data and privacy. CI exercises offline tooling and the Virtual Car binary, **not the proprietary VDASH client**.

## Offline-only G4 classification hardening (2026-11-03)

Per research request, PR #39 skips the VMware LAB job. This is a narrow
branch-specific condition; other pull requests and explicit VMware workflows
retain their pre-existing behavior. Windows x86 build and native J2534
synthetic-route CI are separate offline checks, not a real VDASH run.

The boundary correlator now refuses a cross-source failure classification
when the sanitized J2534 Connect audit reports malformed metadata
(connect.invalid_events > 0). Its report preserves that numeric count but
never copies malformed log text. A missing or non-integer invalid_events
counter is rejected, not treated as zero.

Two additional operator-reported UI states are distinct:
- ui_connect_not_complete: operator saw that Connect had not finished
- ui_connect_completion_unknown: operator could not confirm completion

Neither outcome supports a claim of completed client ECU enumeration.
Only the explicitly observed completion state allows the existing narrow
transport-versus-UI focus; even then VddCommand completion and
InitializeUnits execution remain unverified.

Eight synthetic tests (#09–16) verify invalid metadata, incomplete/unknown
UI completion, bounded positive-path classification, partial/negative OEM
transport, malformed or missing counters, and redaction of private extras.
No emulator ECU reply, J2534 DLL, PIN, EEPROM, or firmware behavior changed.
