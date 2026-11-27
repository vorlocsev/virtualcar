# Virtual Car

Experimental native Windows x86 J2534 diagnostic emulator for Volvo P2.
Independent project; not affiliated with Volvo Cars, VIDA, VDASH or SectorV.

## Status

The native C/C++ implementation is under [`native-release/`](native-release/).
The native provider and C++ registration controller are separate components.
PR [#512](https://github.com/vorlocsev/virtualcar/pull/512) integrated the native
source into `main`. Legacy workflows are archived under `docs/legacy-workflows/`.

The VC127G full-profile x86 candidate was accepted in an existing Windows VMware
VIDA environment, within the scope documented in [release evidence](docs/VC128-release.md).
It represents an XC90 V8 2009 profile (B8444S, TF-80SC AWD). The profile is unchanged
from VC124. See [installation](docs/VC128-install.md) for the binary package and
upgrade precautions. Check [GitHub Releases](https://github.com/vorlocsev/virtualcar/releases)
for actual availability; this README does not establish that a release was uploaded.

## Build and test

Use an isolated Windows x64 environment with Visual Studio C++ tools for x86,
Windows SDK, clang-cl, Windows PowerShell 5.1 (32-bit and 64-bit), and Python 3.
From the repository root:

```powershell
python native-release/native-ci/Run-NativeCI.py --source native-release
```

The script builds the provider, runs 25 synthetic transport test groups,
builds the controller bound to that DLL and runs 10 isolated file-test groups.
Expected final marker: `VC127C2_CI=PASS 35/35`.
Python and PowerShell are build/test tools, not intended runtime dependencies.
The synthetic transport fixture is not an installable vehicle profile.

## Scope and license

Read-only virtual diagnostics. No physical ECU certification, programming,
security access, DTC clearing or full OEM equivalence is claimed. VDASH and
SectorV compatibility for this candidate is not verified.

Original native code is MIT-licensed; see [LICENSE](native-release/LICENSE)
and [license scope](native-release/LICENSE-SCOPE.md). Third-party rights and
historical repository materials are not automatically relicensed. Full-profile
redistribution and unredacted VIN were authorized by the project owner; the
profile is not automatically licensed under MIT. Commercial diagnostic software
and its original databases are not part of the new binary package.
