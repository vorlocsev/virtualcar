#Requires -Version 5.1
# B3A276: real x86 J2534 DLL, synthetic GGD CEM 50 only.
# No Registry32 provider registration, VIDA start, SQL access, hardware or ECU programming.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$DllPath,
  [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([IntPtr]::Size -ne 4) {
  $ps32=Join-Path $env:WINDIR 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
  if (-not (Test-Path -LiteralPath $ps32)) { throw 'WINDOWS_X86_POWERSHELL_NOT_FOUND' }
  & $ps32 -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -OutputDirectory $OutputDirectory
  if ($LASTEXITCODE -ne 0) { throw 'B3A276_X86_CHILD_FAILED' }
  return
}
$src=(Resolve-Path -LiteralPath $DllPath).Path
$dir=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $dir) { throw 'OUTPUT_DIRECTORY_MUST_BE_NEW' }
[void][IO.Directory]::CreateDirectory($dir)
$isolated=Join-Path $dir 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $src -Destination $isolated
$ini=Join-Path $dir 'virtualcar.ini'
# NO private VIN, D2 fixtures or original VIDA data.
$profile=@'
; B3A276 synthetic read-only GGD CEM lab; not an original ECU capture.
[Vehicle]
VIN=YV1CZ0002A0000001
ECUCount=2
BatteryMv=12500
[ECU0]
RequestId=7E0
ResponseId=7E8
[ECU1]
RequestId=18DA50F1
ResponseId=18DAF150
[P2]
StrictRouting=1
[D2_40]
B9FBFrameCount=0
[D2_50]
B9FBFrameCount=0
[PassiveCAN]
Enabled=0
[PassiveTrace]
Enabled=0
[Diagnostics]
EnableGGDCemLab=0
StrictJ2534Filters=0
BackendTelemetryEnabled=0
'@
[IO.File]::WriteAllText($ini,$profile,[Text.Encoding]::ASCII)
$saveTemp=$env:TEMP; $saveTmp=$env:TMP; $saveLocal=$env:LOCALAPPDATA
try {
  $env:TEMP=$dir; $env:TMP=$dir; $env:LOCALAPPDATA=$dir
  $cs=@'
using System;
using System.IO;
using System.Runtime.InteropServices;
public static class B3A276NativeGGD {
  const string Dll = @"__ISOLATED_DLL__";
  const uint ISO=6, FLAG29=0x100, OK=0, EMPTY=16;
  [StructLayout(LayoutKind.Sequential)]
  public struct Msg {
    public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
    [MarshalAs(UnmanagedType.ByValArray, SizeConst=4128)]
    public byte[] Data;
  }
  [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
  static extern IntPtr LoadLibraryW(string path);
  [DllImport("kernel32.dll",CharSet=CharSet.Ansi,ExactSpelling=true)]
  static extern IntPtr GetProcAddress(IntPtr module,string symbol);
  [DllImport("kernel32.dll")]
  static extern bool FreeLibrary(IntPtr module);
  [DllImport(Dll,CallingConvention=CallingConvention.StdCall)]
  static extern uint PassThruOpen(IntPtr name,out uint device);
  [DllImport(Dll,CallingConvention=CallingConvention.StdCall)]
  static extern uint PassThruClose(uint device);
  [DllImport(Dll,CallingConvention=CallingConvention.StdCall)]
  static extern uint PassThruConnect(uint device,uint protocol,uint flags,uint baud,out uint channel);
  [DllImport(Dll,CallingConvention=CallingConvention.StdCall)]
  static extern uint PassThruDisconnect(uint channel);
  [DllImport(Dll,CallingConvention=CallingConvention.StdCall)]
  static extern uint PassThruWriteMsgs(uint channel,ref Msg m,ref uint count,uint timeout);
  [DllImport(Dll,CallingConvention=CallingConvention.StdCall)]
  static extern uint PassThruReadMsgs(uint channel,IntPtr m,ref uint count,uint timeout);

  static void Must(bool pass,string gate) {
    if (!pass) throw new Exception("B3A276_FAIL_"+gate);
    Console.WriteLine("B3A276_PASS_"+gate);
  }
  static Msg NewMessage(uint id,byte[] payload) {
    Msg m=new Msg();m.ProtocolID=ISO;m.TxFlags=FLAG29;m.Data=new byte[4128];
    m.DataSize=(uint)(payload.Length+4);
    m.Data[0]=(byte)(id>>24);m.Data[1]=(byte)(id>>16);
    m.Data[2]=(byte)(id>>8);m.Data[3]=(byte)id;
    Array.Copy(payload,0,m.Data,4,payload.Length);
    return m;
  }
  static Msg Request(uint channel,byte[] payload) {
    Msg tx=NewMessage(0x18DA50F1u,payload);uint count=1;
    Must(PassThruWriteMsgs(channel,ref tx,ref count,10)==OK && count==1,"TX");
    IntPtr buf=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
    try {
      count=1;uint status=PassThruReadMsgs(channel,buf,ref count,150);
      Must(status==OK && count==1,"RX_DELIVERED");
      return (Msg)Marshal.PtrToStructure(buf,typeof(Msg));
    } finally { Marshal.FreeHGlobal(buf); }
  }
  static void CheckReply(Msg rx,byte[] expected,string gate) {
    bool good=rx.ProtocolID==ISO && rx.DataSize==expected.Length+4u &&
      rx.ExtraDataIndex==rx.DataSize && rx.Data!=null &&
      rx.Data[0]==0x18 && rx.Data[1]==0xDA && rx.Data[2]==0xF1 && rx.Data[3]==0x50;
    if(good)for(int i=0;i<expected.Length;i++)if(rx.Data[i+4]!=expected[i])good=false;
    Must(good,gate);
  }
  static uint Connect(uint dev,uint flags,uint rate) {
    uint channel;uint status=PassThruConnect(dev,ISO,flags,rate,out channel);
    Must(status==OK && channel!=0,"CONNECT");
    return channel;
  }
  static void Negative(Msg m,string gate) {
    CheckReply(m,new byte[]{0x7F,0x22,0x31},gate);
  }
  public static void Run(string ini) {
    Must(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,"X86_ABI_4152");
    IntPtr module=LoadLibraryW(Dll);
    Must(module!=IntPtr.Zero,"DLL_LOAD");
    uint d=0,c=0;bool opened=false;
    try {
      string[] exports={"Open","Close","Connect","Disconnect","ReadMsgs","WriteMsgs",
        "StartPeriodicMsg","StopPeriodicMsg","StartMsgFilter","StopMsgFilter",
        "SetProgrammingVoltage","ReadVersion","GetLastError","Ioctl"};
      foreach(string name in exports)
        Must(GetProcAddress(module,"PassThru"+name)!=IntPtr.Zero,"EXPORT_"+name);
      // Default-off gate. Load configuration at each PassThruOpen.
      Must(PassThruOpen(IntPtr.Zero,out d)==OK,"OPEN_DEFAULT_OFF");opened=true;
      c=Connect(d,FLAG29,500000u);
      Negative(Request(c,new byte[]{0x22,0xA4,0x5F}),"DEFAULT_OFF_NRC31");
      Must(PassThruDisconnect(c)==OK,"DISCONNECT_OFF");c=0;
      Must(PassThruClose(d)==OK,"CLOSE_OFF");opened=false;

      string content=File.ReadAllText(ini);
      Must(content.Contains("EnableGGDCemLab=0"),"PRIVATE_INI_EXPECTED_OFF");
      File.WriteAllText(ini,content.Replace("EnableGGDCemLab=0","EnableGGDCemLab=1"),
                        System.Text.Encoding.ASCII);
      Must(PassThruOpen(IntPtr.Zero,out d)==OK,"OPEN_OPT_IN");opened=true;
      c=Connect(d,FLAG29,500000u);
      CheckReply(Request(c,new byte[]{0x22,0xA4,0x5F}),
                 new byte[]{0x62,0xA4,0x5F,0x04},"A45F_POSITIVE");
      CheckReply(Request(c,new byte[]{0x22,0xDD,0x02}),
                 new byte[]{0x62,0xDD,0x02,0x32},"DD02_POSITIVE");
      Negative(Request(c,new byte[]{0x22,0xF0,0x00}),"UNKNOWN_DID_NRC31");
      Negative(Request(c,new byte[]{0x22,0xA4,0x5F,0x00}),"EXTRA_BYTE_NRC31");
      Must(PassThruDisconnect(c)==OK,"DISCONNECT_LAB");c=0;

      c=Connect(d,0u,500000u);
      Negative(Request(c,new byte[]{0x22,0xA4,0x5F}),"MISSING_29BIT_CHANNEL_FLAG_NRC31");
      Must(PassThruDisconnect(c)==OK,"DISCONNECT_NOFLAG");c=0;
      c=Connect(d,FLAG29,125000u);
      Negative(Request(c,new byte[]{0x22,0xDD,0x02}),"WRONG_BAUD_NRC31");
      Must(PassThruDisconnect(c)==OK,"DISCONNECT_125K");c=0;
      Must(PassThruClose(d)==OK,"CLOSE_FINAL");opened=false;
      Console.WriteLine("B3A276_NATIVE_GGD=PASS original_VIDA=NOT_TESTED hardware=NOT_TESTED");
    } finally {
      bool clean=true;
      if(c!=0)clean &= PassThruDisconnect(c)==OK;
      if(opened)clean &= PassThruClose(d)==OK;
      clean &= FreeLibrary(module);
      Must(clean,"CLEANUP");
    }
  }
}
'@
  $cs=$cs.Replace('__ISOLATED_DLL__',$isolated.Replace('"','""'))
  Add-Type -TypeDefinition $cs -Language CSharp
  [B3A276NativeGGD]::Run($ini)
  Write-Output ('B3A276_ISOLATED_DLL_SHA256='+(Get-FileHash -LiteralPath $isolated -Algorithm SHA256).Hash)
  Write-Output 'B3A276_REGISTRY=UNCHANGED; B3A276_VIDA=NOT_TESTED; B3A276_SQL=UNCHANGED'
} finally {
  $env:TEMP=$saveTemp; $env:TMP=$saveTmp; $env:LOCALAPPDATA=$saveLocal
}
