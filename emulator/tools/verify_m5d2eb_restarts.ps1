# M5D-2eB owner-only Windows integration runner.
# Uses only synthetic C# --serve-once and C++ --three-epochs test executables.
# Never registers J2534, touches the car, publishes artifacts or copies identities.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$ServiceDll,
  [Parameter(Mandatory=$true)][string]$NativeX86,
  [Parameter(Mandatory=$true)][string]$NativeX64
)
$ErrorActionPreference = 'Stop'
foreach ($file in @($ServiceDll, $NativeX86, $NativeX64)) {
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
    throw ('M5D2eB required binary missing: ' + $file)
  }
}
$dotnet = (Get-Command dotnet -ErrorAction Stop).Source
if (-not (Test-Path -LiteralPath $env:RUNNER_TEMP -PathType Container)) {
  throw 'M5D2eB requires an isolated Windows runner temporary directory'
}
function Start-Child([string]$Exe, [string]$CommandLine) {
  $start = New-Object System.Diagnostics.ProcessStartInfo
  $start.FileName = $Exe
  $start.Arguments = $CommandLine
  $start.UseShellExecute = $false
  $start.CreateNoWindow = $true
  $child = New-Object System.Diagnostics.Process
  $child.StartInfo = $start
  if (-not $child.Start()) {
    $child.Dispose()
    throw 'M5D2eB owned child process failed to start'
  }
  return $child
}
function Stop-Child([System.Diagnostics.Process]$Child) {
  if ($null -eq $Child) { return }
  try {
    if (-not $Child.HasExited) {
      $Child.Kill() # Only exact retained Process object, not an arbitrary PID.
      if (-not $Child.WaitForExit(5000)) { throw 'M5D2eB owned process did not exit' }
    }
  } finally { $Child.Dispose() }
}
function Test-MarkerValue([string]$Path, [string]$Value) {
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
  # A writer may create the file before publishing its contents. On Windows
  # PowerShell 5.1 Get-Content -Raw can return null for an empty file.
  $content = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
  if ([string]::IsNullOrWhiteSpace($content)) { return $false }
  return ($content.Trim() -eq $Value)
}
function Assert-MarkerReadContract([string]$Work) {
  $path = Join-Path $Work 'marker-contract.tmp'
  try {
    Write-Host 'M5D2eB marker contract case 1/8'
    if (Test-MarkerValue -Path $path -Value 'accepted') {
      throw 'M5D2eB missing marker incorrectly accepted'
    }
    $cases = @(
      @{ Content = ''; Expected = 'accepted'; Match = $false },
      @{ Content = '   '; Expected = 'accepted'; Match = $false },
      @{ Content = 'accept'; Expected = 'accepted'; Match = $false },
      @{ Content = 'revoked'; Expected = 'accepted'; Match = $false },
      @{ Content = 'accepted'; Expected = 'accepted'; Match = $true },
      @{ Content = "revoked`r`n"; Expected = 'revoked'; Match = $true },
      @{ Content = 'verified'; Expected = 'verified'; Match = $true }
    )
    $caseIndex = 1
    foreach ($case in $cases) {
      $caseIndex++
      Write-Host ('M5D2eB marker contract case ' + $caseIndex + '/8')
      [System.IO.File]::WriteAllText($path, $case.Content, [System.Text.Encoding]::ASCII)
      if ((Test-MarkerValue -Path $path -Value $case.Expected) -ne $case.Match) {
        throw ('M5D2eB marker read contract mismatch: case ' + $caseIndex)
      }
    }
    Write-Host 'PASS: M5D2eB marker read contract 8/8'
  } finally {
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Force }
  }
}
function Wait-Marker([string]$Path, [string]$Value, [System.Diagnostics.Process]$Client) {
  $deadline = [DateTime]::UtcNow.AddSeconds(17)
  while ([DateTime]::UtcNow -lt $deadline) {
    if (Test-MarkerValue -Path $Path -Value $Value) { return }
    if ($Client.HasExited) {
      throw ('M5D2eB native client exited too early: ' + $Client.ExitCode)
    }
    Start-Sleep -Milliseconds 50
  }
  throw ('M5D2eB deadline waiting for marker: ' + $Value)
}
function Assert-Exit([System.Diagnostics.Process]$Child, [string]$Label) {
  if (-not $Child.WaitForExit(20000)) { throw ('M5D2eB timeout: ' + $Label) }
  if ($Child.ExitCode -ne 0) {
    throw ('M5D2eB ' + $Label + ' exit ' + $Child.ExitCode)
  }
}
foreach ($arch in @('x86','x64')) {
  $exe = if ($arch -eq 'x86') { $NativeX86 } else { $NativeX64 }
  $id = [guid]::NewGuid().ToString('N')
  $pipe = 'vcm5d2eb-' + $arch + '-' + $id
  $work = Join-Path $env:RUNNER_TEMP ('vcm5d2eb-' + $arch + '-' + $id)
  if (Test-Path -LiteralPath $work) { throw 'M5D2eB refuses stale marker directory' }
  [void][System.IO.Directory]::CreateDirectory($work)
  $hostChild = $null
  $client = $null
  try {
    Write-Host ('M5D2eB starting architecture ' + $arch)
    Assert-MarkerReadContract -Work $work
    $marker = Join-Path $work 'round-0.ready'
    $hostArgs = ('"{0}" --serve-once "{1}" read-held "{2}"' -f $ServiceDll,$pipe,$marker)
    $hostChild = Start-Child -Exe $dotnet -CommandLine $hostArgs
    $clientArgs = ('--three-epochs "{0}" {1} "{2}"' -f $pipe,$hostChild.Id,$work)
    $client = Start-Child -Exe $exe -CommandLine $clientArgs

    for ($round = 0; $round -lt 3; $round++) {
      $marker = Join-Path $work ('round-' + $round + '.ready')
      $revoked = Join-Path $work ('round-' + $round + '.revoked')
      Wait-Marker -Path $marker -Value 'accepted' -Client $client
      if ($round -ne 1) {
        # Two intentional Host crashes while an already accepted read is held.
        $hostChild.Kill()
        if (-not $hostChild.WaitForExit(5000)) {
          throw ('M5D2eB synthetic Host crash did not complete: ' + $round)
        }
      }
      Wait-Marker -Path $revoked -Value 'revoked' -Client $client
      if ($round -eq 1) {
        # Cancellation is performed by the native client, not by killing Host.
        Assert-Exit -Child $hostChild -Label 'cooperatively canceled Host'
      }
      Stop-Child -Child $hostChild
      $hostChild = $null

      $next = $round + 1
      if ($next -lt 3) {
        $nextReady = Join-Path $work ('round-' + $next + '.ready')
        $nextHostArgs = ('"{0}" --serve-once "{1}" read-held "{2}"' -f $ServiceDll,$pipe,$nextReady)
      } else {
        $nextHostArgs = ('"{0}" --serve-once "{1}" read-session' -f $ServiceDll,$pipe)
      }
      $hostChild = Start-Child -Exe $dotnet -CommandLine $nextHostArgs
      $nextPid = Join-Path $work ('round-' + $next + '.pid')
      [System.IO.File]::WriteAllText($nextPid,[string]$hostChild.Id,[System.Text.Encoding]::ASCII)
    }

    Assert-Exit -Child $client -Label ($arch + ' 3-epoch client')
    $verified = Join-Path $work 'round-3.verified'
    if (-not (Test-MarkerValue -Path $verified -Value 'verified')) {
      throw ('M5D2eB ' + $arch + ' final recovery marker missing')
    }
    Assert-Exit -Child $hostChild -Label ($arch + ' final clean Host')
    Write-Host ('PASS: M5D2eB ' + $arch + ' accepted Host crash/cancel/crash and clean fourth Host')
  } catch {
    Write-Host ('M5D2eB FAILURE architecture=' + $arch + ' error=' + $_.FullyQualifiedErrorId)
    Write-Host $_.InvocationInfo.PositionMessage
    Write-Host $_.ScriptStackTrace
    throw
  } finally {
    Stop-Child -Child $client
    Stop-Child -Child $hostChild
    if (Test-Path -LiteralPath $work) {
      Remove-Item -LiteralPath $work -Recurse -Force
    }
  }
}
