# B3A275: isolated exact-head Windows PowerShell 5.1 offline checks.
# Does NOT register J2534, run VIDA, touch SQL, or install drivers.
[CmdletBinding()]
param([Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{40}$')][string]$ExpectedSha)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$emu=Join-Path $root 'emulator'
$head=(& git -C $root rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0) { throw 'git rev-parse HEAD failed' }
if ($head -ne $ExpectedSha) { throw "EXACT_HEAD_MISMATCH expected=$ExpectedSha actual=$head" }
& git -C $root diff --quiet
if ($LASTEXITCODE -ne 0) { throw 'TRACKED_WORKTREE_DIRTY' }
& git -C $root diff --cached --quiet
if ($LASTEXITCODE -ne 0) { throw 'STAGED_CHANGES_PRESENT' }
Write-Host "B3A275_EXACT_HEAD=PASS SHA=$head"
$buildDir=Join-Path $emu '.build'
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
Push-Location $emu
try {
  $gcc=Get-Command gcc -ErrorAction SilentlyContinue
  if ($null -ne $gcc) {
    & $gcc.Source -std=c11 -O2 -Wall -Wextra -o '.build/B3A275-host-test.exe' 'tests/virtualcar_test.c' 'src/p2core/p2_cem_router.c' 'src/p2core/p2_ls_observer.c' 'src/p2core/p2_vehicle_core.c' 'src/p2core/p2_j2534_bridge.c'
    if ($LASTEXITCODE -ne 0) { throw 'HOST_C_COMPILE_FAILED' }
    & '.\.build\B3A275-host-test.exe' | Tee-Object -FilePath '.build/B3A275-host-test.log'
    if ($LASTEXITCODE -ne 0) { throw 'HOST_C_REGRESSION_FAILED' }
    $line=Select-String -Path '.build/B3A275-host-test.log' -SimpleMatch 'B3A274 GGD CEM50 opt-in scoped DID host regression PASS'
    if (-not $line) { throw 'GGD_REGRESSION_MARKER_MISSING' }
    Write-Host 'B3A275_HOST_C=PASS'
  } else { Write-Host 'B3A275_HOST_C=NOT_TESTED (gcc unavailable)' }
  $python=Get-Command python -ErrorAction SilentlyContinue
  if ($null -ne $python) {
    & $python.Source -m unittest discover -s tests -p 'test_*.py'
    if ($LASTEXITCODE -ne 0) { throw 'PYTHON_TESTS_FAILED' }
    Write-Host 'B3A275_PYTHON=PASS'
  } else { Write-Host 'B3A275_PYTHON=NOT_TESTED (python unavailable)' }
  $bash=Join-Path $env:ProgramFiles 'Git\bin\bash.exe'
  $clang=Get-Command clang -ErrorAction SilentlyContinue
  $lld=Get-Command lld-link -ErrorAction SilentlyContinue
  if ((Test-Path -LiteralPath $bash) -and $null -ne $clang -and $null -ne $lld) {
    & $bash 'build-cross.sh'
    if ($LASTEXITCODE -ne 0) { throw 'X86_DLL_BUILD_FAILED' }
    $dll=Join-Path $emu 'VirtualCarJ2534.dll'
    if (-not (Test-Path -LiteralPath $dll)) { throw 'X86_DLL_MISSING' }
    $raw=[System.IO.File]::ReadAllBytes($dll)
    if ($raw.Length -lt 128 -or $raw[0] -ne 0x4D -or $raw[1] -ne 0x5A) { throw 'BAD_DOS_HEADER' }
    $pe=[System.BitConverter]::ToInt32($raw,0x3C)
    if ($pe -lt 64 -or $pe+6 -ge $raw.Length) { throw 'BAD_PE_OFFSET' }
    if ($raw[$pe] -ne 0x50 -or $raw[$pe+1] -ne 0x45 -or $raw[$pe+2] -ne 0 -or $raw[$pe+3] -ne 0) { throw 'BAD_PE_SIGNATURE' }
    $machine=[System.BitConverter]::ToUInt16($raw,$pe+4)
    if ($machine -ne 0x014C) { throw ('NOT_X86_MACHINE: 0x{0:X4}' -f $machine) }
    $sha=(Get-FileHash -Algorithm SHA256 -LiteralPath $dll).Hash
    Write-Host "B3A275_X86_DLL=PASS PE32_MACHINE=014C SHA256=$sha"
  } else {
    Write-Host 'B3A275_X86_DLL=NOT_TESTED (Git Bash + clang + lld-link required)'
  }
  $after=(& git -C $root rev-parse HEAD).Trim()
  if ($after -ne $head) { throw 'SOURCE_HEAD_CHANGED_DURING_TESTS' }
  & git -C $root diff --quiet
  if ($LASTEXITCODE -ne 0) { throw 'TRACKED_SOURCE_CHANGED_DURING_TESTS' }
  Write-Host 'B3A275_VIDA=NOT_TESTED; B3A275_REGISTRY=UNCHANGED; B3A275_SQL=UNCHANGED'
} finally { Pop-Location }
