#Requires -Version 5.1
<#
B3A278: controlled Windows x86 J2534 04.04 provider registration for original VIDA.
Default Inspect is strictly read-only. Register and Unregister require elevated PowerShell.
Never overwrites any existing provider key. Never touches VIDA/SQL/ECU or source profile.
Only the single exact Registry32 key "J2534 Diagnostic Lab 277" is in scope.
#>
[CmdletBinding()]
param(
 [ValidateSet('Inspect','Register','Unregister')][string]$Action='Inspect',
 [string]$LabDirectory='C:\VirtualCar-B3A277-Lab'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$provider='J2534 Diagnostic Lab 277'
$vendor='P2 Diagnostics Lab'
$parentPath='SOFTWARE\PassThruSupport.04.04'
$expectedDllSha='7E5F6BB0B475B088E0CA899A22962109E9301CD10D63F6E09AA266A42F501060'
$folder=[IO.Path]::GetFullPath($LabDirectory).TrimEnd('\')
$dll=Join-Path $folder 'VirtualCarJ2534.dll'
$ini=Join-Path $folder 'virtualcar.ini'
if(-not [IO.File]::Exists($dll) -or -not [IO.File]::Exists($ini)) {
 throw 'B3A278_LAB_FILES_MISSING'
}
if((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -cne $expectedDllSha){
 throw 'B3A278_DLL_SHA_MISMATCH'
}
# Verify only that this is the staged GGD/B9FB copy. Never print INI bytes,
# private VIN, recorded D2 payload, or hashes of private INI.
$profile=[IO.File]::ReadAllText($ini,[Text.Encoding]::Default)
function ConfigValue([string]$section,[string]$key,[switch]$Optional) {
 $sectionPattern='(?im)^\['+[Regex]::Escape($section)+'\]\s*\r?$'
 $matches=[regex]::Matches($profile,$sectionPattern)
 if($matches.Count -ne 1) {throw ('B3A278_SECTION_INVALID_'+$section)}
 $tail=$profile.Substring($matches[0].Index+$matches[0].Length)
 $next=[regex]::Match($tail,'(?m)^\[[^\]\r\n]+\]\s*\r?$')
 $body=if($next.Success){$tail.Substring(0,$next.Index)}else{$tail}
 $valuePattern='(?im)^[ \t]*'+[Regex]::Escape($key)+'\s*=\s*([^\r\n;#]*)'
 $values=[regex]::Matches($body,$valuePattern)
 if($values.Count -eq 0 -and $Optional){return $null}
 if($values.Count -ne 1){throw ('B3A278_KEY_INVALID_'+$section+'_'+$key)}
 return $values[0].Groups[1].Value.Trim()
}
if((ConfigValue 'Diagnostics' 'EnableGGDCemLab') -ne '1' -or
   (ConfigValue 'Vehicle' 'ECUCount') -ne '2' -or
   (ConfigValue 'ECU1' 'RequestId') -cne '18DA50F1' -or
   (ConfigValue 'ECU1' 'ResponseId') -cne '18DAF150' -or
   (ConfigValue 'P2' 'StrictRouting') -ne '1'){
 throw 'B3A278_GGD_LAB_INI_NOT_STAGED'
}
$frames=ConfigValue 'D2_50' 'FrameCount' -Optional
if($null -eq $frames){$frames=ConfigValue 'D2_50' 'B9FBFrameCount'}
if($frames -ne '13'){throw 'B3A278_READVIN_FRAMECOUNT_UNEXPECTED'}
$base=[Microsoft.Win32.RegistryKey]::OpenBaseKey(
 [Microsoft.Win32.RegistryHive]::LocalMachine,
 [Microsoft.Win32.RegistryView]::Registry32
)
function EntryMatches($entry) {
 if($null -eq $entry){return $false}
 $library=[string]$entry.GetValue('FunctionLibrary','')
 try {$library=[IO.Path]::GetFullPath($library)}catch{return $false}
 return ([string]::Equals($library,$dll,[StringComparison]::OrdinalIgnoreCase) -and
  [string]$entry.GetValue('Vendor','') -ceq $vendor -and
  [string]$entry.GetValue('Name','') -ceq $provider -and
  [int]$entry.GetValue('CAN',0) -eq 1 -and
  [int]$entry.GetValue('ISO15765',0) -eq 1 -and
  [int]$entry.GetValue('MessageVersion',0) -eq 0x0404)
}
try {
 $parent=$base.OpenSubKey($parentPath,$Action -ne 'Inspect')
 if($null -eq $parent){throw 'B3A278_J2534_0404_PARENT_MISSING'}
 try {
  $prior=$parent.OpenSubKey($provider,$false)
  try {
   $exists=$null -ne $prior
   $same=EntryMatches $prior
  } finally {if($null -ne $prior){$prior.Dispose()}}
  if($Action -eq 'Inspect'){
   if(-not $exists){Write-Output 'B3A278_REGISTRY=ABSENT_SAFE_TO_REGISTER'}
   elseif($same){Write-Output 'B3A278_REGISTRY=EXACT_MATCH_ALREADY_REGISTERED'}
   else {Write-Output 'B3A278_REGISTRY=NAME_COLLISION_REFUSE_OVERWRITE'}
   Write-Output 'B3A278_LAB_DLL=SHA256_PASS'
   Write-Output 'B3A278_PRIVATE_INI=GGD_AND_B9FB_METADATA_PASS'
   Write-Output 'B3A278_ACTION=INSPECT_READ_ONLY; VIDA=NOT_TESTED'
   return
  }
  $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
  $principal=New-Object Security.Principal.WindowsPrincipal($identity)
  if(-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)){
   throw 'B3A278_ELEVATED_POWERSHELL_REQUIRED'
  }
  $clients=@(Get-Process -Name iexplore,SectorV,VDASH -ErrorAction SilentlyContinue)
  if($clients.Count -gt 0){throw 'B3A278_CLOSE_DIAGNOSTIC_CLIENTS_FIRST'}
  if($Action -eq 'Register'){
   if($exists){throw 'B3A278_PROVIDER_ALREADY_EXISTS_REFUSE_OVERWRITE'}
   $created=$false
   try {
    $entry=$parent.CreateSubKey($provider)
    if($null -eq $entry){throw 'B3A278_CREATE_KEY_FAILED'}
    $created=$true
    try{
     $entry.SetValue('Vendor',$vendor,[Microsoft.Win32.RegistryValueKind]::String)
     $entry.SetValue('Name',$provider,[Microsoft.Win32.RegistryValueKind]::String)
     $entry.SetValue('FunctionLibrary',$dll,[Microsoft.Win32.RegistryValueKind]::String)
     $entry.SetValue('ConfigApplication','',[Microsoft.Win32.RegistryValueKind]::String)
     $entry.SetValue('CAN',1,[Microsoft.Win32.RegistryValueKind]::DWord)
     $entry.SetValue('ISO15765',1,[Microsoft.Win32.RegistryValueKind]::DWord)
     $entry.SetValue('MessageVersion',0x0404,[Microsoft.Win32.RegistryValueKind]::DWord)
     $entry.Flush()
     if(-not (EntryMatches $entry)){throw 'B3A278_VERIFY_NEW_ENTRY_FAILED'}
    }finally{$entry.Dispose()}
   }catch{
    if($created){$parent.DeleteSubKeyTree($provider,$false)}
    throw
   }
   Write-Output 'B3A278_REGISTRY32=REGISTERED_EXACT_NEW_PROVIDER'
   Write-Output 'B3A278_OTHER_PROVIDERS=UNCHANGED'
   Write-Output 'B3A278_VIDA=NOT_TESTED'
  }elseif($Action -eq 'Unregister'){
   if(-not $exists){throw 'B3A278_PROVIDER_MISSING_NOTHING_REMOVED'}
   if(-not $same){throw 'B3A278_PROVIDER_IDENTITY_MISMATCH_REFUSE_DELETE'}
   $parent.DeleteSubKeyTree($provider,$false)
   Write-Output 'B3A278_REGISTRY32=ONLY_LAB_277_REMOVED'
   Write-Output 'B3A278_LAB_FILES=UNCHANGED'
  }
 }finally{$parent.Dispose()}
}finally{$base.Dispose()}
