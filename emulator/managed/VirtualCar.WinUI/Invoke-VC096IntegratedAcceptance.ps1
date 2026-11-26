# VC096: integrated exact-head Windows package build and offline acceptance.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][ValidateSet('Demo','OwnerLocal')][string]$Scope,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [string]$BashExe,
    [string]$PrivateDirectory,
    [string]$ArtworkSourceDirectory,
    [switch]$SkipArtwork,
    [switch]$CaptureScreenshots
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or
    -not [Environment]::UserInteractive) { throw 'Interactive Windows x64 required.' }
if (($Scope -eq 'OwnerLocal') -ne [bool]$PrivateDirectory) { throw 'PrivateDirectory required only for OwnerLocal.' }
if ([bool]$SkipArtwork -eq [bool]$ArtworkSourceDirectory) { throw 'Select local artwork source or explicit SkipArtwork.' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
function Assert-Source {
    $head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'Exact HEAD required.' }
    $dirty = @(& git -C $repo status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean checkout required.' }
}
Assert-Source
if ($OutputDirectory -notmatch '^[A-Za-z]:[\\/]') { throw 'Absolute local output required.' }
$out = [IO.Path]::GetFullPath($OutputDirectory)
if ($out.Length -gt 145 -or $out -match '[^\x20-\x7E]' -or
    [IO.DriveInfo]::new([IO.Path]::GetPathRoot($out)).DriveType -ne [IO.DriveType]::Fixed -or
    (Test-Path -LiteralPath $out)) { throw 'New short ASCII fixed-drive output required.' }
$cursor = Get-Item -LiteralPath (Split-Path -Parent $out)
while ($null -ne $cursor) {
    if ($cursor -isnot [IO.DirectoryInfo] -or
        ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git'))) { throw 'Unsafe output ancestry.' }
    $cursor = $cursor.Parent
}
# No public ZIP, adapter installation, diagnostic-client launch or upload.
[void](New-Item -ItemType Directory -Path $out)
$packageBuild = Join-Path $out 'package-build'
$acceptance = Join-Path $out 'acceptance'
$buildArgs = @{ExpectedSha=$ExpectedSha;OutputDirectory=$packageBuild;PythonExe=$PythonExe}
if ($BashExe) { $buildArgs.BashExe = $BashExe }
if ($PrivateDirectory) { $buildArgs.PrivateDirectory = $PrivateDirectory }
if ($ArtworkSourceDirectory) { $buildArgs.ArtworkSourceDirectory = $ArtworkSourceDirectory }
if ($SkipArtwork) { $buildArgs.SkipArtwork = $true }
& (Join-Path $PSScriptRoot 'Build-VC094Package.ps1') @buildArgs
Assert-Source
$checkArgs = @{ExpectedSha=$ExpectedSha;PackageBuildDirectory=$packageBuild;OutputDirectory=$acceptance;
    PythonExe=$PythonExe;ExpectedScope=$Scope;RequireArtwork=(-not $SkipArtwork);CaptureScreenshots=$CaptureScreenshots}
& (Join-Path $PSScriptRoot 'Test-VC095PackageAcceptance.ps1') @checkArgs
Assert-Source
$reportPath = Join-Path $acceptance 'vc095-offline-acceptance.json'
$result = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
$expectedGates = @('source','package_before','core','python_target','python_full','compileall','normal_home_smoke','final_integrity')
if ($result.schema -ne 'vc095-offline-acceptance-v1' -or $result.source_sha -ne $ExpectedSha -or
    $result.status -ne 'pass' -or $result.package_scope -ne $Scope -or $result.home_refresh -ne 'pass' -or
    $result.release_ready -ne $false -or $result.registration -ne 'not_tested' -or
    $result.original_vida -ne 'not_tested' -or $result.physical_j2534 -ne 'not_tested' -or
    $result.visual_review -ne 'not_tested' -or $result.private_editor_interaction -ne 'not_tested') {
    throw 'Offline acceptance evidence incomplete or contradictory.'
}
$gateNames = @($result.gates.PSObject.Properties.Name)
if ($gateNames.Count -ne $expectedGates.Count) { throw 'Unexpected gate count.' }
foreach ($gate in $expectedGates) {
    if ($gateNames -cnotcontains $gate -or $result.gates.$gate -ne 'pass') { throw 'Offline gate not passed.' }
}
$expectedCapture = if ($CaptureScreenshots) { 'captured_not_reviewed' } else { 'not_requested' }
if ($result.screenshots -ne $expectedCapture) { throw 'Unexpected screenshot scope.' }
$expectedArtwork = if ($SkipArtwork) { 'skipped' } else { 'two_reference_photos' }
if ($result.artwork -ne $expectedArtwork) { throw 'Unexpected artwork scope.' }
[ordered]@{schema='vc096-integrated-offline-v1';source_sha=$ExpectedSha;scope=$Scope;
    status='pass';offline_gates=8;home_refresh='pass';artwork=$result.artwork;screenshots=$result.screenshots;
    acceptance_sha256=(Get-FileHash -LiteralPath $reportPath -Algorithm SHA256).Hash.ToLowerInvariant();
    registration='not_tested';original_vida='not_tested';sectorv='not_tested';vdash='not_tested';
    physical_j2534='not_tested';visual_review='not_tested';private_editor_interaction='not_tested';release_ready=$false} |
    ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out 'vc096-integrated-offline.json') -Encoding UTF8
Write-Host 'VC096_INTEGRATED_OFFLINE=PASS 8/8'
Write-Host 'VC096_RUNTIME_ACCEPTANCE=NOT_TESTED'
