#Requires -Version 5.1
# Reproducible owner-local CEM50 native smoke from the pinned, successful development artifact.
# Read-only Windows x86 J2534, no adapter installation, no original VIDA/physical ECU.
[CmdletBinding()]
param(
    [string]$ArtifactZip,
    [string]$OutputDirectory = (Join-Path $env:TEMP ('J2534-CEM50-Smoke-' + [guid]::NewGuid().ToString('N')))
)
$ErrorActionPreference = 'Stop'
$repo = 'vorlocsev/virtualcar'
$runId = '44669574171'
$artifactName = 'virtualcar-vmware-lab-9553d87d400f9baf80fa16fb4a30d163551a6bbb-attempt-1'
$expectedBase = '9553d87d400f9baf80fa16fb4a30d163551a6bbb'
$zipSha = '45BF8F6E672272B64A18183B268484BF86DA65AB5B652384C2BE1FBE85ADC695'
$dllSha = 'C636BAF8C66266BCA80009A2EFBC729F0D6DB00A3A7BE1384068F5E180F01528'
$probe = Join-Path $PSScriptRoot 'Verify-J2534CEM50.ps1'
if (-not (Test-Path -LiteralPath $probe -PathType Leaf)) { throw 'Local exact-profile CEM50 smoke missing' }
$dir = [IO.Path]::GetFullPath($OutputDirectory)
if ([IO.Directory]::Exists($dir) -or [IO.File]::Exists($dir)) {
    throw 'Output directory already exists: refusing overwrite'
}
[void][IO.Directory]::CreateDirectory($dir)
$download = Join-Path $dir 'source-artifact'
[void][IO.Directory]::CreateDirectory($download)
if ($ArtifactZip) {
    $archive = (Resolve-Path -LiteralPath $ArtifactZip -ErrorAction Stop).Path
    if ($archive -notmatch '\.zip$') { throw 'Local artifact input must be a ZIP' }
    Expand-Archive -LiteralPath $archive -DestinationPath $download
    Write-Host 'LOCAL_ARTIFACT: expanding retained GitHub Actions archive'
} else {
    $gh = Get-Command gh -ErrorAction Stop
    & $gh.Source run download $runId --repo $repo --name $artifactName --dir $download
    if ($LASTEXITCODE -ne 0) { throw 'GitHub artifact download failed (gh auth required)' }
}
$package = Join-Path $download 'VirtualCar-VMware-LAB-ci-9553d87d400f-Windows-x86.zip'
if (-not (Test-Path -LiteralPath $package -PathType Leaf)) { throw 'Expected pinned LAB ZIP missing' }
if ((Get-FileHash -LiteralPath $package -Algorithm SHA256).Hash -cne $zipSha) {
    throw 'Trusted development LAB ZIP SHA256 mismatch'
}
$unpacked = Join-Path $dir 'unpacked'
Expand-Archive -LiteralPath $package -DestinationPath $unpacked
$lab = Join-Path $unpacked 'VirtualCar-VMware-LAB'
$buildinfo = Join-Path $lab 'BUILDINFO.json'
if (-not (Test-Path -LiteralPath $buildinfo -PathType Leaf)) { throw 'Trusted BUILDINFO missing' }
$build = Get-Content -LiteralPath $buildinfo -Raw | ConvertFrom-Json
if ($build.source_commit -cne $expectedBase -or $build.architecture -cne 'windows-x86-pe32') {
    throw 'Unexpected source commit or DLL architecture'
}
$dll = Join-Path $lab 'VirtualCarJ2534.dll'
if (-not (Test-Path -LiteralPath $dll -PathType Leaf) -or
    (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -cne $dllSha) {
    throw 'Trusted x86 DLL SHA256 mismatch'
}
Write-Host 'PINNED_ARTIFACT_VERIFIED: development SHA, nested ZIP and DLL'
$smokeOut = Join-Path $dir 'cem50-native'
& "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $probe -DllPath $dll -ExpectedSha256 $dllSha -OutputDirectory $smokeOut
if ($LASTEXITCODE -ne 0) { throw 'CEM50 native x86 smoke failed' }
$reportPath = Join-Path $smokeOut 'native-check.json'
if (-not (Test-Path -LiteralPath $reportPath -PathType Leaf)) { throw 'Native report missing' }
$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
if ($report.status -cne 'CEM50_NATIVE_PASS' -or
    [int]$report.actual_matched_frame_count -ne 13 -or
    $report.published_vin -cne 'YV1CR855691511566' -or
    $report.vida_readvin_verified -ne $false -or
    $report.physical_adapter_used -ne $false) {
    throw 'Native evidence mismatch'
}
Write-Host 'CEM50_NATIVE_PASS: 13/13 exact frames, no Registry32 or original VIDA used'
Write-Host "Result: $reportPath"
