#requires -Version 5.1
<#
.SYNOPSIS
    Exports minimal Script/ScriptProfileMap/ScriptContent metadata from an
    authorized LOCAL VIDA SQL Server installation. No script/XML/VIN payloads.
.DESCRIPTION
    SELECT-only. No SQL modification, no credentials on disk, no uploads.
    Destination MUST be outside the repository and MUST NOT already exist.
    SqlServer module and database SELECT permissions are required.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$ServerInstance,
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$OutputDirectory,
    [System.Management.Automation.PSCredential]$Credential
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$repositoryRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$destination = [System.IO.Path]::GetFullPath($OutputDirectory)
if ($destination.Equals($repositoryRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $destination.StartsWith(
        $repositoryRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
        [System.IO.Path]::DirectorySeparatorChar,
        [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Private SQL metadata must not be written inside the Git repository.'
}
if (Test-Path -LiteralPath $destination) {
    throw 'The output directory already exists. Choose a new private directory.'
}
if (-not (Get-Command Invoke-Sqlcmd -ErrorAction SilentlyContinue)) {
    throw 'Invoke-Sqlcmd not available. Install the trusted SqlServer module separately, or perform SELECT-only export manually.'
}
$queries = @(
    @{
        File = 'Script.csv'
        Columns = @('id')
        SQL = 'SELECT CONVERT(nvarchar(80), id) AS id FROM [DiagSwdlRepository].[dbo].[Script]'
    },
    @{
        File = 'ScriptProfileMap.csv'
        Columns = @('fkProfile', 'fkScript')
        SQL = 'SELECT CONVERT(nvarchar(80), fkProfile) AS fkProfile, CONVERT(nvarchar(80), fkScript) AS fkScript FROM [DiagSwdlRepository].[dbo].[ScriptProfileMap]'
    },
    @{
        File = 'ScriptContent.csv'
        Columns = @('fkScript', 'fkLanguage')
        SQL = 'SELECT CONVERT(nvarchar(80), fkScript) AS fkScript, CONVERT(nvarchar(80), fkLanguage) AS fkLanguage FROM [DiagSwdlRepository].[dbo].[ScriptContent]'
    }
)
$null = New-Item -ItemType Directory -Path $destination -ErrorAction Stop
foreach ($q in $queries) {
    $params = @{
        ServerInstance = $ServerInstance
        Database = 'DiagSwdlRepository'
        Query = $q.SQL
        QueryTimeout = 45
        ErrorAction = 'Stop'
    }
    if ($null -ne $Credential) {
        $params.Credential = $Credential
    }
    $rows = @(Invoke-Sqlcmd @params)
    $path = Join-Path $destination $q.File
    if ($rows.Count -eq 0) {
        $quoted = @($q.Columns | ForEach-Object { '"' + $_ + '"' })
        [System.IO.File]::WriteAllText($path, ($quoted -join ',') + [Environment]::NewLine,
            (New-Object System.Text.UTF8Encoding($false)))
    } else {
        $rows | Select-Object -Property $q.Columns |
            Export-Csv -LiteralPath $path -Encoding UTF8 -NoTypeInformation
    }
    Write-Host ('Exported metadata-only rows for {0}: {1}' -f $q.File, $rows.Count)
}
Write-Host 'Private local export done. Do NOT upload the source CSV files or any VIDA database.'
