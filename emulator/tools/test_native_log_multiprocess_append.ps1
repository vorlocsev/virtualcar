# B3A325: real Win32 multi-process append regression for the built x86 emulator.
# Synthetic, isolated, no physical J2534, no SectorV/VIDA and no private logs.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$DllPath,
  [ValidateRange(2,6)][int]$Workers=4,
  [ValidateRange(1,64)][int]$Iterations=16,
  [switch]$D2Replay,
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
  [DllImport(@"__DLL__",CallingConvention=CallingConvention.StdCall,ExactSpelling=true)]
  static extern uint PassThruConnect(uint device,uint protocol,uint flags,uint baud,out uint channel);
  [DllImport(@"__DLL__",CallingConvention=CallingConvention.StdCall,ExactSpelling=true)]
  static extern uint PassThruDisconnect(uint channel);
  [DllImport(@"__DLL__",CallingConvention=CallingConvention.StdCall,ExactSpelling=true)]
  static extern uint PassThruWriteMsgs(uint channel,ref Msg message,ref uint count,uint timeout);
  [DllImport(@"__DLL__",CallingConvention=CallingConvention.StdCall,ExactSpelling=true)]
  static extern uint PassThruReadMsgs(uint channel,IntPtr messages,ref uint count,uint timeout);
  [StructLayout(LayoutKind.Sequential)]
  public struct Msg {
    public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
    [MarshalAs(UnmanagedType.ByValArray,SizeConst=4128)] public byte[] Data;
  }
  static readonly byte[,] D2Frames=new byte[13,8] {
    {0x8F,0x50,0xF9,0xFB,0x57,0x00,0x30,0x66},
    {0x09,0x70,0x28,0x30,0x30,0x35,0x0D,0x0A},
    {0x0A,0x59,0x56,0x31,0x43,0x5A,0x30,0x30},
    {0x0B,0x30,0x32,0x41,0x30,0x30,0x30,0x30},
    {0x0C,0x30,0x30,0x31,0x0D,0x0A,0x32,0x35},
    {0x0D,0x31,0x35,0x36,0x38,0x39,0x35,0x32},
    {0x0E,0x0D,0x0A,0x32,0x39,0x35,0x0D,0x0A},
    {0x0F,0x31,0x39,0x38,0x36,0x32,0x35,0x0D},
    {0x08,0x0A,0x32,0x31,0x0D,0x0A,0x32,0x30},
    {0x09,0x30,0x35,0x31,0x32,0x0D,0x0A,0x30},
    {0x0A,0x30,0x30,0x30,0x34,0x33,0x33,0x38},
    {0x0B,0x36,0x30,0x34,0x30,0x38,0x32,0x32},
    {0x4F,0x30,0x36,0x39,0x33,0x31,0x0D,0x0A}
  };
  static void Check(bool ok) {
    if(!ok) throw new InvalidOperationException("synthetic_d2_frame_mismatch");
  }
  static void ReadSyntheticB9FB(uint channel) {
    Msg tx=new Msg();
    tx.ProtocolID=5;tx.TxFlags=0x100;tx.DataSize=12;tx.Data=new byte[4128];
    byte[] req=new byte[]{0x00,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xFB,0,0,0,0};
    Array.Copy(req,tx.Data,req.Length);
    uint written=1;
    Check(PassThruWriteMsgs(channel,ref tx,ref written,100)==0 && written==1);
    uint prior=0;
    IntPtr memory=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
    try {
      for(int frame=0;frame<13;frame++) {
        uint got=1;
        Check(PassThruReadMsgs(channel,memory,ref got,300)==0 && got==1);
        Msg rx=(Msg)Marshal.PtrToStructure(memory,typeof(Msg));
        Check(rx.ProtocolID==5 && rx.DataSize==12 && rx.ExtraDataIndex==12
              && rx.RxStatus==0x100 && rx.Data!=null && rx.Data.Length==4128);
        Check(rx.Data[0]==1 && rx.Data[1]==0x20 && rx.Data[2]==0 && rx.Data[3]==3);
        for(int b=0;b<8;b++) Check(rx.Data[4+b]==D2Frames[frame,b]);
        if(frame>0) Check(rx.Timestamp!=prior);
        prior=rx.Timestamp;
      }
    } finally { Marshal.FreeHGlobal(memory); }
  }
  public static void Run(int loops,bool d2Replay) {
    Check(Marshal.SizeOf(typeof(Msg))==4152);
    for(int i=0;i<loops;i++) {
      uint device;
      if(PassThruOpen(IntPtr.Zero,out device)!=0 || device!=1)
        throw new InvalidOperationException("open_failed");
      if(d2Replay) {
        uint channel;
        Check(PassThruConnect(device,5,0x800,500000,out channel)==0 && channel!=0);
        ReadSyntheticB9FB(channel);
        Check(PassThruDisconnect(channel)==0);
      }
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
    [SyntheticAppendWorker]::Run($Iterations,[bool]$D2Replay)
  } catch {
    if ($D2Replay) { throw 'child_native_d2_replay_failed' }
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
  # $PID is a read-only automatic variable in Windows PowerShell 5.1.
  # Keep the trace PID scoped to a different local identifier.
  $sessions=@{}; $opens=0; $closes=0
  foreach($line in $rows[0..($rows.Count-2)]) {
    if (-not $line -or $line.IndexOf('[PID=',5) -ge 0) {
      throw 'split_or_concatenated_record'
    }
    $m=[regex]::Match($line,'^\[PID=([0-9A-F]{8}) ([^\]\r\n]{1,64})\] (.+)$')
    if (-not $m.Success) { throw 'bad_native_prefix' }
    $tracePid=$m.Groups[1].Value
    $event=$m.Groups[3].Value
    if (-not $sessions.ContainsKey($tracePid)) {
      $sessions[$tracePid]=@{Open=0;Close=0;Balance=0}
    }
    $item=$sessions[$tracePid]
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
  foreach($tracePid in $sessions.Keys) {
    $s=$sessions[$tracePid]
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
    'worker_failed_or_timed_out',
    'child_native_d2_replay_failed','invalid_synthetic_rx_context_words',
    'synthetic_rx_protocol_not_can','missing_synthetic_d2_rx_metadata'
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
$stage='preflight'
try {
  if (-not $env:RUNNER_TEMP -or -not [IO.Directory]::Exists($env:RUNNER_TEMP)) {
    throw 'runner_temp_missing'
  }
  $original=[IO.Path]::GetFullPath($DllPath)
  if (-not [IO.File]::Exists($original)) { throw 'built_x86_dll_missing' }
  $root=Join-Path $env:RUNNER_TEMP ('virtualcar-b3a325-'+[Guid]::NewGuid().ToString('N'))
  $stage='create_scratch'
  [void][IO.Directory]::CreateDirectory($root)
  $dll=Join-Path $root 'VirtualCarJ2534.dll'
  $stage='copy_dll'
  [IO.File]::Copy($original,$dll,$false)
  $stage='hash_compare'
  if ((Get-FileHash -LiteralPath $original -Algorithm SHA256).Hash -cne
      (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash) {
    throw 'isolated_dll_bytes_mismatch'
  }
  $ini=@'
; SYNTHETIC lab only. No physical J2534 or original diagnostic client.
[Diagnostics]
BackendTelemetryEnabled=0
[Vehicle]
ECUCount=1
[D2_40]
B9FBFrameCount=0
[D2_50]
B9FBFrameCount=__FRAME_COUNT__
__D2_FRAMES__
[PassiveCAN]
Enabled=0
[PassiveTrace]
Enabled=0
'@
  if ($D2Replay) {
    # Same PUBLIC synthetic fixture as verify_native_routes.ps1; no real VIN.
    $frames=@'
B9FBFrame0=8F 50 F9 FB 57 00 30 66
B9FBFrame1=09 70 28 30 30 35 0D 0A
B9FBFrame2=0A 59 56 31 43 5A 30 30
B9FBFrame3=0B 30 32 41 30 30 30 30
B9FBFrame4=0C 30 30 31 0D 0A 32 35
B9FBFrame5=0D 31 35 36 38 39 35 32
B9FBFrame6=0E 0D 0A 32 39 35 0D 0A
B9FBFrame7=0F 31 39 38 36 32 35 0D
B9FBFrame8=08 0A 32 31 0D 0A 32 30
B9FBFrame9=09 30 35 31 32 0D 0A 30
B9FBFrameA=0A 30 30 30 34 33 33 38
B9FBFrameB=0B 36 30 34 30 38 32 32
B9FBFrameC=4F 30 36 39 33 31 0D 0A
'@
    $ini=$ini.Replace('__FRAME_COUNT__','13').Replace('__D2_FRAMES__',$frames.Trim())
  } else {
    $ini=$ini.Replace('__FRAME_COUNT__','0').Replace('__D2_FRAMES__','')
  }
  $stage='write_synthetic_profile'
  [IO.File]::WriteAllText((Join-Path $root 'virtualcar.ini'),$ini,[Text.Encoding]::ASCII)
  $ps32=Join-Path $env:WINDIR 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
  if (-not [IO.File]::Exists($ps32)) { throw 'x86_powershell_missing' }
  $stage='launch_workers'
  for($i=0;$i -lt $Workers;$i++){
    $start=New-Object Diagnostics.ProcessStartInfo
    $start.FileName=$ps32
    $mode=if ($D2Replay) {' -D2Replay'} else {''}
    $start.Arguments=('-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "{0}" -DllPath "{1}" -Scratch "{2}" -Child -ChildIndex {3} -Iterations {4}{5}' -f
                      $PSCommandPath,$dll,$root,$i,$Iterations,$mode)
    $start.WorkingDirectory=$root
    $start.UseShellExecute=$false; $start.CreateNoWindow=$true
    $start.EnvironmentVariables['TEMP']=$root
    $start.EnvironmentVariables['TMP']=$root
    $start.EnvironmentVariables['LOCALAPPDATA']=$root
    $p=[Diagnostics.Process]::Start($start)
    if ($null -eq $p) { throw 'worker_spawn_failure' }
    $procs.Add($p)
  }
  $stage='wait_ready'
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
  $stage='wait_workers'
  [IO.File]::WriteAllText((Join-Path $root 'start'),'go')
  foreach($p in $procs) {
    if (-not $p.WaitForExit(90000) -or $p.ExitCode -ne 0) {
      throw 'worker_failed_or_timed_out'
    }
  }
  $stage='assert_log_shape'
  Assert-Results -Root $root -WorkerCount $Workers -LoopCount $Iterations
} catch {
  $code=Get-BoundedFailure ([string]$_.Exception.Message)
  Write-Host ('B3A325_FAILURE_CATEGORY='+$code)
  # Stage and source line are bounded numeric/enum metadata, never a path
  # or private exception message. They identify harness errors deterministically.
  $safeStages=@('preflight','create_scratch','copy_dll','hash_compare',
                'write_synthetic_profile','launch_workers','wait_ready',
                'wait_workers','assert_log_shape')
  if ($safeStages -ccontains $stage) {
    Write-Host ('B3A325_FAILURE_STAGE='+$stage)
  }
  $safeLine=0
  try { $safeLine=[int]$_.InvocationInfo.ScriptLineNumber } catch {}
  if ($safeLine -ge 1 -and $safeLine -le 260) {
    Write-Host ('B3A325_FAILURE_SOURCE_LINE='+$safeLine)
  }
  $typeName=$_.Exception.GetType().Name
  if (@('RuntimeException','MethodException','MethodInvocationException',
        'ParameterBindingException','PropertyAssignmentException',
        'ArgumentException','IOException','InvalidOperationException',
        'ItemNotFoundException') -ccontains $typeName) {
    Write-Host ('B3A325_FAILURE_EXCEPTION_CLASS='+$typeName)
  } else {
    Write-Host 'B3A325_FAILURE_EXCEPTION_CLASS=other'
  }
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
