# B3A325: real Win32 multi-process append regression for the built x86 emulator.
# Synthetic, isolated, no physical J2534, no SectorV/VIDA and no private logs.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$DllPath,
  [ValidateRange(2,6)][int]$Workers=4,
  [ValidateRange(4,64)][int]$Iterations=16,
  [switch]$Child,
  [ValidateRange(0,5)][int]$ChildIndex=0,
  [string]$Scratch=''
)
$ErrorActionPreference='Stop'

function Invoke-Child {
  if ([IntPtr]::Size -ne 4 -or -not $Scratch) { throw 'invalid_x86_child' }
  $root=[IO.Path]::GetFullPath($Scratch)
  $dll=[IO.Path]::GetFullPath($DllPath)
  if (-not $dll.StartsWith($root.TrimEnd('\')+'\',
                          [StringComparison]::OrdinalIgnoreCase)) {
    throw 'dll_outside_disposable_lab'
  }
  $env:TEMP=$root; $env:TMP=$root; $env:LOCALAPPDATA=$root
  $cs=@'
using System;
using System.Runtime.InteropServices;
public static class SyntheticAppendWorker {
  [DllImport(@"__DLL__",CallingConvention=CallingConvention.StdCall,ExactSpelling=true)]
  static extern uint PassThruOpen(IntPtr ignored,out uint device);
  [DllImport(@"__DLL__",CallingConvention=CallingConvention.StdCall,ExactSpelling=true)]
  static extern uint PassThruClose(uint device);
  public static void Run(int loops) {
    for(int i=0;i<loops;i++) {
      uint device;
      if(PassThruOpen(IntPtr.Zero,out device)!=0 || device!=1)
        throw new InvalidOperationException("open_failed");
      if(PassThruClose(device)!=0)
        throw new InvalidOperationException("close_failed");
    }
  }
}
'@
  try {
    Add-Type -TypeDefinition ($cs.Replace('__DLL__',$dll.Replace('"','""'))) -Language CSharp
  } catch {
    throw 'child_csharp_compile_failed'
  }
  [IO.File]::WriteAllText((Join-Path $root ('ready-'+$ChildIndex)),'ready')
  $start=Join-Path $root 'start'
  $until=[DateTime]::UtcNow.AddSeconds(90)
  while (-not [IO.File]::Exists($start)) {
    if ([DateTime]::UtcNow -ge $until) { throw 'gate_timeout' }
    Start-Sleep -Milliseconds 30
  }
  try {
    [SyntheticAppendWorker]::Run($Iterations)
  } catch {
    throw 'child_native_open_close_failed'
  }
}

function Assert-Results([string]$Root,[int]$WorkerCount,[int]$LoopCount) {
  $file=Join-Path $Root 'SectorVVirtualCar.log'
  if (-not [IO.File]::Exists($file)) { throw 'no_native_log' }
  $bytes=[IO.File]::ReadAllBytes($file)
  if ($bytes.Length -lt 60 -or $bytes.Length -gt 8MB) { throw 'log_length' }
  $text=[Text.Encoding]::ASCII.GetString($bytes)
  $crlf=[string][char]13+[char]10
  if (-not $text.EndsWith($crlf) -or $text.Contains([string][char]0)) {
    throw 'incomplete_or_binary_log'
  }
  $rows=[regex]::Split($text,'\r\n')
  if ($rows.Count -lt 2 -or $rows[$rows.Count-1] -cne '') {
    throw 'invalid_crlf_records'
  }
  $sessions=@{}; $opens=0; $closes=0
  foreach($line in $rows[0..($rows.Count-2)]) {
    if (-not $line -or $line.IndexOf('[PID=',5) -ge 0) {
      throw 'split_or_concatenated_record'
    }
    $m=[regex]::Match($line,'^\[PID=([0-9A-F]{8}) ([^\]\r\n]{1,64})\] (.+)$')
    if (-not $m.Success) { throw 'bad_native_prefix' }
    $pid=$m.Groups[1].Value
    $event=$m.Groups[3].Value
    if (-not $sessions.ContainsKey($pid)) {
      $sessions[$pid]=@{Open=0;Close=0;Balance=0}
    }
    $item=$sessions[$pid]
    if ($event -ceq 'PassThruOpen -> device 1') {
      if ($item.Balance -ne 0) { throw 'open_order' }
      $item.Open++; $item.Balance++; $opens++
    } elseif ($event -ceq 'PassThruClose') {
      if ($item.Balance -ne 1) { throw 'close_order' }
      $item.Close++; $item.Balance--; $closes++
    } elseif ($event.StartsWith('TX (app request)') -or
              $event.StartsWith('P2 D2 delivered')) {
      throw 'unexpected_transport_activity'
    }
  }
  $expected=$WorkerCount*$LoopCount
  if ($sessions.Count -ne $WorkerCount -or $opens -ne $expected -or
      $closes -ne $expected) { throw 'lost_or_duplicated_log_records' }
  foreach($pid in $sessions.Keys) {
    $s=$sessions[$pid]
    if ($s.Open -ne $LoopCount -or $s.Close -ne $LoopCount -or
        $s.Balance -ne 0) { throw 'per_process_log_sequence' }
  }
  Write-Host ('PASS B3A325: {0} native x86 processes, {1} Open/Close pairs, {2} complete CRLF rows' -f
              $WorkerCount,$expected,($rows.Count-1))
  Write-Host 'Synthetic shared Win32 logger only; no real client, CAN device or VIN acceptance.'
}

# Exact, closed error vocabulary: no local files, DLL paths, PIDs, or
# PowerShell exception details may appear in either CI or child status.
function Get-BoundedFailure([string]$Reason) {
  $allowed=@(
    'invalid_x86_child','dll_outside_disposable_lab','gate_timeout',
    'child_csharp_compile_failed','child_native_open_close_failed',
    'no_native_log','log_length','incomplete_or_binary_log',
    'invalid_crlf_records','split_or_concatenated_record',
    'bad_native_prefix','open_order','close_order',
    'unexpected_transport_activity','lost_or_duplicated_log_records',
    'per_process_log_sequence','runner_temp_missing',
    'built_x86_dll_missing','isolated_dll_bytes_mismatch',
    'x86_powershell_missing','worker_spawn_failure',
    'worker_ended_before_gate','worker_readiness_timeout',
    'worker_failed_or_timed_out'
  )
  if ($allowed -ccontains $Reason) { return $Reason }
  return 'other_unclassified_failure'
}

if($Child) {
  try { Invoke-Child; exit 0 }
  catch {
    $reason=Get-BoundedFailure ([string]$_.Exception.Message)
    try {
      if ($Scratch -and [IO.Directory]::Exists($Scratch)) {
        [IO.File]::WriteAllText((Join-Path $Scratch ('child-status-'+$ChildIndex)),$reason)
      }
    } catch {}
    exit 2
  }
}
$procs=New-Object 'System.Collections.Generic.List[System.Diagnostics.Process]'
$root=$null
try {
  if (-not $env:RUNNER_TEMP -or -not [IO.Directory]::Exists($env:RUNNER_TEMP)) {
    throw 'runner_temp_missing'
  }
  $original=[IO.Path]::GetFullPath($DllPath)
  if (-not [IO.File]::Exists($original)) { throw 'built_x86_dll_missing' }
  $root=Join-Path $env:RUNNER_TEMP ('virtualcar-b3a325-'+[Guid]::NewGuid().ToString('N'))
  [void][IO.Directory]::CreateDirectory($root)
  $dll=Join-Path $root 'VirtualCarJ2534.dll'
  [IO.File]::Copy($original,$dll,$false)
  if ((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash -cne
      (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash) {
    throw 'isolated_dll_bytes_mismatch'
  }
  $ini=@'
; SYNTHETIC lab only. No ECU fixture or physical J2534.
[Diagnostics]
BackendTelemetryEnabled=0
[Vehicle]
ECUCount=1
[D2_40]
B9FBFrameCount=0
[D2_50]
B9FBFrameCount=0
[PassiveCAN]
Enabled=0
[PassiveTrace]
Enabled=0
'@
  [IO.File]::WriteAllText((Join-Path $root 'virtualcar.ini'),$ini,[Text.Encoding]::ASCII)
  $ps32=Join-Path $env:WINDIR 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
  if (-not [IO.File]::Exists($ps32)) { throw 'x86_powershell_missing' }
  for($i=0;$i -lt $Workers;$i++){
    $start=New-Object Diagnostics.ProcessStartInfo
    $start.FileName=$ps32
    $start.Arguments=('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -DllPath "{1}" -Scratch "{2}" -Child -ChildIndex {3} -Iterations {4}' -f
                      $PSCommandPath,$dll,$root,$i,$Iterations)
    $start.WorkingDirectory=$root
    $start.UseShellExecute=$false; $start.CreateNoWindow=$true
    $start.EnvironmentVariables['TEMP']=$root
    $start.EnvironmentVariables['TMP']=$root
    $start.EnvironmentVariables['LOCALAPPDATA']=$root
    $p=[Diagnostics.Process]::Start($start)
    if ($null -eq $p) { throw 'worker_spawn_failure' }
    $procs.Add($p)
  }
  $until=[DateTime]::UtcNow.AddSeconds(90)
  while($true){
    $ready=0
    for($i=0;$i -lt $Workers;$i++){
      if ([IO.File]::Exists((Join-Path $root ('ready-'+$i)))) { $ready++ }
    }
    if ($ready -eq $Workers) { break }
    foreach($p in $procs) { if ($p.HasExited) { throw 'worker_ended_before_gate' } }
    if ([DateTime]::UtcNow -ge $until) { throw 'worker_readiness_timeout' }
    Start-Sleep -Milliseconds 50
  }
  [IO.File]::WriteAllText((Join-Path $root 'start'),'go')
  foreach($p in $procs) {
    if (-not $p.WaitForExit(90000) -or $p.ExitCode -ne 0) {
      throw 'worker_failed_or_timed_out'
    }
  }
  Assert-Results -Root $root -WorkerCount $Workers -LoopCount $Iterations
} catch {
  $code=Get-BoundedFailure ([string]$_.Exception.Message)
  Write-Host ('B3A325_FAILURE_CATEGORY='+$code)
  if ($root -and [IO.Directory]::Exists($root)) {
    for($i=0;$i -lt $Workers;$i++) {
      try {
        $status=Join-Path $root ('child-status-'+$i)
        if ([IO.File]::Exists($status)) {
          $safe=Get-BoundedFailure ([IO.File]::ReadAllText($status).Trim())
          Write-Host ('B3A325_CHILD_CATEGORY='+$safe)
        }
      } catch {}
    }
  }
  throw 'B3A325 isolated multiprocess native logging regression FAILED'
} finally {
  foreach($p in $procs) {
    try { if (-not $p.HasExited) { $p.Kill() }; $p.Dispose() } catch {}
  }
  if ($root -and [IO.Directory]::Exists($root)) {
    try { [IO.Directory]::Delete($root,$true) } catch {}
  }
}
