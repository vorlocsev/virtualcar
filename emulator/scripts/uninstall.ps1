#Requires -RunAsAdministrator
$ErrorActionPreference='Stop'
$base=[Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,[Microsoft.Win32.RegistryView]::Registry32)
try {
  $parent=$base.OpenSubKey('SOFTWARE\PassThruSupport.04.04',$true)
  if($null -ne $parent){
    try {
      $targets=@()
      foreach($name in @('J2534 Lab Adapter','SectorV Virtual Car')){
        $key=$parent.OpenSubKey($name)
        if($null -eq $key){continue}
        try {
          $targets+= $name
          $legacy=$name -eq 'SectorV Virtual Car'
          $vendor=if($legacy){'SectorV Virtual Lab'}else{'J2534 Lab'}
          $display=if($legacy){'SectorV Virtual Car (J2534)'}else{'J2534 Lab Adapter'}
          $library=$key.GetValue('FunctionLibrary',$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
          $expected=@('Vendor','Name','FunctionLibrary','ConfigApplication','CAN','ISO15765','MessageVersion')
          if($key.SubKeyCount -ne 0 -or $key.ValueCount -ne $expected.Count -or
            @($expected | Where-Object {$_ -notin $key.GetValueNames()}).Count -ne 0 -or
            $key.GetValue('Vendor') -cne $vendor -or $key.GetValue('Name') -cne $display -or
            $library -isnot [string] -or $library -notmatch '^[a-zA-Z]:[\\/]' -or
            [IO.Path]::GetFileName($library) -ine 'VirtualCarJ2534.dll' -or
            $key.GetValueKind('FunctionLibrary') -ne [Microsoft.Win32.RegistryValueKind]::String -or
            $key.GetValue('ConfigApplication') -cne '' -or $key.GetValue('CAN') -ne 1 -or
            $key.GetValue('ISO15765') -ne 1 -or $key.GetValue('MessageVersion') -ne 0x0404){
            throw 'Unrecognized registration. Manual review required.'
          }
        } finally {$key.Close()}
      }
      if($targets.Count -gt 1){throw 'Conflicting registrations. Manual review required.'}
      if($targets.Count -eq 1){$parent.DeleteSubKey($targets[0],$false)}
    } finally {$parent.Close()}
  }
} finally {$base.Close()}
Write-Host 'J2534 adapter registration removed. Other adapters and files remain unchanged.' -ForegroundColor Green
