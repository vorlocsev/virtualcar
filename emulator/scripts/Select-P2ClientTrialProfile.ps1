# Select one research P2 fixture for a SINGLE controlled Windows x86 client run.
# This writes only the sidecar virtualcar.ini. It never launches SectorV,
# VDASH, uploads traces, touches the J2534 registry, or operates a real ECU.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('A_NoD2','B_PublicB9FB','C_MixedB9FB_B9F0')]
    [string]$Variant,
    [switch]$IConfirmClientsClosed,
    [switch]$IUnderstandExperimentalDonorData,
    [switch]$EnableCompositeReplay
)
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
if (-not $IConfirmClientsClosed) {
    throw 'Confirm all clients and VirtualCarControl are CLOSED before replacing the sidecar INI'
}
if ($Variant -ne 'A_NoD2' -and -not $IUnderstandExperimentalDonorData) {
    throw 'Donor/MIXED replies are not XC90 MY2009. Explicit laboratory acknowledgement required'
}
if ($EnableCompositeReplay -and $Variant -ne 'C_MixedB9FB_B9F0') {
    throw 'Composite replay permission is valid ONLY for the mixed laboratory variant'
}
foreach ($processName in @('SectorV','VDASH','VirtualCarControl')) {
    if (@(Get-Process -Name $processName -ErrorAction SilentlyContinue).Count -gt 0) {
        throw 'A diagnostic client or VirtualCarControl is still running'
    }
}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$map=@{
    A_NoD2='p2-trial-00-no-d2.ini'
    B_PublicB9FB='p2-trial-01-public-b9fb-only.ini'
    C_MixedB9FB_B9F0='p2-trial-02-mixed-b9fb-b9f0-locked.ini'
}
$src=Join-Path (Join-Path $root 'profiles') $map[$Variant]
$target=Join-Path $root 'virtualcar.ini'
if (-not [IO.File]::Exists($src) -or -not [IO.File]::Exists($target)) {
    throw 'The extracted LAB bundle is missing its source profile or main virtualcar.ini'
}
if ([IO.Path]::GetFullPath($src) -eq [IO.Path]::GetFullPath($target)) {
    throw 'Source and installed profile must be different'
}
$sourceText=[IO.File]::ReadAllText($src)
if ($sourceText -notmatch '(?m)^; A/B/C controlled native J2534 client trial') {
    throw 'Source does not contain a recognized experimental-trial header'
}
$has13=[regex]::Matches($sourceText,'(?m)^B9FBFrame[0-9A-F]=') # profiles preserve spacing, see next check
$raw13=[regex]::Matches($sourceText,'(?m)^B9FBFrame[0-9A-F]\s*=')
$raw3=[regex]::Matches($sourceText,'(?m)^Frame[0-2]\s*=')
if ($Variant -eq 'A_NoD2' -and
    ($raw13.Count -ne 0 -or $raw3.Count -ne 0 -or $sourceText -notmatch '(?m)^B9FBFrameCount=0$')) {
    throw 'Baseline fixture is not empty'
}
if ($Variant -ne 'A_NoD2' -and
    ($raw13.Count -ne 13 -or $sourceText -notmatch '(?m)^B9FBFrameCount=13$')) {
    throw 'Donor B9FB fingerprint does not match the reviewed 13-frame LAB variant'
}
if ($Variant -eq 'C_MixedB9FB_B9F0') {
    if ($raw3.Count -ne 3 -or
        $sourceText -notmatch '(?m)^FixtureProvenance=local_composite_unverified_trace_import$' -or
        $sourceText -notmatch '(?m)^AllowCompositeReplay=0$') {
        throw 'Mixed source provenance or conservative replay lock is missing'
    }
    if ($EnableCompositeReplay) {
        # This applies only to the locally installed output. The
        # DISTRIBUTED mixed fixture stays LOCKED on disk.
        $sourceText=[regex]::Replace(
            $sourceText,'(?m)^AllowCompositeReplay=0$','AllowCompositeReplay=1')
    }
} elseif ($raw3.Count -ne 0) {
    throw 'B9F0 fixture is prohibited outside the mixed trial'
}
if ($sourceText.Length -lt 100 -or $sourceText.Length -gt 262144) {
    throw 'Invalid profile size'
}
# Every change is restorable. No original profile or backup is packaged
# into SAFE-JSON-REPORTS, written to the repository, or uploaded.
$backupRoot=Join-Path $env:LOCALAPPDATA 'VirtualCar\TrialProfileBackups'
[void][IO.Directory]::CreateDirectory($backupRoot)
$backup=Join-Path $backupRoot ('original-'+[guid]::NewGuid().ToString('N')+'.ini')
[IO.File]::Copy($target,$backup,$false)
$temp=Join-Path $root ('virtualcar.ini.new-'+[guid]::NewGuid().ToString('N'))
# System.IO.File.Replace requires a NONEMPTY backup filename on some
# Windows/.NET builds. Use a unique SAME-VOLUME intermediate for the
# atomic replace. The durable user backup was already made in LOCALAPPDATA.
$replaceBackup=Join-Path $root ('virtualcar.ini.atomic-backup-'+[guid]::NewGuid().ToString('N'))
try {
    [IO.File]::WriteAllText($temp,$sourceText,(New-Object System.Text.UTF8Encoding($false)))
    [IO.File]::Replace($temp,$target,$replaceBackup)
} finally {
    if ([IO.File]::Exists($temp)) {[IO.File]::Delete($temp)}
    if ([IO.File]::Exists($replaceBackup)) {[IO.File]::Delete($replaceBackup)}
}
$hash=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host "READY: $Variant; sidecar profile SHA256=$hash"
if ($Variant -eq 'C_MixedB9FB_B9F0') {
    Write-Host $(if ($EnableCompositeReplay) {
        'LAB ONLY: unverified mixed B9FB/B9F0 replay EXPLICITLY enabled'
    } else {
        'SAFE DEFAULT: unverified mixed B9FB/B9F0 replay remains BLOCKED'
    })
}
Write-Host 'Private backup created locally. Never share profile backups or raw logs.'
Write-Host 'Run Capture-P2ClientRun.ps1 -Phase Begin in a NEW session directory before launching the client.'
