# VC074 — standalone CEM529 preview window

Experimental Windows x64 / .NET 10 / WinUI 3 application. Windows App SDK 1.8.10 is pinned. Self-contained unpackaged output. Existing Go GUI, native x86 J2534 DLL, provider registry, VIDA and CI configuration are unchanged.

From a Windows development checkout with .NET 10 and WinUI build tooling:

```powershell
dotnet build emulator/managed/VirtualCar.WinUI/VirtualCar.WinUI.csproj -c Release -p:Platform=x64
dotnet run --project emulator/managed/VirtualCar.WinUI/VirtualCar.WinUI.csproj -c Release -p:Platform=x64 --no-build
```

Enter explicitly reviewed absolute paths to Python.exe, the checkout's emulator/tools/cem529_config/vc071_view.py, and the existing pinned seven-file private directory outside Git. No paths are saved by the application. Do not use private data in CI.

## Exact-head build and empty-window UI Automation (VC075)

Use a clean checkout of the reviewed VC075 commit, Windows x64, stable .NET 10 SDK and WinUI build prerequisites. The output parent must already exist, outside Git; the output directory must not exist.

```powershell
$sha = (git rev-parse HEAD).Trim() # Compare with the reviewed full PR head first.
$out = Join-Path $env:USERPROFILE 'Downloads\VirtualCar-VC075'
& .\emulator\managed\VirtualCar.WinUI\Build-VC075.ps1 -ExpectedSha $sha -OutputDirectory $out -LaunchSmoke
& .\emulator\managed\VirtualCar.WinUI\Test-VC075Language.ps1 -ExpectedSha $sha -BuildDirectory $out
```

The first script publishes an unpackaged folder, verifies required native PE32+ AMD64 files and managed dependencies, writes a SHA256 inventory, and optionally starts and closes an empty window. The second checks the full published inventory and uses UI Automation on that exact application process to validate EN → RU → EN using three localized controls per language. Run in an interactive desktop, not a headless service. No private profile is loaded. Successful checks do not prove loaded-profile language switching, original VIDA or hardware acceptance. Keep local publish logs and manifests outside Git; no release is created. These scripts have not yet been run on Windows.

## Interface language

EN is the default when no valid preference exists. VC076 restores the last language from `%LOCALAPPDATA%\VirtualCar\WinUI\language.v1`; only the version and EN/RU code are stored. The EN/RU selector in the header changes application text immediately, including the status and audit headings. Original catalog labels, values and policy messages are not translated. Switching language does not invoke the preview subprocess or change the selected profile, draft, search or filter. The application replaces the small settings file atomically; a missing, malformed or oversized file falls back to English. Save failures are nonfatal and reported separately. The VC075 smoke scripts pass `--ephemeral-settings` to start in English without reading or writing the preference. Normal launches do not require this switch.

Additional manual acceptance: switch EN/RU/EN before loading, after loading, with a selected row and unapplied option, with a changed draft and non-default filter, and during a refresh. Verify state and audit digest remain intact, no additional process is launched, and the completion status uses the currently selected language. Check both languages at the intended Windows DPI.

## VC076 settings acceptance (pending)

Run the existing managed Core.Checks project (eight new groups, isolated temporary directories). In a normal interactive launch, select RU, close and reopen; confirm RU, then select EN and reopen. On a disposable Windows account, test missing/corrupt settings and a non-writable destination. Confirm the VC075 ephemeral smoke does not modify normal settings. No private paths or configuration values are persisted.

## VC077 main window and navigation

The shell opens on CEM529 Configuration to preserve the existing acceptance entry point. Left navigation contains Virtual vehicle, CEM529 Configuration, ECU modules, Diagnostics and Connection. At VC077 only the CEM529 workspace was functional; VC078 additionally implements Connection registration. Other pages explicitly state that they are planned; no simulated connection or running status is presented. The CEM editor stays mounted in memory, retaining its local draft, paths, search, filter and selection while navigating. Navigation is disabled during a preview so the cancel control remains reachable. EN/RU applies to all page names and placeholder messages; catalog and audit data remain unchanged.

The VC075 language smoke now includes 15 empty-window navigation checks (five sections for each EN/RU/EN round). It checks the headings, that the CEM load control is hidden on placeholder pages, and that the editor is available again on returning. Run with the exact VC077 published inventory. Loaded-profile navigation remains untested: manually change a lab parameter, record the audit digest, navigate through all sections and back, and verify the draft, selection and digest are preserved. Test switching languages on a placeholder and verify navigation is disabled while a real preview is in progress. Check layout at the intended DPI; the initial window size is unchanged.

## VC078 J2534 Lab Adapter installation and removal (pending Windows acceptance)

Connection exposes Refresh, Install driver and Remove driver. This is the existing J2534 04.04 user-mode x86 provider registration, not a Windows kernel driver. The WinUI application is x64. Publish via Build-VC075.ps1 to include the separate x64 registration helper. The chosen VirtualCarJ2534.dll must be an explicitly reviewed local x86 build at a stable absolute path; keep the DLL and its existing INI in place. No binary is copied or deleted by this feature. The static PE shape and SHA256 checks are not publisher authentication or an export-contract test; verify the DLL's provenance and exact 14 exports independently before use.

Close VIDA and other clients. Install requires explicit confirmation of the path and SHA256, followed by UAC. The helper rechecks the digest, writes only the canonical HKLM Registry32 J2534 Lab Adapter entry and refuses to overwrite a different or unrecognized entry. Remove requires confirmation and UAC; only the recognized entry with the expected path is removed, never other adapters or files. A previous registration is recognized for removal only; remove it explicitly before installing under the new name. If both identities exist, operations are blocked for review. The scripts and read-only provider audits recognize the transition; no automatic registry migration is performed. Registry status is not proof that a DLL is loaded or that VIDA communicates with the virtual vehicle. An interrupted or partial registration requires manual review; there is no automatic destructive rollback. Do not run concurrent external installers. Use a trusted reviewed application build. The ephemeral UI smoke cannot perform registry writes.

Acceptance on a disposable Windows VM, pending:
1. Build the application and helper, inspect exact x64/x86 roles and published hashes.
2. Inspect missing and existing registration without elevation; verify other provider entries unchanged.
3. Reject wrong filename, invalid PE, x64 DLL, remote path and changed SHA256.
4. Cancel the confirmation and UAC; verify no registration changes.
5. Register a reviewed x86 DLL and compare the seven values against the updated installer; verify Registry32 and actual client discovery separately.
6. Refuse conflicts, extra values/subkeys and path mismatch; preserve all unrelated entries.
7. Remove the recognized registration; verify DLL/INI and other providers remain unchanged.
8. Run EN/RU UIA smoke and verify mutation controls disabled in ephemeral mode.

No actual installation, removal, registry modification or Windows execution has been performed in this development session.

## VC079 native ECM scenario preview

The Virtual vehicle workspace reads an explicitly selected local virtualcar.ini (maximum 1 MiB) and inspects only the native B3A316/B3A329 selection and required flags. It distinguishes configured static selections 0–4 and dynamic warm-up from live telemetry; it does not load or start the DLL. Selection labels use the existing native synthetic RPM snapshots. Dynamic requires all seven native prerequisite flags. The proposed two-section patch is displayed only if the relevant gates are enabled. Merge the keys into existing sections manually; never append duplicate sections. Native settings take effect on a subsequent PassThruOpen, not a live session. No private data is persisted or logged, no INI is written, and smoke mode disables profile inspection. This conservative parser accepts simple unquoted relevant values and rejects ambiguous or oversized input; it is not a complete Windows INI parser. Reinspect after any external edit. The registered library path is not automatically bound to the inspected file.

Eight new managed checks cover default-off, five static states, disabled fallback, individual missing prerequisites, dynamic precedence, patch scope, ambiguous profile and size/selector limits. Windows UI and actual native effect remain pending. Next: controlled application of the patch to an owner-approved profile with backup, fingerprint and explicit client-close confirmation, followed by native x86 reopen verification.

## VC080 guarded scenario apply (pending)

Apply scenario is enabled only after a valid inspection and a gate-compatible selection. Before confirmation and again before replacement, the application requires the selected path to be the virtualcar.ini beside the currently recognized J2534 Lab Adapter DLL. The dialog shows the path, scenario and source SHA256 and requires the operator to close diagnostic clients and editors. The helper does not elevate or stop clients. The application cannot independently prove that every external client is closed; do not run concurrent editors or installers.

Only B3A316 Enabled/State and B3A329 Enabled can be changed. Missing target keys/sections are inserted, existing unrelated bytes are preserved, and other prerequisite flags are never enabled automatically. The bounded local file is rechecked against the inspected digest; reparse-point paths are rejected. Same-directory File.Replace writes a unique backup, then the new bytes and backup are verified. An unchanged candidate creates no backup. An error is not proof the original remained unchanged after a replacement attempt: inspect the profile and backup before retrying. No automatic rollback or native session restart occurs. Backups contain the original private profile and must remain local. Ephemeral smoke disables inspection and apply.

Eight new isolated managed checks cover scoped edits, inserted sections/keys, missing gates, ambiguous input, backup, stale digest and no-op. Windows acceptance: inspect the registered profile; cancel confirmation; verify a mismatched path and external edit are refused; apply one static and one eligible dynamic selection in a disposable VM; compare the backup and unrelated settings; close/reopen J2534 manually and verify the native responses; test EN/RU and ephemeral mode. No actual profile mutation or Windows/native execution was performed during authoring.

## VC081 guarded backup restore (pending)

Restore backup accepts an explicit absolute VC080/VC081 backup path beside the inspected profile of the currently registered J2534 Lab Adapter. The last created backup path is populated automatically. The confirmation includes current and backup SHA256 and the backed-up scenario. The operator must close diagnostic clients and editors. Both digests are checked again before replacement.

Restore is deliberately narrower than generic file recovery: the current and backup bytes must match exactly or one must be the exact result of an allowed VC080 scenario transformation of the other. This permits undo of an immediate scenario change and undo of that restore, but may reject older backups after successive changes or unrelated edits. The name is not authentication; this relation check limits changes rather than proving historical provenance. A successful changed restore preserves the previous current file in a new VC081 backup, retains the input backup and verifies both output files. No automatic rollback, arbitrary profile replacement, backup deletion or client restart. Reopen J2534 manually. Ephemeral smoke disables restore. Private backups stay local.

Eight managed temporary-directory groups cover exact restoration, undo, unrelated changes, stale active/backup digests, wrong name, wrong folder and no-op. Windows and native acceptance remain pending; test actual apply/restore/reopen in a disposable VM.

## VC082 ignition candidate (pending)

The Vehicle page exposes the existing B3A157 laboratory setting: baseline synthetic CEM A45F byte 04 or position-II hypothesis byte 07. Neither label establishes an OEM key-position mapping. No arbitrary raw value, physical ignition control, live change or write to ECU is supported. Diagnostics/EnableGGDCemLab must already equal 1; the feature does not enable this gate. The selected registered-adapter profile must pass inspection and explicit confirmation. The only edited values are B3A157_IgnitionLab Enabled and A45FRawByte (literal 07); other settings are preserved. Reopen J2534 manually. The response is conditional on the existing native route and gates.

Uses VC080 digest checks, same-directory replacement and new VC082 backup. VC081 restoration accepts VC082 backups only if equality or an exact allowed single ECM/ignition transformation (either direction) relates the two files. This is not a general rollback of multiple changes. No automatic restart. Malformed or unsupported relevant INI values are rejected. Eight isolated managed checks and the bilingual ephemeral UI smoke lockout are prepared; none has been executed. Owner acceptance: on a disposable VM, use the existing exact native GGD route and compare 04 versus 07 after reopening; keep actual VIDA interpretation separate from byte-level proof.

## VC083 configured ECU inventory (pending)

The ECU modules workspace reads the registered J2534 Lab Adapter's adjacent virtualcar.ini on explicit request. It lists ECU0..ECU31 according to ECUCount, with request/response addresses, expected bitrate and configured part/software text. Missing ECUCount uses the native default of two; absent legacy addresses use the source defaults and are marked. Missing identity text is not replaced by fabricated ECU identities. Extended missing addresses, malformed or overflowing numerics, functional requests, mixed address widths and duplicate request identifiers are flagged conservatively. Invalid or duplicate relevant sections/counts are rejected rather than guessing native fallback. This is a bounded simple INI subset, not an exact Windows INI emulator, full D2 replay inventory or route eligibility proof.

No communication, VIN read, discovery, ECU identification, profile write or data export is performed. Results are a local profile snapshot; refresh after any registration or profile change. Ephemeral smoke disables reading. Eight managed regression groups cover defaults, explicit routes, 32-slot bound, duplicates, malformed values, functional requests, ambiguous input and text/size bounds. Windows compile and UI acceptance remain pending.

## VC084 CAN log monitor (pending)

Diagnostics now exposes Start monitor, Stop monitor and Refresh snapshot, a local log path, TX/RX filter and case-insensitive CAN ID/payload/PID/process text filter. The existing native DLL temporary log filename remains the default for compatibility; it is not the adapter name. Only an explicitly started read-only snapshot refreshes every second. Stop, navigation away, close or read failure stops the timer; changing the path clears the previous snapshot. Ephemeral smoke cannot open the log.

At most 512 KiB of the file tail and 500 newest parsed records are shown. A partial first line in a tail and incomplete last line are discarded. Only TX (app request) and PassThruReadMsgs -> delivered are included; queued RX records are not duplicated. Exact adjacent per-PID/process context records provide channel, protocol, status/flags, bitrate and wrapping 32-bit microsecond value; CAN ID is decoded only with matching CAN/ISO15765 context. Missing context remains unknown and retains the complete recorded byte prefix. The native log can truncate data to 52 bytes; records of that length are marked possibly truncated. The display is not a continuous capture, bus timestamp, physical CAN sniffer, complete ISO-TP frame trace, or verified ECU discovery. Multiple processes and earlier sessions may be present. Raw local log data may contain private diagnostic information; no upload, export or persistence is added.

Eight managed groups cover context parsing, interleaved clients, stale context, duplicate RX suppression, partial records, truncation, row bounds and bounded shared file read. Windows acceptance: run the exact UI build, verify read-only refresh against a controlled native test log, start/stop, filters, navigation, file rotation/truncation and EN/RU labels; inspect layout and update responsiveness. No managed build or runtime test has been performed in this authoring session.

## VC085 diagnostic journal (pending)

Diagnostics adds a selectable Diagnostic journal view over the same bounded VC084 log snapshot. No extra file read, driver connection, transmission or persistence. Labels distinguish request, positive response shape, negative response shape, START_OF_MESSAGE indication and unclassified data. SID, single DID and NRC are shown when the observed shape supports them; NRC 78 is response pending, not terminal failure. Filters include those labels and the summary counts visible records, not transactions or ECU acceptance.

The classifier requires ISO15765 context, channel, a decoded CAN address, compatible flags and nontruncated data. It recognizes a limited set of native supported diagnostic shapes (including 22/62, 7F, 09/49, 10/50, 19/59 and 3E/7E); protected request SIDs may be observed but never executed by this view. Raw CAN/D2, unknown context, unsupported response forms and ambiguous/malformed records remain unclassified. No transport reassembly, request/response pairing, latency, successful VIN read, DTC interpretation or ECU discovery is inferred. The log may contain multiple clients, partial history and private data; no export added.

Eight isolated managed checks cover single DID, NRC, supported service shapes, context, indication, malformed/truncated records, protected request observation and independent counts. Windows acceptance: switch views, verify filters and visible counts with an owner-local controlled trace, verify EN/RU, stop/refresh/navigation and ephemeral read lockout. No managed compilation or test execution has been performed during authoring.

## VC086 integrated synthetic/empty UI acceptance (pending)

Run in a disposable interactive Windows x64 VM, on the reviewed exact VC086 head, using stable .NET 10 SDK and Windows PowerShell 5.1. Do not run an unreviewed PR on the persistent development runner. The output directory must not exist, and its existing parent must be outside Git on a fixed local drive.

```powershell
$sha = (git rev-parse HEAD).Trim()
& .\emulator\managed\VirtualCar.WinUI\Test-VC086Acceptance.ps1 -ExpectedSha $sha -OutputDirectory C:\VC086-Review
```

Supply the independently verified 40-character PR head instead of calculating it from an unknown checkout. The runner requires a clean checkout and eight gates: exact checkout, managed core checks (80 registered groups at authoring), self-contained WinUI and driver helper publish, empty window launch, EN/RU/EN language and 15 navigation checks, three empty journal view switches, ephemeral read/mutation lockout, and post-smoke checkout/file inventory integrity. It writes local logs and vc086-report.json; failed stages stop further execution. The build wrapper includes launch smoke, so a launch failure before its manifest is emitted is reported as a publish-stage failure; later stages remain not_tested.

The accumulated workspace panels are now vertically scrollable; navigating away clears the static ECU inventory. Ephemeral mode disables even private CEM profile load and registry refresh, in addition to all previous mutation and log-read lockouts. No private inputs, original diagnostic software, J2534 DLL launch, provider registration or hardware access is required.

The report explicitly leaves private CEM preview, actual registration, scenario application/restoration, native ignition responses, loaded profile UI, DPI/layout, actual ECU inventory, live log monitoring, VIDA ReadVin/T111/T122 and physical J2534 not_tested. Passing this runner is not final vehicle or OEM acceptance. No release or merge is authorized by its report. Windows execution remains required; no results are asserted by the source changes alone.

## VC087 isolated loaded CEM529 acceptance (pending)

VC086 owner-local synthetic/empty UI acceptance passed at exact head 2cb787b0b584f6f54fa88c16cf712a55cec13bad (owner-provided terminal marker, PR #472; full artifacts not independently reviewed). VC087 is a separate candidate, not yet built or tested.

The new explicit --preview-only launch mode enables local CEM preview while retaining ephemeral settings and the existing read/mutation lockouts for registry, native INI, configured ECU inventory and CAN log. Normal launch and --ephemeral-settings retain their previous roles. Preview is a draft in memory only; no export, ECU writes or driver installation. The user must select a trusted reviewed Python executable and the exact checkout's vc071_view.py. This is an application feature lockout, not an OS sandbox for arbitrary Python code.

Build and first rerun VC086 on the reviewed exact VC087 head using a new external output directory. Then use that build inventory:

```powershell
& .\emulator\managed\VirtualCar.WinUI\Test-VC087LoadedPreview.ps1 -ExpectedSha $sha -BuildDirectory C:\VC087-Review\build -PythonExe $python -PrivateDirectory $private
```

The runner accepts explicit absolute local paths only. The seven pinned private input files must already exist outside Git and be reviewed by the owner. It verifies the build inventory and clean exact source, opens an isolated application instance, selects an editable option offered by the catalog (not a predetermined OEM-valid edit), and exercises eight gates:
1. Baseline 127 parameters / 12 locked / zero changes.
2. Protected row cannot preview or revert.
3. Select an editable row and offered option.
4. Preview one change with a distinct audit digest.
5. EN/RU/EN preserves the draft, selection and filter.
6. Navigation preserves the draft and checks isolated mode lockouts.
7. Revert and close/reload the baseline.
8. Compare SHA256 for the seven inputs before and after, without printing private values or digests.

The result marker VC087_LOADED_CEM_ACCEPTANCE=PASS is emitted only after all gates and normal process exit. Failure stops execution; the runner closes only its own process. UIA control realization, private input compatibility and loaded-state behavior require actual Windows testing. This runner does not prove DPI/layout, normal-mode registry/INI access, live log, ECU inventory, cancellation during real preview, all filter cases, reset-all, dependency-blocked variants, original VIDA acceptance or hardware behavior; those remain separate gates. Do not upload the seven private files or run this on automated CI.

## VC088 isolated ECU inventory and diagnostic monitor acceptance (pending)

VC086 and VC087 passed owner-local at exact head 2de6b78fbaeb5d145834bef2c82bdcf8e7e76551 (PR #473, owner-reported unmodified script markers, Core 80/80, 705-file build inventory, seven unchanged private inputs). VC088 is a new candidate; those results are not automatically carried forward.

Explicit --diagnostics-only launch retains ephemeral preferences and locks out CEM loading, native INI modifications, vehicle profile inspection and driver registration/refresh. It enables read-only inventory from an explicitly selected local virtualcar.ini without querying the registry, and monitoring of an explicitly selected local .log. No default native log is opened in this mode. This is application-level isolation, not a security sandbox. The inventory represents configuration, not actual ECU identification; the log represents recorded application traffic, not wire capture or VIDA acceptance. Normal mode, --ephemeral-settings and --preview-only retain their previous roles.

Build and rerun the VC086 and VC087 scripts on the reviewed exact VC088 head first. Then run:

```powershell
& .\emulator\managed\VirtualCar.WinUI\Test-VC088Diagnostics.ps1 -ExpectedSha $sha -BuildDirectory C:\VC088-Review\build -FixtureDirectory C:\VC088-Fixtures
```

The new fixture directory must not exist. The runner creates three synthetic INI files and a small synthetic log outside Git and the build, checks the exact published inventory, and validates:
1. Configured ECU addresses, bitrates and part label.
2. Duplicate and invalid routes.
3. Ambiguous profile refusal and stale inventory clearing.
4. CAN snapshot with queued RX excluded.
5. TX/RX and payload filters.
6. Journal classification counts, NRC filter and EN/RU.
7. Timer append, stop, manual refresh, navigation and missing log refusal.
8. Disabled unrelated operations, fixture integrity, exact checkout and final build integrity.

The test intentionally appends two records to its own generated log; it checks the exact expected final contents and unchanged INI hashes. It does not read private CEM data or native provider logs, register adapters, invoke native J2534, or exercise real vehicle traffic. The output marker is VC088_DIAGNOSTICS_ACCEPTANCE=PASS 8/8 only after normal process exit and final checks. Generated fixtures remain local for review. Actual registered profile, real native log, file rotation, large-log performance, DPI/layout, and VIDA/hardware gates remain separate. The runner has not yet been executed.

The VC086 Core and both publish commands additionally pass --disable-build-servers and UseSharedCompilation=false to avoid persistent compiler processes after owner-local builds. This is intended to address the prior manual .NET build-server shutdown workaround; it has not been validated on Windows yet. No global build-server shutdown or unrelated process termination is added.

## VC089 measured DPI capture (pending)

VC088 owner-local acceptance passed on 442406d310bad66c4b8c220136b20a418b7e0140. VC089 is a new candidate. Initial window targets 1200 x 800 DIPs, clamped to the current monitor work area. Counts reflow below filters under 1000 DIP; headings wrap. Rerun VC086, VC087 and VC088 on the new exact head first.

On an unlocked unobstructed desktop select actual Windows scale 100, 125, 150, 175 or 200 percent. Run Test-VC089Layout.ps1 with ExpectedSha, BuildDirectory, a new external OutputDirectory and ExpectedScale. Use a separate directory for each actual scale. The script does not change DPI. It checks owner PID, actual DPI, DWM frame within work area, minimum 850 x 450 DIP client, UIA anchors and bottom control visibility/scroll. Ten empty-window top views plus applicable bottom views are captured with SHA256 and measured dimensions. Screen capture is limited to the foreground window rectangle; sampled occlusion checks cannot rule out small overlays. Keep screenshots local and notifications closed. The manifest marks visual_review=not_tested; inspect PNGs separately for clipping, overlap and readability. Loaded-profile/real-log visuals and unsupported scales remain pending. Windows compile and execution are not yet verified.

VC089 first owner run at bc64db22f7c61d64f714b497eeab14ecde7f607b: VC086/087/088 passed (Core 80/80, 705-file inventory, seven unchanged private inputs); layout blocked because the 150% desktop yielded DPI-unaware window DPI 96. Twelve diagnostic PNGs obtained at ExpectedScale=100 are not actual-scale acceptance. Owner reported clipped Russian vehicle navigation and stale English selected values for direction, ECM scenario and ignition. New candidate embeds a PerMonitorV2 application manifest, wraps navigation labels, refreshes the same selected combo indices after localization, and rejects non-PerMonitorV2 window contexts before capture. New exact-head regressions, actual 144-DPI capture and screenshot review remain pending. No ZIP/PNG bytes independently inspected here.

## VC090A native transport and provider preflight (pending)

Base VC089 exact head 4ea39f9bef30f1ef2b7882078ed9cb0287598d3b passed VC086/087/088 and owner visual acceptance at actual 150% / 144 DPI PerMonitorV2. Other DPI scales remain untested. New head requires its own regressions.

After the VC086 publish, VC087 and VC088 checks, run Test-VC090NativePreflight.ps1 with ExpectedSha, BuildDirectory, new external OutputDirectory, PythonExe and optionally BashExe (Git Bash with clang/lld-link available). It archives only the exact tracked emulator/src and build-cross.sh into a new local directory, builds the x86 DLL there, verifies PE32 and 14 exports, runs the existing isolated native no-fixture/READ128 regression and backend audit, synthetic B9FB 13-frame and ISO15765 F190 replay, and VIDA-shaped CAN-MS channel lifecycle. Each test uses a separate copied DLL and synthetic INI/log directory. Native DLL and managed publication fingerprints are checked again at exit. It does not replace the working-tree or registered DLL.

The x64 DriverTool now supports `inspect <64-hex candidate SHA256>` without elevation or registry writes. It reports the same canonical/legacy/conflict state used by WinUI and compares bytes only for a recognized canonical registration. It does not load the registered DLL or expose its path/hash. VC090A checks invalid input rejection and matching before/after observations, not proof of whole-registry invariance. A missing, conflicting or different registration is a deployment blocker/observation, not a failed native transport test. VC090_NATIVE_PREFLIGHT=PASS 8/8 is not provider install/remove, diagnostic-client selection, actual loaded-module identity, VIDA ReadVin/T111/T122 or physical J2534 acceptance. Those require separate owner-reviewed deployment and actual client evidence. Preserve existing providers and private files. No real VIDA or hardware access, registry mutation, CI dispatch or release in this runner. Windows execution pending.

## VC090B canonical registration acceptance (pending)

Base VC090A exact head a99942ba1af4ab1036afed4a40b807a853b9f7f8 passed owner-local eight gates (Core 80/80, 705 managed files, fresh x86 DLL 109568 bytes, 14 exports, native transport). Canonical and legacy keys were absent; 66 other provider entries must be preserved. VC090B is a separate candidate.

Use a disposable owner-controlled Windows/VMware VM with a snapshot and all diagnostic clients closed. Rerun VC086/087/088, VC089 at actual 150%, and VC090A on the new exact head. Never run on the persistent CI runner. This test intentionally changes only the canonical Registry32 registration after explicit owner confirmation; do not proceed without it. Do not remove any historical provider, modify VIDA files, or use a real vehicle. No automatic recovery or mutation is performed by the checkpoint script.

Run Test-VC090BRegistration.ps1 with ExpectedSha, BuildDirectory, NativeDirectory (new passing VC090A output), OutputDirectory (new external fixed-drive directory), and Phase Baseline. It verifies both builds and stages only the verified DLL at OutputDirectory/provider/VirtualCarJ2534.dll. Launch the reviewed published VirtualCar.WinUI.exe with --registration-only. This mode disables private CEM load, vehicle scenario changes, CAN log reads and language persistence; legacy removal is disabled. The canonical-only elevated remove operation checks the confirmed DLL fingerprint and key identity. Normal mode retains its existing actions. Never pass the remove command directly as a substitute for UI acceptance.

Select Connection. Verify absent status, disabled Remove, enabled Install. Enter staged absolute DLL path. In order: (1) open Install confirmation, compare displayed path/hash and cancel; checkpoint InstallCancelled; (2) confirm Install and owner approves UAC, wait for Registered (registry only) and Registration updated; checkpoint Installed; (3) open Remove confirmation, compare path/hash and cancel; checkpoint RemoveCancelled; (4) confirm Remove and owner approves UAC, wait for Not registered; checkpoint Restored. Use the same parameters for each checkpoint except Phase. Confirm UI isolation by checking disabled controls in other sections. Keep local evidence of each action and normal window exit. Stop on any mismatch, conflict or partial key; never delete unrelated entries to force PASS. If mutation has already occurred, review the VM state with the owner before rollback.

Eight acceptance groups: exact managed/native build; absent canonical baseline and other providers; isolated UI; cancel install; actual install and exact seven values/bytes in Registry32; cancel removal; actual canonical removal; restoration and all build/provider fingerprints. The script validates five ordered registry checkpoints, not UI actions. It hashes recursive value names/types/contents and subkey names in both PassThruSupport.04.04 views, excluding only the intended Registry32 canonical key. It refuses a missing Registry32 parent or existing legacy/canonical entry at baseline. It does not snapshot ACLs, other registry trees, or other installed DLL files; identical snapshots do not prove no transient change between checkpoints. Final marker VC090B_REGISTRY_CHECKPOINTS=PASS 5/5 UI_ACTIONS=OWNER_EVIDENCE_REQUIRED is not full UI acceptance. No actual client or physical J2534 gate is inferred. Windows compilation and all new checkpoints are pending.

## VC090C explicit existing VIDA provider observation (pending)

VC090B at 20f6ea6ce575574b241c0513f6fefd9c1a8235f6 remains partial (Baseline/InstallCancelled 2/5; groups 1-4 pass). No authorized disposable VM or registry mutation permission. VC090C is an independent read-only observation, not a bypass of that gate.

Run the existing emulator/tools/audit_vmware_sectorv_process.ps1 with -SelfTest in Windows PowerShell 5.1 x64. The added eight synthetic classifications and key-name validation must pass alongside existing tests. For actual collection, use -OperatorSession -VidaProcessName and -VidaProcessId for an already running, owner-identified client, -VidaProviderKey for the exact existing Registry32 subkey name (not a registry path or display-name guess), -ReferenceDll and -ReferenceSha256 for the previously verified VC090B staged x86 DLL, and -OutputFile for a new local report outside Git. The operator must confirm the selected existing provider and client process; no client is launched, no adapter is installed, and no diagnostic request is sent. If no client is running, report not tested. Existing noncanonical registrations may be observed without renaming or deleting them.

The explicit mode verifies the reference PE32/hash, reads only the named local fixed-drive VirtualCarJ2534.dll registration, checks path and disk fingerprints before/after, and takes two module observations of the explicitly selected PID/start time if possible. Reports contain categorical values, not key names, paths, PID or hashes. A different binary is historical_or_different_binary; do not call it current candidate acceptance. candidate_path_and_disk_bytes_observed is only module-path and disk-byte evidence, not in-memory image verification, authenticated VIDA executable, GUI provider selection, active diagnostic configuration, actual J2534 exchange, ReadVin, T111 or T122. Stable observations are not continuous monitoring. Check actual GUI selection and J2534DiagnosticConnection separately using owner-local evidence; do not modify VIDA XML/SQL. Existing default and legacy operator modes remain unchanged. Windows execution pending; no CI, registry changes or release.

## VC090D native identity-delivery evidence (pending)

VC090C SelfTest passed owner-local 56/56 at 9fe219251762eaae3840d87889da8b3248f6991c; actual VIDA client observation remains not tested. VC090B install/remove remains blocked. This independent offline audit does not bypass either gate.

Run `py -3 -B -m unittest discover -s emulator/tests -p test_audit_vc090d_readvin_evidence.py -v` (eight synthetic groups). The new `emulator/tools/audit_vc090d_readvin_evidence.py` accepts --native-log (frozen bounded native text log), --pid-hex (eight hex digits), --host (exact existing logger prefix host), --expected-vin-file (local ASCII text containing one expected VIN), optional --displayed-vin-file (separately transcribed observed client display, not generated from expected VIN), and --output (new absolute local JSON outside Git). Keep all source material private; no real VIN is passed on the command line or emitted in the report.

The audit requires one complete selected textual PID/host Open/Close interval, immediate TX/RX context with channel/protocol/flags/baud, and uses only delivered RX, not queued markers. Recognizes the existing lab F190 7E0/7E8 ISO15765 500k route and B9FB CEM40/50 base-baud routes. B9FB requires 13 frames, one generation, consecutive delivered-frame tags and the one previously documented 88-byte layout; other valid layouts, untagged older logs, or intervening selected logger lines between delivery and tag do not qualify. Reset, reconnect and overlapping TX conservatively invalidate pending requests. Unmatched or incomplete evidence cannot become a positive overall gate; counts may still show individual matching deliveries. The algorithm is not a universal VIDA log parser. Logger prefix and on-disk VIN equality are not process authentication, OEM identity or same-run GUI proof.

Use the existing synthetic identity log from VC090A/B as an optional regression input; it contains intentional negative controls, so a conservative incomplete/ambiguous overall classification is possible. Do not drop negative rows to force a positive result. A private owner-verified display comparison is independent, and all actual original VIDA ReadVin, ECU and physical J2534 flags remain false. No registry/SQL/VIDA modifications, native DLL changes or new client execution. Existing XML graph and Procmon/module tools remain separate. Windows/owner-local execution pending; no CI dispatch.

## VC090E ECU readout and T111/T122 catalog evidence (pending)

VC090D target tests 8/8 and full Python regression 1232 discovered / 1228 passed / 4 known skips were owner-confirmed at PR #480 exact head 9f1c1ef57d640d573f35b4fa3b1d14aa47222cba. Actual original VIDA remains unverified. VC090E does not unblock registry installation or client binding.

T111_Service and T122_Protocol are CarCom tables, not executable diagnostic scripts. The existing audit_vida_t111_t122_aggregate.py can report a bounded sample of service-to-protocol references; a match is not proof of a selected profile, executed service or positive ECU identification. The new audit_vc090e_ecu_identification.py reconciles such an existing categorical report (optional) with separately owner-reviewed module observations. It never connects to SQL or VIDA. Original static source findings: docs/research/vida-2015a-identity-vin-x40-ecu-states-il.md.

Run `py -3 -B -m unittest discover -s emulator/tests -p test_audit_vc090e_ecu_identification.py -v` and the existing T111/T122 aggregate tests. Then full Python discovery and compileall. For an offline CLI example, create a new external observations JSON with schema vc090e-ecu-observation-v1, evidence_source synthetic, same_run true, and modules array. Each module has exactly module (unique local token), profile (in_configuration / not_in_configuration / unknown), readout (alive / not_alive / not_present / not_observed), transport (positive_identification / no_reply / negative_response / not_observed), and catalog_lookup (matched_variant / default_variant / not_observed). Never invent owner observations. Real observations may use evidence_source owner_reviewed only when independently reviewed locally. The same_run boolean is a claim, not an authenticated session.

Use --observations with the external file, optional --catalog-report with an existing bounded aggregate JSON, and --output for a new external report. Source files are compared before/after, duplicate JSON keys and module tokens rejected. Output contains category counts, discrepancies and gaps, no module tokens or raw data. Distinguish no reply from not observed, and NotPresent from NotAlive. Default CarCom variants do not prove actual ECU replies. Even reported_categories_consistent_only and sample_all_references_matched leave all original client/transport/identity acceptance flags false. The audit does not prove that the catalog and readout came from one run or represent all modules. No original SQL queries or registry changes in this stage; new tests pending.

## Owner-local acceptance (pending)

1. Compile and launch the separate window on Windows x64; no provider install.
2. Run VC073 real process smoke successfully on the reviewed VC073 checkout; then load 127 rows and 12 locked fields in VC074.
3. Search by original catalog label and decimal offset, and exercise all four filters; preserve original labels and values.
4. Select an unlocked catalog option and preview. Check original/selected values, changed count, and audit digest against VC071.
5. Confirm protected fields cannot be edited; only selectable catalog options are offered. Test revert and reset-all.
6. Exercise a blocked dependency and equipment/topology review with previously reviewed lab edits. No export or activation control is available.
7. Cancel during refresh, close while busy, and try invalid paths. Verify stale rows and audit disappear and the profile can be reopened.
8. Hash all seven private inputs before and after; confirm unchanged. Confirm no changes to registry, installed providers, J2534 DLL, or VIDA.

Do not confuse successful preview with OEM validation, original VIDA acceptance, or physical J2534 support. No build/test execution or visual acceptance has been performed when authoring this prototype.
