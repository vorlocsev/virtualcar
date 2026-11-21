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
# Parse actual INI sections/keys before any filesystem or registry writes.
# The native code reads virtualcar.ini beside its own DLL using Win32 INI APIs.
$values = @{}
$sections = @{}
$activeSection = ''
foreach ($rawLine in [IO.File]::ReadAllLines($sourceIni)) {
    $line = $rawLine.Trim()
    if ($line -eq '' -or $line.StartsWith(';') -or $line.StartsWith('#')) { continue }
    if ($line -match '^\[([A-Za-z0-9_]+)\]
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
) {
        $activeSection = $matches[1]
        if ($sections.ContainsKey($activeSection)) { throw 'Duplicate INI section' }
        $sections[$activeSection] = $true
        continue
    }
    if ($activeSection -eq '' -or $line -notmatch '^([A-Za-z0-9_]+)[ \t]*=[ \t]*(.*)
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
) {
        throw 'Unsupported or misplaced INI setting'
    }
    $entry = $activeSection + '.' + $matches[1]
    if ($values.ContainsKey($entry)) { throw 'Duplicate INI setting' }
    $values[$entry] = $matches[2].Trim()
}
if ($values['Vehicle.VIN'] -cne 'YV1CR855691511566' -or
    $values['Vehicle.ModelYear'] -cne '2009' -or
    $values['Vehicle.ECUCount'] -cne '1' -or
    $values['P2.StrictRouting'] -cne '1' -or
    $values['D2_50.ResponseId'] -cne '01200003' -or
    $values['D2_50.B9FBFrameCount'] -cne '13' -or
    $sections.ContainsKey('ECU1')) {
    throw 'Invalid isolated CEM50 identity or routing'
}
foreach ($pair in @(
    'D2_40.B9FBFrameCount', 'D2_40_B9F0.FrameCount',
    'D2_50_B9F0.FrameCount', 'D2_40_B9FC.FrameCount',
    'D2_50_B9FC.FrameCount', 'PassiveCAN.Enabled'
)) {
    if ($values[$pair] -cne '0') { throw 'Unapproved CEM reply or passive trace enabled' }
}
$frameKeys = @($values.Keys | Where-Object { $_ -match '^D2_50\.B9FBFrame[0-9A-F]+
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
 })
if ($frameKeys.Count -ne 13) { throw 'Wrong number of CEM50 B9FB frame keys' }
$wire = New-Object 'System.Collections.Generic.List[byte]'
for ($i = 0; $i -lt 13; $i++) {
    $frameKey = 'D2_50.B9FBFrame' + $i.ToString('X')
    $frameText = $values[$frameKey]
    if ([string]::IsNullOrEmpty($frameText) -or
        $frameText -notmatch '^(?:[0-9A-Fa-f]{2}[ \t]+){7}[0-9A-Fa-f]{2}
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
) {
        throw 'Malformed or missing CEM50 B9FB frame'
    }
    $frame = @($frameText -split '[ \t]+' | ForEach-Object { [Convert]::ToByte($_,16) })
    $expectedHeader = if ($i -eq 0) { 0x8F } elseif ($i -eq 12) { 0x4F } else { 0x08 -bor ($i -band 7) }
    if ($frame[0] -ne $expectedHeader) { throw 'Invalid D2 frame sequence' }
    for ($j = 1; $j -lt 8; $j++) { $wire.Add([byte]$frame[$j]) }
}
if ($wire.Count -ne 91 -or $wire[0] -ne 0x50 -or
    $wire[1] -ne 0xF9 -or $wire[2] -ne 0xFB -or
    [Text.Encoding]::ASCII.GetString($wire.ToArray(),14,17) -cne 'YV1CR855691511566' -or
    [Text.Encoding]::ASCII.GetString($wire.ToArray(),49,6) -cne '511566') {
    throw 'CEM50 B9FB VIN/chassis/payload mismatch'
}
Write-Host 'PROFILE_OK: CEM50 13 frames, VIN and chassis are consistent'

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
