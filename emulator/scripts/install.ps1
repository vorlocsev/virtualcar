#Requires -RunAsAdministrator
$ErrorActionPreference='Stop'
$path=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\VirtualCarJ2534.dll'))
if(-not [IO.File]::Exists($path)){throw "DLL not found: $path"}
$base=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,[Microsoft.Win32.RegistryView]::Registry32)
try {
  $key=$base.CreateSubKey('SOFTWARE\PassThruSupport.04.04\SectorV Virtual Car')
  try {
    $key.SetValue('Vendor','SectorV Virtual Lab',[Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('Name','SectorV Virtual Car (J2534)',[Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('FunctionLibrary',$path,[Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('ConfigApplication','',[Microsoft.Win32.RegistryValueKind]::String)
    $key.SetValue('CAN',1,[Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('ISO15765',1,[Microsoft.Win32.RegistryValueKind]::DWord)
    $key.SetValue('MessageVersion',0x0404,[Microsoft.Win32.RegistryValueKind]::DWord)
  } finally {$key.Close()}
} finally {$base.Close()}
Write-Host 'SectorV Virtual Car registered (J2534 04.04, x86).' -ForegroundColor Green
