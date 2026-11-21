#Requires -Version 5.1
<#
One local Begin / Snapshot / Finish scenario for original VIDA.
Read-only: never launches a client, registers/loads a provider, replaces INI,
changes Dvinholm/VIDA, sends CAN or declares a GUI result.
All outputs are private and must stay outside the checkout.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateSet('Begin','Snapshot','Finish')][string]$Phase,
    [Parameter(Mandatory=$true)][string]$SessionDirectory,
    [Parameter(Mandatory=$true)][string]$ReferenceDll,
    [string]$IdentityJson,
    [switch]$PublishedCem50,
    [Parameter(Mandatory=$true)][string]$AdapterKey,
    [Parameter(Mandatory=$true)][string]$VidaLog,
    [string]$NativeLog = (Join-Path $env:TEMP 'SectorVVirtualCar.log'),
    [string]$PythonExe = 'python',
    [uint32]$ClientProcessId = 0
)
$ErrorActionPreference = 'Stop'
$bindingHelpers = New-Module -Name VirtualCarVidaTrialBinding `
    -ArgumentList (Join-Path $PSScriptRoot 'audit_vmware_sectorv_process.ps1') -ScriptBlock {
        param($Source)
        . $Source -FunctionsOnly
        Export-ModuleMember -Function Get-ClientBindingState, Get-ReferencePe32State
    }
Import-Module $bindingHelpers -Force

function Write-NewPrivateJson($Path, $Value) {
    $bytes = [Text.Encoding]::UTF8.GetBytes(($Value | ConvertTo-Json -Depth 12) + "`n")
    $stream = [IO.File]::Open($Path, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
}

try {
    $session = [IO.Path]::GetFullPath($SessionDirectory)
    $root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..')).TrimEnd('\')
    if ($session -eq $root -or $session.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Private session must be outside checkout'
    }
    if ([string]::IsNullOrWhiteSpace($AdapterKey) -or $AdapterKey.Contains('\') -or $AdapterKey.Contains('/')) {
        throw 'Expected an explicit single Registry32 adapter subkey'
    }
    $reference = (Resolve-Path -LiteralPath $ReferenceDll).Path
    if ((Get-ReferencePe32State $reference) -ne 'x86_pe32_header') { throw 'Expected x86 DLL' }
    $profile = Join-Path ([IO.Path]::GetDirectoryName($reference)) 'virtualcar.ini'
    $profileHash = (Get-FileHash -LiteralPath $profile -Algorithm SHA256).Hash
    $identityHash = ''
    $profileSource = 'private_lab'
    if ($PublishedCem50) {
        if ($IdentityJson) { throw 'IdentityJson applies to the private profile only' }
        $published = Join-Path $PSScriptRoot '..\adapters\cem50\virtualcar.ini'
        if ($profileHash -cne (Get-FileHash -LiteralPath $published -Algorithm SHA256).Hash) {
            throw 'Adjacent profile differs from the published CEM50 profile'
        }
        $profileSource = 'published_cem50'
    } else {
        if (-not $IdentityJson) { throw 'Private lab profile requires IdentityJson' }
        & $PythonExe (Join-Path $PSScriptRoot 'build_b3a146_cem40_lab_profile.py') `
            --validate-only --profile $profile --identity-json $IdentityJson
        if ($LASTEXITCODE -ne 0) { throw 'Lab profile preflight failed' }
        $identityHash = (Get-FileHash -LiteralPath $IdentityJson -Algorithm SHA256).Hash
    }
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine, [Microsoft.Win32.RegistryView]::Registry32)
    try {
        $key = $base.OpenSubKey(('SOFTWARE\PassThruSupport.04.04\' + $AdapterKey), $false)
        if (-not $key) { throw 'Selected Registry32 adapter is absent' }
        try { $registered = [string]$key.GetValue('FunctionLibrary') } finally { $key.Dispose() }
    } finally { $base.Dispose() }
    if (-not [string]::Equals([IO.Path]::GetFullPath($registered), $reference, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Selected registry entry does not point at the exact isolated DLL'
    }
    $fingerprints = @{
        dll = (Get-FileHash -LiteralPath $reference -Algorithm SHA256).Hash
        ini = $profileHash
        identity = $identityHash
    }
    $stateFile = Join-Path $session 'trial-private.json'
    $baseline = Join-Path $session 'log-baseline-private.json'
    $collector = Join-Path $PSScriptRoot 'audit_vida_j2534_session_window.py'
    if ($Phase -eq 'Begin') {
        if (Test-Path -LiteralPath $session) { throw 'Begin requires a new session directory' }
        [void][IO.Directory]::CreateDirectory($session)
        & $PythonExe $collector baseline --vida-log $VidaLog --virtual-log $NativeLog --private-baseline $baseline
        if ($LASTEXITCODE -ne 0) { throw 'Log baseline failed' }
        Write-NewPrivateJson $stateFile @{
            schema = 'virtualcar-vida-cem-trial-v1'; private_do_not_publish = $true
            started_utc = [DateTime]::UtcNow.ToString('o'); fingerprints = $fingerprints
            adapter_key = $AdapterKey; reference_dll = $reference; profile = $profile
            profile_source = $profileSource
            vida_log = [IO.Path]::GetFullPath($VidaLog); native_log = [IO.Path]::GetFullPath($NativeLog)
        }
        $observations = [ordered]@{}
        foreach ($name in @('ReadVin','T111','T122','CemNetworkStatus','EcuIdentification')) {
            $observations[$name] = @{ status = 'NOT_TESTED'; private_evidence_file = ''; note = '' }
        }
        Write-NewPrivateJson (Join-Path $session 'gui-observations-private.json') $observations
        Write-Output 'BEGIN_READY: now perform one original VIDA trial; take Snapshot while the adapter is open.'
        return
    }
    $saved = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json
    if ($saved.schema -cne 'virtualcar-vida-cem-trial-v1' -or $saved.private_do_not_publish -ne $true) {
        throw 'Wrong trial state'
    }
    $savedProfileSource = if ($saved.profile_source) { $saved.profile_source } else { 'private_lab' }
    if ($savedProfileSource -cne $profileSource) { throw 'Trial profile source changed' }
    foreach ($name in @('dll','ini','identity')) {
        if ($saved.fingerprints.$name -cne $fingerprints[$name]) { throw 'Trial inputs changed' }
    }
    if ($saved.adapter_key -cne $AdapterKey -or $saved.reference_dll -ine $reference -or
        $saved.vida_log -ine [IO.Path]::GetFullPath($VidaLog) -or
        $saved.native_log -ine [IO.Path]::GetFullPath($NativeLog)) { throw 'Trial source changed' }
    if ($Phase -eq 'Snapshot') {
        if (-not $ClientProcessId) { throw 'Snapshot needs the actual VIDA client process ID' }
        $client = Get-Process -Id $ClientProcessId
        try {
            $binding = Get-ClientBindingState @($client) $reference
            Write-NewPrivateJson (Join-Path $session ('module-' + $ClientProcessId + '-private.json')) @{
                captured_utc = [DateTime]::UtcNow.ToString('o'); process_id = $ClientProcessId
                process_start_utc = $client.StartTime.ToUniversalTime().ToString('o')
                executable = $client.MainModule.FileName; binding = $binding
                registered_dll = $reference; fingerprints = $fingerprints
                original_vida_authenticity = 'NOT_ATTESTED_BY_PROCESS_NAME'
            }
        } finally { $client.Dispose() }
        Write-Output ('MODULE_SNAPSHOT: ' + $binding)
        return
    }
    & $PythonExe $collector delta --vida-log $VidaLog --virtual-log $NativeLog `
        --private-baseline $baseline --output (Join-Path $session 'append-summary.json')
    if ($LASTEXITCODE -ne 0) { throw 'Log delta failed; rotation or truncation requires a new trial' }
    Write-Output 'FINISH_CAPTURED: GUI statuses remain explicit operator observations, never inferred from RX.'
    Write-Output 'Retain local screenshots for ReadVin, T111, T122, CEM NETWORK and ECU identification.'
} catch {
    # Exception text can contain VIN, paths or original application details.
    Write-Error 'VIDA_CEM_TRIAL_FAILED: verify phase, isolated paths, profile, registry binding and unchanged log baseline.'
    exit 1
}
