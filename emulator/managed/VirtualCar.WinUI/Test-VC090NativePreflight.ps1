# VC090A: isolated exact-source native transport and read-only registry preflight.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [string]$BashExe
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::UserInteractive) { throw 'Interactive Windows desktop required.' }
$directory = (Resolve-Path -LiteralPath $BuildDirectory).Path
$manifest = Get-Content -LiteralPath (Join-Path $directory 'build-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema -ne 'vc075-winui-build-v1' -or $manifest.source_sha -ne $ExpectedSha -or
    $manifest.publish -ne 'pass' -or $manifest.platform -ne 'win-x64') { throw 'Build manifest mismatch.' }
$app = Join-Path $directory 'app'
# Verify complete inventory before starting the exact published application.
$actual = @(Get-ChildItem -LiteralPath $app -Recurse -File)
if ($actual.Count -ne @($manifest.files).Count) { throw 'Published inventory count mismatch.' }
$seen = @{}
foreach ($entry in $manifest.files) {
    if ($entry.path -notmatch '^[^\\/:]+(?:/[^\\/:]+)*$' -or ($entry.path.Split('/') | Where-Object { $_ -in @('.','..') })) {
        throw 'Invalid relative inventory path.'
    }
    if ($seen.ContainsKey($entry.path)) { throw 'Duplicate inventory path.' }
    $seen[$entry.path] = $true
    $file = Get-Item -LiteralPath (Join-Path $app $entry.path)
    if ($file -isnot [IO.FileInfo] -or $file.Length -ne $entry.bytes -or
        (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256) {
        throw 'Published file fingerprint mismatch.'
    }
}

. (Join-Path $PSScriptRoot 'Invoke-VCNative.ps1')
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
function Assert-Checkout {
    $head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'Exact source checkout required.' }
    $dirty = @(& git -C $repo status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean source checkout required.' }
}
function Assert-Publish {
    $actual = @(Get-ChildItem -LiteralPath $app -Recurse -File)
    if ($actual.Count -ne @($manifest.files).Count) { throw 'Final published inventory count mismatch.' }
    foreach ($entry in $manifest.files) {
        $file = Get-Item -LiteralPath (Join-Path $app $entry.path)
        if ($file -isnot [IO.FileInfo] -or $file.Length -ne $entry.bytes -or
            (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256) { throw 'Final published fingerprint mismatch.' }
    }
}
Assert-Checkout
if ($OutputDirectory -notmatch '^[a-zA-Z]:[\\/]') { throw 'Absolute local output path required.' }
$out = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $out) { throw 'Output directory already exists.' }
if ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($out)).DriveType -ne [IO.DriveType]::Fixed) { throw 'Fixed local drive required.' }
$cursor = Get-Item -LiteralPath (Split-Path -Parent $out)
if ($cursor -isnot [IO.DirectoryInfo]) { throw 'Output parent must be a directory.' }
while ($null -ne $cursor) {
    if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git')) -or
        $cursor.FullName.TrimEnd('\') -eq $directory.TrimEnd('\')) { throw 'Output must be outside Git, publish inventory and reparse ancestry.' }
    $cursor = $cursor.Parent
}
if ($PythonExe -notmatch '^[a-zA-Z]:[\\/]' -or -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'Absolute existing local Python executable required.' }
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$git = (Get-Command git -CommandType Application | Select-Object -First 1).Source
if ($BashExe) {
    if ($BashExe -notmatch '^[a-zA-Z]:[\\/]' -or -not (Test-Path -LiteralPath $BashExe -PathType Leaf)) { throw 'Absolute existing Bash executable required.' }
    $bash = (Resolve-Path -LiteralPath $BashExe).Path
} else {
    $bash = (Get-Command bash -CommandType Application | Select-Object -First 1).Source
}
$tar = (Get-Command tar.exe -CommandType Application | Select-Object -First 1).Source
$ps32 = Join-Path $env:WINDIR 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
if (-not (Test-Path -LiteralPath $ps32 -PathType Leaf)) { throw 'Windows x86 PowerShell required.' }
$helper = Join-Path $app 'driver-tools\VirtualCar.DriverTool.exe'
[void](New-Item -ItemType Directory -Path $out)
$gates = [ordered]@{
    source_and_managed_inventory='pass'
    fresh_native_build='not_tested'
    x86_export_contract='not_tested'
    native_silence_and_evidence='not_tested'
    synthetic_identity_replay='not_tested'
    can_ms_lifecycle='not_tested'
    registry32_preflight='not_tested'
    final_integrity='not_tested'
}
$report = [ordered]@{
    schema='vc090-native-preflight-v1'
    source_sha=$ExpectedSha.ToLowerInvariant()
    status='fail'
    failed_stage=''
    gates=$gates
    native_dll_sha256=''
    native_dll_bytes=0
    registry_state='not_assessed'
    registered_dll_match='not_assessed'
    registration_install_remove='not_tested'
    vida_provider_selection='not_tested'
    vida_loaded_module_identity='not_tested'
    vida_readvin='not_tested'
    vida_t111='not_tested'
    vida_t122='not_tested'
    physical_j2534='not_tested'
}
function Run-Logged([string]$exe,[string[]]$arguments,[string]$working,[string]$name) {
    $log = Join-Path $out ($name + '.log')
    $exit = Invoke-VCNativeLogged -Executable $exe -Arguments $arguments -WorkingDirectory $working -Log $log
    if ($exit -ne 0) { throw "Command failed: $name (exit $exit)." }
}
function Require-Log([string]$name,[string[]]$markers) {
    $content = Get-Content -LiteralPath (Join-Path $out ($name + '.log')) -Raw -Encoding UTF8
    foreach ($marker in $markers) {
        if (-not $content.Contains($marker)) { throw "Missing expected evidence in $name." }
    }
}
function Assert-NativeCopy([string]$name) {
    $copy = Join-Path $out ($name + '\VirtualCarJ2534.dll')
    if ((Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne $report.native_dll_sha256) { throw "Native copy mismatch: $name." }
}
function Read-Registration([string]$name) {
    Run-Logged $helper @('inspect',$report.native_dll_sha256) $app $name
    $lines = @(Get-Content -LiteralPath (Join-Path $out ($name + '.log')) -Encoding UTF8 | Where-Object { $_.Trim() })
    if ($lines.Count -ne 2 -or $lines[0] -notmatch '^VC090_REGISTRY_STATE=(Absent|Registered|LegacyRegistered|Conflict|Unavailable)$' -or
        $lines[1] -notmatch '^VC090_REGISTERED_DLL_MATCH=(not_assessed|exact_bytes|different_bytes|unverifiable)$') { throw 'Unexpected read-only registration output.' }
    $state = $lines[0].Split('=')[1]
    $match = $lines[1].Split('=')[1]
    if (($state -eq 'Registered' -and $match -eq 'not_assessed') -or
        ($state -ne 'Registered' -and $match -ne 'not_assessed')) { throw 'Inconsistent registration observation.' }
    return [pscustomobject]@{state=$state;match=$match}
}
$stage = 'fresh_native_build'
try {
    # Export only the tracked native source/build script to a new external directory.
    # No overwrite of the working-tree DLL or of an installed provider.
    $source = Join-Path $out 'source'
    [void](New-Item -ItemType Directory -Path $source)
    $archive = Join-Path $out 'native-source.tar'
    Run-Logged $git @('-C',$repo,'archive','--format=tar',('--output='+$archive),$ExpectedSha,'emulator/src','emulator/build-cross.sh') $repo 'archive'
    Run-Logged $tar @('-xf',$archive,'-C',$source) $out 'extract'
    $emulator = Join-Path $source 'emulator'
    $dll = Join-Path $emulator 'VirtualCarJ2534.dll'
    if (Test-Path -LiteralPath $dll) { throw 'Unexpected pre-existing DLL in source archive.' }
    Run-Logged $bash @('./build-cross.sh') $emulator 'native-build'
    if (-not (Test-Path -LiteralPath $dll -PathType Leaf)) { throw 'New native DLL not produced.' }
    $report.native_dll_sha256 = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.native_dll_bytes = (Get-Item -LiteralPath $dll).Length
    $gates[$stage]='pass'
    $stage='x86_export_contract'
    $verifier = Join-Path $repo 'emulator\native-cpp\tests\verify_pe_exports.py'
    Run-Logged $python @('-B',$verifier,$dll,'Win32') $repo 'exports'
    Require-Log 'exports' @('PASS: PE machine/format and exact 14 exports (Win32)')
    $gates[$stage]='pass'
    $stage='registry32_preflight'
    $before = Read-Registration 'registration-before'
    $report.registry_state = $before.state
    $report.registered_dll_match = $before.match
    if ($before.state -eq 'Unavailable') { throw 'Registry32 observation unavailable.' }
    $route = Join-Path $repo 'emulator\tools\verify_native_routes.ps1'
    $common = @('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$route,'-DllPath',$dll,'-OutputDirectory')
    $stage='native_silence_and_evidence'
    Run-Logged $ps32 ($common + @(Join-Path $out 'silence')) $repo 'silence'
    Assert-NativeCopy 'silence'
    Require-Log 'silence' @('PASS group 2:','PASS group 3:','PASS group 4:','PASS group 5:','PASS group 6:','PASS group 7:','PASS group 8:')
    $audit = Join-Path $repo 'emulator\tools\verify_native_routes.py'
    Run-Logged $python @('-B',$audit,(Join-Path $out 'silence\VirtualCar\dev47-backend.jsonl'),'--output',(Join-Path $out 'native-route-audit.json')) $repo 'route-audit'
    Require-Log 'route-audit' @('PASS: synthetic native DLL route evidence')
    $gates[$stage]='pass'
    $stage='synthetic_identity_replay'
    Run-Logged $ps32 ($common + @((Join-Path $out 'identity'),'-IdentityReplay')) $repo 'identity'
    Assert-NativeCopy 'identity'
    Require-Log 'identity' @('PASS group 4: synthetic 13-frame B9FB native x86 replay','PASS group 9: isolated synthetic ECM F190 native ISO15765 VIN')
    $gates[$stage]='pass'
    $stage='can_ms_lifecycle'
    Run-Logged $ps32 ($common + @((Join-Path $out 'can-ms'),'-CanMsPreflight')) $repo 'can-ms'
    Assert-NativeCopy 'can-ms'
    Require-Log 'can-ms' @('PASS B3A331 gate 1:','PASS B3A331 gate 2:','PASS B3A331 gate 8:','PASS B3A331: owner-independent x86 virtual CAN-MS channel lifecycle')
    $gates[$stage]='pass'
    $stage='registry32_preflight'
    $badLog = Join-Path $out 'registration-invalid.log'
    $badExit = Invoke-VCNativeLogged -Executable $helper -Arguments @('inspect','invalid') -WorkingDirectory $app -Log $badLog
    if ($badExit -ne 2) { throw 'Invalid fingerprint input was not rejected.' }
    $after = Read-Registration 'registration-after'
    if ($before.state -ne $after.state -or $before.match -ne $after.match) { throw 'Registration observations changed during preflight.' }
    $report.registry_state = $after.state
    $report.registered_dll_match = $after.match
    if ($after.state -eq 'Unavailable') { throw 'Registry32 observation unavailable.' }
    # An absent/conflicting/different provider is an observed state, not install acceptance.
    $gates[$stage]='pass'
    $stage='final_integrity'
    Assert-Checkout
    Assert-Publish
    if ((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne $report.native_dll_sha256) { throw 'Native source-build DLL changed.' }
    foreach ($name in @('silence','identity','can-ms')) { Assert-NativeCopy $name }
    $gates[$stage]='pass'
    $report.status='pass'
}
catch {
    $gates[$stage]='fail'
    $report.failed_stage=$stage
    throw
}
finally {
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'vc090-native-preflight.json') -Encoding UTF8
}
Write-Host "VC090_NATIVE_PREFLIGHT=PASS 8/8 SHA=$ExpectedSha"
Write-Host "VC090_REGISTRY_STATE=$($report.registry_state) DLL_MATCH=$($report.registered_dll_match)"
Write-Host 'VC090_REGISTRATION_INSTALL_REMOVE=NOT_TESTED'
Write-Host 'VC090_VIDA_READVIN_T111_T122=NOT_TESTED'
Write-Host 'VC090_PHYSICAL_J2534=NOT_TESTED'
