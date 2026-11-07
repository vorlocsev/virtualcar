# Run in Windows PowerShell, no Administrator rights required.
param([string]$SectorVPath = '')
$ErrorActionPreference = 'Stop'
$expected = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\VirtualCarJ2534.dll'))
$entry = 'SOFTWARE\PassThruSupport.04.04\SectorV Virtual Car'

function Get-Architecture([string]$path) {
  if (-not [IO.File]::Exists($path)) { return 'File not found' }
  $fs = [IO.File]::OpenRead($path)
  try {
    $reader = New-Object IO.BinaryReader($fs)
    if ($reader.ReadUInt16() -ne 0x5A4D) { return 'Invalid MZ header' }
    $fs.Seek(0x3C,[IO.SeekOrigin]::Begin) | Out-Null
    $offset = $reader.ReadInt32()
    if ($offset -lt 64 -or $offset -gt 1048576) { return 'Invalid PE offset' }
    $fs.Seek($offset,[IO.SeekOrigin]::Begin) | Out-Null
    if ($reader.ReadUInt32() -ne 0x4550) { return 'Invalid PE signature' }
    $machine = $reader.ReadUInt16()
    switch ($machine) {
      0x014c { return 'x86' }
      0x8664 { return 'x64' }
      0xAA64 { return 'ARM64' }
      default { return ('Other: 0x{0:X4}' -f $machine) }
    }
  } finally { $fs.Dispose() }
}

Write-Host 'SectorV Virtual Car - J2534 registration diagnostics' -ForegroundColor Cyan
Write-Host ('Expected DLL: {0}' -f $expected)
Write-Host ('Expected DLL architecture: {0}' -f (Get-Architecture $expected))
$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,[Microsoft.Win32.RegistryView]::Registry32)
try {
  $key = $base.OpenSubKey($entry)
  if ($null -eq $key) {
    Write-Host 'Registry32: NOT REGISTERED' -ForegroundColor Yellow
  } else {
    try {
      $actual = [string]$key.GetValue('FunctionLibrary','')
      $name = [string]$key.GetValue('Name','')
      Write-Host ('Registry32 Name: {0}' -f $name)
      Write-Host ('Registry32 FunctionLibrary: {0}' -f $actual)
      Write-Host ('Registered DLL architecture: {0}' -f (Get-Architecture $actual))
      if ($actual -and ([string]::Equals([IO.Path]::GetFullPath($actual),$expected,[StringComparison]::OrdinalIgnoreCase))) {
        Write-Host 'Registry32: OK (path matches)' -ForegroundColor Green
      } else {
        Write-Host 'Registry32: STALE or invalid DLL path' -ForegroundColor Yellow
      }
    } finally { $key.Close() }
  }
} finally { $base.Close() }
if ($SectorVPath) {
  Write-Host ('SectorV executable architecture: {0}' -f (Get-Architecture $SectorVPath))
}
Write-Host 'If Registry32 is missing or stale: run VirtualCarControl.exe as administrator, click Install, then restart SectorV.'
Write-Host 'The emulator only registers J2534 v04.04, 32-bit; x64/05.00 applications may not see it.'
