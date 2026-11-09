#requires -Version 5.1
<#
.SYNOPSIS
  Exports exactly ONE private ReadVin ZIP from an authorized LOCAL VIDA SQL database.
.DESCRIPTION
  SELECT-only. No script is executed, no CAN/J2534 operations, no credentials
  or raw bytes written to Git. Requires an already installed trusted SqlServer
  module. Use only on an owner-controlled VIDA installation.
  The output is a PRIVATE ORIGINAL SCRIPT ARCHIVE; NEVER UPLOAD IT.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$ServerInstance,
    [Parameter(Mandatory=$true)][ValidateNotNullOrEmpty()][string]$OutputZip,
    [ValidateRange(0, 255)][int]$LanguageId = 15,
    [System.Management.Automation.PSCredential]$Credential,
    [switch]$TrustServerCertificate
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$maxArchive = 1048576
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$dest = [System.IO.Path]::GetFullPath($OutputZip)
$prefix = $root.TrimEnd([System.IO.Path]::DirectorySeparatorChar) +
    [System.IO.Path]::DirectorySeparatorChar
if ($dest.Equals($root, [System.StringComparison]::OrdinalIgnoreCase) -or
    $dest.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing original script export into Git repository.'
}
if (-not $dest.EndsWith('.zip', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Output must have .zip extension.'
}
if (Test-Path -LiteralPath $dest) { throw 'Refusing to overwrite existing original script.' }
$parent = Split-Path -Parent $dest
if (-not (Test-Path -LiteralPath $parent -PathType Container)) {
    throw 'Output parent directory must exist.'
}
# Do not follow a linked output parent into another location.
if (([System.IO.File]::GetAttributes($parent) -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
    throw 'Linked output folder is not supported.'
}
$cmd = Get-Command Invoke-Sqlcmd -ErrorAction SilentlyContinue
if (-not $cmd) { throw 'Trusted SqlServer Invoke-Sqlcmd module is not installed.' }
if ($TrustServerCertificate -and -not $cmd.Parameters.ContainsKey('TrustServerCertificate')) {
    throw 'SqlServer module does not support the explicitly requested TLS flag.'
}
# CLR enum ReadVin=4 and SQL ScriptType.Id=7 are DIFFERENT namespaces.
# A second description check helps detect version drift.
$languageLiteral = [string]$LanguageId
$where = "st.id = 7 AND st.Description = N'ReadVin' AND sc.fkLanguage = $languageLiteral"
$joins = @'
FROM dbo.Script AS s
JOIN dbo.ScriptType AS st ON st.id = s.fkScriptType
JOIN dbo.ScriptContent AS sc ON sc.fkScript = s.id
'@
$metaQuery = "SELECT COUNT_BIG(*) AS CandidateCount, MAX(DATALENGTH(sc.XmlDataCompressed)) AS ArchiveLength $joins WHERE $where;"
$dataQuery = "SELECT sc.XmlDataCompressed AS ArchiveBytes $joins WHERE $where;"
$params = @{
    ServerInstance = $ServerInstance
    Database = 'DiagSwdlRepository'
    QueryTimeout = 30
    MaxBinaryLength = $maxArchive
    ErrorAction = 'Stop'
}
if ($null -ne $Credential) { $params.Credential = $Credential }
if ($TrustServerCertificate) { $params.TrustServerCertificate = $true }
$metadata = @(Invoke-Sqlcmd @params -Query $metaQuery)
if ($metadata.Count -ne 1) { throw 'Expected one SQL summary row.' }
$count = [long]$metadata[0].CandidateCount
$length = [long]$metadata[0].ArchiveLength
if ($count -ne 1 -or $length -lt 30 -or $length -gt $maxArchive) {
    throw 'Expected exactly one bounded ReadVin archive for this local language.'
}
$rows = @(Invoke-Sqlcmd @params -Query $dataQuery)
if ($rows.Count -ne 1) { throw 'Ambiguous or missing ReadVin archive.' }
$bytes = $rows[0].ArchiveBytes
if ($bytes -is [System.Data.SqlTypes.SqlBinary]) { $bytes = $bytes.Value }
if ($bytes -isnot [byte[]] -or $bytes.Length -ne $length) {
    throw 'Archive truncated or database row changed; nothing written.'
}
if ($bytes.Length -lt 30 -or $bytes[0] -ne 0x50 -or $bytes[1] -ne 0x4B -or
    $bytes[2] -ne 0x03 -or $bytes[3] -ne 0x04) {
    throw 'Unexpected ZIP signature; nothing written.'
}
$stream = [System.IO.File]::Open($dest, [System.IO.FileMode]::CreateNew,
    [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
Write-Host 'ONE PRIVATE ReadVin ZIP created; no raw contents printed. DO NOT UPLOAD IT.'
Write-Host 'This does not prove the script is selected by VIDA at runtime or that VIN works.'
