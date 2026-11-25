# VC074 — standalone CEM529 preview window

Experimental Windows x64 / .NET 10 / WinUI 3 application. Windows App SDK 1.8.10 is pinned. Self-contained unpackaged output. Existing Go GUI, native x86 J2534 DLL, provider registry, VIDA and CI configuration are unchanged.

From a Windows development checkout with .NET 10 and WinUI build tooling:

```powershell
dotnet build emulator/managed/VirtualCar.WinUI/VirtualCar.WinUI.csproj -c Release -p:Platform=x64
dotnet run --project emulator/managed/VirtualCar.WinUI/VirtualCar.WinUI.csproj -c Release -p:Platform=x64 --no-build
```

Enter explicitly reviewed absolute paths to Python.exe, the checkout's emulator/tools/cem529_config/vc071_view.py, and the existing pinned seven-file private directory outside Git. No paths are saved by the application. Do not use private data in CI.

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
