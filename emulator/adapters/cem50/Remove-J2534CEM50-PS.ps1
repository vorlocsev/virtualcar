#Requires -Version 5.1
<#
Remove ONLY the dedicated CEM50 PS laboratory provider after reviewing provenance.
DRY RUN by default. Never remove the legacy CEM50 or other J2534 providers.
Close VIDA and any process using the PS DLL before -Apply.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9A-Fa-f]{64}$')][string]$ExpectedSha256,
    [switch]$Apply,
    [switch]$IConfirmClientClosed
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$verifiedHead = '9ab3738d6c53442f83c57727f6eaaf44e383c618'
$verifiedDllSha = '7F21E2606C6E7981ECDEDFE6769F180981C6DDFFFFBCC5C35CD4A6E983C98C3E'
$name = 'J2534 Diagnostic Interface CEM50 PS'
$keyPath = 'SOFTWARE\PassThruSupport.04.04\J2534 Diagnostic Interface CEM50 PS'
$directory = Join-Path $env:ProgramData 'J2534-CEM50-PS'
$dll = Join-Path $directory 'J2534CEM50PS.dll'
$ini = Join-Path $directory 'virtualcar.ini'

if ($ExpectedSha256.ToUpperInvariant() -cne $verifiedDllSha) {
    throw 'Expected SHA256 does not match approved PS native binary'
}
if (-not [IO.Directory]::Exists($directory) -or
    -not [IO.File]::Exists($dll) -or -not [IO.File]::Exists($ini)) {
    throw 'Dedicated PS installation is incomplete or absent; refusing removal'
}
if (([IO.File]::GetAttributes($directory) -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
    ([IO.File]::GetAttributes($dll) -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
    ([IO.File]::GetAttributes($ini) -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Unexpected PS installation reparse point'
}
$entries = @([IO.Directory]::GetFileSystemEntries($directory))
if ($entries.Count -ne 2) { throw 'Unexpected extra files in PS installation' }
if ((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -cne $verifiedDllSha) {
    throw 'Installed PS binary digest mismatch'
}
$cfg = [IO.File]::ReadAllText($ini)
if (-not $cfg.Contains('VIN = YV1CR855691511566') -or
    -not $cfg.Contains('[J2534_2]') -or
    -not $cfg.Contains('Enabled = 1') -or
    -not $cfg.Contains('B9FBFrameCount = 13') -or
    -not $cfg.Contains('FixtureAuthority = synthetic_lab_not_oem_attested')) {
    throw 'Installed PS profile has been modified'
}
$reg = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
    [Microsoft.Win32.RegistryHive]::LocalMachine,
    [Microsoft.Win32.RegistryView]::Registry32)
try {
    $key = $reg.OpenSubKey($keyPath)
    if ($null -eq $key) { throw 'Dedicated PS Registry32 key absent' }
    try {
        if ($key.GetValue('Vendor') -cne 'VirtualCar CEM50 Synthetic Lab' -or
            $key.GetValue('Name') -cne $name -or
            $key.GetValue('FunctionLibrary') -cne $dll -or
            $key.GetValue('LabSourceSha') -cne $verifiedHead -or
            $key.GetValue('LabDllSha256') -cne $verifiedDllSha -or
            [int]$key.GetValue('CAN') -ne 1 -or
            [int]$key.GetValue('ISO15765') -ne 1 -or
            [int]$key.GetValue('CAN_PS') -ne 1 -or
            [int]$key.GetValue('ISO15765_PS') -ne 1 -or
            [int]$key.GetValue('MessageVersion') -ne 0x0404 -or
            @($key.GetSubKeyNames()).Count -ne 0) {
            throw 'Registry32 key not owned by this exact PS test installation'
        }
    } finally {
        $key.Close()
    }
    Write-Host "PREFLIGHT_PASS: only $name qualifies for removal"
    if (-not $Apply) {
        Write-Host "DRY_RUN_ONLY: would remove dedicated PS key and $directory"
        return
    }
    if (-not $IConfirmClientClosed) {
        throw '-Apply requires -IConfirmClientClosed after closing VIDA and other clients'
    }
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        throw '-Apply requires elevated Windows PowerShell'
    }
    # Removal is not atomic: if deletion fails, stop, inspect the dedicated PS
    # directory/key and do not touch any other J2534 installation.
    $reg.DeleteSubKeyTree($keyPath, $false)
    Remove-Item -LiteralPath $directory -Recurse -Force -ErrorAction Stop
    Write-Host 'REMOVED_PS_PROVIDER: dedicated synthetic PS key/directory only'
} finally {
    $reg.Close()
}
