#Requires -Version 5.1
<#
 B3A277: stage a new isolated GGD CEM50 lab for original VIDA testing.
 COPY ONLY: no Registry32 writes, no client launch, no SQL modifications.
 The tested B3A276 x86 DLL is copied from the active local checkout.
 The existing B3A261 private profile is copied without publishing VIN or frame bytes.
#>
[CmdletBinding()]
param(
 [string]$BaselineIni = 'C:\VirtualCar-B3A261-Lab\virtualcar.ini',
 [string]$OutputDirectory = 'C:\VirtualCar-B3A277-Lab',
 [string]$DllPath = 'C:\VirtualCar-B3A275-Review\emulator\VirtualCarJ2534.dll'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$expectedDllSha='7E5F6BB0B475B088E0CA899A22962109E9301CD10D63F6E09AA266A42F501060'
function Find-Section([string]$ini,[string]$section) {
  $pattern='(?im)^\['+[Regex]::Escape($section)+'\][ \t]*\r?\n'
  $all=[regex]::Matches($ini,$pattern)
  if($all.Count -gt 1){throw ("DUPLICATE_INI_SECTION: "+$section)}
  if($all.Count -eq 0){return $null}
  $start=$all[0].Index+$all[0].Length
  $next=[regex]::Match($ini.Substring($start),'(?m)^\[[^\]\r\n]+\][ \t]*\r?$',[System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
  $end=if($next.Success){$start+$next.Index}else{$ini.Length}
  return @{ Start=$start; End=$end; Body=$ini.Substring($start,$end-$start) }
}
function Get-Key([string]$ini,[string]$section,[string]$key){
  $s=Find-Section $ini $section
  if($null -eq $s){return $null}
  $pat='(?im)^[ \t]*'+[Regex]::Escape($key)+'[ \t]*=[ \t]*([^\r\n;#]*)'
  $ms=[regex]::Matches($s.Body,$pat)
  if($ms.Count -gt 1){throw ("DUPLICATE_INI_KEY: "+$section+'/'+$key)}
  if($ms.Count -eq 0){return $null}
  return $ms[0].Groups[1].Value.Trim()
}
function Set-Key([string]$ini,[string]$section,[string]$key,[string]$value){
  $s=Find-Section $ini $section
  if($null -eq $s){return ($ini.TrimEnd(" `r","`n")+"`r`n`r`n[$section]`r`n$key=$value`r`n")}
  $pat='(?im)^([ \t]*'+[Regex]::Escape($key)+'[ \t]*=[ \t]*)[^\r\n]*'
  $ms=[regex]::Matches($s.Body,$pat)
  if($ms.Count -gt 1){throw ("DUPLICATE_INI_KEY: "+$section+'/'+$key)}
  if($ms.Count -eq 1){
    $old=$ms[0]
    $body=$s.Body.Substring(0,$old.Index)+$old.Groups[1].Value+$value+$s.Body.Substring($old.Index+$old.Length)
  }else{
    $body=$s.Body.TrimEnd("`r","`n")+"`r`n$key=$value`r`n`r`n"
  }
  return $ini.Substring(0,$s.Start)+$body+$ini.Substring($s.End)
}
$dll=(Resolve-Path -LiteralPath $DllPath).Path
$iniPath=(Resolve-Path -LiteralPath $BaselineIni).Path
$target=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $target){throw 'B3A277_REFUSE_EXISTING_TARGET'}
if([string]::Equals($target,[IO.Path]::GetDirectoryName($iniPath),[StringComparison]::OrdinalIgnoreCase) -or
   [string]::Equals($target,[IO.Path]::GetDirectoryName($dll),[StringComparison]::OrdinalIgnoreCase)){
  throw 'B3A277_TARGET_NOT_ISOLATED'
}
$before=(Get-FileHash -LiteralPath $iniPath -Algorithm SHA256).Hash
$actualDll=(Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
if($actualDll -cne $expectedDllSha){throw 'B3A277_DLL_SHA_MISMATCH'}
$raw=[IO.File]::ReadAllText($iniPath,[Text.Encoding]::Default)
if($raw.Length -lt 100){throw 'B3A277_INI_TOO_SMALL'}
$cnt=Get-Key $raw 'D2_50' 'FrameCount'
if($null -eq $cnt){$cnt=Get-Key $raw 'D2_50' 'B9FBFrameCount'}
if($cnt -cne '13'){throw 'B3A277_READVIN_13FRAME_NOT_PRESENT'}
$block=Find-Section $raw 'D2_50'
if($null -eq $block){throw 'B3A277_D2_50_SECTION_MISSING'}
foreach($i in 0..12){
  $hex=('0123456789ABCDEF')[$i]
  $v=Get-Key $raw 'D2_50' ('B9FBFrame'+$hex)
  if($null -eq $v){$v=Get-Key $raw 'D2_50' ('Frame'+$hex)}
  if([string]::IsNullOrWhiteSpace($v)){throw 'B3A277_INCOMPLETE_B9FB_FRAMES'}
}
if((Get-Key $raw 'P2' 'StrictRouting') -ne '1'){throw 'B3A277_STRICT_ROUTING_NOT_ENABLED'}
$updated=$raw
$updated=Set-Key $updated 'Diagnostics' 'EnableGGDCemLab' '1'
$updated=Set-Key $updated 'Vehicle' 'ECUCount' '2'
$updated=Set-Key $updated 'ECU1' 'RequestId' '18DA50F1'
$updated=Set-Key $updated 'ECU1' 'ResponseId' '18DAF150'
foreach($spec in @(
  @('Diagnostics','EnableGGDCemLab','1'),
  @('Vehicle','ECUCount','2'),
  @('ECU1','RequestId','18DA50F1'),
  @('ECU1','ResponseId','18DAF150'),
  @('P2','StrictRouting','1')
)){
  if((Get-Key $updated $spec[0] $spec[1]) -cne $spec[2]){throw 'B3A277_INI_VALIDATION_FAILED'}
}
# Confirm the D2_50 section was not modified. No raw VIN or B9FB byte values logged.
$oldD2=(Find-Section $raw 'D2_50').Body
$newD2=(Find-Section $updated 'D2_50').Body
if($oldD2 -cne $newD2){throw 'B3A277_B9FB_SECTION_CHANGED'}
[void][IO.Directory]::CreateDirectory($target)
Copy-Item -LiteralPath $dll -Destination (Join-Path $target 'VirtualCarJ2534.dll')
[IO.File]::WriteAllText((Join-Path $target 'virtualcar.ini'),$updated,[Text.Encoding]::Default)
$after=(Get-FileHash -LiteralPath $iniPath -Algorithm SHA256).Hash
if($before -cne $after){throw 'B3A277_BASELINE_PROFILE_CHANGED'}
if((Get-FileHash -LiteralPath (Join-Path $target 'VirtualCarJ2534.dll') -Algorithm SHA256).Hash -cne $expectedDllSha){
  throw 'B3A277_COPIED_DLL_HASH_MISMATCH'
}
Write-Output 'B3A277_STAGE=PASS'
Write-Output 'B3A277_B9FB_13FRAME=PRESERVED'
Write-Output 'B3A277_GGD_CEM50=ENABLED_IN_NEW_COPY'
Write-Output 'B3A277_BASELINE_INI=UNCHANGED'
Write-Output 'B3A277_REGISTRY=UNCHANGED; VIDA=NOT_TESTED; ORIGINAL_ECU_ID=NOT_TESTED'
Write-Output ('B3A277_DLL_SHA256='+$expectedDllSha)
Write-Output ('B3A277_LAB_DIRECTORY='+$target)
