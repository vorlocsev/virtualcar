# VC095: exact-head package acceptance. No adapter operation or VIDA launch.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$PackageBuildDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$PythonExe
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Invoke-VCNative.ps1')
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitOperatingSystem -or
    -not [Environment]::UserInteractive) { throw 'Interactive Windows x64 required.' }
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
function Assert-Checkout {
    $head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'Exact HEAD required.' }
    $dirty = @(& git -C $repo status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean checkout required.' }
}
function Assert-LocalDirectory([string]$path) {
    if ($path -notmatch '^[A-Za-z]:[\\/]') { throw 'Absolute local directory required.' }
    $dir = Get-Item -LiteralPath $path
    if ($dir -isnot [IO.DirectoryInfo] -or [IO.DriveInfo]::new($dir.Root.FullName).DriveType -ne [IO.DriveType]::Fixed) { throw 'Fixed local directory required.' }
    while ($null -ne $dir) {
        if (($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
            (Test-Path -LiteralPath (Join-Path $dir.FullName '.git'))) { throw 'Unsafe directory ancestry.' }
        $dir = $dir.Parent
    }
}
Assert-Checkout
Assert-LocalDirectory $PackageBuildDirectory
if ($OutputDirectory -notmatch '^[A-Za-z]:[\\/]') { throw 'Absolute output required.' }
$out = [IO.Path]::GetFullPath($OutputDirectory)
Assert-LocalDirectory (Split-Path -Parent $out)
$build = [IO.Path]::GetFullPath($PackageBuildDirectory).TrimEnd('\')
if ((Test-Path -LiteralPath $out) -or $out.StartsWith($build+'\',[StringComparison]::OrdinalIgnoreCase) -or $out -eq $build) {
    throw 'New output outside package build required.'
}
if ($PythonExe -notmatch '^[A-Za-z]:[\\/]' -or -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'Absolute Python executable required.' }
$python = (Resolve-Path -LiteralPath $PythonExe).Path
$dotnet = (Get-Command dotnet -CommandType Application | Select-Object -First 1).Source
[void](New-Item -ItemType Directory -Path $out)
$package = Join-Path $build 'VirtualCar'
$manifest = Join-Path $build 'package-manifest.json'
$managed = Join-Path $build 'build\build-manifest.json'
$native = Join-Path $build 'native\vc090-native-preflight.json'
$audit = Join-Path $repo 'emulator\tools\audit_vc094g_package.py'
$report = [ordered]@{schema='vc095-offline-acceptance-v1';source_sha=$ExpectedSha;status='fail';failed_stage='';
    gates=[ordered]@{source='pass';package_before='not_tested';core='not_tested';python_target='not_tested';python_full='not_tested';compileall='not_tested';normal_home_smoke='not_tested';final_integrity='not_tested'};
    visual_review='not_tested';private_editor_interaction='not_tested';registration='not_tested';original_vida='not_tested';physical_j2534='not_tested';release_ready=$false}
function Run-Logged([string]$exe,[string[]]$arguments,[string]$name) {
    $log = Join-Path $out ($name+'.log')
    $exitCode = Invoke-VCNativeLogged -Executable $exe -Arguments $arguments -WorkingDirectory $repo -Log $log
    if ($exitCode -ne 0) { throw "Check failed: $name exit=$exitCode." }
    return $log
}
function Check-Package([string]$name) {
    $log = Run-Logged $python @('-B',$audit,'--package',$package,'--manifest',$manifest,'--build-manifest',$managed,'--native-preflight',$native,'--expected-head',$ExpectedSha) $name
    if (-not (Select-String -LiteralPath $log -Pattern '^VC094G_PACKAGE_INTEGRITY=PASS files=\d+$' -Quiet)) { throw 'Missing package integrity result.' }
}
function Check-PythonCount([string]$log,[int]$count,[int]$skips) {
    $lines = @(Get-Content -LiteralPath ($log+'.stderr'))
    if (@($lines | Where-Object { $_ -match ('^Ran '+$count+' tests? in ') }).Count -ne 1) { throw 'Unexpected Python discovery count.' }
    $expected = if ($skips) { 'OK (skipped='+$skips+')' } else { 'OK' }
    if ($lines -notcontains $expected) { throw 'Unexpected Python test summary.' }
}
$stage = 'package_before'
try {
    $evidenceHashes = @{}
    foreach ($file in @($manifest,$managed,$native)) { $evidenceHashes[$file]=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash }
    Check-Package 'package-before'
    $packageInfo = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $report.gates[$stage]='pass'
    $stage='core'
    $core = Join-Path $PSScriptRoot '..\VirtualCar.Core.Checks\VirtualCar.Core.Checks.csproj'
    $log = Run-Logged $dotnet @('run','--project',$core,'-c','Release','--disable-build-servers','-p:UseSharedCompilation=false') 'core'
    if (@(Get-Content -LiteralPath $log | Where-Object { $_ -eq 'VirtualCar.Core synthetic checks: 160/160' }).Count -ne 1) { throw 'Expected exact Core 160/160.' }
    $report.gates[$stage]='pass'
    $stage='python_target'
    $log = Run-Logged $python @('-B','-m','unittest','discover','-s','emulator/tests','-p','test_audit_vc094g_package.py','-v') 'python-target'
    Check-PythonCount $log 8 0
    $report.gates[$stage]='pass'
    $stage='python_full'
    $log = Run-Logged $python @('-B','-m','unittest','discover','-s','emulator/tests') 'python-full'
    Check-PythonCount $log 1256 4
    $report.gates[$stage]='pass'
    $stage='compileall'
    [void](Run-Logged $python @('-X',('pycache_prefix='+(Join-Path $out 'pycache')),'-m','compileall','-q','emulator') 'compileall')
    $report.gates[$stage]='pass'
    $stage='normal_home_smoke'
    # Launch the actual renamed apphost with no arguments. Only observe controls;
    # no UI actions or registry modifications are requested by this script.
    Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
    $process = Start-Process -FilePath (Join-Path $package 'VirtualCar.exe') -WorkingDirectory $package -PassThru
    try {
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $ready = $false
        do {
            $process.Refresh()
            if ($process.HasExited) { throw 'Packaged application exited before readiness.' }
            if ($process.MainWindowHandle -ne [IntPtr]::Zero -and $process.MainWindowTitle -eq 'Virtual Car') {
                try {
                    $window = [System.Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
                    if ($null -ne $window -and $window.Current.ProcessId -eq $process.Id) {
                        $ready = $true
                        foreach ($id in @('VC094A.Vehicle','VC094A.Vehicle.Name','VC094A.Connection.Status','VC094A.Advanced')) {
                            $condition = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,$id)
                            $element = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)
                            if ($null -eq $element -or $element.Current.ProcessId -ne $process.Id) { $ready=$false; break }
                            if ($id -eq 'VC094A.Vehicle.Name' -and $packageInfo.private_profile_included -and $element.Current.Name -notlike '*XC90 V8*2009*') { $ready=$false; break }
                        }
                    }
                } catch { $ready=$false }
            }
            if (-not $ready) { Start-Sleep -Milliseconds 250 }
        } until ($ready -or $timer.Elapsed.TotalSeconds -ge 60)
        if (-not $ready) { throw 'Normal home automation controls not observed.' }
    } finally {
        try {
            $process.Refresh()
            if (-not $process.HasExited) {
                [void]$process.CloseMainWindow()
                if (-not $process.WaitForExit(10000)) {
                    $process.Kill(); [void]$process.WaitForExit(5000); throw 'Normal close failed.'
                }
            }
            if ($process.ExitCode -ne 0) { throw 'Packaged application exited abnormally.' }
        } finally { $process.Dispose() }
    }
    $report.gates[$stage]='pass'
    $stage='final_integrity'
    Assert-Checkout
    foreach ($file in $evidenceHashes.Keys) {
        if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $evidenceHashes[$file]) { throw 'Evidence manifest changed.' }
    }
    Check-Package 'package-after'
    $report.gates[$stage]='pass'
    $report.status='pass'
    Write-Host 'VC095_OFFLINE_ACCEPTANCE=PASS 8/8'
} catch {
    $report.failed_stage=$stage
    $report.gates[$stage]='fail'
    throw
} finally {
    $report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'vc095-offline-acceptance.json') -Encoding UTF8
    Write-Host 'VC095_RUNTIME_ACCEPTANCE=NOT_TESTED'
}
