#Requires -RunAsAdministrator
# Select or remove ONLY the dedicated Virtual Car CAN_PS A/B LAB J2534 registration.
# Windows PowerShell 5.1, 32-bit registry view, no existing adapter replacement.
[CmdletBinding()]
param(
    [ValidateSet('CONTROL','A_FILTER','B_D8_WRITE','C_D8_PERIODIC')]
    [string]$Mode,
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$entry = 'Virtual Car CANPS AB LAB'
$keyPath = 'SOFTWARE\PassThruSupport.04.04'
$owner = 'VirtualCar-CANPS-AB-v1'

if (!$Remove -and [string]::IsNullOrEmpty($Mode)) {
    throw 'Specify -Mode CONTROL|A_FILTER|B_D8_WRITE|C_D8_PERIODIC or -Remove'
}
if ($Remove -and ![string]::IsNullOrEmpty($Mode)) {
    throw 'Use either -Mode or -Remove, not both'
}

# Avoid changing DLL registrations while a known diagnostic client is alive.
$busy = @(Get-Process -Name 'vdash_u','vdash','SectorV' -ErrorAction SilentlyContinue)
if ($busy.Count -gt 0) {
    throw 'Close VDASH, SectorV and all associated workers before switching LAB mode'
}

$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
    [Microsoft.Win32.RegistryHive]::LocalMachine,
    [Microsoft.Win32.RegistryView]::Registry32
)
try {
    if ($Remove) {
        $parent = $base.OpenSubKey($keyPath, $true)
        if ($null -eq $parent) {
            Write-Host 'LAB adapter is not registered.'
            return
        }
        try {
            $existing = $parent.OpenSubKey($entry, $false)
            if ($null -eq $existing) {
                Write-Host 'LAB adapter is not registered.'
                return
            }
            try {
                if ($existing.GetValue('LabOwner', '') -ne $owner) {
                    throw 'Refusing to delete a J2534 entry not owned by this LAB'
                }
            } finally {
                $existing.Close()
            }
            $parent.DeleteSubKeyTree($entry, $false)
        } finally {
            $parent.Close()
        }
        Write-Host 'Dedicated Virtual Car CAN_PS LAB entry removed. Other adapters unchanged.' -ForegroundColor Green
        return
    }

    $folder = Join-Path $PSScriptRoot $Mode
    $dll = Join-Path $folder 'VirtualCarJ2534.dll'
    $ini = Join-Path $folder 'virtualcar.ini'
    $manifest = Join-Path $PSScriptRoot 'BUILDINFO.json'

    foreach ($f in @($dll, $ini, $manifest)) {
        if (![IO.File]::Exists($f)) { throw "Missing LAB package file: $f" }
    }
    $info = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
    if ($info.format -ne 'virtualcar-canps-api-only-ab-v1' -or
        $info.architecture -ne 'windows-x86-pe32' -or
        $info.contains_private_data -ne $false) {
        throw 'Unexpected build manifest'
    }
    $expected = @{'CONTROL'=0; 'A_FILTER'=1; 'B_D8_WRITE'=2; 'C_D8_PERIODIC'=3}
    $modeNo = $expected[$Mode]
    if ($info.mode_directories.$Mode -ne $modeNo) {
        throw 'Manifest mode does not match requested mode'
    }
    $actualHash = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne [string]$info.dll_sha256) {
        throw 'DLL SHA256 mismatch: refusing LAB registration'
    }
    $config = Get-Content -LiteralPath $ini -Raw
    if ($config -notmatch '(?m)^EnableCanPsConfigProbe=1\s*$' -or
        $config -notmatch ('(?m)^CanPsApiOutcomeMode=' + $modeNo + '\s*$') -or
        $config -notmatch '(?m)^VIN=YV1CZ0002A0000001\s*$') {
        throw 'Profile differs from expected synthetic experiment'
    }

    $parent = $base.CreateSubKey($keyPath)
    try {
        $existing = $parent.OpenSubKey($entry, $false)
        if ($null -ne $existing) {
            try {
                if ($existing.GetValue('LabOwner', '') -ne $owner) {
                    throw 'Refusing to overwrite an existing non-LAB J2534 entry'
                }
            } finally { $existing.Close() }
        }
        $key = $parent.CreateSubKey($entry)
        try {
            $key.SetValue('LabOwner', $owner, [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('Vendor', 'Virtual Car Laboratory', [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('Name', 'Virtual Car CAN_PS A/B LAB', [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('FunctionLibrary', [IO.Path]::GetFullPath($dll),
                [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('ConfigApplication', '', [Microsoft.Win32.RegistryValueKind]::String)
            $key.SetValue('CAN', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
            $key.SetValue('ISO15765', 1, [Microsoft.Win32.RegistryValueKind]::DWord)
            $key.SetValue('MessageVersion', 0x0404, [Microsoft.Win32.RegistryValueKind]::DWord)
        } finally { $key.Close() }
    } finally { $parent.Close() }
    Write-Host ("LAB adapter set: {0}, DLL SHA256 {1}" -f $Mode, $actualHash) -ForegroundColor Green
    Write-Host 'Now choose Virtual Car CAN_PS A/B LAB in VDASH; never select a physical adapter.'
    Write-Host 'After the run close VDASH, then select another mode or use -Remove.'
} finally {
    $base.Close()
}
