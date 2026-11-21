#Requires -Version 5.1
<#
Register only an independently staged CEM50 B9FB x86 J2534 laboratory adapter.
Dry-run by default. -Apply requires administrator and an absent Registry32 key.
Never modifies an existing adapter, installed VIDA, SQL or ECU.
#>
[CmdletBinding()]
param(
    [string]$PackageDirectory = $PSScriptRoot,
    [Parameter(Mandatory=$true)][string]$ExpectedVin,
    [switch]$Apply
)
$ErrorActionPreference = 'Stop'
$adapterName = 'J2534 CEM50 B9FB'
$keyPath = 'SOFTWARE\PassThruSupport.04.04\J2534 CEM50 B9FB'
if ($adapterName -match 'Virtual' -or $ExpectedVin -cnotmatch '^[A-HJ-NPR-Z0-9]{17}$') {
    throw 'Invalid display name or owner VIN'
}
$root = [IO.Path]::GetFullPath($PackageDirectory)
$dll = Join-Path $root 'VirtualCarJ2534.dll'
$ini = Join-Path $root 'virtualcar.ini'
$manifestPath = Join-Path $root 'adapter_manifest.json'
foreach ($f in @($dll,$ini,$manifestPath)) {
    if (-not [IO.File]::Exists($f)) { throw 'Incomplete staged CEM50 adapter directory' }
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema_version -cne 'j2534-cem50-isolated-lab-v1' -or
    $manifest.adapter_display_name -cne $adapterName -or
    $manifest.d2_b9fb_frame_count -ne 13 -or
    $manifest.registration_applied -ne $false -or
    $manifest.vehicle_vin_equals_b9fb_vin -ne $true) {
    throw 'Staged manifest does not match isolated CEM50 contract'
}
$actualSha = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
if ($actualSha -cne ([string]$manifest.dll_sha256).ToUpperInvariant()) {
    throw 'Staged DLL SHA256 mismatch'
}
$bytes = [IO.File]::ReadAllBytes($dll)
if ($bytes.Length -lt 512 -or $bytes[0] -ne 0x4D -or $bytes[1] -ne 0x5A) {
    throw 'Expected x86 PE DLL'
}
$pe = [BitConverter]::ToInt32($bytes,0x3C)
if ($pe -lt 0x40 -or ($pe + 26) -gt $bytes.Length -or
    [BitConverter]::ToUInt32($bytes,$pe) -ne 0x00004550 -or
    [BitConverter]::ToUInt16($bytes,$pe+4) -ne 0x014C -or
    [BitConverter]::ToUInt16($bytes,$pe+24) -ne 0x010B) {
    throw 'Not PE32 x86'
}
$raw = [IO.File]::ReadAllText($ini)
$vehicle = [regex]::Match($raw,'(?ms)^\[Vehicle\][ \t]*\r?\n(?<body>.*?)(?=^\[|\z)')
$cem = [regex]::Match($raw,'(?ms)^\[D2_50\][ \t]*\r?\n(?<body>.*?)(?=^\[|\z)')
if (-not $vehicle.Success -or -not $cem.Success) { throw 'Missing Vehicle/CEM50 section' }
$vinMatch = [regex]::Match($vehicle.Groups['body'].Value,'(?mi)^vin[ \t]*=[ \t]*([A-HJ-NPR-Z0-9]{17})[ \t]*\r?$')
$yearMatch = [regex]::IsMatch($vehicle.Groups['body'].Value,'(?mi)^modelyear[ \t]*=[ \t]*2009[ \t]*\r?$')
$countMatch = [regex]::IsMatch($cem.Groups['body'].Value,'(?mi)^b9fbframecount[ \t]*=[ \t]*13[ \t]*\r?$')
$frames = [regex]::Matches($cem.Groups['body'].Value,'(?mi)^b9fbframe[0-9a-c][ \t]*=')
if (-not $vinMatch.Success -or $vinMatch.Groups[1].Value -cne $ExpectedVin -or
    -not $yearMatch -or -not $countMatch -or $frames.Count -ne 13) {
    throw 'Private VIN or CEM50 B9FB frame count does not match expected lab'
}
$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
    [Microsoft.Win32.RegistryHive]::LocalMachine,
    [Microsoft.Win32.RegistryView]::Registry32)
try {
    $old = $base.OpenSubKey($keyPath, $false)
    if ($old) { $old.Close(); throw 'Adapter key already exists; refusing overwrite' }
    if (-not $Apply) {
        Write-Host 'CEM50_ADAPTER: DRY_RUN_ONLY'
        Write-Host 'Adapter: J2534 CEM50 B9FB'
        Write-Host 'Registry32 unchanged; no diagnostic connection attempted'
        return
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw 'Administrator privileges required for -Apply'
    }
    $created = $false
    try {
        $key = $base.CreateSubKey($keyPath)
        if (-not $key) { throw 'Failed to create Registry32 J2534 key' }
        $created = $true
        try {
            $key.SetValue('Vendor','J2534 CEM50 Laboratory',
                [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('Name',$adapterName,
                [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('FunctionLibrary',$dll,
                [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('ConfigApplication','',
                [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('CAN',1,[Microsoft.Win32.RegistryValueKind]::DWord)
            $key.SetValue('ISO15765',1,[Microsoft.Win32.RegistryValueKind]::DWord)
            $key.SetValue('MessageVersion',0x0404,[Microsoft.Win32.RegistryValueKind]::DWord)
            $key.Flush()
        } finally { $key.Close() }
    } catch {
        if ($created) { $base.DeleteSubKeyTree($keyPath,$false) }
        throw
    }
    Write-Host 'CEM50_ADAPTER: CREATED'
    Write-Host 'Registered isolated J2534 CEM50 B9FB (Registry32)'
    Write-Host 'VIDA ReadVin and ECU identification remain NOT_VERIFIED'
} finally { $base.Close() }
