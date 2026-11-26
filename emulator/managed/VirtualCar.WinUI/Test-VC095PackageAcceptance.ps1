# VC095: exact-head package acceptance. No adapter operation or VIDA launch.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$PackageBuildDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [ValidateSet('Any','Demo','OwnerLocal')][string]$ExpectedScope = 'Any',
    [switch]$RequireArtwork,
    [switch]$CaptureScreenshots
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
    screenshots='not_requested';package_scope='not_tested';artwork='not_tested';home_refresh='not_tested';visual_review='not_tested';private_editor_interaction='not_tested';registration='not_tested';original_vida='not_tested';physical_j2534='not_tested';release_ready=$false}
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
function Capture-PreviewWindow($window, [string]$name) {
    if (-not $CaptureScreenshots) { return }
    Add-Type -AssemblyName System.Drawing,System.Windows.Forms
    if ($window.Current.ProcessId -ne $process.Id || $window.Current.IsOffscreen) {
        throw 'Preview window not visible for capture.'
    }
    $r = $window.Current.BoundingRectangle
    if ($r.IsEmpty -or $r.Width -lt 1 -or $r.Height -lt 1 -or
        $r.Width -gt 8192 -or $r.Height -gt 8192) { throw 'Invalid capture bounds.' }
    $x = [int][Math]::Floor($r.X); $y = [int][Math]::Floor($r.Y)
    $w = [int][Math]::Ceiling($r.Right) - $x; $h = [int][Math]::Ceiling($r.Bottom) - $y
    $rect = [Drawing.Rectangle]::new($x,$y,$w,$h)
    # One screen only; do not capture pixels outside the preview window bounds.
    $screen = [Windows.Forms.Screen]::FromRectangle($rect)
    if (-not $screen.Bounds.Contains($rect)) { throw 'Preview window crosses screen bounds.' }
    $file = Join-Path $out ($name + '.png')
    $bitmap = [Drawing.Bitmap]::new($w,$h)
    try {
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        try { $graphics.CopyFromScreen($x,$y,0,0,$bitmap.Size) }
        finally { $graphics.Dispose() }
        $stream = [IO.File]::Open($file,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write,[IO.FileShare]::None)
        try { $bitmap.Save($stream,[Drawing.Imaging.ImageFormat]::Png) }
        finally { $stream.Dispose() }
    } finally { $bitmap.Dispose() }
}
$stage = 'package_before'
try {
    $evidenceHashes = @{}
    foreach ($file in @($manifest,$managed,$native)) { $evidenceHashes[$file]=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash }
    Check-Package 'package-before'
    $packageInfo = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $actualScope = if ($packageInfo.private_profile_included) { 'OwnerLocal' } else { 'Demo' }
    if ($ExpectedScope -ne 'Any' -and $actualScope -ne $ExpectedScope) { throw 'Unexpected package scope.' }
    if ($RequireArtwork -and $packageInfo.artwork -ne 'two_reference_photos') { throw 'Required artwork missing.' }
    $report.package_scope = $actualScope
    $report.artwork = $packageInfo.artwork
    $report.gates[$stage]='pass'
    $stage='core'
    $core = Join-Path $PSScriptRoot '..\VirtualCar.Core.Checks\VirtualCar.Core.Checks.csproj'
    $log = Run-Logged $dotnet @('run','--project',$core,'-c','Release','--disable-build-servers','-p:UseSharedCompilation=false') 'core'
    if (@(Get-Content -LiteralPath $log | Where-Object { $_ -eq 'VirtualCar.Core synthetic checks: 192/192' }).Count -ne 1) { throw 'Expected exact Core 192/192.' }
    $report.gates[$stage]='pass'
    $stage='python_target'
    $log = Run-Logged $python @('-B','-m','unittest','discover','-s','emulator/tests','-p','test_audit_vc094g_package.py','-v') 'python-target'
    Check-PythonCount $log 12 0
    $log = Run-Logged $python @('-B','-m','unittest','discover','-s','emulator/tests','-p','test_prepare_vc094b_local_profile.py','-v') 'python-private-package'
    Check-PythonCount $log 24 0
    $report.gates[$stage]='pass'
    $stage='python_full'
    $log = Run-Logged $python @('-B','-m','unittest','discover','-s','emulator/tests') 'python-full'
    Check-PythonCount $log 1284 4
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
                        foreach ($id in @('VC094A.Vehicle','VC094A.Vehicle.Name','VC094A.Connection.Status','VC094A.Advanced','VC094A.Language')) {
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
        # Inspect the language list without selecting another language or changing settings.
        $languageCondition = [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::AutomationIdProperty,'VC094A.Language')
        $language = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$languageCondition)
        if ($null -eq $language -or $language.Current.ProcessId -ne $process.Id) { throw 'Language selector missing.' }
        $expand = $language.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
        $expand.Expand()
        try {
            foreach ($choice in @(@{id='VC094A.Language.EN';name='English'},@{id='VC094A.Language.RU';name=[string]([char]0x0420)+[char]0x0443+[char]0x0441+[char]0x0441+[char]0x043A+[char]0x0438+[char]0x0439})) {
                $condition = [System.Windows.Automation.PropertyCondition]::new(
                    [System.Windows.Automation.AutomationElement]::AutomationIdProperty,$choice.id)
                $timerChoice = [Diagnostics.Stopwatch]::StartNew()
                $item = $null
                do {
                    $item = $window.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)
                    if ($null -eq $item) { $item = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
                        [System.Windows.Automation.TreeScope]::Descendants,
                        [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@(
                            $condition,[System.Windows.Automation.PropertyCondition]::new(
                                [System.Windows.Automation.AutomationElement]::ProcessIdProperty,$process.Id)))) }
                    if ($null -eq $item) { Start-Sleep -Milliseconds 100 }
                } until ($null -ne $item -or $timerChoice.Elapsed.TotalSeconds -ge 5)
                if ($null -eq $item -or $item.Current.ProcessId -ne $process.Id -or $item.Current.Name -ne $choice.name) {
                    throw 'Expected bilingual language option not observed.'
                }
            }
        } finally { $expand.Collapse() }
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
    # A separate process exercises actual language switching in a no-write mode.
    # The real no-argument startup check above remains mandatory.
    $process = Start-Process -FilePath (Join-Path $package 'VirtualCar.exe') -WorkingDirectory $package -ArgumentList '--home-preview' -PassThru
    try {
        function Find-HomeControl($root, [string]$id, [switch]$Desktop) {
            $byId = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,$id)
            $byPid = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::ProcessIdProperty,$process.Id)
            $condition = [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($byId,$byPid))
            $timer = [Diagnostics.Stopwatch]::StartNew()
            do {
                $process.Refresh()
                if ($process.HasExited) { throw 'Preview process exited.' }
                $item = $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)
                if ($null -eq $item -and $Desktop) {
                    $item = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$condition)
                }
                if ($null -ne $item) { return $item }
                Start-Sleep -Milliseconds 100
            } until ($timer.Elapsed.TotalSeconds -ge 5)
            throw "Preview control missing: $id"
        }
        $timer = [Diagnostics.Stopwatch]::StartNew()
        $previewWindow = $null
        do {
            $process.Refresh()
            if ($process.HasExited) { throw 'Preview process exited before readiness.' }
            if ($process.MainWindowHandle -ne [IntPtr]::Zero -and $process.MainWindowTitle -eq 'Virtual Car') {
                try {
                    $candidate = [System.Windows.Automation.AutomationElement]::FromHandle($process.MainWindowHandle)
                    if ($candidate.Current.ProcessId -eq $process.Id) {
                        [void](Find-HomeControl $candidate 'VC094A.Language')
                        $previewWindow = $candidate
                    }
                } catch { $previewWindow = $null }
            }
            if ($null -eq $previewWindow) { Start-Sleep -Milliseconds 200 }
        } until ($null -ne $previewWindow -or $timer.Elapsed.TotalSeconds -ge 60)
        if ($null -eq $previewWindow) { throw 'Home preview not ready.' }
        $selector = Find-HomeControl $previewWindow 'VC094A.Language'
        $originalVehicle = (Find-HomeControl $previewWindow 'VC094A.Vehicle.Name').Current.Name
        $cases = @(
            @{code='EN';advanced='Advanced settings';connection='Connection'},
            @{code='RU';advanced='Расширенные настройки';connection='Подключение'},
            @{code='EN';advanced='Advanced settings';connection='Connection'}
        )
        $count = 0
        foreach ($case in $cases) {
            if ($count -gt 0) {
                $expand = $selector.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
                $expand.Expand()
                $choice = Find-HomeControl $previewWindow ('VC094A.Language.'+$case.code) -Desktop
                $choice.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
                if ($expand.Current.ExpandCollapseState -eq [System.Windows.Automation.ExpandCollapseState]::Expanded) { $expand.Collapse() }
            }
            $timer = [Diagnostics.Stopwatch]::StartNew()
            do {
                $advanced = Find-HomeControl $previewWindow 'VC094A.Advanced'
                $connection = Find-HomeControl $previewWindow 'VC094F.Connection.Title'
                if ($advanced.Current.Name -eq $case.advanced -and $connection.Current.Name -eq $case.connection) { break }
                Start-Sleep -Milliseconds 100
            } until ($timer.Elapsed.TotalSeconds -ge 5)
            if ($advanced.Current.Name -ne $case.advanced -or $connection.Current.Name -ne $case.connection -or $advanced.Current.IsEnabled) { throw 'Preview localization or advanced lockout failed.' }
            # Model display names can legitimately change across languages. EN must round-trip.
            if ($case.code -eq 'EN' -and (Find-HomeControl $previewWindow 'VC094A.Vehicle.Name').Current.Name -ne $originalVehicle) { throw 'Vehicle selection changed.' }
            $observedActions = 0
            foreach ($id in @('VC094A.Connection.Enable','VC094A.Connection.Disable')) {
                $byId = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,$id)
                $action = $previewWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$byId)
                if ($null -ne $action) {
                    $observedActions++
                    if ($action.Current.ProcessId -ne $process.Id -or $action.Current.IsEnabled) { throw 'Adapter action enabled in preview.' }
                }
            }
            if ($observedActions -eq 0) { throw 'No adapter control observed.' }
            Capture-PreviewWindow $previewWindow ('home-language-' + $count + '-' + $case.code)
            $count++
        }
        if ($count -ne 3) { throw 'Incomplete language regression.' }
        Write-Host 'VC095B_HOME_LANGUAGE=PASS 3/3'
        $refresh = Find-HomeControl $previewWindow 'VC094A.Refresh'
        $notice = Find-HomeControl $previewWindow 'VC094A.Notice'
        if (-not $refresh.Current.IsEnabled -or $notice.Current.Name -like '*Local profile checked. No changes.*') {
            throw 'Refresh precondition failed.'
        }
        $refresh.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
        $refreshTimer = [Diagnostics.Stopwatch]::StartNew()
        do {
            $notice = Find-HomeControl $previewWindow 'VC094A.Notice'
            if ($notice.Current.Name -like '*Local profile checked. No changes.*') { break }
            Start-Sleep -Milliseconds 100
        } until ($refreshTimer.Elapsed.TotalSeconds -ge 15)
        if ($notice.Current.Name -notlike '*Local profile checked. No changes.*' -or
            (Find-HomeControl $previewWindow 'VC094A.Vehicle.Name').Current.Name -ne $originalVehicle -or
            (Find-HomeControl $previewWindow 'VC094A.Advanced').Current.IsEnabled) {
            throw 'Stable local refresh or selection preservation failed.'
        }
        $observedActions = 0
        foreach ($id in @('VC094A.Connection.Enable','VC094A.Connection.Disable')) {
            $byId = [System.Windows.Automation.PropertyCondition]::new([System.Windows.Automation.AutomationElement]::AutomationIdProperty,$id)
            $action = $previewWindow.FindFirst([System.Windows.Automation.TreeScope]::Descendants,$byId)
            if ($null -ne $action) {
                $observedActions++
                if ($action.Current.ProcessId -ne $process.Id -or $action.Current.IsEnabled) { throw 'Refresh enabled adapter action in preview.' }
            }
        }
        if ($observedActions -eq 0) { throw 'No adapter action observed after refresh.' }
        Capture-PreviewWindow $previewWindow 'home-refresh-en'
        if ($CaptureScreenshots) { $report.screenshots = 'captured_not_reviewed' }
        $report.home_refresh = 'pass'
        Write-Host 'VC096_HOME_STABLE_REFRESH=PASS'
    } finally {
        try {
            $process.Refresh()
            if (-not $process.HasExited) {
                [void]$process.CloseMainWindow()
                if (-not $process.WaitForExit(10000)) {
                    $process.Kill(); [void]$process.WaitForExit(5000); throw 'Preview close failed.'
                }
            }
            if ($process.ExitCode -ne 0) { throw 'Preview exited abnormally.' }
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
