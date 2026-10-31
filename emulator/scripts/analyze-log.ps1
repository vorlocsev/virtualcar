# Read-only diagnostic summary. Runs in Windows PowerShell 5.1 without administrator rights.
param([string]$Path = (Join-Path $env:TEMP 'SectorVVirtualCar.log'), [int]$Tail = 50)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $Path)) { Write-Error ('Log not found: ' + $Path); exit 1 }
$allLines = @(Get-Content -LiteralPath $Path)
$lines = @($allLines)
for ($i=0; $i -lt $allLines.Count; $i++) {
  if ($allLines[$i] -like '=== SECTORV VIRTUALCAR SESSION *') {
    $lines = @($allLines | Select-Object -Skip ($i + 1))
  }
}
Write-Host ('SectorV Virtual Car | log lines: {0}' -f $lines.Count) -ForegroundColor Cyan
Write-Host ('File: {0}' -f $Path)
Write-Host 'Notes: RX delivered to J2534 caller does NOT prove that SectorV accepted the vehicle.'
$processIdCounts = @{}
$labels = @{}
foreach ($line in $lines) {
  if ($line -match '^\[PID=([0-9A-F]{8}) ([^\]]+)\]') {
    $processId = $Matches[1];$hostName = $Matches[2]
  } else { $processId = 'legacy';$hostName = 'Unknown (older log)' }
  if (-not $processIdCounts.ContainsKey($processId)) { $processIdCounts[$processId] = 0; $labels[$processId] = $hostName }
  $processIdCounts[$processId]++
}
Write-Host "`nEntries grouped by process:"
foreach ($processId in @($processIdCounts.Keys | Sort-Object)) {
  Write-Host ('  {0} {1}: {2} lines' -f $processId, $labels[$processId], $processIdCounts[$processId])
}
$sectorLines = @($lines | Where-Object { $_ -match '^\[PID=[0-9A-F]{8} SectorV\.exe\]' })
# Without an explicit session marker, older versions and prior process IDs
# must not be mixed with the latest SectorV run.
$hasSessionMarker = @($allLines | Where-Object { $_ -like '=== SECTORV VIRTUALCAR SESSION *' }).Count -gt 0
if (-not $hasSessionMarker -and $sectorLines.Count -gt 0) {
  $lastLine = [string]$sectorLines[$sectorLines.Count - 1]
  if ($lastLine -match '^\[PID=([0-9A-F]{8}) SectorV\.exe\]') {
    $latestProcessId = $Matches[1]
    $sectorLines = @($sectorLines | Where-Object { $_ -match ('^\[PID=' + $latestProcessId + ' SectorV\.exe\]') })
    Write-Host ('No session marker; latest SectorV process PID: {0}' -f $latestProcessId)
  }
}
Write-Host ("`nSectorV.exe lines: {0} (legacy lines excluded from counts)" -f $sectorLines.Count)
Write-Host "`nProbe summary (SectorV.exe only):"
$probes = [ordered]@{
 'P3 VIN F114 requested' = 'TX \(app request\).*00 00 07 26 03 22 F1 14'
 'P3 VIN F114 generated' = 'P3 CEM F114 VIN reply'
 'P3 F1B0 requested' = 'TX \(app request\).*00 00 07 26 03 22 F1 B0'
 'P3 F1B0 lab response generated' = 'P3 CEM F1B0 configured lab fixture'
 'P3 F1A3 requested' = 'TX \(app request\).*00 00 07 26 03 22 F1 A3'
 'P3 F1A3 lab response generated' = 'P3 CEM F1A3 configured lab fixture'
 'Functional ECUReset 11 81 requested' = 'TX \(app request\).*00 00 07 DF 02 11 81'
 'P2 D2 read replay staged' = 'P2 D2 read-only recorded frames staged'
 'P2 D2 read missing fixture' = 'P2 D2 read command: no validated response fixture'
 'P2 D2 0x01200003 received' = 'PassThruReadMsgs -> delivered 01 20 00 03'
 'F1B0 unavailable in SectorV' = 'P3 CEM F1B0 unavailable'
 'F1A3 unavailable in SectorV' = 'P3 CEM F1A3 unavailable'
 'D2 FF C8 without fixture' = 'D2 FF C8 discovery probe: no verified'
}
foreach ($label in $probes.Keys) {
  $count = @($sectorLines | Where-Object { $_ -match $probes[$label] }).Count
  Write-Host ('  {0}: {1}' -f $label, $count)
}
Write-Host ("`nLast {0} relevant events:" -f $Tail)
$pattern = 'PassThruOpen|PassThruClose|PassThruConnect|PassThruDisconnect|TX \(app request\)|P3 CEM|D2 .*fixture|P2 D2|Functional ECUReset|ISO-TP FC|ISO-TP FlowControl|PassThruReadMsgs -> delivered'
@($sectorLines | Where-Object { $_ -match $pattern } | Select-Object -Last $Tail) | ForEach-Object { Write-Host $_ }
