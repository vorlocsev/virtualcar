#Requires -Version 5.1
<#
Guided, read-only SectorV operator capture on the user's isolated Windows guest.
It never launches SectorV, loads J2534, changes registration, sends CAN, or
infers VIN/ECU acceptance. A single-run flag remains an operator assertion.
Only the existing Python collector writes the private baseline and redacted reports.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('Begin','Module','Finish')][string]$Phase,
    [Parameter(Mandatory=$true)][string]$SessionDir,
    [string]$J2534Log = '',
    [string]$BackendLog = '',
    [string]$PythonExe = '',
    [switch]$IsolatedReadOnlyVm,
    [switch]$PhysicalAdapterDisconnected,
    [switch]$SingleRunConfirmed,
    [switch]$NonInteractive,
    [string]$ReferenceDll = '',
    [string]$AdapterListed = '',
    [string]$AdapterSelected = '',
    [string]$Connection = '',
    [string]$EcuList = '',
    [string]$VehicleIdentity = '',
    [string]$ErrorCategory = ''
)
$ErrorActionPreference = 'Stop'

# Do not print real source paths, interpreter paths or exception text.
function Select-Observation {
    param([string]$Label, [string]$Value, [string[]]$Allowed)
    if ([string]::IsNullOrWhiteSpace($Value)) {
        if ($NonInteractive) { throw 'Missing explicit observation' }
        $Value = Read-Host ("{0} ({1}; Enter = unknown)" -f $Label,
                             ($Allowed -join '/'))
        if ([string]::IsNullOrWhiteSpace($Value)) { $Value = 'unknown' }
    }
    $Value = $Value.Trim().ToLowerInvariant()
    if ($Allowed -cnotcontains $Value) { throw 'Unsupported observation' }
    return $Value
}


# Text comes exclusively from this fixed allowlist, never from client paths,
# binary metadata, VIN or user-provided diagnostic logs. Keep ASCII for PS5.1.
function Get-SafeReferenceAdvice {
    param([string]$Status)
    switch -CaseSensitive ($Status) {
        'x86_pe32_header' {
            return 'J2534 reference: x86 PE32 header observed; exports, binding and VIN/ECU are NOT verified.'
        }
        'other_pe' {
            return 'J2534 reference WARNING: not an x86 PE32 header. Choose an x86 reference before relying on byte comparison.'
        }
        'invalid_pe' {
            return 'J2534 reference WARNING: invalid PE header. Replace the reference before relying on byte comparison.'
        }
        'unverifiable' {
            return 'J2534 reference WARNING: file architecture could not be inspected. Check the local reference DLL.'
        }
        'not_compared' {
            return 'J2534 reference: none supplied; installed DLL byte equivalence and architecture are not checked.'
        }
        'not_assessed_by_this_tool' {
            return 'J2534 reference: legacy observation did not assess PE32 architecture.'
        }
        default { throw 'Unsupported J2534 reference status' }
    }
}

try {
    if (-not $IsolatedReadOnlyVm -or -not $PhysicalAdapterDisconnected) {
        throw 'Required isolated offline lab confirmations are absent'
    }
    $tools = $PSScriptRoot
    $collector = Join-Path $tools 'audit_sectorv_operator_session.py'
    $moduleTool = Join-Path $tools 'audit_vmware_sectorv_process.ps1'
    if (-not (Test-Path -LiteralPath $collector -PathType Leaf)) {
        throw 'Operator collector not included'
    }
    if ([string]::IsNullOrWhiteSpace($J2534Log)) {
        $J2534Log = Join-Path $env:TEMP 'SectorVVirtualCar.log'
    }
    if ([string]::IsNullOrWhiteSpace($BackendLog)) {
        $BackendLog = Join-Path $env:LOCALAPPDATA 'VirtualCar\dev47-backend.jsonl'
    }
    $phaseArgs = @()
    if ($Phase -eq 'Begin') {
        if ($SingleRunConfirmed -or $ReferenceDll) {
            throw 'Begin must not assert GUI results'
        }
        $phaseArgs = @('begin', '--session-dir', $SessionDir,
                       '--j2534', $J2534Log, '--backend', $BackendLog)
    } elseif ($Phase -eq 'Module') {
        if ($SingleRunConfirmed -or -not (Test-Path -LiteralPath $moduleTool -PathType Leaf)) {
            throw 'Module step is not ready'
        }
        if (-not (Test-Path -LiteralPath $SessionDir -PathType Container)) {
            throw 'No prior private operator session'
        }
        # A module snapshot is meaningful only between Begin and Finish.
        # An arbitrary existing folder is not evidence of an active session.
        $baseline = Join-Path $SessionDir 'p0-before.private.json'
        $windowReport = Join-Path $SessionDir 'p0-window.redacted.json'
        $triageReport = Join-Path $SessionDir 'p0-triage.redacted.json'
        if (-not (Test-Path -LiteralPath $baseline -PathType Leaf) -or
            (Test-Path -LiteralPath $windowReport) -or
            (Test-Path -LiteralPath $triageReport)) {
            throw 'Module snapshot requires an unfinished operator baseline'
        }
        $moduleReport = Join-Path $SessionDir 'p0-module.redacted.json'
        $moduleArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', $moduleTool, '-OperatorSession', '-OutputFile', $moduleReport)
        if ($ReferenceDll) { $moduleArgs += @('-ReferenceDll', $ReferenceDll) }
        $winps = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
        if (-not (Test-Path -LiteralPath $winps -PathType Leaf)) {
            throw 'Windows PowerShell 5.1 not available'
        }
        & $winps @moduleArgs | Out-Null
        if ($LASTEXITCODE -ne 0) { throw 'Module snapshot failed' }
        # This JSON was just created by the local read-only module inspector.
        # Re-check the fixed schema and render ONLY category-based advice.
        $moduleState = Get-Content -LiteralPath $moduleReport -Raw -Encoding UTF8 |
                       ConvertFrom-Json -ErrorAction Stop
        if ($moduleState.schema_version -cne 'virtualcar-sectorv-process-binding-operator-v1' -or
            $moduleState.scope -cne 'operator_requested_current_host_snapshot_only' -or
            $moduleState.accepted_vin_or_ecu -cne 'not_verified') {
            throw 'Invalid operator module evidence'
        }
        Write-Host (Get-SafeReferenceAdvice -Status ([string]$moduleState.reference_dll_pe32))
        Write-Host 'Redacted module snapshot captured; client and VIN identity remain unverified.'
        exit 0
    } else {
        $observations = @(
            @('adapter-listed', 'Adapter listed', $AdapterListed, @('yes','no','unknown')),
            @('adapter-selected', 'Adapter selected', $AdapterSelected, @('yes','no','unknown')),
            @('connection', 'Connection', $Connection, @('connected','failed','not_attempted','unknown')),
            @('ecu-list', 'ECU list', $EcuList, @('populated','empty','not_opened','unknown')),
            @('vehicle-identity', 'Vehicle identity', $VehicleIdentity, @('displayed','not_displayed','unknown')),
            @('error-category', 'Error category', $ErrorCategory,
              @('none','adapter_missing','connect_error','vin_read_failed',
                'vehicle_unrecognized','timeout','other','unknown'))
        )
        $phaseArgs = @('finish', '--session-dir', $SessionDir,
                       '--j2534', $J2534Log, '--backend', $BackendLog,
                       '--isolated-read-only-vm', '--physical-adapter-disconnected')
        foreach ($item in $observations) {
            $value = Select-Observation -Label $item[1] -Value $item[2] -Allowed $item[3]
            # Build the switch as ONE string. An isolated '--' terminates
            # argparse option parsing and silently loses all six GUI states.
            $option = '--' + [string]$item[0]
            $phaseArgs += $option
            $phaseArgs += [string]$value
        }
        if ($SingleRunConfirmed) { $phaseArgs += '--single-run-confirmed' }
        $moduleReport = Join-Path $SessionDir 'p0-module.redacted.json'
        if (Test-Path -LiteralPath $moduleReport -PathType Leaf) {
            $phaseArgs += @('--module-snapshot', $moduleReport)
        }
    }
    # Python paths may contain spaces. Pass them as distinct literal arguments.
    $prefix = @()
    if ([string]::IsNullOrWhiteSpace($PythonExe)) {
        $py = Get-Command py.exe -ErrorAction SilentlyContinue
        if ($null -eq $py) { throw 'Python 3 launcher unavailable' }
        $PythonExe = $py.Source
        $prefix = @('-3')
    } else {
        $py = Get-Command $PythonExe -ErrorAction SilentlyContinue
        if ($null -eq $py) { throw 'Selected Python not available' }
        $PythonExe = $py.Source
    }
    & $PythonExe @prefix $collector @phaseArgs | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Operator collector rejected inputs' }
    if ($Phase -eq 'Begin') {
        Write-Host 'Private baseline saved. Run SectorV manually in the isolated VM; no client was launched.'
    } else {
        Write-Host 'Redacted window and GUI triage saved. No OEM VIN or ECU acceptance was inferred.'
        # Read ONLY the strict, redacted report that the trusted Python
        # collector has just written. Never print private logs or exception
        # details. The action text comes from a fixed Python allowlist.
        $reportPath = Join-Path $SessionDir 'p0-triage.redacted.json'
        $safeReport = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ([string]::IsNullOrWhiteSpace([string]$safeReport.first_next_action_ru) -or
            [string]$safeReport.first_next_action_ru -match '[\r\n]' -or
            [string]$safeReport.first_next_action_ru -match '[<>]') {
            throw 'Unsafe or missing next diagnostic action'
        }
        if ($null -ne $safeReport.operator_module_snapshot) {
            # Python strictly validated this optional categorical snapshot.
            # Never echo raw module properties or arbitrary GUI text.
            Write-Host (Get-SafeReferenceAdvice -Status (
                [string]$safeReport.operator_module_snapshot.reference_pe32_header))
        }
        Write-Host ('Следующий безопасный шаг: ' + [string]$safeReport.first_next_action_ru)
    }
    exit 0
} catch {
    [Console]::Error.WriteLine('Read-only SectorV operator helper stopped: missing, unsafe or unverified input.')
    exit 2
}
