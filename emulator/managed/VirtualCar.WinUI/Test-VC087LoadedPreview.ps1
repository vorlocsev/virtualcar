# VC087: owner-local loaded CEM preview smoke. No provider or vehicle writes.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [Parameter(Mandatory=$true)][string]$PythonExe,
    [Parameter(Mandatory=$true)][string]$PrivateDirectory
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

# Explicitly reviewed paths only. Do not print private paths, values or hashes.
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'Exact source checkout required.' }
$dirty = @(& git -C $repo status --porcelain --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean source checkout required.' }
$script = Join-Path $repo 'emulator\tools\cem529_config\vc071_view.py'
foreach ($path in @($PythonExe,$PrivateDirectory,$script)) {
    if ($path -notmatch '^[a-zA-Z]:[\\/]') { throw 'Absolute local paths required.' }
    $full = [IO.Path]::GetFullPath($path)
    if ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($full)).DriveType -ne [IO.DriveType]::Fixed) { throw 'Local fixed drive required.' }
    $item = Get-Item -LiteralPath $full
    while ($null -ne $item) {
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse-point paths not allowed.' }
        # Parent and Directory return CLR objects, not provider-decorated PS objects.
        if ($item -is [IO.DirectoryInfo]) { $item = $item.Parent }
        elseif ($item -is [IO.FileInfo]) { $item = $item.Directory }
        else { throw 'Unexpected filesystem object.' }
    }
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf) -or -not (Test-Path -LiteralPath $script -PathType Leaf) -or
    -not (Test-Path -LiteralPath $PrivateDirectory -PathType Container)) { throw 'Reviewed inputs unavailable.' }
$cursor = Get-Item -LiteralPath $PrivateDirectory
while ($null -ne $cursor) {
    if (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git')) { throw 'Private inputs must be outside Git.' }
    $cursor = $cursor.Parent
}
$inputNames = @(
    'VC041-529.private.json','VC0586-candidate.private.ini','VC0586-vida-acceptance.private.json',
    'VC0586-catalog-coverage.private.json','VC056-result.private.json','VC0591-configuration-store.private.json',
    'VC046-XC90-V8-20261125-085427.private.json'
)
function Fingerprints {
    foreach ($name in $inputNames) {
        $file = Get-Item -LiteralPath (Join-Path $PrivateDirectory $name)
        if ($file -isnot [IO.FileInfo] -or ($file.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Invalid input file.' }
        (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }
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
function Select-FirstRow($window) {
    $list = Wait-Element $window 'VC087.Rows'
    $condition = [System.Windows.Automation.PropertyCondition]::new(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,[System.Windows.Automation.ControlType]::ListItem)
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        foreach ($item in $list.FindAll([System.Windows.Automation.TreeScope]::Descendants,$condition)) {
            if ($item.Current.ProcessId -eq $process.Id -and -not $item.Current.IsOffscreen -and
                $item.Current.AutomationId -match '^VC087\.Row\.\d+$') {
                $id = $item.Current.AutomationId
                $item.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern).Select()
                return $id
            }
        }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    throw 'Visible CEM row unavailable.'
}
function Get-SelectionId($window,[string]$id) {
    $element = Wait-Element $window $id
    $selection = @($element.GetCurrentPattern([System.Windows.Automation.SelectionPattern]::Pattern).GetSelection())
    if ($selection.Length -ne 1) { throw "Unexpected selection: $id" }
    return $selection[0].Current.AutomationId
}
function Wait-Preview($window,[int]$changed,[string]$language) {
    $expected = if ($language -eq 'RU') {
        "Параметры: 127 · защищено: 12 · изменено: $changed"
    } else { "Parameters: 127 · locked: 12 · changed: $changed" }
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        if ($process.HasExited) { throw ('Preview process exited: 0x{0:X8}' -f $process.ExitCode) }
        $counts = Find-Element $window 'VC087.Counts'
        $audit = Find-Element $window 'VC087.Audit'
        if ($null -ne $counts -and $null -ne $audit -and $counts.Current.Name -ceq $expected -and
            (Wait-Element $window 'VC087.Close').Current.IsEnabled) {
            $match = [regex]::Match($audit.Current.Name,'(?:Audit SHA256|SHA256 аудита): ([0-9a-f]{64})')
            if ($match.Success) { return $match.Groups[1].Value }
        }
        Start-Sleep -Milliseconds 200
    } while ($timer.Elapsed.TotalSeconds -lt 45)
    throw 'Expected CEM count and audit not observed.'
}
$before = @(Fingerprints)
$passed = 0
$step = 'launch'
$process = Start-Process -FilePath (Join-Path $app 'VirtualCar.WinUI.exe') -WorkingDirectory $app -ArgumentList '--preview-only' -PassThru
try {
    $window = Wait-OwnedWindow $process
    $step = '01 baseline 127/12'
    Set-Value $window 'VC087.Python' $PythonExe
    Set-Value $window 'VC087.Script' $script
    Set-Value $window 'VC087.Data' $PrivateDirectory
    Invoke-Control $window 'VC075.Load'
    $baseline = Wait-Preview $window 0 'EN'
    $passed++; Write-Host "PASS $step"
    $step = '02 locked row'
    [void](Select-Combo $window 'VC075.Filter' 'VC087.Filter.Locked' '')
    $locked = Select-FirstRow $window
    Require-Disabled $window @('VC087.Options','VC087.Preview','VC087.Revert')
    $passed++; Write-Host "PASS $step"
    $step = '03 editable row and option'
    [void](Select-Combo $window 'VC075.Filter' 'VC087.Filter.Editable' '')
    $row = Select-FirstRow $window
    if ($row -eq $locked) { throw 'Locked row exposed as editable.' }
    $option = Select-Combo $window 'VC087.Options' '' 'VC087.Option.'
    if ((Get-SelectionId $window 'VC087.Options') -ne $option) { throw 'Option not selected.' }
    $passed++; Write-Host "PASS $step"
    $step = '04 changed preview'
    Invoke-Control $window 'VC087.Preview'
    $edited = Wait-Preview $window 1 'EN'
    if ($edited -eq $baseline) { throw 'Audit did not change.' }
    $passed++; Write-Host "PASS $step"
    $step = '05 language preserves draft'
    Set-Language $window 'RU'
    if ((Wait-Preview $window 1 'RU') -ne $edited -or (Get-SelectionId $window 'VC087.Rows') -ne $row -or
        (Get-SelectionId $window 'VC075.Filter') -ne 'VC087.Filter.Editable') { throw 'Draft changed on language switch.' }
    Set-Language $window 'EN'
    if ((Wait-Preview $window 1 'EN') -ne $edited) { throw 'Draft changed on language switch.' }
    $passed++; Write-Host "PASS $step"
    $step = '06 navigation and isolation'
    Select-Section $window 'Vehicle'
    Require-Disabled $window @('VC079.Vehicle.Inspect','VC080.Vehicle.Apply','VC081.Vehicle.Restore','VC082.Ignition.Apply')
    Select-Section $window 'Modules'
    Require-Disabled $window @('VC083.Modules.Refresh')
    Select-Section $window 'Diagnostics'
    Require-Disabled $window @('VC084.Monitor.Start','VC084.Monitor.Refresh')
    Select-Section $window 'Connection'
    Require-Disabled $window @('VC078.Driver.Refresh','VC078.Driver.Install','VC078.Driver.Remove')
    Select-Section $window 'Configuration'
    if ((Wait-Preview $window 1 'EN') -ne $edited -or (Get-SelectionId $window 'VC087.Rows') -ne $row) {
        throw 'Draft changed on navigation.'
    }
    $passed++; Write-Host "PASS $step"
    $step = '07 revert and reload'
    Invoke-Control $window 'VC087.Revert'
    if ((Wait-Preview $window 0 'EN') -ne $baseline) { throw 'Revert baseline mismatch.' }
    Invoke-Control $window 'VC087.Close'
    Assert-Name $window 'VC087.Counts' 'No data'
    Invoke-Control $window 'VC075.Load'
    if ((Wait-Preview $window 0 'EN') -ne $baseline) { throw 'Reload baseline mismatch.' }
    $passed++; Write-Host "PASS $step"
}
catch { throw "VC087 failed at $step (inspect local UI; no private values exported)." }
finally {
    try {
        $process.Refresh()
        if (-not $process.HasExited) {
            [void]$process.CloseMainWindow()
            if (-not $process.WaitForExit(5000)) {
                $process.Kill()
                [void]$process.WaitForExit(5000)
                throw 'Preview window did not close normally.'
            }
        }
        if ($process.ExitCode -ne 0) { throw ('Preview exit: 0x{0:X8}' -f $process.ExitCode) }
    }
    finally {
        $process.Dispose()
        $after = @(Fingerprints)
        if ($before.Count -ne 7 -or $after.Count -ne 7 -or ($before -join ',') -cne ($after -join ',')) {
            throw 'Private input integrity not established.'
        }
        $passed++; Write-Host 'PASS 08 seven input files unchanged'
    }
}
if ($passed -ne 8) { throw 'Incomplete VC087 acceptance.' }
Write-Host "VC087_LOADED_CEM_ACCEPTANCE=PASS 8/8 SHA=$ExpectedSha"
