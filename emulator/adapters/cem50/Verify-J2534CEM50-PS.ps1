#Requires -Version 5.1
# Exact J2534-2 CAN_PS CEM50 x86 smoke: isolated DLL copy, no registry/VIDA/hardware.
[CmdletBinding()]
param(
 [Parameter(Mandatory=$true)][string]$DllPath,
 [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256,
 [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
 & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -ExpectedSha256 $ExpectedSha256 -OutputDirectory $OutputDirectory
 exit $LASTEXITCODE
}
$src=(Resolve-Path -LiteralPath $DllPath -ErrorAction Stop).Path
$ini=Join-Path $PSScriptRoot 'virtualcar.ini'
$out=[IO.Path]::GetFullPath($OutputDirectory)
if ((Test-Path -LiteralPath $out) -or -not (Test-Path -LiteralPath $ini)) { throw 'Output exists or INI missing' }
if ([IO.Path]::GetFileName($src) -ine 'VirtualCarJ2534.dll') { throw 'Only emulator x86 DLL is allowed' }
$sha=(Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
if ($sha -ine $ExpectedSha256) { throw 'Source DLL SHA256 mismatch' }
$b=[IO.File]::ReadAllBytes($src)
if ($b.Length -lt 256 -or $b[0] -ne 0x4D -or $b[1] -ne 0x5A) { throw 'Invalid PE' }
$pe=[BitConverter]::ToInt32($b,0x3C)
if ($pe -lt 64 -or $pe+26 -ge $b.Length -or
 $b[$pe] -ne 0x50 -or $b[$pe+1] -ne 0x45 -or
 [BitConverter]::ToUInt16($b,$pe+4) -ne 0x014C -or
 [BitConverter]::ToUInt16($b,$pe+24) -ne 0x010B) { throw 'DLL not x86 PE32' }
$cfg=[IO.File]::ReadAllText($ini)
if (-not $cfg.Contains('[J2534_2]') -or -not $cfg.Contains('Enabled = 1') -or
 -not $cfg.Contains('VIN = YV1CR855691511566') -or
 -not $cfg.Contains('B9FBFrameCount = 13')) { throw 'Unexpected PS fixture' }
[void][IO.Directory]::CreateDirectory($out)
$dll=Join-Path $out 'J2534CEM50PS.dll'
Copy-Item -LiteralPath $src -Destination $dll
Copy-Item -LiteralPath $ini -Destination (Join-Path $out 'virtualcar.ini')
if ((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ine $sha) { throw 'Staged DLL mismatch' }
$wasLocal=$env:LOCALAPPDATA; $wasTemp=$env:TEMP; $wasTmp=$env:TMP
try {
 $env:LOCALAPPDATA=$out; $env:TEMP=$out; $env:TMP=$out
 $code=@'
using System;
using System.Runtime.InteropServices;
public static class CEM50PSProbe {
 const string Library=@"__DLL_PATH__";
 [StructLayout(LayoutKind.Sequential)]
 public struct Msg {
    public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
    [MarshalAs(UnmanagedType.ByValArray,SizeConst=4128)] public byte[] Data;
 }
 [StructLayout(LayoutKind.Sequential)] public struct Config { public uint Parameter,Value; }
 [StructLayout(LayoutKind.Sequential)] public struct ConfigList { public uint Count; public IntPtr Ptr; }
 [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
 static extern uint PassThruOpen(IntPtr name,out uint device);
 [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
 static extern uint PassThruClose(uint device);
 [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
 static extern uint PassThruConnect(uint device,uint protocol,uint flags,uint baud,out uint channel);
 [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
 static extern uint PassThruDisconnect(uint channel);
 [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
 static extern uint PassThruIoctl(uint channel,uint ioctl,ref ConfigList config,IntPtr output);
 [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
 static extern uint PassThruWriteMsgs(uint channel,ref Msg msg,ref uint count,uint timeout);
 [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
 static extern uint PassThruReadMsgs(uint channel,IntPtr msg,ref uint count,uint timeout);
 static void Check(bool condition,string gate) {
   if(!condition)throw new InvalidOperationException("CEM50 PS: "+gate);
 }
 static void Pins(uint channel,uint value) {
   IntPtr cfg=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Config)));
   try {
     Marshal.StructureToPtr(new Config { Parameter=0x8001u,Value=value },cfg,false);
     ConfigList list=new ConfigList { Count=1u,Ptr=cfg };
     Check(PassThruIoctl(channel,2u,ref list,IntPtr.Zero)==0u,"J1962 SET_CONFIG");
     Marshal.StructureToPtr(new Config { Parameter=0x8001u,Value=0u },cfg,false);
     Check(PassThruIoctl(channel,1u,ref list,IntPtr.Zero)==0u,"J1962 GET_CONFIG");
     Config got=(Config)Marshal.PtrToStructure(cfg,typeof(Config));
     Check(got.Value==value,"J1962 readback");
   }finally{Marshal.FreeHGlobal(cfg);}
 }
 static readonly byte[,] Frames=new byte[13,8] {
  {0x8F,0x50,0xF9,0xFB,0x57,0x00,0x30,0x66},
  {0x09,0x70,0x28,0x30,0x30,0x35,0x0D,0x0A},
  {0x0A,0x59,0x56,0x31,0x43,0x52,0x38,0x35},
  {0x0B,0x35,0x36,0x39,0x31,0x35,0x31,0x31},
  {0x0C,0x35,0x36,0x36,0x0D,0x0A,0x32,0x35},
  {0x0D,0x31,0x35,0x36,0x38,0x39,0x35,0x32},
  {0x0E,0x0D,0x0A,0x32,0x39,0x35,0x0D,0x0A},
  {0x0F,0x35,0x31,0x31,0x35,0x36,0x36,0x0D},
  {0x08,0x0A,0x32,0x31,0x0D,0x0A,0x32,0x30},
  {0x09,0x30,0x35,0x31,0x32,0x0D,0x0A,0x30},
  {0x0A,0x30,0x30,0x30,0x34,0x33,0x33,0x38},
  {0x0B,0x36,0x30,0x34,0x30,0x38,0x32,0x32},
  {0x4F,0x30,0x36,0x39,0x33,0x31,0x0D,0x0A}
 };
 static Msg Request() {
   Msg m=new Msg();
   m.ProtocolID=0x8004u; m.TxFlags=0x100u; m.DataSize=12u;
   m.Data=new byte[4128];
   byte[] payload={0,0x0F,0xFF,0xFE,0xCB,0x50,0xB9,0xFB,0,0,0,0};
   Array.Copy(payload,m.Data,payload.Length);
   return m;
 }
 public static void Run() {
   uint dev=0,can=0,ms=0; bool opened=false,hasCan=false,hasMs=false;
   try {
     Check(PassThruOpen(IntPtr.Zero,out dev)==0u&&dev!=0u,"Open");
     opened=true;
     Check(PassThruConnect(dev,0x8004u,0u,500000u,out can)==0u&&can!=0u,"CAN_PS 500k");
     hasCan=true;
     Msg m=Request();
     uint count=1u;
     Check(PassThruWriteMsgs(can,ref m,ref count,0u)==19u&&count==0u,"unbound pins reject TX");
     Pins(can,0x060Eu);
     count=1u;
     Check(PassThruWriteMsgs(can,ref m,ref count,5000u)==0u&&count==1u,"CAN_PS B9FB TX");
     IntPtr rxptr=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
     try {
       for(int i=0;i<13;i++) {
         count=1u;
         Check(PassThruReadMsgs(can,rxptr,ref count,1500u)==0u&&count==1u,"CAN_PS RX "+i);
         Msg r=(Msg)Marshal.PtrToStructure(rxptr,typeof(Msg));
         Check(r.ProtocolID==0x8004u&&r.DataSize==12u&&(r.RxStatus&0x100u)!=0,
               "PS RX protocol/status");
         byte[] id={0x01,0x20,0,0x03};
         for(int j=0;j<4;j++)Check(r.Data[j]==id[j],"response CAN ID "+i);
         for(int j=0;j<8;j++)Check(r.Data[4+j]==Frames[i,j],"D2 "+i+" "+j);
       }
       count=1u;
       Check(PassThruReadMsgs(can,rxptr,ref count,0u)==16u,"extra CEM50 RX");
       Check(PassThruDisconnect(can)==0u,"CAN_PS Disconnect");
       hasCan=false;
       Check(PassThruConnect(dev,0x8004u,0u,125000u,out ms)==0u&&ms!=0u,"CAN_PS MS Connect");
       hasMs=true;
       Pins(ms,0x030Bu);
       m=Request();count=1u;
       Check(PassThruWriteMsgs(ms,ref m,ref count,5000u)==0u&&count==1u,"CAN_PS MS TX");
       count=1u;
       Check(PassThruReadMsgs(ms,rxptr,ref count,0u)==16u,"500k CEM fixture leaked to 125k");
     }finally{Marshal.FreeHGlobal(rxptr);}
   } finally {
     if(hasMs)Check(PassThruDisconnect(ms)==0u,"MS Disconnect");
     if(hasCan)Check(PassThruDisconnect(can)==0u,"CAN Disconnect");
     if(opened)Check(PassThruClose(dev)==0u,"Close");
   }
   Console.WriteLine("CEM50_PS_NATIVE_PASS: 13/13 exact CAN_PS D2 frames, HS/MS isolated");
 }
}
'@
 $code=$code.Replace('__DLL_PATH__',$dll)
 Add-Type -TypeDefinition $code -Language CSharp -ErrorAction Stop
 [CEM50PSProbe]::Run()
 $report=[ordered]@{
   schema_version='cem50_ps_native_x86_v1'
   status='CEM50_PS_NATIVE_PASS'
   published_vin='YV1CR855691511566'
   protocol_id='0x8004'
   j1962_hs='0x060E'
   j1962_ms='0x030B'
   matched_frames=13
   dll_sha256=$sha
   vida_readvin_verified=$false
   ecu_identification_verified=$false
   physical_adapter_used=$false
 }
 [IO.File]::WriteAllText((Join-Path $out 'ps-native-check.json'),
    ($report | ConvertTo-Json -Depth 4),[Text.Encoding]::UTF8)
 Write-Host "CEM50_PS_NATIVE_PASS: report $out\ps-native-check.json"
} finally {
 $env:LOCALAPPDATA=$wasLocal; $env:TEMP=$wasTemp; $env:TMP=$wasTmp
}
