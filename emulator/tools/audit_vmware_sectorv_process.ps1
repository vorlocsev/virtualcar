#Requires -Version 5.1
<#
Read-only, strictly redacted snapshot of SectorV process -> registered J2534 DLL
on the *current self-hosted CI runner*. Never starts SectorV, loads a DLL,
changes registry, opens other processes by PID or prints a path, PID or VIN.
A process-name match is not proof of the genuine SectorV binary.
#>
[CmdletBinding()]
param(
    [switch]$SelfTest,
    [switch]$OperatorSession,
    [string]$ReferenceDll,
    [string]$OutputFile
)
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

# Operator-requested *local* snapshot; the flag does not attest that this
# host is the guest VM or that the name-matched process is authentic SectorV.
function Get-ByteEquivalence {
    param([string]$RegisteredPath, [string]$ReferencePath)
    if ([string]::IsNullOrWhiteSpace($ReferencePath)) { return 'not_compared' }
    try {
        $paths = @()
        foreach ($raw in @($RegisteredPath, $ReferencePath)) {
            if ([string]::IsNullOrWhiteSpace($raw)) { return 'comparison_unverifiable' }
            $expanded = [Environment]::ExpandEnvironmentVariables($raw.Trim().Trim('"'))
            if (-not [IO.Path]::IsPathRooted($expanded) -or $expanded.StartsWith('\\')) {
                return 'comparison_unverifiable'
            }
            $full = [IO.Path]::GetFullPath($expanded)
            $file = New-Object IO.FileInfo($full)
            if (-not $file.Exists -or $file.Length -lt 96 -or
                $file.Length -gt 67108864) { return 'comparison_unverifiable' }
            $paths += $file
        }
        # A digest is only a point-in-time byte comparison, not a version,
        # code-identity or application-acceptance attestation.
        $beforeA = @($paths[0].Length, $paths[0].LastWriteTimeUtc.Ticks)
        $beforeB = @($paths[1].Length, $paths[1].LastWriteTimeUtc.Ticks)
        $hashA = (Get-FileHash -LiteralPath $paths[0].FullName -Algorithm SHA256).Hash
        $hashB = (Get-FileHash -LiteralPath $paths[1].FullName -Algorithm SHA256).Hash
        $paths[0].Refresh(); $paths[1].Refresh()
        if ($paths[0].Length -ne $beforeA[0] -or
            $paths[0].LastWriteTimeUtc.Ticks -ne $beforeA[1] -or
            $paths[1].Length -ne $beforeB[0] -or
            $paths[1].LastWriteTimeUtc.Ticks -ne $beforeB[1]) {
            return 'comparison_unverifiable'
        }
        if ($paths[0].Length -eq $paths[1].Length -and
            [string]::Equals($hashA, $hashB, [StringComparison]::Ordinal)) {
            return 'exact_bytes_at_snapshot'
        }
        return 'different_bytes_at_snapshot'
    } catch {
        # Never surface file locations, identifiers, hashes or exceptions.
        return 'comparison_unverifiable'
    }
}

function Get-OperatorNextGate {
    param([string]$Observation, [string]$Comparison)
    if ($Comparison -eq 'different_bytes_at_snapshot') {
        return 'resolve_reference_vs_registered_dll_difference'
    }
    if ($Comparison -ne 'exact_bytes_at_snapshot') {
        return 'verify_reference_and_registered_dll_equivalence'
    }
    if ($Observation -eq 'client_not_observed_in_local_snapshot' -or
        $Observation -eq 'client_process_listing_unavailable') {
        return 'observe_client_with_gui_open'
    }
    if ($Observation -ne 'registered_library_loaded_in_name_matched_client') {
        return 'verify_registered_dll_in_client_module_list'
    }
    return 'collect_same_run_redacted_j2534_and_gui_evidence'
}

function Write-ExclusiveOperatorReport {
    param([string]$Content, [string]$Destination)
    try {
        if ([string]::IsNullOrWhiteSpace($Destination) -or
            -not [IO.Path]::IsPathRooted($Destination) -or
            $Destination.StartsWith('\\')) { throw 'invalid path' }
        $full = [IO.Path]::GetFullPath($Destination)
        $root = [IO.Path]::GetFullPath(
            (Join-Path $PSScriptRoot '..\..')).TrimEnd('\') + '\'
        if ($full.StartsWith($root, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'output inside source tree'
        }
        $bytes = [Text.Encoding]::UTF8.GetBytes($Content + "`n")
        $stream = [IO.File]::Open($full, [IO.FileMode]::CreateNew,
                                 [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $stream.Write($bytes, 0, $bytes.Length) }
        finally { $stream.Dispose() }
    } catch {
        throw 'Operator report not created: output must be a NEW local file outside the source tree'
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

    # Eight additional no-client, no-registry, synthetic operator-mode tests.
    $operatorChecks=0
    $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ([Guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $tempRoot -ErrorAction Stop | Out-Null
    try {
        $first = Join-Path $tempRoot 'installed.dll'
        $second = Join-Path $tempRoot 'tested.dll'
        $reportPath = Join-Path $tempRoot 'binding.redacted.json'
        $body = New-Object byte[] 128
        for ($j=0; $j -lt $body.Length; $j++) { $body[$j]=[byte]($j % 256) }
        [IO.File]::WriteAllBytes($first, $body)
        [IO.File]::WriteAllBytes($second, $body)
        if ((Get-ByteEquivalence $first $second) -cne 'exact_bytes_at_snapshot') {
            throw 'operator test 1: equal snapshot'
        }; $operatorChecks++
        $body[0]=12;[IO.File]::WriteAllBytes($second, $body)
        if ((Get-ByteEquivalence $first $second) -cne 'different_bytes_at_snapshot') {
            throw 'operator test 2: differing snapshot'
        }; $operatorChecks++
        if ((Get-ByteEquivalence $first (Join-Path $tempRoot 'missing.dll')) -cne 'comparison_unverifiable') {
            throw 'operator test 3: missing reference'
        }; $operatorChecks++
        if ((Get-ByteEquivalence $first '') -cne 'not_compared') {
            throw 'operator test 4: no comparison'
        }; $operatorChecks++
        if ((Get-ByteEquivalence $first 'relative.dll') -cne 'comparison_unverifiable') {
            throw 'operator test 5: no relative DLL'
        }; $operatorChecks++
        $safe = '{"schema_version":"virtualcar-sectorv-process-binding-operator-v1","accepted_vin_or_ecu":"not_verified"}'
        Write-ExclusiveOperatorReport $safe $reportPath
        if (([IO.File]::ReadAllText($reportPath)).Trim() -cne $safe) {
            throw 'operator test 6: private report content'
        }; $operatorChecks++
        $preserved = [IO.File]::ReadAllBytes($reportPath)
        $blocked = $false
        try { Write-ExclusiveOperatorReport $safe $reportPath }
        catch { $blocked=$true }
        $afterAttempt = [IO.File]::ReadAllBytes($reportPath)
        if (-not $blocked -or
            [Convert]::ToBase64String($preserved) -cne
            [Convert]::ToBase64String($afterAttempt)) {
            throw 'operator test 7: exclusive output'
        }; $operatorChecks++
        if ((Get-OperatorNextGate 'registered_library_loaded_in_name_matched_client' 'exact_bytes_at_snapshot') -cne
                'collect_same_run_redacted_j2534_and_gui_evidence' -or
            (Get-OperatorNextGate 'registered_library_loaded_in_name_matched_client' 'different_bytes_at_snapshot') -cne
                'resolve_reference_vs_registered_dll_difference' -or
            (Get-OperatorNextGate 'client_not_observed_in_local_snapshot' 'exact_bytes_at_snapshot') -cne
                'observe_client_with_gui_open') {
            throw 'operator test 8: conservative next gate'
        }; $operatorChecks++
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host ("PASS: {0}/{0} synthetic operator binding and byte-comparison tests" -f $operatorChecks)
}

if ($SelfTest) {
    if ($OperatorSession -or $ReferenceDll -or $OutputFile) {
        throw 'Self-test cannot combine with operator collection'
    }
    Invoke-LocalSelfTests
    exit 0
}
if (-not $OperatorSession -and ($ReferenceDll -or $OutputFile)) {
    throw 'Operator-only parameters require -OperatorSession'
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

# Default CI mode is backward compatible and scoped only to that runner.
# Operator mode is a current-host observation *claimed by the operator* to
# be in the GUI guest; even a loaded DLL and byte match do not verify a VIN.
if ($OperatorSession) {
    if ($processObservation -eq 'client_not_observed_in_runner_context') {
        $processObservation = 'client_not_observed_in_local_snapshot'
    }
    $comparison = Get-ByteEquivalence -RegisteredPath $library -ReferencePath $ReferenceDll
    $result = [ordered]@{
        schema_version = 'virtualcar-sectorv-process-binding-operator-v1'
        scope = 'operator_requested_current_host_snapshot_only'
        observation = $processObservation
        installed_vs_reference_dll = $comparison
        next_safe_gate = Get-OperatorNextGate $processObservation $comparison
        name_matched_executable_authenticity = 'not_verified'
        operator_same_run_pairing = 'not_independently_attested'
        registered_provider_unchanged_during_run = 'not_verified'
        reference_dll_pe32 = 'not_assessed_by_this_tool'
        client_was_launched_by_audit = $false
        accepted_vin_or_ecu = 'not_verified'
    }
    $serialized = $result | ConvertTo-Json -Compress
    if ($OutputFile) {
        Write-ExclusiveOperatorReport -Content $serialized -Destination $OutputFile
        Write-Output 'Redacted operator process binding snapshot created locally; no client acceptance asserted.'
    } else {
        Write-Output $serialized
    }
} else {
    $result = [ordered]@{
        schema_version = 'virtualcar-sectorv-process-binding-v1'
        scope = 'current_ci_runner_process_snapshot_only'
        observation = $processObservation
        name_matched_executable_authenticity = 'not_verified'
        client_was_launched_by_audit = $false
        accepted_vin_or_ecu = 'not_verified'
    }
    Write-Output ($result | ConvertTo-Json -Compress)
}
