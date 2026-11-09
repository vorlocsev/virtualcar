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
    }
    exit 0
} catch {
    [Console]::Error.WriteLine('Read-only SectorV operator helper stopped: missing, unsafe or unverified input.')
    exit 2
}
