#Requires -Version 5.1
<#
Create an isolated Windows x86 J2534 CEM50 provider. Dry-run unless -Apply.
The profile is synthetic; no original VIDA, SQL or physical ECU operations.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$SourceDll,
    [Parameter(Mandatory=$true)][ValidatePattern('^[a-fA-F0-9]{64}$')][string]$ExpectedSha256,
    [switch]$Apply
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$name = 'J2534 Diagnostic Interface CEM50'
$keyPath = 'SOFTWARE\PassThruSupport.04.04\J2534 Diagnostic Interface CEM50'
$targetDirectory = Join-Path $env:ProgramData 'J2534-CEM50'
$targetDll = Join-Path $targetDirectory 'J2534CEM50.dll'
$targetIni = Join-Path $targetDirectory 'virtualcar.ini'
$sourceIni = Join-Path $PSScriptRoot 'virtualcar.ini'
$src = [IO.Path]::GetFullPath($SourceDll)
if (-not [IO.File]::Exists($src) -or -not [IO.File]::Exists($sourceIni)) {
    throw 'Source DLL or published CEM50 INI missing'
}
if ([string]::Equals($src, $targetDll, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Source DLL must differ from the new isolated installation'
}
$sha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
if ($sha -ine $ExpectedSha256) { throw 'Source DLL SHA256 mismatch' }

# Require an x86 Windows PE32 image before staging. This does not authenticate the binary.
$b = [IO.File]::ReadAllBytes($src)
if ($b.Length -lt 256 -or $b[0] -ne 0x4D -or $b[1] -ne 0x5A) {
    throw 'Not a PE DLL'
}
$pe = [BitConverter]::ToInt32($b, 0x3C)
if ($pe -lt 64 -or $pe + 26 -ge $b.Length -or
    $b[$pe] -ne 0x50 -or $b[$pe+1] -ne 0x45 -or
    [BitConverter]::ToUInt16($b, $pe+4) -ne 0x014C -or
    [BitConverter]::ToUInt16($b, $pe+24) -ne 0x010B) {
    throw 'Expected a 32-bit x86 PE32 J2534 DLL'
}
$cfg = [IO.File]::ReadAllText($sourceIni)
if (-not $cfg.Contains('VIN = YV1CR855691511566') -or
    -not $cfg.Contains('B9FBFrameCount = 13') -or
    -not $cfg.Contains('ResponseId = 01200003')) {
    throw 'CEM50 profile identity or frame count mismatch'
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
        throw 'J2534 CEM50 registration already exists; never overwrite'
    }
    if ([IO.Directory]::Exists($targetDirectory)) {
        throw 'J2534 CEM50 directory already exists; never overwrite'
    }
    if (-not $Apply) {
        Write-Host "DRY_RUN_ONLY: $name, x86 source SHA256=$sha"
        Write-Host "New directory: $targetDirectory"
        return
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
    if ((Get-FileHash -LiteralPath $targetDll -Algorithm SHA256).Hash -ine $sha -or
        [IO.File]::ReadAllText($targetIni) -cne $cfg) {
        throw 'Staged DLL/INI differ from reviewed inputs'
    }
    $key = $reg.CreateSubKey($keyPath)
    if ($null -eq $key) { throw 'Unable to register isolated provider' }
    $createdKey = $true
    $key.SetValue('Vendor', 'J2534 CEM50 Lab', [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('Name', $name, [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('FunctionLibrary', $targetDll, [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('ConfigApplication', '', [Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('CAN', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('ISO15765', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('MessageVersion', 0x0404, [Microsoft.Win32.RegistryValueKind]::DWord)
    $key.Flush()
    Write-Host "CREATED: $name, Registry32, DLL SHA256=$sha"
} catch {
    if ($null -ne $key) { $key.Close(); $key=$null }
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
