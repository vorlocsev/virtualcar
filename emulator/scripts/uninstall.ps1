#Requires -RunAsAdministrator
$ErrorActionPreference='Stop'
$base=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,[Microsoft.Win32.RegistryView]::Registry32)
try {
  $parent=$base.OpenSubKey('SOFTWARE\PassThruSupport.04.04',$true)
  if($null -ne $parent){try{$parent.DeleteSubKeyTree('SectorV Virtual Car',$false)}finally{$parent.Close()}}
} finally {$base.Close()}
Write-Host 'Virtual adapter registration removed. Other J2534 adapters remain unchanged.' -ForegroundColor Green
