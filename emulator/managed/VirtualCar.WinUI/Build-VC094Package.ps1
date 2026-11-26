# Build an offline self-contained package from an exact reviewed checkout.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [string]$BashExe,
    [string]$PrivateDirectory,
    [string]$ArtworkSourceDirectory,
    [switch]$SkipArtwork,
    [switch]$PublicZip
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
function Assert-Checkout {
    $head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'Exact checkout required.' }
    $dirty = @(& git -C $repo status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean checkout required.' }
}
if ($PublicZip -and $PrivateDirectory) { throw 'Public ZIP must not contain owner-local data.' }
if ($SkipArtwork -and $ArtworkSourceDirectory) { throw 'Choose artwork source or skip, not both.' }
Assert-Checkout
if ($OutputDirectory -notmatch '^[a-zA-Z]:[\\/]') { throw 'Absolute local output required.' }
$out = [IO.Path]::GetFullPath($OutputDirectory)
if ($out -match '[^\x20-\x7E]' -or $out.Length -gt 160 -or
    [IO.DriveInfo]::new([IO.Path]::GetPathRoot($out)).DriveType -ne [IO.DriveType]::Fixed -or
    (Test-Path -LiteralPath $out)) { throw 'New short ASCII fixed-drive output required.' }
$cursor = Get-Item -LiteralPath (Split-Path -Parent $out)
while ($null -ne $cursor) {
    if ($cursor -isnot [IO.DirectoryInfo] -or
        ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git'))) { throw 'Unsafe output ancestry.' }
    $cursor = $cursor.Parent
}
[void](New-Item -ItemType Directory -Path $out)
$build = Join-Path $out 'build'
$native = Join-Path $out 'native'
$package = Join-Path $out 'VirtualCar'
& (Join-Path $PSScriptRoot 'Build-VC075.ps1') -ExpectedSha $ExpectedSha -OutputDirectory $build -LaunchSmoke
$argsNative = @{ExpectedSha=$ExpectedSha;BuildDirectory=$build;OutputDirectory=$native;PythonExe=$PythonExe}
if ($BashExe) { $argsNative.BashExe = $BashExe }
& (Join-Path $PSScriptRoot 'Test-VC090NativePreflight.ps1') @argsNative
Assert-Checkout
$preflight = Get-Content -LiteralPath (Join-Path $native 'vc090-native-preflight.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($preflight.status -ne 'pass' -or $preflight.source_sha -ne $ExpectedSha) { throw 'Native preflight incomplete.' }
$dll = Join-Path $native 'source\emulator\VirtualCarJ2534.dll'
$hash = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne $preflight.native_dll_sha256) { throw 'Native candidate changed.' }
Copy-Item -LiteralPath (Join-Path $build 'app') -Destination $package -Recurse
# Preserve original managed apphost target and dependency filenames; change only
# the public executable filename in this separate package.
Rename-Item -LiteralPath (Join-Path $package 'VirtualCar.WinUI.exe') -NewName 'VirtualCar.exe'
$profiles = [ordered]@{'p2'='virtualcar-p2.ini';'obd'='virtualcar-default.ini';'p2-vin-demo'='virtualcar-p2-b9fb-lab-vin.ini'}
$inventory = @()
foreach ($id in $profiles.Keys) {
    $dir = Join-Path $package ('vehicle-data\' + $id)
    [void](New-Item -ItemType Directory -Path $dir -Force)
    $ini = Join-Path $repo ('emulator\' + $profiles[$id])
    $target = Join-Path $dir 'virtualcar.ini'
    $lib = Join-Path $dir 'VirtualCarJ2534.dll'
    Copy-Item -LiteralPath $ini -Destination $target
    Copy-Item -LiteralPath $dll -Destination $lib
    [IO.File]::WriteAllText((Join-Path $dir 'candidate.sha256'),$hash,[Text.Encoding]::ASCII)
    $profileHash = (Get-FileHash -LiteralPath $ini -Algorithm SHA256).Hash.ToLowerInvariant()
    if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $profileHash -or
        (Get-FileHash -LiteralPath $lib -Algorithm SHA256).Hash -ne $hash) { throw 'Package copy mismatch.' }
    $inventory += [ordered]@{id=$id;profile_sha256=$profileHash;native_sha256=$hash;scope='synthetic_or_historical_demo'}
}
$privateIncluded = $false
if ($PrivateDirectory) {
    $python = (Resolve-Path -LiteralPath $PythonExe).Path
    $script = Join-Path $repo 'emulator\tools\prepare_vc094b_local_profile.py'
    & $python -B $script --private-dir $PrivateDirectory --package $package
    if ($LASTEXITCODE -ne 0) { throw 'Owner-local profile preparation failed. Do not distribute this output.' }
    $local = Join-Path $package 'vehicle-data\xc90-v8-2009'
    $inventory += [ordered]@{id='xc90-v8-2009';profile_sha256=(Get-FileHash -LiteralPath (Join-Path $local 'virtualcar.ini') -Algorithm SHA256).Hash.ToLowerInvariant();native_sha256=$hash;scope='owner_local_private'}
    $privateIncluded = $true
}
$artworkStatus = 'skipped'
if (-not $SkipArtwork) {
    $artworkArgs = @{Package=$package;WorkDirectory=$out}
    if ($ArtworkSourceDirectory) { $artworkArgs.SourceDirectory = $ArtworkSourceDirectory }
    & (Join-Path $PSScriptRoot 'Prepare-VC094Artwork.ps1') @artworkArgs
    $artworkStatus = 'two_reference_photos'
}
Assert-Checkout
$files = @(Get-ChildItem -LiteralPath $package -Recurse -File | Sort-Object FullName | ForEach-Object {
    [ordered]@{path=$_.FullName.Substring($package.Length+1).Replace('\','/');bytes=$_.Length;sha256=(Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
})
[ordered]@{schema='vc094a-package-v1';source_sha=$ExpectedSha;native_sha256=$hash;profiles=$inventory;files=$files;
    original_vida='not_tested';physical_j2534='not_tested';registration='not_tested';private_profile_included=$privateIncluded;artwork=$artworkStatus;package_ui='not_tested'} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $out 'package-manifest.json') -Encoding UTF8
$audit = Join-Path $repo 'emulator\tools\audit_vc094g_package.py'
$auditArgs = @('-B',$audit,'--package',$package,'--manifest',(Join-Path $out 'package-manifest.json'),'--build-manifest',(Join-Path $build 'build-manifest.json'),'--native-preflight',(Join-Path $native 'vc090-native-preflight.json'),'--expected-head',$ExpectedSha)
if ($PublicZip) { $auditArgs += @('--zip',(Join-Path $out 'VirtualCar-Windows-x64-demo.zip')) }
& $PythonExe @auditArgs
if ($LASTEXITCODE -ne 0) { throw 'Package integrity failed. Do not distribute partial output.' }
Assert-Checkout
Write-Host 'VC094G_PACKAGE=BUILT_INTEGRITY_CHECKED_NOT_ACCEPTED'
