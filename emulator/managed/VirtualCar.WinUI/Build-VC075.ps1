# VC075: owner-local build/optional empty-window smoke. No provider or private inputs.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$LaunchSmoke
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem) {
    throw 'Windows x64 is required.'
}
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$project = Join-Path $PSScriptRoot 'VirtualCar.WinUI.csproj'
function GitText([string[]]$Arguments) {
    $result = @(& git -C $repo @Arguments)
    if ($LASTEXITCODE -ne 0) { throw 'Git preflight failed.' }
    return ($result -join [Environment]::NewLine).Trim()
}
$head = GitText @('rev-parse','HEAD')
if ($head -ne $ExpectedSha) { throw 'Exact HEAD mismatch.' }
if (GitText @('status','--porcelain','--untracked-files=all')) { throw 'Clean checkout required.' }
if ($OutputDirectory -notmatch '^[a-zA-Z]:[\\/]') { throw 'Absolute local output path required.' }
$out = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $out) { throw 'Output directory must not already exist.' }
$parent = Split-Path -Parent $out
if (-not (Test-Path -LiteralPath $parent -PathType Container)) { throw 'Output parent must exist.' }
$cursor = Get-Item -LiteralPath $parent
while ($null -ne $cursor) {
    if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse-point output ancestry is not supported.' }
    if (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git')) { throw 'Output must be outside Git checkouts.' }
    $cursor = $cursor.Parent
}
$dotnet = (Get-Command dotnet -CommandType Application | Select-Object -First 1).Source
Push-Location $repo
try {
    $sdk = (& $dotnet --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $sdk -notmatch '^10\.0\.\d+$') { throw '.NET 10 stable SDK is required.' }
    Write-Host "VC075_HEAD=$head"
    Write-Host "VC075_DOTNET_SDK=$sdk"
    [void](New-Item -ItemType Directory -Path $out)
    $publish = Join-Path $out 'app'
    $log = Join-Path $out 'publish.log'
    $publishArgs = @('publish',$project,'-c','Release','-r','win-x64','--self-contained','true',
        '-p:Platform=x64','-p:PublishSingleFile=false','-p:PublishTrimmed=false',
        '-p:PublishReadyToRun=false','-p:PublishAot=false','-o',$publish)
    # Keep native Windows App SDK dependencies as separate files.
    & $dotnet @publishArgs *> $log
    if ($LASTEXITCODE -ne 0) { throw 'Publish failed. See local publish.log.' }
    $toolProject = Join-Path $PSScriptRoot '..\VirtualCar.DriverTool\VirtualCar.DriverTool.csproj'
    $toolOut = Join-Path $publish 'driver-tools'
    $toolLog = Join-Path $out 'driver-tool-publish.log'
    $toolArgs = @('publish',$toolProject,'-c','Release','-r','win-x64','--self-contained','true',
        '-p:PublishSingleFile=false','-p:PublishTrimmed=false','-p:PublishAot=false','-o',$toolOut)
    & $dotnet @toolArgs *> $toolLog
    if ($LASTEXITCODE -ne 0) { throw 'Driver tool publish failed. See local driver-tool-publish.log.' }
}
finally { Pop-Location }
function Assert-Amd64([string]$Path) {
    $stream = [IO.File]::OpenRead($Path)
    $reader = $null
    try {
        $reader = New-Object IO.BinaryReader($stream)
        if ($stream.Length -lt 64 -or $reader.ReadUInt16() -ne 0x5A4D) { throw 'Invalid DOS header.' }
        $stream.Position = 60
        $offset = $reader.ReadInt32()
        if ($offset -lt 64 -or $offset -gt ($stream.Length - 26)) { throw 'Invalid PE offset.' }
        $stream.Position = $offset
        if ($reader.ReadUInt32() -ne 0x4550 -or $reader.ReadUInt16() -ne 0x8664) { throw 'Not an AMD64 PE.' }
        $stream.Position = $offset + 24
        if ($reader.ReadUInt16() -ne 0x20B) { throw 'Not a PE32+ executable.' }
    }
    finally { if ($null -ne $reader) { $reader.Dispose() } else { $stream.Dispose() } }
}
$exe = Join-Path $publish 'VirtualCar.WinUI.exe'
foreach ($name in @('VirtualCar.WinUI.exe','Microsoft.UI.Xaml.dll','coreclr.dll','hostfxr.dll','hostpolicy.dll')) {
    $file = Join-Path $publish $name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing runtime file: $name" }
    Assert-Amd64 $file
}
foreach ($name in @('VirtualCar.WinUI.dll','VirtualCar.Core.dll','VirtualCar.WinUI.deps.json','VirtualCar.WinUI.runtimeconfig.json')) {
    if (-not (Test-Path -LiteralPath (Join-Path $publish $name) -PathType Leaf)) { throw "Missing managed file: $name" }
}
Assert-Amd64 (Join-Path $publish 'driver-tools\VirtualCar.DriverTool.exe')
foreach ($name in @('VirtualCar.DriverTool.dll','VirtualCar.DriverTool.deps.json','VirtualCar.DriverTool.runtimeconfig.json','coreclr.dll')) {
    if (-not (Test-Path -LiteralPath (Join-Path $publish ('driver-tools\' + $name)) -PathType Leaf)) {
        throw "Missing driver tool runtime file: $name"
    }
}
if (GitText @('status','--porcelain','--untracked-files=all')) { throw 'Build altered the clean checkout.' }
if ((GitText @('rev-parse','HEAD')) -ne $head) { throw 'HEAD changed during build.' }
$files = @(Get-ChildItem -LiteralPath $publish -Recurse -File | Sort-Object FullName | ForEach-Object {
    [ordered]@{
        path = $_.FullName.Substring($publish.Length + 1).Replace('\','/')
        bytes = $_.Length
        sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    }
})
$smoke = 'not_tested'
if ($LaunchSmoke) {
    $process = Start-Process -FilePath $exe -WorkingDirectory $publish -ArgumentList '--ephemeral-settings' -PassThru
    try {
        $watch = [Diagnostics.Stopwatch]::StartNew()
        $handle = [IntPtr]::Zero
        while ($watch.Elapsed.TotalSeconds -lt 20) {
            $process.Refresh()
            if ($process.HasExited) { throw 'Application exited before showing a window.' }
            $handle = $process.MainWindowHandle
            if ($handle -ne [IntPtr]::Zero) { break }
            Start-Sleep -Milliseconds 200
        }
        if ($handle -eq [IntPtr]::Zero) { throw 'No main window within 20 seconds.' }
        Start-Sleep -Milliseconds 1000
        $process.Refresh()
        if ($process.HasExited) { throw 'Application exited during empty-window smoke.' }
        $smoke = 'window_present'
    }
    finally {
        try {
            $process.Refresh()
            if (-not $process.HasExited) {
                [void]$process.CloseMainWindow()
                if (-not $process.WaitForExit(5000)) {
                    $process.Kill()
                    [void]$process.WaitForExit(5000)
                    throw 'Application did not close normally.'
                }
            }
        }
        finally { $process.Dispose() }
    }
}
$report = [ordered]@{
    schema = 'vc075-winui-build-v1'
    source_sha = $head
    sdk = $sdk
    platform = 'win-x64'
    publish = 'pass'
    native_pe = 'amd64'
    launch_smoke = $smoke
    bilingual_ui = 'not_tested'
    private_preview = 'not_tested'
    vida = 'not_tested'
    physical_j2534 = 'not_tested'
    files = $files
}
$report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'build-manifest.json') -Encoding UTF8
Write-Host 'VC075_PUBLISH=PASS'
Write-Host "VC075_LAUNCH=$smoke"
Write-Host 'VC075_BILINGUAL_UI=NOT_TESTED'
Write-Host 'VC075_PRIVATE_PREVIEW=NOT_TESTED'
