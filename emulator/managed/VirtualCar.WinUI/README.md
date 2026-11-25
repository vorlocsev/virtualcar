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

The shell opens on CEM529 Configuration to preserve the existing acceptance entry point. Left navigation contains Virtual vehicle, CEM529 Configuration, ECU modules, Diagnostics and Connection. Only the CEM529 workspace is functional at this stage. Other pages explicitly state that they are planned; no simulated connection or running status is presented. The CEM editor stays mounted in memory, retaining its local draft, paths, search, filter and selection while navigating. Navigation is disabled during a preview so the cancel control remains reachable. EN/RU applies to all page names and placeholder messages; catalog and audit data remain unchanged.

The VC075 language smoke now includes 15 empty-window navigation checks (five sections for each EN/RU/EN round). It checks the headings, that the CEM load control is hidden on placeholder pages, and that the editor is available again on returning. Run with the exact VC077 published inventory. Loaded-profile navigation remains untested: manually change a lab parameter, record the audit digest, navigate through all sections and back, and verify the draft, selection and digest are preserved. Test switching languages on a placeholder and verify navigation is disabled while a real preview is in progress. Check layout at the intended DPI; the initial window size is unchanged.

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
