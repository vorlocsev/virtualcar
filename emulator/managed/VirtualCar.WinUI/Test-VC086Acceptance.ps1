# VC086: exact-head owner-local synthetic build and interactive empty-window acceptance.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or
    -not [Environment]::UserInteractive) { throw 'Interactive Windows x64 required.' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
function GitText([string[]]$Arguments) {
    $value = @(& git -C $repo @Arguments)
    if ($LASTEXITCODE -ne 0) { throw 'Git preflight failed.' }
    return ($value -join [Environment]::NewLine).Trim()
}
function Assert-Checkout {
    if ((GitText @('rev-parse','HEAD')) -ne $ExpectedSha -or
        (GitText @('status','--porcelain','--untracked-files=all'))) {
        throw 'Exact clean checkout required.'
    }
}
Assert-Checkout
if ($OutputDirectory -notmatch '^[a-zA-Z]:[\\/]') { throw 'Absolute local output path required.' }
$out = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $out) { throw 'Output directory already exists.' }
$drive = [IO.DriveInfo]::new([IO.Path]::GetPathRoot($out))
if ($drive.DriveType -ne [IO.DriveType]::Fixed) { throw 'Fixed local drive required.' }
$cursor = Get-Item -LiteralPath (Split-Path -Parent $out)
if (-not $cursor.PSIsContainer) { throw 'Output parent must be a directory.' }
while ($null -ne $cursor) {
    if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git'))) {
        throw 'Output must be outside Git and reparse-point ancestry.'
    }
    $cursor = $cursor.Parent
}
$dotnet = (Get-Command dotnet -CommandType Application | Select-Object -First 1).Source
[void](New-Item -ItemType Directory -Path $out)
$gates = [ordered]@{
    exact_checkout = 'pass'
    core_checks = 'not_tested'
    winui_publish = 'not_tested'
    empty_window = 'not_tested'
    bilingual_navigation = 'not_tested'
    journal_switch = 'not_tested'
    empty_mode_lockout = 'not_tested'
    final_integrity = 'not_tested'
}
$report = [ordered]@{
    schema = 'vc086-integrated-acceptance-v1'
    source_sha = $ExpectedSha.ToLowerInvariant()
    sdk = 'not_tested'
    platform = 'win-x64'
    status = 'fail'
    failed_stage = ''
    gates = $gates
    owner_checks = [ordered]@{
        private_cem_preview = 'not_tested'
        driver_install_remove = 'not_tested'
        profile_apply_restore = 'not_tested'
        native_ignition = 'not_tested'
        ecu_inventory = 'not_tested'
        live_log_monitor = 'not_tested'
        loaded_profile_ui = 'not_tested'
        layout_dpi = 'not_tested'
        vida_readvin = 'not_tested'
        vida_t111 = 'not_tested'
        vida_t122 = 'not_tested'
        physical_j2534 = 'not_tested'
    }
}
$stage = 'core_checks'
Push-Location $repo
try {
    $sdk = (& $dotnet --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $sdk -notmatch '^10\.0\.\d+$') { throw '.NET 10 stable SDK required.' }
    $report.sdk = $sdk
    $coreLog = Join-Path $out 'core-checks.log'
    $core = Join-Path $PSScriptRoot '..\VirtualCar.Core.Checks\VirtualCar.Core.Checks.csproj'
    & $dotnet run --project $core -c Release *> $coreLog
    if ($LASTEXITCODE -ne 0) { throw 'Managed core checks failed.' }
    $summary = @(Get-Content -LiteralPath $coreLog | Where-Object {
        $_ -match '^VirtualCar\.Core synthetic checks: (\d+)/(\d+)$'
    })
    if ($summary.Count -ne 1 -or $summary[0] -notmatch '^VirtualCar\.Core synthetic checks: (\d+)/(\d+)$' -or
        [int]$Matches[1] -ne [int]$Matches[2] -or [int]$Matches[2] -lt 80) {
        throw 'Managed check summary incomplete or below expected minimum.'
    }
    $report['core_summary'] = $summary[0]
    $gates.core_checks = 'pass'
    Assert-Checkout
    $stage = 'winui_publish'
    $build = Join-Path $out 'build'
    & (Join-Path $PSScriptRoot 'Build-VC075.ps1') -ExpectedSha $ExpectedSha -OutputDirectory $build -LaunchSmoke *> (Join-Path $out 'build.log')
    $manifest = Get-Content -LiteralPath (Join-Path $build 'build-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($manifest.schema -ne 'vc075-winui-build-v1' -or $manifest.source_sha -ne $ExpectedSha -or
        $manifest.platform -ne 'win-x64' -or $manifest.publish -ne 'pass' -or $manifest.native_pe -ne 'amd64') {
        throw 'Publish manifest mismatch.'
    }
    $gates.winui_publish = 'pass'
    $stage = 'empty_window'
    if ($manifest.launch_smoke -ne 'window_present') { throw 'Launch smoke missing.' }
    $gates.empty_window = 'pass'
    $stage = 'bilingual_navigation'
    $uiLog = Join-Path $out 'ui-smoke.log'
    & (Join-Path $PSScriptRoot 'Test-VC075Language.ps1') -ExpectedSha $ExpectedSha -BuildDirectory $build *> $uiLog
    $ui = @(Get-Content -LiteralPath $uiLog)
    if ($ui -notcontains "VC075_SOURCE_SHA=$ExpectedSha" -or
        $ui -notcontains 'VC075_EMPTY_UI_LANG=PASS 3/3' -or
        $ui -notcontains 'VC077_EMPTY_NAVIGATION=PASS 15/15') { throw 'Bilingual navigation evidence missing.' }
    $gates.bilingual_navigation = 'pass'
    $stage = 'journal_switch'
    if ($ui -notcontains 'VC086_EMPTY_JOURNAL=PASS 3/3') { throw 'Journal switching evidence missing.' }
    $gates.journal_switch = 'pass'
    $stage = 'empty_mode_lockout'
    if ($ui -notcontains 'VC086_EMPTY_LOCKOUT=PASS') { throw 'Empty mode lockout evidence missing.' }
    $gates.empty_mode_lockout = 'pass'
    $stage = 'final_integrity'
    Assert-Checkout
    $app = Join-Path $build 'app'
    $files = @(Get-ChildItem -LiteralPath $app -Recurse -File)
    if ($files.Count -ne @($manifest.files).Count) { throw 'Final file inventory count changed.' }
    foreach ($entry in $manifest.files) {
        $file = Get-Item -LiteralPath (Join-Path $app $entry.path)
        if ($file.PSIsContainer -or $file.Length -ne $entry.bytes -or
            (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256) {
            throw 'Final build fingerprint mismatch.'
        }
    }
    $gates.final_integrity = 'pass'
    $report.status = 'pass'
    Write-Host "VC086_SYNTHETIC_UI_ACCEPTANCE=PASS SHA=$ExpectedSha"
}
catch {
    $gates[$stage] = 'fail'
    $report.failed_stage = $stage
    throw
}
finally {
    Pop-Location
    $report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $out 'vc086-report.json') -Encoding UTF8
}
