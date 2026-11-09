#Requires -Version 5.1
<#
Read-only, strictly redacted snapshot of SectorV process -> registered J2534 DLL
on the *current self-hosted CI runner*. Never starts SectorV, loads a DLL,
changes registry, opens other processes by PID or prints a path, PID or VIN.
A process-name match is not proof of the genuine SectorV binary.
#>
[CmdletBinding()]
param([switch]$SelfTest)
$ErrorActionPreference = 'Stop'

function Get-ClientBindingState {
    param([object[]]$Clients, [string]$RegisteredPath)
    if ($null -eq $Clients -or $Clients.Count -eq 0) {
        return 'client_not_observed_in_runner_context'
    }
    if ($Clients.Count -ne 1) {
        return 'multiple_client_name_matches'
    }
    if ([string]::IsNullOrWhiteSpace($RegisteredPath)) {
        return 'registered_library_unknown'
    }
    try {
        $value = [Environment]::ExpandEnvironmentVariables($RegisteredPath.Trim().Trim('"'))
        if (-not [IO.Path]::IsPathRooted($value) -or $value.StartsWith('\\')) {
            return 'registered_library_path_unverifiable'
        }
        $expected = [IO.Path]::GetFullPath($value)
    } catch {
        return 'registered_library_path_unverifiable'
    }
    try {
        $modules = @($Clients[0].Modules)
        # PowerShell 5.1 can turn an inaccessible ScriptProperty/Modules
        # getter into $null without raising a terminating exception. Empty
        # enumeration is NOT proof that the registered DLL is absent.
        if ($modules.Count -eq 0 -or
            ($modules.Count -eq 1 -and $null -eq $modules[0])) {
            return 'client_module_list_unavailable'
        }
        foreach ($module in $modules) {
            if ($null -eq $module -or [string]::IsNullOrWhiteSpace($module.FileName)) {
                continue
            }
            $actual = [IO.Path]::GetFullPath([string]$module.FileName)
            if ([string]::Equals($actual, $expected, [StringComparison]::OrdinalIgnoreCase)) {
                return 'registered_library_loaded_in_name_matched_client'
            }
        }
        return 'registered_library_not_in_enumerated_modules'
    } catch {
        return 'client_module_list_unavailable'
    }
}

function Invoke-LocalSelfTests {
    $expected = 'C:\VirtualCarLab\VirtualCarJ2534.dll'
    $other = 'C:\VirtualCarLab\OtherJ2534.dll'
    $yes = [pscustomobject]@{Modules=@([pscustomobject]@{FileName=$expected})}
    $no = [pscustomobject]@{Modules=@([pscustomobject]@{FileName=$other})}
    $inaccessible = New-Object PSObject
    $inaccessible | Add-Member -MemberType ScriptProperty -Name Modules -Value {throw 'denied'}
    $cases = @(
        @{Clients=@();Path=$expected;Want='client_not_observed_in_runner_context'},
        @{Clients=@($yes,$yes);Path=$expected;Want='multiple_client_name_matches'},
        @{Clients=@($yes);Path=$null;Want='registered_library_unknown'},
        @{Clients=@($yes);Path='relative.dll';Want='registered_library_path_unverifiable'},
        @{Clients=@($yes);Path=$expected;Want='registered_library_loaded_in_name_matched_client'},
        @{Clients=@($yes);Path='c:\VIRTUALCARLAB\VIRTUALCARJ2534.DLL';Want='registered_library_loaded_in_name_matched_client'},
        @{Clients=@($no);Path=$expected;Want='registered_library_not_in_enumerated_modules'},
        @{Clients=@($inaccessible);Path=$expected;Want='client_module_list_unavailable'},
        @{Clients=@([pscustomobject]@{Modules=@()});Path=$expected;Want='client_module_list_unavailable'}
    )
    $passed=0
    foreach ($case in $cases) {
        $actual = Get-ClientBindingState -Clients $case.Clients -RegisteredPath $case.Path
        if ($actual -cne $case.Want) {
            # Both expected and actual are from a closed set of public category
            # constants. Never emit a path, process object, hash or exception.
            $allowed = @(
                'client_not_observed_in_runner_context',
                'multiple_client_name_matches',
                'registered_library_unknown',
                'registered_library_path_unverifiable',
                'registered_library_loaded_in_name_matched_client',
                'registered_library_not_in_enumerated_modules',
                'client_module_list_unavailable'
            )
            $safeActual = if ($allowed -ccontains $actual) { $actual } else { 'unexpected_category' }
            throw ('SectorV binding synthetic test #{0}: expected={1}; actual={2}' -f
                   ($passed+1), $case.Want, $safeActual)
        }
        $passed++
    }
    # Output remains categorical, including when a private path is supplied.
    $result = @{
        schema_version = 'virtualcar-sectorv-process-binding-v1'
        scope = 'current_ci_runner_process_snapshot_only'
        observation = Get-ClientBindingState -Clients @($yes) -RegisteredPath $expected
        name_matched_executable_authenticity = 'not_verified'
        client_was_launched_by_audit = $false
        accepted_vin_or_ecu = 'not_verified'
    } | ConvertTo-Json -Compress
    if ($result.Contains('C:\') -or $result.Contains('VirtualCarJ2534.dll') -or
        $result.Contains('PassThruOpen') -or $result.Contains('PID')) {
        throw 'Redaction self-test failed'
    }
    Write-Host ("PASS: {0}/{0} redacted SectorV process-binding tests" -f $passed)
}

if ($SelfTest) {
    Invoke-LocalSelfTests
    exit 0
}

# Read ONLY the 32-bit canonical Virtual Car J2534 registry key.
# The process observation is passive and checks only the exact name SectorV.
$library = $null
try {
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine,
        [Microsoft.Win32.RegistryView]::Registry32)
    try {
        $key = $base.OpenSubKey('SOFTWARE\PassThruSupport.04.04\SectorV Virtual Car', $false)
        if ($null -ne $key) {
            try {
                $kind = $key.GetValueKind('FunctionLibrary')
                if ($kind -eq [Microsoft.Win32.RegistryValueKind]::String -or
                    $kind -eq [Microsoft.Win32.RegistryValueKind]::ExpandString) {
                    $library = [string]$key.GetValue('FunctionLibrary', $null,
                        [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                }
            } finally { $key.Dispose() }
        }
    } finally { $base.Dispose() }
} catch {
    $library = $null
}

$processes = @()
try {
    $processes = @(Get-Process -Name 'SectorV' -ErrorAction SilentlyContinue)
} catch {
    # A restricted CI token can be unable to enumerate another user session.
    # Do not treat that as client absence or client failure.
    $processes = @()
    $processObservation = 'client_process_listing_unavailable'
}
if (-not $processObservation) {
    $processObservation = Get-ClientBindingState -Clients $processes -RegisteredPath $library
}

# Fixed allowlisted categories only. Never serialize processes, registry values,
# exception messages, module paths, file hashes, environment or identifiers.
$result = [ordered]@{
    schema_version = 'virtualcar-sectorv-process-binding-v1'
    scope = 'current_ci_runner_process_snapshot_only'
    observation = $processObservation
    name_matched_executable_authenticity = 'not_verified'
    client_was_launched_by_audit = $false
    accepted_vin_or_ecu = 'not_verified'
}
Write-Output ($result | ConvertTo-Json -Compress)
