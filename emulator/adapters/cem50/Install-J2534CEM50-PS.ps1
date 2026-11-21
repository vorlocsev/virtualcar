#Requires -Version 5.1
<#
Side-by-side, owner-local synthetic CEM50 J2534-2 PS provider.
DRY RUN by default. No installer is executed by CI or by this file on import.
Evidence must be from the completed PR #418 exact-head native Windows x86 run.
This is not a claim of VIDA ReadVin or J2534-2 certification.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceDll,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9A-Fa-f]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory=$true)][string]$SummaryJson,
    [Parameter(Mandatory=$true)][string]$NativeReportJson,
    [switch]$Apply,
    [switch]$IConfirmOfflineSynthetic
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$verifiedHead = '9ab3738d6c53442f83c57727f6eaaf44e383c618'
$verifiedDllSha = '7F21E2606C6E7981ECDEDFE6769F180981C6DDFFFFBCC5C35CD4A6E983C98C3E'
$publishedVin = 'YV1CR855691511566'
$name = 'J2534 Diagnostic Interface CEM50 PS'
$keyPath = 'SOFTWARE\PassThruSupport.04.04\J2534 Diagnostic Interface CEM50 PS'
$targetDirectory = Join-Path $env:ProgramData 'J2534-CEM50-PS'
$targetDll = Join-Path $targetDirectory 'J2534CEM50PS.dll'
$targetIni = Join-Path $targetDirectory 'virtualcar.ini'
$sourceIni = Join-Path $PSScriptRoot 'virtualcar.ini'

$src = [IO.Path]::GetFullPath($SourceDll)
$summaryPath = [IO.Path]::GetFullPath($SummaryJson)
$nativePath = [IO.Path]::GetFullPath($NativeReportJson)
if (-not [IO.File]::Exists($src) -or -not [IO.File]::Exists($sourceIni) -or
    -not [IO.File]::Exists($summaryPath) -or -not [IO.File]::Exists($nativePath)) {
    throw 'Missing source DLL, profile, summary or native PS report'
}
if ([IO.Path]::GetFileName($src) -cne 'VirtualCarJ2534.dll') {
    throw 'Only a verified emulator VirtualCarJ2534.dll is permitted'
}
$evidenceDirectory = [IO.Path]::GetDirectoryName($summaryPath)
$expectedSource = Join-Path $evidenceDirectory 'exact-head\emulator\VirtualCarJ2534.dll'
$expectedNative = Join-Path $evidenceDirectory 'native-ps\ps-native-check.json'
if (-not [string]::Equals($src, $expectedSource, [StringComparison]::OrdinalIgnoreCase) -or
    -not [string]::Equals($nativePath, $expectedNative, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Source DLL and native report must belong to the same exact-head evidence directory'
}
$sha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash.ToUpperInvariant()
if ($sha -cne $ExpectedSha256.ToUpperInvariant() -or $sha -cne $verifiedDllSha) {
    throw 'DLL SHA256 differs from owner-verified native PR #418 binary'
}
$summary = Get-Content -LiteralPath $summaryPath -Raw -Encoding UTF8 | ConvertFrom-Json
$native = Get-Content -LiteralPath $nativePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($summary.source_sha -cne $verifiedHead -or
    $summary.branch -cne 'feature/cem50-j2534-2-ps-protocol-20261121' -or
    $summary.dll_sha256 -cne $verifiedDllSha -or
    $summary.vin -cne $publishedVin -or
    $summary.python_suite -cne 'PASS' -or
    $summary.c_host_suite -cne 'PASS' -or
    $summary.route_evidence_suite -cne 'PASS' -or
    $summary.windows_x86_build -cne 'PASS' -or
    $summary.can_ps_native -cne 'PASS' -or
    $summary.vida_readvin_verified -ne $false -or
    $summary.ecu_identification_verified -ne $false -or
    $summary.installed_provider_modified -ne $false -or
    $summary.physical_adapter_used -ne $false) {
    throw 'Untrusted or incomplete exact-head validation summary'
}
if ($native.status -cne 'CEM50_PS_NATIVE_PASS' -or
    $native.dll_sha256 -cne $verifiedDllSha -or
    $native.published_vin -cne $publishedVin -or
    $native.protocol_id -cne '0x8004' -or
    $native.j1962_hs -cne '0x060E' -or
    $native.j1962_ms -cne '0x030B' -or
    [int]$native.matched_frames -ne 13 -or
    $native.iso15765_ps_f190_verified -ne $true -or
    $native.vida_readvin_verified -ne $false -or
    $native.ecu_identification_verified -ne $false -or
    $native.physical_adapter_used -ne $false) {
    throw 'Untrusted or incomplete isolated x86 PS native report'
}

# Refuse non-PE32 binaries; this does not authenticate an executable.
$b = [IO.File]::ReadAllBytes($src)
if ($b.Length -lt 256 -or $b[0] -ne 0x4D -or $b[1] -ne 0x5A) {
    throw 'Invalid PE image'
}
$pe = [BitConverter]::ToInt32($b, 0x3C)
if ($pe -lt 64 -or $pe + 26 -ge $b.Length -or
    $b[$pe] -ne 0x50 -or $b[$pe+1] -ne 0x45 -or
    [BitConverter]::ToUInt16($b, $pe+4) -ne 0x014C -or
    [BitConverter]::ToUInt16($b, $pe+24) -ne 0x010B) {
    throw 'Expected Windows x86 PE32 DLL'
}

# PS opt-in is only in the reviewed synthetic CEM50 profile.
$cfg = [IO.File]::ReadAllText($sourceIni)
$entries = @{}
$sections = @{}
$section = ''
foreach ($raw in [IO.File]::ReadAllLines($sourceIni)) {
    $line = $raw.Trim()
    if (-not $line -or $line.StartsWith(';') -or $line.StartsWith('#')) { continue }
    if ($line -match '^\[([A-Za-z0-9_]+)\]$') {
        $section = $matches[1]
        if ($sections.ContainsKey($section)) { throw 'Duplicate profile section' }
        $sections[$section] = $true
        continue
    }
    if (-not $section -or -not ($line -match '^([A-Za-z0-9_]+)[ \t]*=[ \t]*(.*)$')) {
        throw 'Malformed profile entry'
    }
    $entry = $section + '.' + $matches[1]
    if ($entries.ContainsKey($entry)) { throw 'Duplicate profile entry' }
    $entries[$entry] = $matches[2].Trim()
}
if ($entries['Vehicle.VIN'] -cne $publishedVin -or
    $entries['Vehicle.ModelYear'] -cne '2009' -or
    $entries['Vehicle.ECUCount'] -cne '1' -or
    $entries['J2534_2.Enabled'] -cne '1' -or
    $entries['P2.FixtureAuthority'] -cne 'synthetic_lab_not_oem_attested' -or
    $entries['P2.StrictRouting'] -cne '1' -or
    $entries['D2_50.ResponseId'] -cne '01200003' -or
    $entries['D2_50.B9FBFrameCount'] -cne '13' -or
    $entries['PassiveCAN.Enabled'] -cne '0' -or
    $sections.ContainsKey('ECU1')) {
    throw 'Unexpected CEM50 PS profile identity or routing'
}
foreach ($field in @('D2_40.B9FBFrameCount','D2_40_B9F0.FrameCount',
                      'D2_50_B9F0.FrameCount','D2_40_B9FC.FrameCount',
                      'D2_50_B9FC.FrameCount')) {
    if ($entries[$field] -cne '0') { throw 'Unverified CEM response enabled' }
}
$frameKeys = @($entries.Keys | Where-Object { $_ -match '^D2_50\.B9FBFrame[0-9A-F]+$' })
if ($frameKeys.Count -ne 13) { throw 'Expected exactly 13 B9FB frames' }
$wire = New-Object 'System.Collections.Generic.List[byte]'
for ($i=0; $i -lt 13; $i++) {
    $hex = $entries['D2_50.B9FBFrame' + $i.ToString('X')]
    if ([string]::IsNullOrEmpty($hex) -or
        $hex -notmatch '^(?:[0-9A-Fa-f]{2}[ \t]+){7}[0-9A-Fa-f]{2}$') {
        throw 'Invalid B9FB frame bytes'
    }
    $frame = @($hex -split '[ \t]+' | ForEach-Object { [Convert]::ToByte($_, 16) })
    $header = if ($i -eq 0) { 0x8F } elseif ($i -eq 12) { 0x4F } else { 0x08 -bor ($i -band 7) }
    if ($frame[0] -ne $header) { throw 'Invalid B9FB transport sequence' }
    for ($j=1; $j -lt 8; $j++) { $wire.Add([byte]$frame[$j]) }
}
if ($wire.Count -ne 91 -or
    $wire[0] -ne 0x50 -or $wire[1] -ne 0xF9 -or $wire[2] -ne 0xFB -or
    [Text.Encoding]::ASCII.GetString($wire.ToArray(),14,17) -cne $publishedVin -or
    [Text.Encoding]::ASCII.GetString($wire.ToArray(),49,6) -cne '511566') {
    throw 'B9FB identity or chassis mismatched'
}

$reg = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
    [Microsoft.Win32.RegistryHive]::LocalMachine,
    [Microsoft.Win32.RegistryView]::Registry32)
$createdDirectory = $false
$createdKey = $false
$key = $null
try {
    $existing = $reg.OpenSubKey($keyPath)
    if ($null -ne $existing) {
        $existing.Close()
        throw 'Dedicated PS registration already exists; never overwrite'
    }
    if ([IO.Directory]::Exists($targetDirectory) -or [IO.File]::Exists($targetDirectory)) {
        throw 'Dedicated PS directory already exists; never overwrite'
    }
    Write-Host "PREFLIGHT_PASS: native verified CEM50 PS x86; existing J2534-1 unchanged"
    if (-not $Apply) {
        Write-Host "DRY_RUN_ONLY: $name, SHA256=$sha"
        Write-Host "Proposed directory: $targetDirectory"
        return
    }
    if (-not $IConfirmOfflineSynthetic) {
        throw '-Apply requires -IConfirmOfflineSynthetic'
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw '-Apply requires elevated Windows PowerShell'
    }
    [void][IO.Directory]::CreateDirectory($targetDirectory)
    $createdDirectory = $true
    Copy-Item -LiteralPath $src -Destination $targetDll -ErrorAction Stop
    Copy-Item -LiteralPath $sourceIni -Destination $targetIni -ErrorAction Stop
    if ((Get-FileHash -LiteralPath $targetDll -Algorithm SHA256).Hash -cne $verifiedDllSha -or
        [IO.File]::ReadAllText($targetIni) -cne $cfg) {
        throw 'Copied DLL/INI differs from verified source'
    }
    $key = $reg.CreateSubKey($keyPath)
    if ($null -eq $key) { throw 'Failed to create dedicated PS registration' }
    $createdKey = $true
    $key.SetValue('Vendor', 'VirtualCar CEM50 Synthetic Lab', [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('Name', $name, [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('FunctionLibrary', $targetDll, [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('ConfigApplication', '', [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('CAN', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('ISO15765', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('CAN_PS', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('ISO15765_PS', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('MessageVersion', 0x0404, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('LabSourceSha', $verifiedHead, [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('LabDllSha256', $verifiedDllSha, [Microsoft.Win32.RegistryValueKind]::String)
    $key.Flush()
    if ($key.GetValue('Name') -cne $name -or
        $key.GetValue('FunctionLibrary') -cne $targetDll -or
        $key.GetValue('LabDllSha256') -cne $verifiedDllSha -or
        $key.GetValue('LabSourceSha') -cne $verifiedHead -or
        [int]$key.GetValue('CAN') -ne 1 -or
        [int]$key.GetValue('ISO15765') -ne 1 -or
        [int]$key.GetValue('CAN_PS') -ne 1 -or
        [int]$key.GetValue('ISO15765_PS') -ne 1 -or
        [int]$key.GetValue('MessageVersion') -ne 0x0404) {
        throw 'Dedicated PS Registry32 readback mismatch'
    }
    Write-Host "CREATED_PS_PROVIDER: $name, Registry32, SHA256=$sha"
} catch {
    if ($null -ne $key) { $key.Close(); $key = $null }
    if ($createdKey) {
        try { $reg.DeleteSubKeyTree($keyPath, $false) } catch { }
    }
    if ($createdDirectory) {
        try { Remove-Item -LiteralPath $targetDirectory -Recurse -Force } catch { }
    }
    throw
} finally {
    if ($null -ne $key) { $key.Close() }
    $reg.Close()
}
