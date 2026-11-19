#requires -Version 5.1
<#
B3A312: direct read-only SQL Server connector to installed local VIDA CarCom.
No SQL modifications, J2534, VIN copying, stored procedure execution or ECU replies.
Probe = schema/connectivity only; Analyze = owner-private exact profile lists.
#>
[CmdletBinding()]
param(
 [ValidateSet('Probe','Analyze')][string]$Mode='Probe',
 [ValidateSet('.\VIDA','(local)\VIDA','localhost\VIDA','127.0.0.1\VIDA')]
 [string]$ServerInstance='.\VIDA',
 [string]$VidaRoot='E:\vida',
 [string]$ExactProfiles='E:\VirtualCar\VIDA-private\p0-exact-43-private.txt',
 [string]$GeneralProfiles='E:\VirtualCar\VIDA-private\p0-general-private.txt',
 [string]$Output='E:\VirtualCar\VIDA-private\p0-live-cem-001.json'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$required=[ordered]@{
 T161_Profile=@('id','identifier')
 T160_DefaultEcuVariant=@('fkT161_Profile','fkT100_EcuVariant')
 T100_EcuVariant=@('id','fkT101_Ecu')
 T101_Ecu=@('id','identifier')
 T120_Config_EcuVariant=@('fkT100_EcuVariant','fkT121_Config')
 T121_Config=@('id','fkT122_Protocol','busRate')
 T122_Protocol=@('id','identifier')
}
function Read-SqlTable($con,[string]$query,$value) {
 $cmd=$con.CreateCommand()
 try {
  $cmd.CommandText=$query
  $cmd.CommandTimeout=15
  if($PSBoundParameters.ContainsKey('value')) {
   $p=$cmd.Parameters.Add('@value',[System.Data.SqlDbType]::VarChar,128)
   if($null -eq $value){throw 'null SQL selector'}
   $p.Value=[string]$value
  }
  $table=New-Object System.Data.DataTable
  $adapter=New-Object System.Data.SqlClient.SqlDataAdapter -ArgumentList $cmd
  try {[void]$adapter.Fill($table)} finally {$adapter.Dispose()}
  return ,$table
 } finally {$cmd.Dispose()}
}
function Unique-Row($con,[string]$query,$value) {
 $t=Read-SqlTable $con $query $value
 if($t.Rows.Count -ne 1){throw 'ambiguous or absent CarCom link'}
 foreach($x in $t.Rows[0].ItemArray) {
  if($null -eq $x -or [System.Convert]::IsDBNull($x)){throw 'null CarCom link'}
 }
 return ,$t.Rows[0].ItemArray
}
function Read-ProfileLines([string]$path,[int]$low,[int]$high) {
 if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw 'missing private profile input'}
 $item=Get-Item -LiteralPath $path
 if($item.Length -le 0 -or $item.Length -gt 16384){throw 'invalid input size'}
 $encoding=[System.Text.UTF8Encoding]::new($false,$true)
 $lines=[System.IO.File]::ReadAllLines($item.FullName,$encoding)
 if($lines.Length -lt $low -or $lines.Length -gt $high){throw 'incorrect profile count'}
 $seen=@{}
 foreach($line in $lines){
  if($line.Length -lt 1 -or $line.Length -gt 128 -or $line -cne $line.Trim() -or
      $line -match '[\x00-\x1f\x7f]'){throw 'invalid private profile identifier'}
  $key=$line.ToUpperInvariant()
  if($seen.ContainsKey($key)){throw 'duplicate profile identifier'}
  $seen[$key]=$true
 }
 return ,$lines
}
function Get-Counts($con,[string[]]$names) {
 $r=[ordered]@{
  input_profiles=$names.Length; profiles_with_defaults=0; profiles_without_defaults=0
  direct_default_variant_rows=0; default_cem_variant_rows=0; default_other_ecu_rows=0
  cem_variants_without_config=0; cem_config_rows=0; cem_d2_config_rows=0
  cem_ggd_config_rows=0; cem_other_protocol_config_rows=0; cem_config_missing_bitrate_rows=0
 }
 foreach($name in $names){
  $profileDbId=Unique-Row $con 'SELECT TOP (2) [id] FROM [dbo].[T161_Profile] WHERE [identifier]=@value' $name
  $defaults=Read-SqlTable $con 'SELECT TOP (33) [fkT100_EcuVariant] FROM [dbo].[T160_DefaultEcuVariant] WHERE [fkT161_Profile]=@value' $profileDbId[0]
  if($defaults.Rows.Count -gt 32){throw 'unbounded default references'}
  if($defaults.Rows.Count -gt 0){$r.profiles_with_defaults++}
  else {$r.profiles_without_defaults++}
  $r.direct_default_variant_rows+=$defaults.Rows.Count
  foreach($d in $defaults.Rows){
   $vid=$d[0]
   if([System.Convert]::IsDBNull($vid)){throw 'null ECU variant'}
   $ecuFk=Unique-Row $con 'SELECT TOP (2) [fkT101_Ecu] FROM [dbo].[T100_EcuVariant] WHERE [id]=@value' $vid
   $ecuName=Unique-Row $con 'SELECT TOP (2) [identifier] FROM [dbo].[T101_Ecu] WHERE [id]=@value' $ecuFk[0]
   if(([string]$ecuName[0]).Trim().ToUpperInvariant() -ne 'CEM'){
    $r.default_other_ecu_rows++
    continue
   }
   $r.default_cem_variant_rows++
   $configs=Read-SqlTable $con 'SELECT TOP (33) [fkT121_Config] FROM [dbo].[T120_Config_EcuVariant] WHERE [fkT100_EcuVariant]=@value' $vid
   if($configs.Rows.Count -gt 32){throw 'unbounded CEM configs'}
   if($configs.Rows.Count -eq 0){$r.cem_variants_without_config++}
   foreach($cfg in $configs.Rows){
    if([System.Convert]::IsDBNull($cfg[0])){throw 'null CEM configuration'}
    $info=Read-SqlTable $con 'SELECT TOP (2) [fkT122_Protocol],[busRate] FROM [dbo].[T121_Config] WHERE [id]=@value' $cfg[0]
    if($info.Rows.Count -ne 1 -or [System.Convert]::IsDBNull($info.Rows[0][0])){
     throw 'ambiguous CEM configuration'
    }
    $proto=Unique-Row $con 'SELECT TOP (2) [identifier] FROM [dbo].[T122_Protocol] WHERE [id]=@value' $info.Rows[0][0]
    $r.cem_config_rows++
    if([System.Convert]::IsDBNull($info.Rows[0][1])){$r.cem_config_missing_bitrate_rows++}
    switch(([string]$proto[0]).Trim().ToUpperInvariant()){
     'D2' {$r.cem_d2_config_rows++}
     'GGD' {$r.cem_ggd_config_rows++}
     default {$r.cem_other_protocol_config_rows++}
    }
   }
  }
 }
 if($r.input_profiles -ne ($r.profiles_with_defaults+$r.profiles_without_defaults) -or
    $r.direct_default_variant_rows -ne ($r.default_cem_variant_rows+$r.default_other_ecu_rows) -or
    $r.cem_config_rows -ne ($r.cem_d2_config_rows+$r.cem_ggd_config_rows+$r.cem_other_protocol_config_rows)){
  throw 'inconsistent CarCom counts'
 }
 return $r
}
$con=$null
$phase='preflight'
try{
 if(-not(Test-Path -LiteralPath $VidaRoot -PathType Container)){throw 'VIDA installation root absent'}
 $phase='connection'
 Add-Type -AssemblyName System.Data
 $b=New-Object System.Data.SqlClient.SqlConnectionStringBuilder
 $b.DataSource=$ServerInstance
 $b.InitialCatalog='CarCom'
 $b.IntegratedSecurity=$true
 $b.ApplicationIntent=[System.Data.SqlClient.ApplicationIntent]::ReadOnly
 $b.ConnectTimeout=6
 $b.Encrypt=$false  # Local legacy named SQL Server instance only.
 $b.Pooling=$false
 $con=[System.Data.SqlClient.SqlConnection]::new($b.ConnectionString)
 $con.Open()
 $phase='database'
 $db=Read-SqlTable $con 'SELECT DB_NAME() AS [database_name]'
 if($db.Rows.Count -ne 1 -or ([string]$db.Rows[0][0]) -cne 'CarCom'){throw 'unexpected database'}
 $phase='schema'
 $schema=Read-SqlTable $con @'
SELECT t.[name] AS [table_name],c.[name] AS [column_name]
FROM [sys].[tables] AS t
JOIN [sys].[schemas] AS s ON s.[schema_id]=t.[schema_id]
JOIN [sys].[columns] AS c ON c.[object_id]=t.[object_id]
WHERE s.[name]=N'dbo' AND t.[name] IN
(N'T161_Profile',N'T160_DefaultEcuVariant',N'T100_EcuVariant',
 N'T101_Ecu',N'T120_Config_EcuVariant',N'T121_Config',N'T122_Protocol')
'@
 $present=@{}
 foreach($row in $schema.Rows){
  $t=[string]$row[0]
  if(-not $present.ContainsKey($t)){$present[$t]=@{}}
  $present[$t][[string]$row[1]]=$true
 }
 foreach($t in $required.Keys){
  if(-not $present.ContainsKey($t)){throw 'missing required CarCom table'}
  foreach($col in $required[$t]){
   if(-not $present[$t].ContainsKey($col)){throw 'missing required CarCom column'}
  }
 }
 if($Mode -eq 'Probe'){
  [pscustomobject]@{
   status='connected';source='installed_local_vida';database='CarCom'
   schema='seven_expected_tables_present';source_rows_read=$false
   live_readvin_verified=$false;read_only_sql=$true
  } | ConvertTo-Json -Compress
  return
 }
 $phase='private_input'
 $exact=Read-ProfileLines $ExactProfiles 43 43
 $general=Read-ProfileLines $GeneralProfiles 1 8
 $seen=@{}
 foreach($n in $exact){$seen[$n.ToUpperInvariant()]=$true}
 foreach($n in $general){
  if($seen.ContainsKey($n.ToUpperInvariant())){throw 'overlap of private profile sets'}
 }
 $out=[System.IO.Path]::GetFullPath($Output)
 $vida=[System.IO.Path]::GetFullPath($VidaRoot).TrimEnd('\')+'\'
 $repo=[System.IO.Path]::GetFullPath((Join-Path (Split-Path -Parent $PSCommandPath) '..\..')).TrimEnd('\')+'\'
 if($out.StartsWith($vida,[System.StringComparison]::OrdinalIgnoreCase) -or
    $out.StartsWith($repo,[System.StringComparison]::OrdinalIgnoreCase)){
  throw 'unsafe report output directory'
 }
 if($out -ieq [System.IO.Path]::GetFullPath($ExactProfiles) -or
    $out -ieq [System.IO.Path]::GetFullPath($GeneralProfiles)){
  throw 'source/output path collision'
 }
 $phase='aggregation'
 $a=Get-Counts $con $exact
 $g=Get-Counts $con $general
 $report=[ordered]@{
  schema_version='virtualcar-xc90-v8-installed-vida-carcom-v1'
  status='local_sqlserver_carcom_direct_profile_counts'
  source='installed_local_vida_carcom'
  vehicle_catalog_hint=[ordered]@{
   model='XC90';model_year=2009;engine='B8444S'
   generation='P2-Restyling';platform_family='P2'
  }
  live_carcom_schema_checked=$true
  select_only_queries=$true
  original_profile_selection_provenance_verified=$false
  source_sql_snapshot_consistent=$false
  original_vida_runtime_profile_selected=$false
  profile_parentage_or_effective_inithw_verified=$false
  cem_hardware_h_l_verified=$false
  d2_baudrate_from_null_inferred=$false
  client_ecu_alive_verified=$false
  original_vida_readvin_accepted=$false
  response_fixture_selection_approved=$false
  contains_owner_identifiers_vin_payloads_or_config_values=$false
  exact_xc90_v8_my2009=$a
  general_profile_comparators=$g
 }
 $phase='report'
 $json=ConvertTo-Json -InputObject $report -Depth 6
 $stream=[System.IO.File]::Open($out,[System.IO.FileMode]::CreateNew,
                               [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
 try{
  $data=([System.Text.UTF8Encoding]::new($false)).GetBytes($json+[Environment]::NewLine)
  $stream.Write($data,0,$data.Length)
 }finally{$stream.Dispose()}
 [pscustomobject]@{
  status='aggregate_report_saved';source='installed_local_vida'
  original_vida_modified=$false;runtime_profile_proven=$false
 } | ConvertTo-Json -Compress
}
catch{
 # Error output is intentionally bounded: no SQL, profile IDs, paths or payloads.
 $safeError=[pscustomobject]@{
  status='failed';phase=$phase;error_class=$_.Exception.GetType().Name
 } | ConvertTo-Json -Compress
 [Console]::Error.WriteLine($safeError)
 exit 2
}
finally{if($null -ne $con){$con.Dispose()}}
