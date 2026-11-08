# One-time OWNER-LOCAL installer for private VIDA offline SQLite files.
# Run on the Windows VMware guest, not in GitHub Actions. Does not call SQL,
# GitHub API or copy original data to the repository or artifacts.
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$SourceFolder,
    [Parameter(Mandatory = $true)][string]$ValidatorZip,
    [string]$DestinationFolder = 'E:\VirtualCar\VIDA-private',
    [string]$ToolsFolder = 'E:\VirtualCar\VIDA-tools',
    [switch]$ConfigureRunnerService
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$names = @(
    'DiagSwdlRepository', 'CarCom', 'BaseData', 'DiagSwdlSession',
    'DiceTiming', 'ImageRepository', 'EPC', 'servicerep_ru-RU',
    'AccessServer'
)

function FullPath([string]$path) {
    return [IO.Path]::GetFullPath($path).TrimEnd('\', '/')
}

$source = FullPath $SourceFolder
$destination = FullPath $DestinationFolder
$tools = FullPath $ToolsFolder
$pythonManifest = 'E:\VirtualCar\Tools\python312.path'

if ($source -eq $destination) {
    throw 'Source and destination directories must differ.'
}
if ($destination -match '(?i)[\/]_work([\/]|$)' -or
    $destination -match '(?i)[\/]\.git([\/]|$)') {
    throw 'Refusing to store private data inside a GitHub workspace.'
}
if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw 'Source directory not accessible. Connect the local VMware share first.'
}
if (Test-Path -LiteralPath $destination) {
    throw 'Destination already exists; refusing overwrite or partial reuse.'
}
if (-not (Test-Path -LiteralPath $ValidatorZip -PathType Leaf)) {
    throw 'Local offline validator ZIP not found.'
}
if (-not (Test-Path -LiteralPath $pythonManifest -PathType Leaf)) {
    throw 'Existing VMware runner Python manifest not found.'
}
$python = (Get-Content -LiteralPath $pythonManifest -Raw).Trim()
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Runner Python executable not found.'
}

$expected = @()
[long]$sourceBytes = 0
foreach ($name in $names) {
    foreach ($suffix in @('.sqlite', '.manifest.json')) {
        $item = Get-Item -LiteralPath (Join-Path $source ($name + $suffix)) -ErrorAction Stop
        if ($item.PSIsContainer -or
            (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0)) {
            throw 'Input must be a regular file, not a directory or reparse point.'
        }
        $sourceBytes += $item.Length
        $expected += $item.Name
    }
}

$destinationParent = Split-Path -Parent $destination
if (-not (Test-Path -LiteralPath $destinationParent -PathType Container)) {
    throw 'Destination drive parent does not exist. Verify E:\VirtualCar.'
}
$driveRoot = [IO.Path]::GetPathRoot($destination)
$drive = [IO.DriveInfo]::new($driveRoot)
if ($drive.AvailableFreeSpace -lt ($sourceBytes + 1GB)) {
    throw 'Insufficient disk space for the private SQLite copies and safety margin.'
}

if (-not (Test-Path -LiteralPath $tools -PathType Container)) {
    New-Item -ItemType Directory -Path $tools -Force | Out-Null
}
$validator = Join-Path $tools 'verify_offline_collection.py'
if (-not (Test-Path -LiteralPath $validator -PathType Leaf)) {
    if (Test-Path -LiteralPath (Join-Path $tools 'verify_vida_sqlite.py')) {
        throw 'Tools directory is partially initialized; inspect it manually.'
    }
    Expand-Archive -LiteralPath $ValidatorZip -DestinationPath $tools
}
foreach ($required in @('verify_offline_collection.py', 'verify_vida_sqlite.py',
                        'export_vida_sqlite.py')) {
    if (-not (Test-Path -LiteralPath (Join-Path $tools $required) -PathType Leaf)) {
        throw 'Offline validator package incomplete.'
    }
}

$stage = Join-Path $destinationParent (
    'VIDA-private.staging-' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    foreach ($file in $expected) {
        # Each file is copied just once. No source records are printed.
        Copy-Item -LiteralPath (Join-Path $source $file) -Destination $stage -ErrorAction Stop
        Write-Host ('Copied private file: ' + $file)
    }
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python $validator --folder $stage
    if ($LASTEXITCODE -ne 0) {
        throw 'SQLite integrity, row-count or SHA-256 verification failed.'
    }
    Move-Item -LiteralPath $stage -Destination $destination -ErrorAction Stop
    Write-Host 'SUCCESS: Nine VIDA SQLite databases verified and placed outside the GitHub checkout.'
} catch {
    # A failed transfer is intentionally left staged for local inspection.
    # Never overwrite an existing live dataset to "resume" silently.
    Write-Warning 'Installation incomplete. Source unchanged. Inspect staging directory locally.'
    throw
}

$services = @(Get-CimInstance Win32_Service |
    Where-Object { $_.Name -like 'actions.runner.*' })
if ($services.Count -eq 0) {
    Write-Warning 'No actions.runner.* Windows service. If you use run.cmd, reconfigure the runner as a Windows service.'
} else {
    foreach ($svc in $services) {
        if ($ConfigureRunnerService) {
            Set-Service -Name $svc.Name -StartupType Automatic
            if ($svc.State -ne 'Running') {
                Start-Service -Name $svc.Name
            }
        }
    }
    $services = @(Get-CimInstance Win32_Service |
        Where-Object { $_.Name -like 'actions.runner.*' })
    foreach ($svc in $services) {
        Write-Host ("Runner service state: {0}; startup: {1}" -f $svc.State, $svc.StartMode)
    }
}
Write-Host 'NOTE: Auto-starting the Windows runner service does not power on a stopped VMware guest.'
