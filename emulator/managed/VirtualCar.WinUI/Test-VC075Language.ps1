# VC075: interactive desktop bilingual UI Automation smoke, empty profile only.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$BuildDirectory
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
    if ($file.PSIsContainer -or $file.Length -ne $entry.bytes -or
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
        if ($process.HasExited) { throw 'Application exited before UIA readiness.' }
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
$exe = Join-Path $app 'VirtualCar.WinUI.exe'
$process = Start-Process -FilePath $exe -WorkingDirectory $app -ArgumentList '--ephemeral-settings' -PassThru
$passed = 0
$navigationPassed = 0
$journalPassed = 0
try {
    $window = Wait-OwnedWindow $process
    foreach ($case in @(
        @{ code='EN'; heading='CEM529 Configuration'; load='Load profile'; audit='Configuration audit' },
        @{ code='RU'; heading='Конфигурация CEM529'; load='Загрузить профиль'; audit='Аудит конфигурации' },
        @{ code='EN'; heading='CEM529 Configuration'; load='Load profile'; audit='Configuration audit' }
    )) {
        if ($passed -gt 0) { Set-Language $window $case.code }
        Assert-Name $window 'VC075.Heading' $case.heading
        Assert-Name $window 'VC075.Load' $case.load
        Assert-Name $window 'VC075.AuditHeading' $case.audit
        if ((Wait-Element $window 'VC075.Load').Current.IsEnabled) { throw 'Private CEM load enabled in ephemeral smoke.' }
        $passed++
        Write-Host "PASS language $($case.code)"
        $sections = if ($case.code -eq 'RU') {
            @(
                @{ key='Vehicle'; label='Виртуальный автомобиль' },
                @{ key='Modules'; label='Электронные блоки' },
                @{ key='Diagnostics'; label='Диагностика' },
                @{ key='Connection'; label='Подключение' }
            )
        } else {
            @(
                @{ key='Vehicle'; label='Virtual vehicle' },
                @{ key='Modules'; label='ECU modules' },
                @{ key='Diagnostics'; label='Diagnostics' },
                @{ key='Connection'; label='Connection' }
            )
        }
        foreach ($section in $sections) {
            Select-Section $window $section.key
            Assert-Name $window 'VC075.Heading' $section.label
            Assert-Name $window 'VC077.PlaceholderHeading' $section.label
            Assert-EditorHidden $window
            if ($section.key -eq 'Diagnostics') {
                Select-JournalView $window 'Journal'
                $emptyJournal = if ($case.code -eq 'RU') { 'Нет записей журнала.' } else { 'No log records available.' }
                Assert-Name $window 'VC085.Diagnostics.Summary' $emptyJournal
                Select-JournalView $window 'Can'
                $journalPassed++
                $start = Wait-Element $window 'VC084.Monitor.Start'
                $stop = Wait-Element $window 'VC084.Monitor.Stop'
                $refresh = Wait-Element $window 'VC084.Monitor.Refresh'
                if ($start.Current.IsEnabled -or $stop.Current.IsEnabled -or $refresh.Current.IsEnabled) {
                    throw 'Log monitoring enabled in ephemeral smoke.'
                }
                if ($case.code -eq 'RU') {
                    Assert-Name $window 'VC084.Monitor.Start' 'Запустить монитор'
                } else {
                    Assert-Name $window 'VC084.Monitor.Start' 'Start monitor'
                }
            }
            if ($section.key -eq 'Modules') {
                $read = Wait-Element $window 'VC083.Modules.Refresh'
                if ($read.Current.IsEnabled) { throw 'ECU inventory inspection enabled in ephemeral smoke.' }
                if ($case.code -eq 'RU') {
                    Assert-Name $window 'VC083.Modules.Refresh' 'Прочитать настроенные ECU'
                } else {
                    Assert-Name $window 'VC083.Modules.Refresh' 'Read configured ECUs'
                }
            }
            if ($section.key -eq 'Vehicle') {
                $apply = Wait-Element $window 'VC080.Vehicle.Apply'
                $inspect = Wait-Element $window 'VC079.Vehicle.Inspect'
                $restore = Wait-Element $window 'VC081.Vehicle.Restore'
                $ignition = Wait-Element $window 'VC082.Ignition.Apply'
                if ($ignition.Current.IsEnabled) { throw 'Ignition mutation enabled in ephemeral smoke.' }
                if ($restore.Current.IsEnabled) { throw 'Restore enabled in ephemeral smoke.' }
                if ($apply.Current.IsEnabled -or $inspect.Current.IsEnabled) { throw 'Profile modification or inspection enabled in ephemeral smoke.' }
                if ($case.code -eq 'RU') {
                    Assert-Name $window 'VC080.Vehicle.Apply' 'Применить сценарий'
                    Assert-Name $window 'VC081.Vehicle.Restore' 'Восстановить копию'
                    Assert-Name $window 'VC082.Ignition.Apply' 'Применить кандидат зажигания'
                } else {
                    Assert-Name $window 'VC080.Vehicle.Apply' 'Apply scenario'
                    Assert-Name $window 'VC081.Vehicle.Restore' 'Restore backup'
                    Assert-Name $window 'VC082.Ignition.Apply' 'Apply ignition candidate'
                }
            }
            if ($section.key -eq 'Connection') {
                $driverRefresh = Wait-Element $window 'VC078.Driver.Refresh'
                if ($driverRefresh.Current.IsEnabled) { throw 'Registry refresh enabled in ephemeral smoke.' }
                $install = Wait-Element $window 'VC078.Driver.Install'
                $remove = Wait-Element $window 'VC078.Driver.Remove'
                if ($install.Current.IsEnabled -or $remove.Current.IsEnabled) { throw 'Driver mutation enabled in ephemeral smoke.' }
                if ($case.code -eq 'RU') {
                    Assert-Name $window 'VC078.Driver.Install' 'Установить драйвер'
                    Assert-Name $window 'VC078.Driver.Remove' 'Удалить драйвер'
                } else {
                    Assert-Name $window 'VC078.Driver.Install' 'Install driver'
                    Assert-Name $window 'VC078.Driver.Remove' 'Remove driver'
                }
            }
            $navigationPassed++
            Write-Host "PASS navigation $($case.code) $($section.key)"
        }
        Select-Section $window 'Configuration'
        Assert-Name $window 'VC075.Heading' $case.heading
        Assert-Name $window 'VC075.Load' $case.load
        Assert-Name $window 'VC075.AuditHeading' $case.audit
        $navigationPassed++
        Write-Host "PASS navigation $($case.code) Configuration"
    }
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
if ($passed -ne 3 -or $navigationPassed -ne 15 -or $journalPassed -ne 3) { throw 'Language/navigation checks incomplete.' }
Write-Host "VC075_SOURCE_SHA=$ExpectedSha"
Write-Host 'VC075_EMPTY_UI_LANG=PASS 3/3'
Write-Host 'VC077_EMPTY_NAVIGATION=PASS 15/15'
Write-Host 'VC086_EMPTY_JOURNAL=PASS 3/3'
Write-Host 'VC086_EMPTY_LOCKOUT=PASS'
Write-Host 'VC077_LOADED_PROFILE_NAVIGATION=NOT_TESTED'
Write-Host 'VC075_LOADED_PROFILE_LANG=NOT_TESTED'
Write-Host 'VC075_PRIVATE_PREVIEW=NOT_TESTED'
