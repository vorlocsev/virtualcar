#Requires -RunAsAdministrator
$ErrorActionPreference='Stop'
$path=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\VirtualCarJ2534.dll'))
if(-not [IO.File]::Exists($path)){throw "DLL not found: $path"}
$base=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,[Microsoft.Win32.RegistryView]::Registry32)
try {
  $parent=$base.CreateSubKey('SOFTWARE\PassThruSupport.04.04')
  try {
    foreach($name in @('J2534 Lab Adapter','SectorV Virtual Car')){
      $existing=$parent.OpenSubKey($name)
      if($null -ne $existing){$existing.Dispose();throw 'Existing registration found. Remove the recognized registration before installing.'}
    }
    $key=$parent.CreateSubKey('J2534 Lab Adapter')
    try {
      $key.SetValue('Vendor','J2534 Lab',[Microsoft.Win32.RegistryValueKind]::String)
      $key.SetValue('Name','J2534 Lab Adapter',[Microsoft.Win32.RegistryValueKind]::String)
      $key.SetValue('FunctionLibrary',$path,[Microsoft.Win32.RegistryValueKind]::String)
      $key.SetValue('ConfigApplication','',[Microsoft.Win32.RegistryValueKind]::String)
      $key.SetValue('CAN',1,[Microsoft.Win32.RegistryValueKind]::DWord)
      $key.SetValue('ISO15765',1,[Microsoft.Win32.RegistryValueKind]::DWord)
      $key.SetValue('MessageVersion',0x0404,[Microsoft.Win32.RegistryValueKind]::DWord)
    } finally {$key.Close()}
  } finally {$parent.Close()}
} finally {$base.Close()}
Write-Host 'J2534 Lab Adapter registered (J2534 04.04, x86).' -ForegroundColor Green
