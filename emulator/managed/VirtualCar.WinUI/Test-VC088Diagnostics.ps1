# VC088: owner-local read-only diagnostics UI acceptance; generated fixtures only.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [Parameter(Mandatory=$true)][string]$FixtureDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::UserInteractive) { throw 'Interactive Windows desktop required.' }
$directory = (Resolve-Path -LiteralPath $BuildDirectory).Path
$manifest = Get-Content -LiteralPath (Join-Path $directory 'build-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema -ne 'vc075-winui-build-v1' -or $manifest.source_sha -ne $ExpectedSha -or
    $manifest.publish -ne 'pass' -or $manifest.platform -ne 'win-x64') { throw 'Build manifest mismatch.' }
$app = Join-Path $directory 'app'
# Verify complete inventory before starting the exact published application.
$actual = @(Get-ChildItem -LiteralPath $app -Recurse -File)
if ($actual.Count -ne @($manifest.files).Count) { throw 'Published inventory count mismatch.' }
$seen = @{}
foreach ($entry in $manifest.files) {
    if ($entry.path -notmatch '^[^\\/:]+(?:/[^\\/:]+)*$' -or ($entry.path.Split('/') | Where-Object { $_ -in @('.','..') })) {
        throw 'Invalid relative inventory path.'
    }
    if ($seen.ContainsKey($entry.path)) { throw 'Duplicate inventory path.' }
    $seen[$entry.path] = $true
    $file = Get-Item -LiteralPath (Join-Path $app $entry.path)
    if ($file -isnot [IO.FileInfo] -or $file.Length -ne $entry.bytes -or
        (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256) {
        throw 'Published file fingerprint mismatch.'
    }
}
Add-Type -AssemblyName UIAutomationClient,UIAutomationTypes
if (-not ('VC086.WindowOwnership' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace VC086 {
    public static class WindowOwnership {
        [DllImport("user32.dll", SetLastError = true)]
        public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
    }
}
'@
}
function Find-Element($root, [string]$id) {
    $idCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $id)
    $pidCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $process.Id)
    $condition = [System.Windows.Automation.AndCondition]::new(
        [System.Windows.Automation.Condition[]]@($idCondition,$pidCondition))
    return $root.FindFirst([System.Windows.Automation.TreeScope]::Descendants, $condition)
}
function Wait-OwnedWindow($process) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    $last = 'No HWND'
    do {
        $process.Refresh()
        if ($process.HasExited) { throw ('Application exited before UIA readiness: 0x{0:X8}' -f $process.ExitCode) }
        $hwnd = $process.MainWindowHandle
        if ($hwnd -ne [IntPtr]::Zero) {
            [uint32]$owner = 0
            $thread = [VC086.WindowOwnership]::GetWindowThreadProcessId($hwnd, [ref]$owner)
            $last = "HWND=$hwnd owner=$owner expected=$($process.Id)"
            if ($thread -ne 0 -and $owner -eq $process.Id) {
                try {
                    $candidate = [System.Windows.Automation.AutomationElement]::FromHandle($hwnd)
                    if ($null -ne $candidate) {
                        $uiaPid = $candidate.Current.ProcessId
                        $uiaHwnd = $candidate.Current.NativeWindowHandle
                        $last += " UIA_PID=$uiaPid UIA_HWND=$uiaHwnd"
                        # WinUI may expose a host provider at the native window root.
                        # Require the exact HWND and unique app-owned anchors instead
                        # of trusting the provider PID or selecting an arbitrary window.
                        if ([int64]$uiaHwnd -eq $hwnd.ToInt64()) {
                            $heading = Find-Element $candidate 'VC075.Heading'
                            $nav = Find-Element $candidate 'VC077.Navigation'
                            $lang = Find-Element $candidate 'VC075.Language'
                            if ($null -ne $heading -and $null -ne $nav -and $null -ne $lang) {
                                [uint32]$confirmedOwner = 0
                                $confirmedThread = [VC086.WindowOwnership]::GetWindowThreadProcessId($hwnd, [ref]$confirmedOwner)
                                if ($confirmedThread -ne 0 -and $confirmedOwner -eq $process.Id -and -not $process.HasExited) {
                                    Write-Host "VC086_UIA_OWNED_WINDOW=PASS $last"
                                    return $candidate
                                }
                            }
                        }
                    }
                }
                catch [System.Windows.Automation.ElementNotAvailableException] {
                    $last += ' UIA provider not ready'
                }
            }
        }
        Start-Sleep -Milliseconds 200
    } while ($timer.Elapsed.TotalSeconds -lt 30)
    throw "No owned and ready WinUI window: $last"
}
function Wait-Element($root, [string]$id) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $element = Find-Element $root $id
        if ($null -ne $element) { return $element }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    throw "Missing automation element: $id"
}
function Assert-Name($root, [string]$id, [string]$name) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $element = Find-Element $root $id
        if ($null -ne $element -and $element.Current.Name -ceq $name) { return }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    throw "Unexpected localized text: $id"
}
function Set-Language($window, [string]$code) {
    $selector = Wait-Element $window 'VC075.Language'
    $expand = $selector.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    $expand.Expand()
    # WinUI may put the popup in the desktop tree instead of under the ComboBox.
    $pidCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $process.Id)
    $idCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, "VC075.Language.$code")
    $condition = [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($pidCondition,$idCondition))
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $item = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
            [System.Windows.Automation.TreeScope]::Descendants, $condition)
        if ($null -ne $item) { break }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    if ($null -eq $item) { throw "Language option unavailable: $code" }
    $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    if ($expand.Current.ExpandCollapseState -eq [System.Windows.Automation.ExpandCollapseState]::Expanded) {
        $expand.Collapse()
    }
}
function Select-JournalView($window, [string]$choice) {
    $selector = Wait-Element $window 'VC085.Diagnostics.View'
    $expand = $selector.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    $expand.Expand()
    $pidCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $process.Id)
    $idCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::AutomationIdProperty, "VC086.View.$choice")
    $condition = [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($pidCondition,$idCondition))
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $item = [System.Windows.Automation.AutomationElement]::RootElement.FindFirst(
            [System.Windows.Automation.TreeScope]::Descendants, $condition)
        if ($null -ne $item) { break }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    if ($null -eq $item) { throw "Journal view option unavailable: $choice" }
    $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    if ($expand.Current.ExpandCollapseState -eq [System.Windows.Automation.ExpandCollapseState]::Expanded) {
        $expand.Collapse()
    }
}
function Select-Section($window, [string]$section) {
    $item = Wait-Element $window "VC077.Nav.$section"
    $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
}
function Assert-EditorHidden($window) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $load = Find-Element $window 'VC075.Load'
        if ($null -eq $load -or $load.Current.IsOffscreen) { return }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    throw 'CEM editor visible outside configuration workspace.'
}

function Set-Value($window,[string]$id,[string]$value) {
    $element = Wait-Element $window $id
    $element.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern).SetValue($value)
}
function Invoke-Control($window,[string]$id) {
    $element = Wait-Element $window $id
    if (-not $element.Current.IsEnabled) { throw "Control disabled: $id" }
    $element.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
}
function Require-Disabled($window,[string[]]$ids) {
    foreach ($id in $ids) {
        if ((Wait-Element $window $id).Current.IsEnabled) { throw "Unexpected enabled control: $id" }
    }
}
function Select-Combo($window,[string]$selectorId,[string]$itemId,[string]$prefix) {
    $selector = Wait-Element $window $selectorId
    $expand = $selector.GetCurrentPattern([System.Windows.Automation.ExpandCollapsePattern]::Pattern)
    $expand.Expand()
    $pidCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $process.Id)
    $listCondition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::ListItem)
    $condition = if ($itemId) {
        $idCondition = [System.Windows.Automation.PropertyCondition]::new(
            [System.Windows.Automation.AutomationElement]::AutomationIdProperty, $itemId)
        [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($pidCondition,$idCondition))
    } else {
        [System.Windows.Automation.AndCondition]::new([System.Windows.Automation.Condition[]]@($pidCondition,$listCondition))
    }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $items = [System.Windows.Automation.AutomationElement]::RootElement.FindAll(
            [System.Windows.Automation.TreeScope]::Descendants, $condition)
        $item = $null
        foreach ($candidate in $items) {
            if (-not $candidate.Current.IsOffscreen -and
                ($itemId -or $candidate.Current.AutomationId.StartsWith($prefix,[StringComparison]::Ordinal))) {
                $item = $candidate
                break
            }
        }
        if ($null -ne $item) { break }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    if ($null -eq $item) { throw "Combo option unavailable: $selectorId" }
    $chosen = $item.Current.AutomationId
    $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
    if ($expand.Current.ExpandCollapseState -eq [System.Windows.Automation.ExpandCollapseState]::Expanded) { $expand.Collapse() }
    return $chosen
}

$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
function Assert-Checkout {
    $head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'Exact source checkout required.' }
    $dirty = @(& git -C $repo status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean source checkout required.' }
}
Assert-Checkout
if ($FixtureDirectory -notmatch '^[a-zA-Z]:[\\/]') { throw 'Absolute local fixture path required.' }
$fixtures = [IO.Path]::GetFullPath($FixtureDirectory)
if (Test-Path -LiteralPath $fixtures) { throw 'Fixture directory already exists.' }
if ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($fixtures)).DriveType -ne [IO.DriveType]::Fixed) { throw 'Fixed drive required.' }
$cursor = Get-Item -LiteralPath (Split-Path -Parent $fixtures)
if ($cursor -isnot [IO.DirectoryInfo]) { throw 'Fixture parent must be a directory.' }
while ($null -ne $cursor) {
    if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git')) -or
        $cursor.FullName.TrimEnd('\') -eq $directory.TrimEnd('\')) {
        throw 'Fixture directory must be outside Git, build inventory and reparse ancestry.'
    }
    $cursor = $cursor.Parent
}
[void](New-Item -ItemType Directory -Path $fixtures)
foreach ($name in @('valid','routes','ambiguous')) { [void](New-Item -ItemType Directory -Path (Join-Path $fixtures $name)) }
$valid = Join-Path $fixtures 'valid\virtualcar.ini'
$routes = Join-Path $fixtures 'routes\virtualcar.ini'
$ambiguous = Join-Path $fixtures 'ambiguous\virtualcar.ini'
$log = Join-Path $fixtures 'fixture.log'
[IO.File]::WriteAllLines($valid,[string[]]@('[Vehicle]','ECUCount=2','[ECU0]','RequestId=7E0','ResponseId=7E8','ExpectedBaud=500000','PartNumber=LAB-ECM','Software=LAB-1','[ECU1]','RequestId=726','ResponseId=72E','ExpectedBaud=125000','PartNumber=LAB-CEM','Software=LAB-2'),[Text.Encoding]::ASCII)
[IO.File]::WriteAllLines($routes,[string[]]@('[Vehicle]','ECUCount=3','[ECU0]','RequestId=7E0','ResponseId=7E8','[ECU1]','RequestId=7E0','ResponseId=7E8','[ECU2]','RequestId=20000000','ResponseId=7E8'),[Text.Encoding]::ASCII)
[IO.File]::WriteAllLines($ambiguous,[string[]]@('[Vehicle]','ECUCount=2','ecuCount=1'),[Text.Encoding]::ASCII)
$iniHashes = @(@($valid,$routes,$ambiguous) | ForEach-Object { (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash })
$prefix = '[PID=00000001 lab.exe] '
$tx = $prefix + 'TX context channel/protocol/flags/baud/time-us (BE) 00 00 00 01 00 00 00 06 00 00 00 00 00 07 A1 20 00 00 00 01 '
$rx = $prefix + 'RX context channel/protocol/status/baud/time-us (BE) 00 00 00 01 00 00 00 06 00 00 00 00 00 07 A1 20 00 00 00 02 '
$start = $prefix + 'RX context channel/protocol/status/baud/time-us (BE) 00 00 00 01 00 00 00 06 00 00 00 02 00 07 A1 20 00 00 00 03 '
$raw = $prefix + 'TX context channel/protocol/flags/baud/time-us (BE) 00 00 00 01 00 00 00 05 00 00 00 00 00 07 A1 20 00 00 00 04 '
$request = $prefix + 'TX (app request) 00 00 07 E0 22 F1 87 '
$positive = $prefix + 'PassThruReadMsgs -> delivered 00 00 07 E8 62 F1 87 41 '
$negative = $prefix + 'PassThruReadMsgs -> delivered 00 00 07 E8 7F 22 78 '
$indication = $prefix + 'PassThruReadMsgs -> delivered 00 00 07 E8 '
$unknown = $prefix + 'TX (app request) 00 00 07 E0 01 02 '
$queued = $prefix + 'RX (simulated) 00 00 07 E8 62 F1 87 41 '
$nl = [Environment]::NewLine
$initial = (@($tx,$request,$rx,$positive,$rx,$negative,$start,$indication,$raw,$unknown,$queued) -join $nl) + $nl
$extra = (@($tx,$request) -join $nl) + $nl
[IO.File]::WriteAllText($log,$initial,[Text.Encoding]::ASCII)
function Assert-Contains($window,[string]$id,[string]$expected) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $element = Find-Element $window $id
        if ($null -ne $element -and $element.Current.Name.Contains($expected)) { return }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 10)
    throw "Unexpected content for $id (expected $expected)"
}
function Assert-NoElement($window,[string]$id) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        if ($null -eq (Find-Element $window $id)) { return }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    throw "Stale automation element: $id"
}
function Assert-Monitor($window,[string]$state,[string]$count) {
    Assert-Contains $window 'VC088.Monitor.Status' "$state · $count ·"
}
function Assert-Journal($window,[string]$text) {
    Assert-Contains $window 'VC085.Diagnostics.Summary' $text
}
$process = Start-Process -FilePath (Join-Path $app 'VirtualCar.WinUI.exe') -WorkingDirectory $app -ArgumentList '--diagnostics-only' -PassThru
$passed = 0
$step = 'launch'
try {
    $window = Wait-OwnedWindow $process
    $step = '01 configured ECU inventory'
    Select-Section $window 'Modules'
    Set-Value $window 'VC088.Modules.Profile' $valid
    Invoke-Control $window 'VC083.Modules.Refresh'
    Assert-Contains $window 'VC083.Modules.Status' 'Profile snapshot: 2 slots. Discovery not performed.'
    Assert-Contains $window 'VC088.Ecu.0' 'TX 7E0 / RX 7E8 · 500000'
    Assert-Contains $window 'VC088.Ecu.0' 'LAB-ECM'
    Assert-Contains $window 'VC088.Ecu.1' 'TX 726 / RX 72E · 125000'
    $passed++; Write-Host "PASS $step"
    $step = '02 duplicate and invalid routes'
    Set-Value $window 'VC088.Modules.Profile' $routes
    Invoke-Control $window 'VC083.Modules.Refresh'
    Assert-Contains $window 'VC083.Modules.Status' 'Profile snapshot: 3 slots.'
    Assert-Contains $window 'VC088.Ecu.0' 'Duplicate request ID'
    Assert-Contains $window 'VC088.Ecu.1' 'Duplicate request ID'
    Assert-Contains $window 'VC088.Ecu.2' 'Invalid or unsupported route'
    $passed++; Write-Host "PASS $step"
    $step = '03 ambiguous profile clears stale inventory'
    Set-Value $window 'VC088.Modules.Profile' $ambiguous
    Invoke-Control $window 'VC083.Modules.Refresh'
    Assert-Name $window 'VC083.Modules.Status' 'Profile unavailable or ambiguous.'
    Assert-NoElement $window 'VC088.Ecu.0'
    $passed++; Write-Host "PASS $step"
    $step = '04 CAN snapshot and queued RX exclusion'
    Select-Section $window 'Diagnostics'
    Set-Value $window 'VC088.Monitor.Path' $log
    Invoke-Control $window 'VC084.Monitor.Refresh'
    Assert-Monitor $window 'Snapshot' '5/5'
    $passed++; Write-Host "PASS $step"
    $step = '05 TX/RX and payload filtering'
    [void](Select-Combo $window 'VC088.Monitor.Direction' 'VC088.Direction.TX' '')
    Assert-Monitor $window 'Snapshot' '2/5'
    [void](Select-Combo $window 'VC088.Monitor.Direction' 'VC088.Direction.RX' '')
    Assert-Monitor $window 'Snapshot' '3/5'
    [void](Select-Combo $window 'VC088.Monitor.Direction' 'VC088.Direction.All' '')
    Set-Value $window 'VC088.Monitor.Filter' '7F 22 78'
    Assert-Monitor $window 'Snapshot' '1/5'
    Set-Value $window 'VC088.Monitor.Filter' ''
    Assert-Monitor $window 'Snapshot' '5/5'
    $passed++; Write-Host "PASS $step"
    $step = '06 journal classification and localization'
    Select-JournalView $window 'Journal'
    Assert-Journal $window 'Requests 1 · Positive 1 · Negative 1 · Indications 1 · Unclassified 1'
    Set-Value $window 'VC088.Monitor.Filter' 'NRC 78'
    Assert-Monitor $window 'Snapshot' '1/5'
    Assert-Journal $window 'Requests 0 · Positive 0 · Negative 1 · Indications 0 · Unclassified 0'
    Set-Value $window 'VC088.Monitor.Filter' ''
    Set-Language $window 'RU'
    Assert-Journal $window 'Запросы 1 · Положительные 1 · Отрицательные 1 · Индикации 1 · Без классификации 1'
    Set-Language $window 'EN'
    Select-JournalView $window 'Can'
    $passed++; Write-Host "PASS $step"
    $step = '07 live append, stop, navigation and read failure'
    Invoke-Control $window 'VC084.Monitor.Start'
    Assert-Monitor $window 'Monitoring log' '5/5'
    [IO.File]::AppendAllText($log,$extra,[Text.Encoding]::ASCII)
    Assert-Monitor $window 'Monitoring log' '6/6'
    Invoke-Control $window 'VC084.Monitor.Stop'
    Assert-Monitor $window 'Snapshot' '6/6'
    [IO.File]::AppendAllText($log,$extra,[Text.Encoding]::ASCII)
    Start-Sleep -Milliseconds 1600
    Assert-Monitor $window 'Snapshot' '6/6'
    Invoke-Control $window 'VC084.Monitor.Refresh'
    Assert-Monitor $window 'Snapshot' '7/7'
    Invoke-Control $window 'VC084.Monitor.Start'
    Select-Section $window 'Modules'
    Select-Section $window 'Diagnostics'
    Assert-Monitor $window 'Snapshot' '7/7'
    Require-Disabled $window @('VC084.Monitor.Stop')
    Set-Value $window 'VC088.Monitor.Path' (Join-Path $fixtures 'missing.log')
    Invoke-Control $window 'VC084.Monitor.Refresh'
    Assert-Name $window 'VC088.Monitor.Status' 'Log unavailable. Monitoring stopped.'
    $passed++; Write-Host "PASS $step"
    $step = '08 isolated controls and fixture integrity'
    Select-Section $window 'Vehicle'
    Require-Disabled $window @('VC079.Vehicle.Inspect','VC080.Vehicle.Apply','VC081.Vehicle.Restore','VC082.Ignition.Apply')
    Select-Section $window 'Connection'
    Require-Disabled $window @('VC078.Driver.Refresh','VC078.Driver.Install','VC078.Driver.Remove')
    Select-Section $window 'Configuration'
    Require-Disabled $window @('VC075.Load')
    Assert-Checkout
    $after = @(@($valid,$routes,$ambiguous) | ForEach-Object { (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash })
    if (($iniHashes -join ',') -cne ($after -join ',') -or
        [IO.File]::ReadAllText($log,[Text.Encoding]::ASCII) -cne ($initial + $extra + $extra)) { throw 'Fixture integrity mismatch.' }
    $passed++; Write-Host "PASS $step"
}
catch { throw "VC088 failed at $step : $($_.Exception.Message)" }
finally {
    try {
        $process.Refresh()
        if (-not $process.HasExited) {
            [void]$process.CloseMainWindow()
            if (-not $process.WaitForExit(5000)) {
                $process.Kill()
                [void]$process.WaitForExit(5000)
                throw 'Diagnostics window did not close normally.'
            }
        }
        if ($process.ExitCode -ne 0) { throw ('Diagnostics exit: 0x{0:X8}' -f $process.ExitCode) }
    }
    finally { $process.Dispose() }
}
Assert-Checkout
$finalFiles = @(Get-ChildItem -LiteralPath $app -Recurse -File)
if ($finalFiles.Count -ne @($manifest.files).Count) { throw 'Final build inventory count mismatch.' }
foreach ($entry in $manifest.files) {
    $file = Get-Item -LiteralPath (Join-Path $app $entry.path)
    if ($file -isnot [IO.FileInfo] -or $file.Length -ne $entry.bytes -or
        (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256) { throw 'Final build integrity mismatch.' }
}
if ($passed -ne 8) { throw 'Incomplete VC088 acceptance.' }
Write-Host "VC088_DIAGNOSTICS_ACCEPTANCE=PASS 8/8 SHA=$ExpectedSha"
