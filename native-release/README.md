# Virtual Car native source candidate (VC127B4)

Local review only. The native x86 J2534 source set was recovered from the VC126 RC1 build graph and passed 25 synthetic transport groups with a standalone fixture. The controller source is the original VC122. Its build script binds only the provider SHA256 to the chosen DLL; it does not install or launch anything.

Build J2534 from an x86 Visual Studio developer PowerShell using native/j2534/Build-J2534.ps1 (MSVC linker, clang-cl, Windows SDK, Python 3 for PE audit). Build controller with native/controller/Build-Controller.ps1 -DllPath <built DLL> -OutputDirectory <new directory>. Test using the fixtures under native/tests. The synthetic profile is a transport-only fixture and deliberately does not meet the installer profile gates. Do not copy it next to the controller as virtualcar.ini. The existing installer targets the same registry key and installation directory as private RC1: do not launch the controller on a working installation. No installation or VIDA acceptance is implied.

No private INI or raw diagnostic logs are included. License, source provenance and historical public exposure audit remain unresolved. No license grant or public release approval is implied.
