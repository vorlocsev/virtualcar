# Virtual Car: new C#/.NET 10 implementation

This directory is the **new implementation**, separate from the legacy
C + Go regression baseline under emulator/. It is under staged migration,
not yet the main executable, adapter or a published release.

## Projects

- src/VirtualCar.Core: managed state/session lifecycle and SHA-256 checked
  read-only scenario materialization. No database or CAN stack yet.
- tests/VirtualCar.Core.Smoke: 8 synthetic, package-free .NET 10 gates.
- src/VirtualCar.J2534.AbiProbe: **NONFUNCTIONAL** native J2534 ABI canary,
  returning ERR_NOT_SUPPORTED from all 14 standard exports. Do not register.
- tests/VirtualCar.J2534.AbiSmoke: x86/x64 native library load and export
  check; calls PassThruOpen/Connect and requires rejection.

## Local .NET 10 checks

    dotnet run --project dotnet/tests/VirtualCar.Core.Smoke -c Release

On Windows with .NET 10 SDK and MSVC native toolchain:

    dotnet publish dotnet/src/VirtualCar.J2534.AbiProbe -c Release -r win-x64 --self-contained true -p:PublishAot=true -p:NativeLib=Shared
    dotnet publish dotnet/src/VirtualCar.J2534.AbiProbe -c Release -r win-x86 --self-contained true -p:PublishAot=true -p:NativeLib=Shared

CI additionally validates each ABI DLL with a matching-bitness console
host; it deliberately never calls FreeLibrary on Native AOT library.
Native AOT shared libraries currently do not support unloading.

## Not implemented

Real PassThru channel, real ECU data, Go->C# schema repository,
CAN/ISO-TP, Volvo P2/D2, Named Pipes, Windows UI, physical DiCE,
Dvinholm integration or any real OEM vehicle identity.

See docs/architecture/VIRTUALCAR-CSHARP-DOTNET10-MIGRATION.md.
