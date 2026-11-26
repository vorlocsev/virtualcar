# Run inside the unlocked, interactive VMware Windows guest. No CI dispatch.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][ValidateSet('Demo','OwnerLocal')][string]$Scope,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$PythonExe,
    [string]$BashExe,
    [string]$PrivateDirectory,
    [string]$ArtworkSourceDirectory,
    [switch]$SkipArtwork,
    [switch]$CaptureScreenshots
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or
    -not [Environment]::UserInteractive -or [Diagnostics.Process]::GetCurrentProcess().SessionId -eq 0) {
    throw 'Interactive Windows x64 user session required.'
}
if (($Scope -eq 'OwnerLocal') -ne [bool]$PrivateDirectory) { throw 'Invalid private scope.' }
if ([bool]$SkipArtwork -eq [bool]$ArtworkSourceDirectory) { throw 'Explicit artwork policy required.' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$actual = (& git -C $repo rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $actual -ne $ExpectedSha) { throw 'Exact HEAD required.' }
$dirty = @(& git -C $repo status --porcelain --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean checkout required.' }
if (-not $PythonExe) {
    $PythonExe = (Get-Content -LiteralPath 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
}
if ($PythonExe -notmatch '^[A-Za-z]:[\\/]' -or -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw 'Absolute Python executable required.'
}
if ($OutputDirectory -notmatch '^[A-Za-z]:[\\/]') { throw 'Absolute output required.' }
$out = [IO.Path]::GetFullPath($OutputDirectory)
if ($out.Length -gt 130 -or $out -match '[^\x20-\x7E]' -or
    [IO.DriveInfo]::new([IO.Path]::GetPathRoot($out)).DriveType -ne [IO.DriveType]::Fixed -or
    (Test-Path -LiteralPath $out)) { throw 'New short local fixed-drive output required.' }
$cursor = Get-Item -LiteralPath (Split-Path -Parent $out)
while ($null -ne $cursor) {
    if ($cursor -isnot [IO.DirectoryInfo] -or
        ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git'))) { throw 'Unsafe output ancestry.' }
    $cursor = $cursor.Parent
}
[void](New-Item -ItemType Directory -Path $out)
$run = Join-Path $out 'run'
$transcript = Join-Path $out 'guest-transcript.txt'
$report = [ordered]@{schema='vc096a-guest-evidence-v1';source_sha=$ExpectedSha;scope=$Scope;
    status='fail';failure_type='';screenshots='not_tested';offline_report_sha256='';
    registration='not_tested';original_vida='not_tested';sectorv='not_tested';vdash='not_tested';
    physical_j2534='not_tested';visual_review='not_tested';release_ready=$false}
$started = $false
try {
    Start-Transcript -LiteralPath $transcript -NoClobber | Out-Null
    $started = $true
    $argsRun = @{ExpectedSha=$ExpectedSha;Scope=$Scope;OutputDirectory=$run;PythonExe=$PythonExe;
        SkipArtwork=$SkipArtwork;CaptureScreenshots=$CaptureScreenshots}
    if ($BashExe) { $argsRun.BashExe=$BashExe }
    if ($PrivateDirectory) { $argsRun.PrivateDirectory=$PrivateDirectory }
    if ($ArtworkSourceDirectory) { $argsRun.ArtworkSourceDirectory=$ArtworkSourceDirectory }
    & (Join-Path $PSScriptRoot 'Invoke-VC096IntegratedAcceptance.ps1') @argsRun
    $path = Join-Path $run 'vc096-integrated-offline.json'
    $result = Get-Content -LiteralPath $path -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($result.schema -ne 'vc096-integrated-offline-v1' -or $result.source_sha -ne $ExpectedSha -or
        $result.scope -ne $Scope -or $result.status -ne 'pass' -or $result.offline_gates -ne 8 -or
        $result.release_ready -ne $false) { throw 'Integrated result incomplete.' }
    $report.offline_report_sha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
    $report.screenshots = $result.screenshots
    $report.status = 'pass'
} catch {
    $report.failure_type = $_.Exception.GetType().Name
    throw
} finally {
    if ($started) {
        try { Stop-Transcript | Out-Null }
        catch { $report.status='fail'; $report.failure_type='TranscriptFailure'; throw }
        finally {
            $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out 'vc096a-guest-evidence.json') -Encoding UTF8
        }
    } else {
        $report | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $out 'vc096a-guest-evidence.json') -Encoding UTF8
    }
}
Write-Host 'VC096A_GUEST_OFFLINE=PASS'
Write-Host 'VC096A_RUNTIME_ACCEPTANCE=NOT_TESTED'
