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
