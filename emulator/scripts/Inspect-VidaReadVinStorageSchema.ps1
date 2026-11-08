#requires -Version 5.1
<#
.SYNOPSIS
  Inspects the installed VIDA DiagSwdlRepository catalog layout, read-only.
.DESCRIPTION
  Catalog views ONLY: sys.tables, sys.schemas, sys.columns, sys.types.
  Does not read any Script/ScriptContent rows, invoke GetScript, decrypt,
  decompress XML, execute VIDA or J2534, or modify SQL configuration.
  Writes one private, bounded JSON outside the Git repository (CreateNew).
  SQL permissions can hide objects. No column data or schema names are exported.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$ServerInstance,
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$OutputFile,
    [System.Management.Automation.PSCredential]$Credential
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$output = [System.IO.Path]::GetFullPath($OutputFile)
$prefix = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
if ($output.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or
    $output.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing private metadata output inside the Git repository.'
}
if (Test-Path -LiteralPath $output) { throw 'Output already exists; refusing overwrite.' }
if (-not (Test-Path -LiteralPath (Split-Path -Parent $output) -PathType Container)) {
    throw 'Output parent folder must already exist.'
}
if (-not (Get-Command Invoke-Sqlcmd -ErrorAction SilentlyContinue)) {
    throw 'Invoke-Sqlcmd is not installed; trusted SqlServer module is required.'
}

# Fixed SQL with no caller-supplied identifiers and no Script/ScriptContent row reads.
# Actual table and column names may differ from code assumptions.
$query = @'
SELECT t.name AS TableName, s.name AS SchemaName,
       c.name AS ColumnName, ty.name AS SqlType,
       c.max_length AS MaxLength, c.is_nullable AS IsNullable
FROM sys.tables t
JOIN sys.schemas s ON s.schema_id=t.schema_id
JOIN sys.columns c ON c.object_id=t.object_id
JOIN sys.types ty ON ty.user_type_id=c.user_type_id
WHERE t.name IN (N'Script', N'ScriptType', N'ScriptProfileMap',
                 N'ScriptContent', N'ScriptCarFunction')
ORDER BY t.name, s.name, c.column_id;
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
if ($rows.Count -gt 256) { throw 'Unexpectedly many catalog columns.' }

function TypeClass([string]$name) {
    switch -Regex ($name.ToLowerInvariant()) {
        '^(char|nchar|varchar|nvarchar|text|ntext)$' { return 'text' }
        '^(binary|varbinary|image|timestamp|rowversion)$' { return 'binary' }
        '^(tinyint|smallint|int|bigint)$' { return 'integer' }
        '^(decimal|numeric|float|real|money|smallmoney)$' { return 'numeric' }
        '^(date|datetime|datetime2|datetimeoffset|smalldatetime|time)$' { return 'datetime' }
        '^bit$' { return 'boolean' }
        '^uniqueidentifier$' { return 'identifier' }
        '^xml$' { return 'xml' }
        default { return 'other' }
    }
}
$expected = @('Script', 'ScriptType', 'ScriptProfileMap', 'ScriptContent', 'ScriptCarFunction')
$groups = [ordered]@{}
foreach ($name in $expected) {
    $groups[$name] = [ordered]@{
        visibility = 'not_visible_or_absent'
        visible_dbo_table = $false
        visible_non_dbo_table = $false
        columns = @()
    }
}
foreach ($r in $rows) {
    $table = [string]$r.TableName
    if ($expected -cnotcontains $table) { throw 'Unexpected table name from SQL catalog.' }
    $column = [string]$r.ColumnName
    if ($column.Length -gt 80 -or $column -cnotmatch '^[A-Za-z_][A-Za-z0-9_]{0,79}$') {
        throw 'Unexpected column metadata; report not created.'
    }
    $schema = [string]$r.SchemaName
    $type = [string]$r.SqlType
    if ($type.Length -gt 128 -or $type.Length -eq 0) {
        throw 'Unexpected type metadata; report not created.'
    }
    $length = [int]$r.MaxLength
    if ($length -lt -1 -or $length -gt 32767) {
        throw 'Unexpected SQL column length metadata.'
    }
    $isNullable = [int]$r.IsNullable
    if ($isNullable -notin @(0, 1)) { throw 'Invalid SQL nullable metadata.' }
    $entry = $groups[$table]
    $entry.visibility = 'at_least_one_visible_table'
    if ($schema -ceq 'dbo') { $entry.visible_dbo_table = $true }
    else { $entry.visible_non_dbo_table = $true }
    $entry.columns += [ordered]@{
        name = $column
        type_category = (TypeClass $type)
        max_length_bytes = $length
        nullable = ($isNullable -eq 1)
    }
    if ($entry.columns.Count -gt 64) { throw 'Unexpected column count per table.' }
}
$report = [ordered]@{
    schema_version = 'virtualcar-vida-readvin-storage-catalog-v1'
    source = 'owner_local_SQL_catalog_only'
    read_only = $true
    contains_table_rows = $false
    contains_xml = $false
    contains_vin_or_can = $false
    contains_sql_credentials = $false
    contains_source_paths = $false
    schema_names_redacted = $true
    catalog_metadata_visibility_permission_dependent = $true
    catalog_tables = $groups
    sql_getscript_executed = $false
    selected_readvin_script_proven = $false
    b9fb_to_vin_mapping_verified = $false
    xc90_v8_my2009_identity_accepted = $false
    replay_approved = $false
    note = 'Visible catalog columns only. Absence may reflect SQL permissions. ' +
           'No script row, compressed XML or effective GetScript selection is established.'
}
$json = ConvertTo-Json -InputObject $report -Depth 9
$bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes($json + [Environment]::NewLine)
$stream = [System.IO.File]::Open($output, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
Write-Host 'VIDA storage catalog metadata summarized. Actual ReadVin XML remains unverified.'
