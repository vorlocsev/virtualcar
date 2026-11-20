#Requires -Version 5.1
<#
Read-only, strictly redacted snapshot of name-matched client -> registered J2534 DLL.
Default mode checks SectorV on the *current self-hosted CI runner*. OperatorSession
checks the *current host* and does not prove it is the target guest VM.
Never starts SectorV, loads a DLL, changes registry, opens a process by PID,
prints private paths, hashes or VINs. A name match is not binary authenticity.
#>
[CmdletBinding()]
param(
    [switch]$SelfTest,
    [switch]$OperatorSession,
    [ValidateSet('iexplore','java','VidaMonitor','w3wp')]
    [string]$VidaProcessName = '',
    [ValidateRange(1,2147483647)]
    [int]$VidaProcessId = 0,
    [string]$ReferenceDll,
    [string]$OutputFile
)
$ErrorActionPreference = 'Stop'

function Get-ClientModulePaths {
    param([Diagnostics.Process]$Client)
    if ($Client.HasExited) { return }
    if (-not ('VirtualCarAudit.ModuleSnapshot' -as [type])) {
        Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace VirtualCarAudit {
    public static class ModuleSnapshot {
        const uint SnapModule = 0x08;
        const uint SnapModule32 = 0x10;
        const int ErrorBadLength = 24;
        const int ErrorNoMoreFiles = 18;
        const int MaxPath = 260;

        [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
        struct ModuleEntry {
            public uint Size, ModuleId, ProcessId, GlobalUsage, ProcessUsage;
            public IntPtr BaseAddress;
            public uint BaseSize;
            public IntPtr Module;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 256)] public string Name;
            [MarshalAs(UnmanagedType.ByValTStr, SizeConst = MaxPath)] public string Path;
        }

        [DllImport("kernel32.dll", SetLastError = true)]
        static extern SafeFileHandle CreateToolhelp32Snapshot(uint flags, uint processId);
        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode, ExactSpelling = true)]
        static extern bool Module32FirstW(SafeFileHandle snapshot, ref ModuleEntry entry);
        [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode, ExactSpelling = true)]
        static extern bool Module32NextW(SafeFileHandle snapshot, ref ModuleEntry entry);

        public static string[] Read(uint processId) {
            // A native 64-bit module list can omit every WOW64 client DLL.
            uint flags = SnapModule;
            if (Environment.Is64BitProcess) flags |= SnapModule32;

            // The loader list can change while Windows is taking a snapshot.
            for (int attempt = 0; attempt < 4; attempt++) {
                using (SafeFileHandle snapshot = CreateToolhelp32Snapshot(flags, processId)) {
                    if (snapshot.IsInvalid) {
                        if (Marshal.GetLastWin32Error() == ErrorBadLength) continue;
                        return null;
                    }

                    ModuleEntry entry = new ModuleEntry { Size = (uint)Marshal.SizeOf(typeof(ModuleEntry)) };
                    if (!Module32FirstW(snapshot, ref entry)) return null;
                    List<string> paths = new List<string>();
                    do {
                        // Toolhelp uses a fixed buffer. An incomplete path cannot prove absence.
                        paths.Add(entry.Path != null && entry.Path.Length < MaxPath - 1 ? entry.Path : null);
                    } while (Module32NextW(snapshot, ref entry));
                    return Marshal.GetLastWin32Error() == ErrorNoMoreFiles ? paths.ToArray() : null;
                }
            }
            return null;
        }
    }
}
'@
    }
    $paths = [VirtualCarAudit.ModuleSnapshot]::Read([uint32]$Client.Id)
    if (-not $Client.HasExited) { $paths }
}

function Get-ClientBindingState {
    param([object[]]$Clients, [string]$RegisteredPath,
          [scriptblock]$ReadModulePaths = { param($client) Get-ClientModulePaths $client })
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
        $paths = @(& $ReadModulePaths $Clients[0])
        if ($paths.Count -eq 0) {
            return 'client_module_list_unavailable'
        }
        $complete = $true
        foreach ($path in $paths) {
            if ([string]::IsNullOrWhiteSpace($path) -or -not [IO.Path]::IsPathRooted($path)) {
                $complete = $false
                continue
            }
            $actual = [IO.Path]::GetFullPath($path)
            if ([string]::Equals($actual, $expected, [StringComparison]::OrdinalIgnoreCase)) {
                return 'registered_library_loaded_in_name_matched_client'
            }
        }
        if (-not $complete) { return 'client_module_list_unavailable' }
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
            $file = [IO.FileInfo]::new($full)
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

# Read only bounded PE header bytes; this checks architecture, not export
# contracts, binary provenance or executable authenticity. Never load the DLL.
function Get-ReferencePe32State {
    param([string]$ReferencePath)
    if ([string]::IsNullOrWhiteSpace($ReferencePath)) {
        return 'not_compared'
    }
    try {
        $expanded = [Environment]::ExpandEnvironmentVariables($ReferencePath.Trim().Trim('"'))
        if (-not [IO.Path]::IsPathRooted($expanded) -or $expanded.StartsWith('\\')) {
            return 'unverifiable'
        }
        $full = [IO.Path]::GetFullPath($expanded)
        $file = [IO.FileInfo]::new($full)
        if (-not $file.Exists) { return 'unverifiable' }
        if ($file.Length -lt 96 -or $file.Length -gt 67108864) {
            return 'invalid_pe'
        }
        $stream = [IO.File]::Open($full, [IO.FileMode]::Open,
            [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try {
            $dos = New-Object byte[] 64
            if ($stream.Read($dos, 0, 64) -ne 64 -or
                $dos[0] -ne 0x4D -or $dos[1] -ne 0x5A) {
                return 'invalid_pe'
            }
            [uint32]$offset = [BitConverter]::ToUInt32($dos, 0x3C)
            if ($offset -lt 64 -or $offset -gt 4096 -or
                ([long]$offset + 26) -gt $stream.Length) {
                return 'invalid_pe'
            }
            [void]$stream.Seek([long]$offset, [IO.SeekOrigin]::Begin)
            $coff = New-Object byte[] 26
            if ($stream.Read($coff, 0, 26) -ne 26 -or
                $coff[0] -ne 0x50 -or $coff[1] -ne 0x45 -or
                $coff[2] -ne 0 -or $coff[3] -ne 0) {
                return 'invalid_pe'
            }
            [uint16]$machine = [BitConverter]::ToUInt16($coff, 4)
            [uint16]$magic = [BitConverter]::ToUInt16($coff, 24)
            if ($machine -eq 0x014C -and $magic -eq 0x010B) {
                return 'x86_pe32_header'
            }
            return 'other_pe'
        } finally {
            $stream.Dispose()
        }
    } catch {
        # No caller-controlled values, binary paths or exceptions leave this tool.
        return 'unverifiable'
    }
}

function Get-OperatorNextGate {
    param([string]$Observation, [string]$Comparison,
          [string]$ReferencePe32 = 'not_assessed_by_this_tool')
    if ($Comparison -eq 'different_bytes_at_snapshot') {
        return 'resolve_reference_vs_registered_dll_difference'
    }
    if ($ReferencePe32 -eq 'invalid_pe' -or $ReferencePe32 -eq 'other_pe') {
        return 'verify_reference_pe32_before_gui'
    }
    if ($Observation -eq 'client_not_observed_in_local_snapshot' -or
        $Observation -eq 'client_process_listing_unavailable') {
        return 'observe_client_with_gui_open'
    }
    if ($Observation -ne 'registered_library_loaded_in_name_matched_client') {
        return 'verify_registered_dll_in_client_module_list'
    }
    if ($Comparison -eq 'not_compared') {
        return 'collect_gui_evidence_without_reference_attestation'
    }
    if ($Comparison -ne 'exact_bytes_at_snapshot') {
        return 'verify_reference_and_registered_dll_equivalence'
    }
    if ($ReferencePe32 -eq 'unverifiable') {
        return 'verify_reference_pe32_before_gui'
    }
    return 'collect_same_run_redacted_j2534_and_gui_evidence'
}

# The VIDA mode is a passive, named-process module observation. The selected
# process name is an operator hint, NOT an authenticated VIDA executable.
# An exact registered DLL path at one instant does not show whether an XML
# config was loaded, J2534 was invoked, or a ReadVin script was selected.
# B3A338. Process PID and birth time stay in memory; identity is untrusted.
function Select-VidaExactPidCandidate {
    param([object[]]$NameMatches, [int]$SelectedProcessId)
    $matches=@($NameMatches | Where-Object { $_.Id -eq $SelectedProcessId })
    if ($matches.Count -eq 0) {
        return [pscustomobject]@{Category='selected_pid_not_in_name_matches';Client=$null;BirthTicks=[long]0}
    }
    if ($matches.Count -ne 1) {
        return [pscustomobject]@{Category='selected_pid_ambiguous_in_name_matches';Client=$null;BirthTicks=[long]0}
    }
    try {
        $candidate=$matches[0]
        if ($candidate.HasExited) { throw 'candidate_exited' }
        [long]$ticks=$candidate.StartTime.ToUniversalTime().Ticks
        if ($ticks -le 0) { throw 'invalid_process_start' }
        return [pscustomobject]@{Category='pid_name_and_starttime_observed';Client=$candidate;BirthTicks=$ticks}
    } catch {
        return [pscustomobject]@{Category='selected_pid_starttime_unavailable';Client=$null;BirthTicks=[long]0}
    }
}
function Test-VidaExactPidSnapshotStable {
    param([object]$Client, [long]$ExpectedBirthTicks)
    if ($null -eq $Client -or $ExpectedBirthTicks -le 0) { return 'unverifiable' }
    try {
        if ($Client.HasExited) { return 'process_exited_after_snapshot' }
        [long]$actual=$Client.StartTime.ToUniversalTime().Ticks
        if ($actual -ne $ExpectedBirthTicks) { return 'process_starttime_changed' }
        return 'same_pid_process_starttime_after_snapshot'
    } catch { return 'unverifiable' }
}

function Get-VidaNextGate {
    param([string]$Observation, [string]$Comparison,
          [string]$ReferencePe32)
    if ($Observation -eq 'multiple_client_name_matches') {
        return 'select_unambiguous_original_client_process'
    }
    if ($Observation -eq 'client_not_observed_in_local_snapshot' -or
        $Observation -eq 'client_process_listing_unavailable') {
        return 'observe_original_client_only_when_already_running'
    }
    if ($Observation -ne 'registered_library_loaded_in_name_matched_client') {
        return 'verify_virtual_provider_module_in_original_client'
    }
    if ($ReferencePe32 -ne 'x86_pe32_header') {
        return 'verify_reference_virtual_dll_pe32'
    }
    if ($Comparison -ne 'exact_bytes_at_snapshot') {
        return 'verify_registered_vs_reference_binary_equivalence'
    }
    return 'independently_observe_active_vida_config_and_readvin'
}

function New-VidaModuleReport {
    param([string]$ProcessName, [string]$Observation,
          [string]$Comparison, [string]$ReferencePe32,
          [string]$PidSelection = 'not_requested',
          [string]$StarttimeStability = 'not_assessed')
    if (@('iexplore','java','VidaMonitor','w3wp') -cnotcontains $ProcessName) {
        throw 'Unsupported VIDA process name category'
    }
    $loaded = $Observation -ceq 'registered_library_loaded_in_name_matched_client'
    # Path matching is strictly weaker than binary provenance, and both
    # are strictly weaker than a proven original VIDA process identity.
    return [ordered]@{
        schema_version = 'virtualcar-vida-process-binding-operator-v1'
        scope = 'operator_requested_current_host_name_match_only'
        selected_process_name_category = $ProcessName
        registered_virtual_module_observation = $Observation
        installed_vs_reference_dll = $Comparison
        reference_dll_pe32 = $ReferencePe32
        selected_private_pid_name_starttime_observation = $PidSelection
        selected_private_pid_starttime_snapshot_stability = $StarttimeStability
        selected_pid_is_authenticated_original_vida = $false
        registered_dll_module_path_seen_in_name_matched_process = $loaded
        selected_process_is_authenticated_original_vida = $false
        loaded_binary_memory_matches_disk_verified = $false
        active_vida_diagnostic_config_loaded_verified = $false
        effective_diagnostic_connection_mode_verified = $false
        original_vida_script_selection_verified = $false
        original_vida_j2534_tx_rx_verified = $false
        original_vida_vin_accepted_verified = $false
        ecu_identity_accepted_verified = $false
        client_started_by_audit = $false
        physical_adapter_examined = $false
        next_safe_gate = Get-VidaNextGate $Observation $Comparison $ReferencePe32
    }
}

function Invoke-VidaExactPidSelfTests {
    # Entirely synthetic processes; no original VIDA or J2534 is invoked.
    $birth=[datetime]'2026-01-01T00:00:00Z'
    $match=[pscustomobject]@{Id=321;HasExited=$false;StartTime=$birth}
    $other=[pscustomobject]@{Id=987;HasExited=$false;StartTime=$birth}
    $exited=[pscustomobject]@{Id=321;HasExited=$true;StartTime=$birth}
    $missingTime=[pscustomobject]@{Id=321;HasExited=$false;StartTime=$null}
    $count=0
    if ((Select-VidaExactPidCandidate @() 321).Category -cne
            'selected_pid_not_in_name_matches') { throw 'VIDA PID gate 1' }
    $count++
    if ((Select-VidaExactPidCandidate @($other) 321).Category -cne
            'selected_pid_not_in_name_matches') { throw 'VIDA PID gate 2' }
    $count++
    if ((Select-VidaExactPidCandidate @($match,$match) 321).Category -cne
            'selected_pid_ambiguous_in_name_matches') { throw 'VIDA PID gate 3' }
    $count++
    if ((Select-VidaExactPidCandidate @($exited) 321).Category -cne
            'selected_pid_starttime_unavailable') { throw 'VIDA PID gate 4' }
    $count++
    if ((Select-VidaExactPidCandidate @($missingTime) 321).Category -cne
            'selected_pid_starttime_unavailable') { throw 'VIDA PID gate 5' }
    $count++
    $chosen=Select-VidaExactPidCandidate @($other,$match) 321
    if ($chosen.Category -cne 'pid_name_and_starttime_observed' -or
        $chosen.Client.Id -ne 321 -or $chosen.BirthTicks -le 0) {
        throw 'VIDA PID gate 6'
    }
    $count++
    if ((Test-VidaExactPidSnapshotStable $match $chosen.BirthTicks) -cne
            'same_pid_process_starttime_after_snapshot' -or
        (Test-VidaExactPidSnapshotStable $exited $chosen.BirthTicks) -cne
            'process_exited_after_snapshot') { throw 'VIDA PID gate 7' }
    $count++
    $report=New-VidaModuleReport 'iexplore' 'registered_library_loaded_in_name_matched_client' 'exact_bytes_at_snapshot' 'x86_pe32_header' $chosen.Category 'same_pid_process_starttime_after_snapshot'
    $safe=$report | ConvertTo-Json -Compress
    if ((Test-VidaExactPidSnapshotStable $match ($chosen.BirthTicks+1)) -cne
            'process_starttime_changed' -or
        $safe.Contains('321') -or $safe.Contains('2026-01-01') -or
        $report.selected_pid_is_authenticated_original_vida -ne $false -or
        $report.original_vida_vin_accepted_verified -ne $false) {
        throw 'VIDA PID gate 8'
    }
    $count++
    Write-Host ('PASS: {0}/{0} synthetic VIDA exact-PID/starttime and redaction gates' -f $count)
}

function Invoke-VidaBindingSelfTests {
    $loaded='registered_library_loaded_in_name_matched_client'
    $absent='registered_library_not_in_enumerated_modules'
    $cases=@(
        @{O=$loaded; C='exact_bytes_at_snapshot'; P='x86_pe32_header';
          Want='independently_observe_active_vida_config_and_readvin'},
        @{O=$loaded; C='different_bytes_at_snapshot'; P='x86_pe32_header';
          Want='verify_registered_vs_reference_binary_equivalence'},
        @{O=$loaded; C='exact_bytes_at_snapshot'; P='other_pe';
          Want='verify_reference_virtual_dll_pe32'},
        @{O=$absent; C='exact_bytes_at_snapshot'; P='x86_pe32_header';
          Want='verify_virtual_provider_module_in_original_client'},
        @{O='client_module_list_unavailable'; C='exact_bytes_at_snapshot';
          P='x86_pe32_header';
          Want='verify_virtual_provider_module_in_original_client'},
        @{O='client_not_observed_in_local_snapshot'; C='exact_bytes_at_snapshot';
          P='x86_pe32_header';
          Want='observe_original_client_only_when_already_running'},
        @{O='multiple_client_name_matches'; C='exact_bytes_at_snapshot';
          P='x86_pe32_header';
          Want='select_unambiguous_original_client_process'},
        @{O='client_process_listing_unavailable'; C='not_compared';
          P='unverifiable';
          Want='observe_original_client_only_when_already_running'}
    )
    $checked=0
    foreach ($case in $cases) {
        $report=New-VidaModuleReport 'iexplore' $case.O $case.C $case.P
        if ($report.next_safe_gate -cne $case.Want -or
            $report.original_vida_vin_accepted_verified -ne $false -or
            $report.active_vida_diagnostic_config_loaded_verified -ne $false -or
            $report.selected_process_is_authenticated_original_vida -ne $false -or
            $report.registered_dll_module_path_seen_in_name_matched_process -ne
                ($case.O -ceq $loaded)) {
            throw 'VIDA process-binding synthetic gate mismatch'
        }
        $checked++
    }
    $raw=(New-VidaModuleReport 'java' $loaded 'exact_bytes_at_snapshot' 'x86_pe32_header' |
          ConvertTo-Json -Compress)
    if ($raw.Contains('C:\') -or $raw.Contains('PID=') -or
        $raw.Contains('YV1') -or $raw.Contains('sha256') -or
        $raw.Contains('VirtualCarJ2534.dll')) {
        throw 'VIDA operator module redaction failed'
    }
    $reject=$false
    try { [void](New-VidaModuleReport 'sectorv.exe' $loaded 'exact_bytes_at_snapshot' 'x86_pe32_header') }
    catch { $reject=$true }
    if (-not $reject) { throw 'Unapproved process name accepted' }
    Write-Host ('PASS: {0}/{0} synthetic VIDA module attribution gates; redaction and unknown-name rejection' -f $checked)
}

function Write-ExclusiveOperatorReport {
    param([string]$Content, [string]$Destination)
    try {
        if ([string]::IsNullOrWhiteSpace($Destination) -or
            -not [IO.Path]::IsPathRooted($Destination) -or
            $Destination.StartsWith('\\')) { throw 'invalid path' }
        $full = [IO.Path]::GetFullPath($Destination)
        # In source: repo/emulator/tools -> protect repo root.
        # In standalone LAB: LAB/tools -> protect only the LAB subtree.
        # Guard the real distribution root, never the parent drive.
        $distRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
        if ((Test-Path -LiteralPath (Join-Path $distRoot 'BUILDINFO.json') -PathType Leaf) -and
            (Test-Path -LiteralPath (Join-Path $distRoot 'VirtualCarJ2534.dll') -PathType Leaf)) {
            $root = $distRoot.TrimEnd('\') + '\'
        } else {
            $root = [IO.Path]::GetFullPath(
                (Join-Path $PSScriptRoot '..\..')).TrimEnd('\') + '\'
        }
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
    $readTestModulePaths = { param($client) foreach ($module in $client.Modules) { $module.FileName } }
    foreach ($case in $cases) {
        $actual = Get-ClientBindingState -Clients $case.Clients -RegisteredPath $case.Path `
            -ReadModulePaths $readTestModulePaths
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
        observation = Get-ClientBindingState -Clients @($yes) -RegisteredPath $expected `
            -ReadModulePaths $readTestModulePaths
        name_matched_executable_authenticity = 'not_verified'
        client_was_launched_by_audit = $false
        accepted_vin_or_ecu = 'not_verified'
    } | ConvertTo-Json -Compress
    if ($result.Contains('C:\') -or $result.Contains('VirtualCarJ2534.dll') -or
        $result.Contains('PassThruOpen') -or $result.Contains('PID')) {
        throw 'Redaction self-test failed'
    }
    Write-Host ("PASS: {0}/{0} redacted SectorV process-binding tests" -f $passed)
    Invoke-ModuleSnapshotSelfTests
    Invoke-VidaBindingSelfTests
    Invoke-VidaExactPidSelfTests

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
                'observe_client_with_gui_open' -or
            (Get-OperatorNextGate 'registered_library_loaded_in_name_matched_client' 'not_compared') -cne
                'collect_gui_evidence_without_reference_attestation') {
            throw 'operator test 8: conservative next gate'
        }; $operatorChecks++
        # Eight synthetic read-only reference architecture checks. The test
        # bytes are PE *header* fixtures, not usable code or a J2534 driver.
        $peChecks=0
        if ((Get-ReferencePe32State '') -cne 'not_compared') {
            throw 'reference PE test 1: not supplied'
        }; $peChecks++
        if ((Get-ReferencePe32State 'relative.dll') -cne 'unverifiable') {
            throw 'reference PE test 2: nonlocal reference'
        }; $peChecks++
        if ((Get-ReferencePe32State (Join-Path $tempRoot 'missing.dll')) -cne 'unverifiable') {
            throw 'reference PE test 3: absent reference'
        }; $peChecks++
        if ((Get-ReferencePe32State $first) -cne 'invalid_pe') {
            throw 'reference PE test 4: no DOS header'
        }; $peChecks++
        $pe=New-Object byte[] 512
        $pe[0]=0x4D;$pe[1]=0x5A
        [BitConverter]::GetBytes([uint32]0x80).CopyTo($pe,0x3C)
        $pe[0x80]=0x50;$pe[0x81]=0x45
        [BitConverter]::GetBytes([uint16]0x014C).CopyTo($pe,0x84)
        [BitConverter]::GetBytes([uint16]0x010B).CopyTo($pe,0x98)
        [IO.File]::WriteAllBytes($first,$pe)
        if ((Get-ReferencePe32State $first) -cne 'x86_pe32_header') {
            throw 'reference PE test 5: x86 header'
        }; $peChecks++
        [BitConverter]::GetBytes([uint16]0x8664).CopyTo($pe,0x84)
        [BitConverter]::GetBytes([uint16]0x020B).CopyTo($pe,0x98)
        [IO.File]::WriteAllBytes($first,$pe)
        if ((Get-ReferencePe32State $first) -cne 'other_pe') {
            throw 'reference PE test 6: x64 header'
        }; $peChecks++
        [BitConverter]::GetBytes([uint32]5000).CopyTo($pe,0x3C)
        [IO.File]::WriteAllBytes($first,$pe)
        if ((Get-ReferencePe32State $first) -cne 'invalid_pe') {
            throw 'reference PE test 7: invalid PE offset'
        }; $peChecks++
        if ((Get-OperatorNextGate 'registered_library_loaded_in_name_matched_client' 'exact_bytes_at_snapshot' 'other_pe') -cne
                'verify_reference_pe32_before_gui' -or
            (Get-OperatorNextGate 'registered_library_loaded_in_name_matched_client' 'exact_bytes_at_snapshot' 'x86_pe32_header') -cne
                'collect_same_run_redacted_j2534_and_gui_evidence') {
            throw 'reference PE test 8: conservative next action'
        }; $peChecks++
        Write-Host ("PASS: {0}/{0} synthetic reference PE32 header tests" -f $peChecks)
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host ("PASS: {0}/{0} synthetic operator binding and byte-comparison tests" -f $operatorChecks)
}

function Invoke-ModuleSnapshotSelfTests {
    $loaded = 'registered_library_loaded_in_name_matched_client'
    $absent = 'registered_library_not_in_enumerated_modules'
    $unknown = 'client_module_list_unavailable'
    $current = [Diagnostics.Process]::GetCurrentProcess()
    try {
        $ownImage = $current.MainModule.FileName
        $elsewhere = Join-Path 'C:\VirtualCarLab' ([IO.Path]::GetFileName($ownImage))
        if ((Get-ClientBindingState @($current) $ownImage) -cne $loaded) {
            throw 'module snapshot test 1: current process image'
        }
        if ((Get-ClientBindingState @($current) $elsewhere) -cne $absent) {
            throw 'module snapshot test 2: exact path required'
        }
        if ((Get-ClientBindingState @($current) $elsewhere { @($ownImage, $null) }) -cne $unknown) {
            throw 'module snapshot test 3: incomplete paths cannot prove absence'
        }
        if ((Get-ClientBindingState @($current) $ownImage { @($null, $ownImage) }) -cne $loaded) {
            throw 'module snapshot test 4: an exact path still proves observation'
        }
    } finally { $current.Dispose() }

    $windowsDir = 'System32'
    if ([Environment]::Is64BitOperatingSystem) { $windowsDir = 'SysWOW64' }
    $childExe = Join-Path $env:WINDIR "$windowsDir\WindowsPowerShell\v1.0\powershell.exe"
    $child = Start-Process -FilePath $childExe -WindowStyle Hidden -PassThru `
        -ArgumentList '-NoProfile -NonInteractive -Command "Start-Sleep -Seconds 30"'
    try {
        # Query an actual x86 DLL in a disposable system process from the
        # same bitness of PowerShell that runs the operator snapshot.
        $dllDir = 'System32'
        if ([Environment]::Is64BitProcess) { $dllDir = 'SysWOW64' }
        $kernel = Join-Path $env:WINDIR "$dllDir\kernel32.dll"
        $binding = $unknown
        for ($attempt = 0; $attempt -lt 50; $attempt++) {
            $binding = Get-ClientBindingState @($child) $kernel
            if ($binding -eq $loaded -or $child.HasExited) { break }
            Start-Sleep -Milliseconds 100
        }
        if ($binding -cne $loaded) { throw 'module snapshot test 5: x86 DLL in x86 child' }
        if ((Get-ClientBindingState @($child) 'C:\VirtualCarLab\Unloaded.dll') -cne $absent) {
            throw 'module snapshot test 6: complete child snapshot excludes unrelated DLL'
        }
        $child.Kill()
        if (-not $child.WaitForExit(5000) -or (Get-ClientBindingState @($child) $kernel) -cne $unknown) {
            throw 'module snapshot test 7: exited process cannot prove absence'
        }
    } finally {
        if (-not $child.HasExited) { $child.Kill() }
        $child.Dispose()
    }
    Write-Host 'PASS: 7/7 process module snapshot tests (including x86 DLL enumeration)'
}

if ($SelfTest) {
    if ($OperatorSession -or $ReferenceDll -or $OutputFile -or $VidaProcessName -or $VidaProcessId) {
        throw 'Self-test cannot combine with operator collection'
    }
    Invoke-LocalSelfTests
    exit 0
}
if (-not $OperatorSession -and ($ReferenceDll -or $OutputFile -or $VidaProcessName -or $VidaProcessId)) {
    throw 'Operator-only parameters require -OperatorSession'
}
if ($VidaProcessId -and -not $VidaProcessName) {
    throw 'Exact VIDA PID selection requires -VidaProcessName'
}
if ($VidaProcessName -and [string]::IsNullOrWhiteSpace($ReferenceDll)) {
    throw 'VIDA operator module observation requires an explicit reference DLL'
}

# Read ONLY the 32-bit canonical Virtual Car J2534 registry key.
# Default process observation checks SectorV; operator-only VIDA name
# selection stays explicit and does not authenticate any original executable.
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
    $clientName=if ($VidaProcessName) { $VidaProcessName } else { 'SectorV' }
    $processes = @(Get-Process -Name $clientName -ErrorAction SilentlyContinue)
} catch {
    # A restricted CI token can be unable to enumerate another user session.
    # Do not treat that as client absence or client failure.
    $processes = @()
    $processObservation = 'client_process_listing_unavailable'
}
$vidaPidSelection='not_requested'
$vidaPidStability='not_assessed'
$vidaChosenClient=$null
[long]$vidaBirthTicks=0
if ($VidaProcessId) {
    if ($processObservation -eq 'client_process_listing_unavailable') {
        $vidaPidSelection='client_process_listing_unavailable'
    } else {
        $selection=Select-VidaExactPidCandidate -NameMatches $processes -SelectedProcessId $VidaProcessId
        $vidaPidSelection=$selection.Category
        if ($vidaPidSelection -eq 'pid_name_and_starttime_observed') {
            $vidaChosenClient=$selection.Client
            $vidaBirthTicks=$selection.BirthTicks
            $processes=@($vidaChosenClient)
        } else {
            # Never fall back to another process if the explicit PID failed.
            $processes=@()
            if ($vidaPidSelection -eq 'selected_pid_starttime_unavailable') {
                $processObservation='client_process_listing_unavailable'
            } else {
                $processObservation='client_not_observed_in_local_snapshot'
            }
        }
    }
}
if (-not $processObservation) {
    $processObservation = Get-ClientBindingState -Clients $processes -RegisteredPath $library
}
if ($VidaProcessId -and $null -ne $vidaChosenClient) {
    $vidaPidStability=Test-VidaExactPidSnapshotStable -Client $vidaChosenClient -ExpectedBirthTicks $vidaBirthTicks
    if ($vidaPidStability -ne 'same_pid_process_starttime_after_snapshot') {
        # A process exit or changed birth time invalidates its module snapshot.
        $processObservation='client_module_list_unavailable'
    }
}

# Default CI mode is backward compatible and scoped only to that runner.
# Operator mode is a current-host observation *claimed by the operator* to
# be in the GUI guest; even a loaded DLL and byte match do not verify a VIN.
if ($OperatorSession) {
    if ($processObservation -eq 'client_not_observed_in_runner_context') {
        $processObservation = 'client_not_observed_in_local_snapshot'
    }
    $comparison = Get-ByteEquivalence -RegisteredPath $library -ReferencePath $ReferenceDll
    $referencePe32 = Get-ReferencePe32State -ReferencePath $ReferenceDll
    if ($VidaProcessName) {
        $result=New-VidaModuleReport -ProcessName $VidaProcessName -Observation $processObservation -Comparison $comparison -ReferencePe32 $referencePe32 -PidSelection $vidaPidSelection -StarttimeStability $vidaPidStability
    } else {
    $result = [ordered]@{
        schema_version = 'virtualcar-sectorv-process-binding-operator-v1'
        scope = 'operator_requested_current_host_snapshot_only'
        observation = $processObservation
        installed_vs_reference_dll = $comparison
        next_safe_gate = Get-OperatorNextGate $processObservation $comparison $referencePe32
        name_matched_executable_authenticity = 'not_verified'
        operator_same_run_pairing = 'not_independently_attested'
        registered_provider_unchanged_during_run = 'not_verified'
        reference_dll_pe32 = $referencePe32
        client_was_launched_by_audit = $false
        accepted_vin_or_ecu = 'not_verified'
    }
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
