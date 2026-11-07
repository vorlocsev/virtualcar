#requires -Version 5.1
<#
.SYNOPSIS
    Inspects only SQL catalog metadata for VIDA 2015A GetScript.
.DESCRIPTION
    Does not execute the GetScript procedure, read table rows, recover scripts,
    extract VIN, run VIDA, contact DiCE or change database settings.
    A procedure or table not visible to this account is NOT proven absent.
    One redacted JSON output is written with CreateNew, outside the Git repo.
    Requires a pre-installed trusted SqlServer module (Invoke-Sqlcmd).
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$ServerInstance,
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$OutputFile,
    [System.Management.Automation.PSCredential]$Credential
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$output = [System.IO.Path]::GetFullPath($OutputFile)
$prefix = $repositoryRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if ($output.Equals($repositoryRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $output.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing to write private lab metadata inside the Git repository.'
}
if (Test-Path -LiteralPath $output) {
    throw 'Output already exists; never overwrite an existing report.'
}
if (-not (Test-Path -LiteralPath (Split-Path -Parent $output) -PathType Container)) {
    throw 'Output parent directory must already exist.'
}
if (-not (Get-Command Invoke-Sqlcmd -ErrorAction SilentlyContinue)) {
    throw 'Invoke-Sqlcmd is not installed. Install a trusted SqlServer module separately.'
}

# Only Microsoft SQL Server *catalog views*. No script/table content is read.
# Schema is deliberately fixed to dbo. Invisible means absent OR not permitted.
$query = @'
SELECT
  (SELECT COUNT(*) FROM sys.procedures p JOIN sys.schemas s ON s.schema_id=p.schema_id
   WHERE s.name=N'dbo' AND p.name=N'GetScript') AS ProcedureVisibleCount,
  (SELECT COUNT(*) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P')) AS ParameterVisibleCount,
  (SELECT COUNT(*) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@scriptType') AS ScriptTypePresent,
  (SELECT COUNT(*) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@profileList') AS ProfileListPresent,
  (SELECT COUNT(*) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@scriptId') AS ScriptIdPresent,
  (SELECT COUNT(*) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@languageCode') AS LanguageCodePresent,
  (SELECT COUNT(*) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@ecuType') AS EcuTypePresent,
  (SELECT MAX(TYPE_NAME(p.user_type_id)) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@scriptType') AS ScriptTypeSqlType,
  (SELECT MAX(TYPE_NAME(p.user_type_id)) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@profileList') AS ProfileListSqlType,
  (SELECT MAX(TYPE_NAME(p.user_type_id)) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@scriptId') AS ScriptIdSqlType,
  (SELECT MAX(TYPE_NAME(p.user_type_id)) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@languageCode') AS LanguageCodeSqlType,
  (SELECT MAX(TYPE_NAME(p.user_type_id)) FROM sys.parameters p
   WHERE p.object_id=OBJECT_ID(N'dbo.GetScript',N'P') AND p.name=N'@ecuType') AS EcuTypeSqlType,
  (SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
   WHERE s.name=N'dbo' AND t.name=N'Script') AS ScriptTableVisibleCount,
  (SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
   WHERE s.name=N'dbo' AND t.name=N'ScriptType') AS ScriptTypeTableVisibleCount,
  (SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
   WHERE s.name=N'dbo' AND t.name=N'ScriptProfileMap') AS ProfileMapTableVisibleCount,
  (SELECT COUNT(*) FROM sys.tables t JOIN sys.schemas s ON s.schema_id=t.schema_id
   WHERE s.name=N'dbo' AND t.name=N'ScriptContent') AS ScriptContentTableVisibleCount;
'@
$params = @{
    ServerInstance = $ServerInstance
    Database = 'DiagSwdlRepository'
    Query = $query
    QueryTimeout = 30
    ErrorAction = 'Stop'
}
if ($null -ne $Credential) { $params.Credential = $Credential }
$rows = @(Invoke-Sqlcmd @params)
if ($rows.Count -ne 1) { throw 'Expected exactly one SQL catalog row.' }
$row = $rows[0]

function ReadCount([string]$name) {
    $value = $row.$name
    if ($null -eq $value -or $value -is [bool]) { throw 'Invalid catalog counter.' }
    $number = [long]$value
    if ($number -lt 0 -or $number -gt 256) { throw 'Unexpected catalog counter.' }
    return [int]$number
}
function Visible([string]$name) {
    $count = ReadCount $name
    if ($count -gt 1) { throw 'Unexpected duplicate catalog object.' }
    return ($count -eq 1)
}
function SqlTypeCategory([string]$name) {
    $raw = $row.$name
    if ($null -eq $raw -or ([string]$raw).Length -eq 0) { return 'unavailable' }
    if ($raw -isnot [string]) { throw 'Unexpected SQL type metadata.' }
    switch -Regex ($raw.ToLowerInvariant()) {
        '^(char|nchar|varchar|nvarchar|text|ntext)$' { return 'text' }
        '^(tinyint|smallint|int|bigint)$' { return 'integer' }
        '^bit$' { return 'boolean' }
        '^uniqueidentifier$' { return 'identifier' }
        '^xml$' { return 'xml' }
        default { return 'other' }
    }
}
$procedureVisible = Visible 'ProcedureVisibleCount'
$parameterCount = ReadCount 'ParameterVisibleCount'
$presence = [ordered]@{
    scriptType = (Visible 'ScriptTypePresent')
    profileList = (Visible 'ProfileListPresent')
    scriptId = (Visible 'ScriptIdPresent')
    languageCode = (Visible 'LanguageCodePresent')
    ecuType = (Visible 'EcuTypePresent')
}
$knownCount = @($presence.Values | Where-Object { $_ }).Count
if ($parameterCount -lt $knownCount) { throw 'Contradictory SQL catalog parameter counts.' }
$types = [ordered]@{
    scriptType = (SqlTypeCategory 'ScriptTypeSqlType')
    profileList = (SqlTypeCategory 'ProfileListSqlType')
    scriptId = (SqlTypeCategory 'ScriptIdSqlType')
    languageCode = (SqlTypeCategory 'LanguageCodeSqlType')
    ecuType = (SqlTypeCategory 'EcuTypeSqlType')
}
$tables = [ordered]@{
    Script = (Visible 'ScriptTableVisibleCount')
    ScriptType = (Visible 'ScriptTypeTableVisibleCount')
    ScriptProfileMap = (Visible 'ProfileMapTableVisibleCount')
    ScriptContent = (Visible 'ScriptContentTableVisibleCount')
}
$report = [ordered]@{
    schema_version = 'virtualcar-vida-getscript-catalog-v1'
    read_only = $true
    source = 'local_authorized_sql_catalog_metadata_only'
    procedure_visibility = $(if ($procedureVisible) { 'visible_dbo_GetScript' } else { 'not_visible_or_absent' })
    visible_parameter_count = $parameterCount
    expected_parameter_presence = $presence
    expected_parameter_type_categories = $types
    other_visible_parameter_count = ($parameterCount - $knownCount)
    table_metadata_visibility = $tables
    no_stored_procedure_executed = $true
    no_table_rows_read = $true
    contains_script_or_vehicle_data = $false
    runtime_readvin_script_selected = 'unknown'
    b9fb_to_vin_mapping = 'unknown'
    xc90_v8_my2009_identity_accepted = 'unknown'
    replay_approved = $false
    note = 'Catalog visibility depends on SQL permissions; absence from this report does not prove database objects missing.'
}
$json = ConvertTo-Json -InputObject $report -Depth 6
$utf8 = New-Object System.Text.UTF8Encoding($false)
$bytes = $utf8.GetBytes($json + [Environment]::NewLine)
$stream = [System.IO.File]::Open($output, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
Write-Host 'VIDA GetScript catalog-only audit done; runtime ReadVin/vehicle acceptance UNKNOWN.'
