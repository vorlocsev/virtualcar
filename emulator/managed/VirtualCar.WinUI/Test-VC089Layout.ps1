# VC089 actual-DPI empty-window capture. Owner-local interactive desktop only.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][ValidateSet(100,125,150,175,200)][int]$ExpectedScale
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


$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
function Assert-Checkout {
    $head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'Exact source checkout required.' }
    $dirty = @(& git -C $repo status --porcelain --untracked-files=all)
    if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean source checkout required.' }
}
Assert-Checkout
if ($OutputDirectory -notmatch '^[a-zA-Z]:[\\/]') { throw 'Absolute local output directory required.' }
$out = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $out) { throw 'Output directory already exists.' }
if ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($out)).DriveType -ne [IO.DriveType]::Fixed) { throw 'Fixed local drive required.' }
$cursor = Get-Item -LiteralPath (Split-Path -Parent $out)
if ($cursor -isnot [IO.DirectoryInfo]) { throw 'Output parent must be a directory.' }
while ($null -ne $cursor) {
    if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        (Test-Path -LiteralPath (Join-Path $cursor.FullName '.git')) -or
        $cursor.FullName.TrimEnd('\') -eq $directory.TrimEnd('\')) { throw 'Unsafe output ancestry.' }
    $cursor = $cursor.Parent
}
[void](New-Item -ItemType Directory -Path $out)
Add-Type -AssemblyName System.Drawing
if (-not ('VC089.NativeLayout' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
namespace VC089 {
    public static class NativeLayout {
        [StructLayout(LayoutKind.Sequential)]
        public struct RECT { public int Left, Top, Right, Bottom; }
        [StructLayout(LayoutKind.Sequential)]
        public struct POINT { public int X, Y; }
        [StructLayout(LayoutKind.Sequential)]
        public struct MONITORINFO { public int Size; public RECT Monitor, Work; public int Flags; }
        [DllImport("user32.dll")] public static extern uint GetDpiForWindow(IntPtr h);
        [DllImport("user32.dll")] public static extern IntPtr GetWindowDpiAwarenessContext(IntPtr h);
        [DllImport("user32.dll")] public static extern bool AreDpiAwarenessContextsEqual(IntPtr a, IntPtr b);
        [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr context);
        [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT rect);
        [DllImport("user32.dll")] public static extern IntPtr MonitorFromWindow(IntPtr h, uint flags);
        [DllImport("user32.dll", CharSet=CharSet.Auto)] public static extern bool GetMonitorInfo(IntPtr h, ref MONITORINFO info);
        [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
        [DllImport("user32.dll")] public static extern bool IsIconic(IntPtr h);
        [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
        [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h, uint flags);
        [DllImport("dwmapi.dll")] public static extern int DwmGetWindowAttribute(IntPtr h, int attribute, out RECT rect, int size);
        public static RECT Frame(IntPtr h) {
            RECT r;
            if (DwmGetWindowAttribute(h,9,out r,Marshal.SizeOf(typeof(RECT))) != 0)
                throw new InvalidOperationException("DWM frame bounds unavailable.");
            return r;
        }
        public static RECT Client(IntPtr h) {
            RECT r;
            if (!GetClientRect(h,out r)) throw new InvalidOperationException("Client size unavailable.");
            return r;
        }
        public static RECT Work(IntPtr h) {
            MONITORINFO i = new MONITORINFO();
            i.Size = Marshal.SizeOf(typeof(MONITORINFO));
            if (!GetMonitorInfo(MonitorFromWindow(h,2),ref i)) throw new InvalidOperationException("Monitor work area unavailable.");
            return i.Work;
        }
        public static bool SampleVisible(IntPtr h, RECT r) {
            for (int x=1;x<=5;x++) for(int y=1;y<=5;y++) {
                POINT p = new POINT { X=r.Left+(r.Right-r.Left)*x/6, Y=r.Top+(r.Bottom-r.Top)*y/6 };
                if (GetAncestor(WindowFromPoint(p),2)!=h) return false;
            }
            return true;
        }
    }
}
'@
}
$records = [System.Collections.Generic.List[object]]::new()
function Assert-Visible($window,[string]$id,$frame) {
    $timer = [Diagnostics.Stopwatch]::StartNew()
    do {
        $element = Find-Element $window $id
        if ($null -ne $element -and -not $element.Current.IsOffscreen) {
            $bounds = $element.Current.BoundingRectangle
            if (-not $bounds.IsEmpty -and $bounds.Width -gt 1 -and $bounds.Height -gt 1 -and
                $bounds.Left -ge ($frame.Left-2) -and $bounds.Top -ge ($frame.Top-2) -and
                $bounds.Right -le ($frame.Right+2) -and $bounds.Bottom -le ($frame.Bottom+2)) { return }
        }
        Start-Sleep -Milliseconds 100
    } while ($timer.Elapsed.TotalSeconds -lt 5)
    throw "Element outside visible window: $id"
}
function Capture-View($window,[string]$language,[string]$section,[string]$position,[string[]]$anchors) {
    $process.Refresh()
    if ($process.HasExited) { throw 'Application exited during layout capture.' }
    $hwnd = $process.MainWindowHandle
    [uint32]$owner = 0
    if ($hwnd -eq [IntPtr]::Zero -or [VC086.WindowOwnership]::GetWindowThreadProcessId($hwnd,[ref]$owner) -eq 0 -or $owner -ne $process.Id) { throw 'Window ownership changed.' }
    $context = [VC089.NativeLayout]::GetWindowDpiAwarenessContext($hwnd)
    if (-not [VC089.NativeLayout]::AreDpiAwarenessContextsEqual($context,[IntPtr](-4))) {
        throw 'Window is not PerMonitorV2 DPI-aware. DPI-unaware/system-aware captures are not acceptance evidence.'
    }
    $dpi = [VC089.NativeLayout]::GetDpiForWindow($hwnd)
    if ($dpi -ne ($ExpectedScale * 96 / 100)) { throw "Actual DPI $dpi does not match requested scale $ExpectedScale." }
    $frame = [VC089.NativeLayout]::Frame($hwnd)
    $work = [VC089.NativeLayout]::Work($hwnd)
    $width = $frame.Right - $frame.Left
    $height = $frame.Bottom - $frame.Top
    if ($width -le 0 -or $height -le 0 -or $frame.Left -lt $work.Left -or $frame.Top -lt $work.Top -or
        $frame.Right -gt $work.Right -or $frame.Bottom -gt $work.Bottom) { throw 'Visible window exceeds monitor work area.' }
    $client = [VC089.NativeLayout]::Client($hwnd)
    $clientWidth = [Math]::Round(($client.Right-$client.Left)*96.0/$dpi,1)
    $clientHeight = [Math]::Round(($client.Bottom-$client.Top)*96.0/$dpi,1)
    if ($clientWidth -lt 850 -or $clientHeight -lt 450) { throw "Insufficient client viewport: $clientWidth x $clientHeight DIP. Use a larger display/work area." }
    foreach ($id in @('VC075.Heading','VC075.Language','VC077.Navigation') + $anchors) { Assert-Visible $window $id $frame }
    [void][VC089.NativeLayout]::SetForegroundWindow($hwnd)
    Start-Sleep -Milliseconds 350
    if ([VC089.NativeLayout]::IsIconic($hwnd) -or [VC089.NativeLayout]::GetForegroundWindow() -ne $hwnd -or
        -not [VC089.NativeLayout]::SampleVisible($hwnd,$frame)) { throw 'Window is not foreground/unobscured at sampled points.' }
    $name = "VC089-$ExpectedScale-$language-$section-$position.png"
    $target = Join-Path $out $name
    $bitmap = [Drawing.Bitmap]::new($width,$height)
    $graphics = [Drawing.Graphics]::FromImage($bitmap)
    try {
        $graphics.CopyFromScreen($frame.Left,$frame.Top,0,0,[Drawing.Size]::new($width,$height))
        if ([VC089.NativeLayout]::GetForegroundWindow() -ne $hwnd -or -not [VC089.NativeLayout]::SampleVisible($hwnd,$frame)) { throw 'Window obscured during capture.' }
        $bitmap.Save($target,[Drawing.Imaging.ImageFormat]::Png)
    }
    finally { $graphics.Dispose(); $bitmap.Dispose() }
    $records.Add([ordered]@{ language=$language; section=$section; position=$position; dpi=$dpi; scale_percent=$ExpectedScale; dpi_awareness='PerMonitorV2'; client_width_dip=$clientWidth; client_height_dip=$clientHeight; width_px=$width; height_px=$height; file=$name; sha256=(Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash })
    Write-Host ("PASS capture {0} {1} {2} DPI={3} client={4}x{5}" -f $language,$section,$position,$dpi,$clientWidth,$clientHeight)
}
function Scroll-Workspace($window,[double]$percent) {
    $element = Find-Element $window 'VC089.WorkspaceScroll'
    $pattern = $null
    if ($null -eq $element -or -not $element.TryGetCurrentPattern([System.Windows.Automation.ScrollPattern]::Pattern,[ref]$pattern)) { return $false }
    if ($pattern.Current.VerticallyScrollable) {
        $pattern.SetScrollPercent(-1,$percent)
        Start-Sleep -Milliseconds 300
        if ([Math]::Abs($pattern.Current.VerticalScrollPercent-$percent) -gt 2) { throw 'Requested scroll position not reached.' }
        return $true
    }
    return $false
}
$previousDpi = [VC089.NativeLayout]::SetThreadDpiAwarenessContext([IntPtr](-4))
if ($previousDpi -eq [IntPtr]::Zero) { throw 'Per-monitor DPI awareness unavailable.' }
$process = $null
try {
    $process = Start-Process -FilePath (Join-Path $app 'VirtualCar.WinUI.exe') -WorkingDirectory $app -ArgumentList '--ephemeral-settings' -PassThru
    $window = Wait-OwnedWindow $process
    foreach ($lang in @('EN','RU')) {
        if ($lang -eq 'RU') { Set-Language $window 'RU' }
        foreach ($section in @('Configuration','Vehicle','Modules','Diagnostics','Connection')) {
            Select-Section $window $section
            $heading = if ($lang -eq 'RU') {
                @{Configuration='Конфигурация CEM529';Vehicle='Виртуальный автомобиль';Modules='Электронные блоки';Diagnostics='Диагностика';Connection='Подключение'}[$section]
            } else {
                @{Configuration='CEM529 Configuration';Vehicle='Virtual vehicle';Modules='ECU modules';Diagnostics='Diagnostics';Connection='Connection'}[$section]
            }
            Assert-Name $window 'VC075.Heading' $heading
            if ($section -eq 'Configuration') {
                Capture-View $window $lang $section 'top' @('VC075.Load','VC075.Search','VC075.Filter','VC075.AuditHeading')
            } else {
                Assert-EditorHidden $window
                [void](Scroll-Workspace $window 0)
                $anchor = @{Vehicle='VC079.Vehicle.Inspect';Modules='VC083.Modules.Refresh';Diagnostics='VC084.Monitor.Start';Connection='VC078.Driver.Refresh'}[$section]
                Capture-View $window $lang $section 'top' @('VC077.PlaceholderHeading',$anchor)
                $bottom = @{Vehicle='VC081.Vehicle.Restore';Modules='VC083.Modules.Status';Diagnostics='VC088.Monitor.Status';Connection='VC078.Driver.Remove'}[$section]
                $scrolled = Scroll-Workspace $window 100
                if ($scrolled) {
                    Capture-View $window $lang $section 'bottom' @($bottom)
                    [void](Scroll-Workspace $window 0)
                } else {
                    Assert-Visible $window $bottom ([VC089.NativeLayout]::Frame($process.MainWindowHandle))
                }
            }
        }
    }
    Set-Language $window 'EN'
}
finally {
    try {
        if ($null -ne $process) {
            $process.Refresh()
            if (-not $process.HasExited) {
                [void]$process.CloseMainWindow()
                if (-not $process.WaitForExit(5000)) {
                    $process.Kill()
                    [void]$process.WaitForExit(5000)
                    throw 'Layout window did not close normally.'
                }
            }
            if ($process.ExitCode -ne 0) { throw ('Layout exit: 0x{0:X8}' -f $process.ExitCode) }
        }
    }
    finally {
        if ($null -ne $process) { $process.Dispose() }
        [void][VC089.NativeLayout]::SetThreadDpiAwarenessContext($previousDpi)
    }
}
Assert-Checkout
$finalFiles = @(Get-ChildItem -LiteralPath $app -Recurse -File)
if ($finalFiles.Count -ne @($manifest.files).Count) { throw 'Final inventory count mismatch.' }
foreach ($entry in $manifest.files) {
    $file = Get-Item -LiteralPath (Join-Path $app $entry.path)
    if ($file -isnot [IO.FileInfo] -or $file.Length -ne $entry.bytes -or
        (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256) { throw 'Final build integrity mismatch.' }
}
if (@($records | Where-Object {$_.position -eq 'top'}).Count -ne 10) { throw 'Incomplete page capture.' }
[ordered]@{schema='vc089-layout-evidence-v1';source_sha=$ExpectedSha;scale_percent=$ExpectedScale;dpi_awareness='PerMonitorV2';status='capture_pass';visual_review='not_tested';captures=@($records.ToArray())} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $out 'vc089-layout.json') -Encoding UTF8
Write-Host "VC089_LAYOUT_CAPTURE=PASS SCALE=$ExpectedScale SHA=$ExpectedSha VISUAL_REVIEW=NOT_TESTED"
