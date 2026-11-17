#Requires -Version 5.1
<# B3A277 offline, real x86 J2534: preserve private CEM50 B9FB 13/13
   and verify opted-in GGD A45F/DD02 2/2 on the SAME copied DLL/INI.
   Never registers adapter, runs VIDA, touches SQL or opens hardware. #>
[CmdletBinding()]
param(
 [string]$LabDirectory='C:\VirtualCar-B3A277-Lab',
 [string]$OutputDirectory='C:\VirtualCar-B3A277-Native'
)
$ErrorActionPreference='Stop';Set-StrictMode -Version Latest
if([IntPtr]::Size -ne 4){
 $x86=Join-Path $env:WINDIR 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
 & $x86 -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -LabDirectory $LabDirectory -OutputDirectory $OutputDirectory
 if($LASTEXITCODE -ne 0){throw 'B3A277_X86_NATIVE_CHILD_FAILED'}
 return
}
$sha='7E5F6BB0B475B088E0CA899A22962109E9301CD10D63F6E09AA266A42F501060'
$sourceDll=(Resolve-Path -LiteralPath (Join-Path $LabDirectory 'VirtualCarJ2534.dll')).Path
$sourceIni=(Resolve-Path -LiteralPath (Join-Path $LabDirectory 'virtualcar.ini')).Path
if((Get-FileHash -LiteralPath $sourceDll -Algorithm SHA256).Hash -cne $sha){throw 'B3A277_DLL_HASH_MISMATCH'}
$iniText=[IO.File]::ReadAllText($sourceIni,[Text.Encoding]::Default)
if($iniText -notmatch '(?im)^EnableGGDCemLab\s*=\s*1\s*$' -or
 $iniText -notmatch '(?im)^B9FBFrameCount\s*=\s*13\s*$' -or
 $iniText -notmatch '(?im)^RequestId\s*=\s*18DA50F1\s*$' -or
 $iniText -notmatch '(?im)^ResponseId\s*=\s*18DAF150\s*$'){
 throw 'B3A277_INI_NOT_STAGED'
}
$dest=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $dest){throw 'B3A277_USE_NEW_NATIVE_OUTPUT_DIRECTORY'}
[void][IO.Directory]::CreateDirectory($dest)
$dll=Join-Path $dest 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $sourceDll -Destination $dll
Copy-Item -LiteralPath $sourceIni -Destination (Join-Path $dest 'virtualcar.ini')
$savedTemp=$env:TEMP;$savedTmp=$env:TMP;$savedLocal=$env:LOCALAPPDATA
try{
 $env:TEMP=$dest;$env:TMP=$dest;$env:LOCALAPPDATA=$dest
 $code=@'
using System;
using System.Runtime.InteropServices;
public static class B3A277Combined {
 const string Dll=@"__DLL__";
 const uint CAN=5u,ISO=6u,FLAG29=0x100u;
 [StructLayout(LayoutKind.Sequential)] public struct Msg {
  public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
  [MarshalAs(UnmanagedType.ByValArray,SizeConst=4128)] public byte[] Data;
 }
 [DllImport(Dll,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruOpen(IntPtr n,out uint dev);
 [DllImport(Dll,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruClose(uint dev);
 [DllImport(Dll,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruConnect(uint dev,uint proto,uint flags,uint baud,out uint ch);
 [DllImport(Dll,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruDisconnect(uint ch);
 [DllImport(Dll,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruStartMsgFilter(uint ch,uint type,ref Msg mask,ref Msg pattern,ref Msg flow,out uint id);
 [DllImport(Dll,EntryPoint="PassThruStartMsgFilter",CallingConvention=CallingConvention.StdCall)] static extern uint StartCanFilter(uint ch,uint type,ref Msg mask,ref Msg pattern,IntPtr zero,out uint id);
 [DllImport(Dll,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruWriteMsgs(uint ch,ref Msg msg,ref uint n,uint timeout);
 [DllImport(Dll,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruReadMsgs(uint ch,ref Msg msg,ref uint n,uint timeout);
 static void Must(bool x,string gate){ if(!x)throw new Exception("B3A277_"+gate); }
 static Msg Frame(uint proto,uint id,byte[] payload){
  Msg m=new Msg();m.ProtocolID=proto;m.TxFlags=FLAG29;m.Data=new byte[4128];m.DataSize=(uint)(4+payload.Length);
  m.Data[0]=(byte)(id>>24);m.Data[1]=(byte)(id>>16);m.Data[2]=(byte)(id>>8);m.Data[3]=(byte)id;
  Array.Copy(payload,0,m.Data,4,payload.Length);return m;
 }
 static Msg FilterId(uint proto,uint id){
  return Frame(proto,id,new byte[0]);
 }
 static Msg Receive(uint ch,uint timeout) {
  Msg rx=new Msg();rx.Data=new byte[4128];uint n=1;
  Must(PassThruReadMsgs(ch,ref rx,ref n,timeout)==0&&n==1,"RX_MISSING");
  return rx;
 }
 static void Send(uint ch,Msg m){
  uint n=1;Must(PassThruWriteMsgs(ch,ref m,ref n,100)==0&&n==1,"TX_REJECTED");
 }
 static void CheckDid(uint ch,byte high,byte low,byte expected) {
  Send(ch,Frame(ISO,0x18DA50F1u,new byte[]{0x22,high,low}));
  Msg rx=Receive(ch,500);
  Must(rx.ProtocolID==ISO&&rx.DataSize==8&&rx.ExtraDataIndex==8
   &&rx.Data[0]==0x18&&rx.Data[1]==0xDA&&rx.Data[2]==0xF1&&rx.Data[3]==0x50
   &&rx.Data[4]==0x62&&rx.Data[5]==high&&rx.Data[6]==low&&rx.Data[7]==expected,"DID_REPLY");
 }
 public static void Run(){
  Must(IntPtr.Size==4&&Marshal.SizeOf(typeof(Msg))==4152,"ABI");
  uint device=0,can=0,iso=0,filterCan=0,filterIso=0;
  Must(PassThruOpen(IntPtr.Zero,out device)==0,"OPEN");
  try{
   Must(PassThruConnect(device,CAN,FLAG29,500000u,out can)==0,"CAN_CONNECT");
   try{
    Msg mask=FilterId(CAN,0xffffffffu),pat=FilterId(CAN,0x01200003u);
    for(int j=0;j<4;j++)mask.Data[j]=0xFF;
    Must(StartCanFilter(can,1u,ref mask,ref pat,IntPtr.Zero,out filterCan)==0,"CAN_PASS_FILTER");
    Send(can,Frame(CAN,0x000ffffeu,new byte[]{0xCB,0x50,0xB9,0xFB,0,0,0,0}));
    for(int k=0;k<13;k++){
     Msg rx=Receive(can,1000u);
     byte header=(byte)(k==0?0x8F:k==12?0x4F:(0x08|(k&7)));
     Must(rx.ProtocolID==CAN&&rx.DataSize==12&&rx.ExtraDataIndex==12
      &&rx.Data[0]==1&&rx.Data[1]==0x20&&rx.Data[2]==0&&rx.Data[3]==3
      &&rx.Data[4]==header,"B9FB_FRAME");
     if(k==0)Must(rx.Data[5]==0x50&&rx.Data[6]==0xF9&&rx.Data[7]==0xFB,"B9FB_ECHO");
    }
    Console.WriteLine("B3A277_NATIVE_B9FB=PASS_13_OF_13_CAN_500000");
   } finally {Must(PassThruDisconnect(can)==0,"CAN_DISCONNECT");can=0;}
   Must(PassThruConnect(device,ISO,FLAG29,500000u,out iso)==0,"ISO_CONNECT");
   try{
    Msg mask=FilterId(ISO,0xffffffffu),pat=FilterId(ISO,0x18DAF150u),flow=FilterId(ISO,0x18DA50F1u);
    for(int j=0;j<4;j++)mask.Data[j]=0xFF;
    Must(PassThruStartMsgFilter(iso,3u,ref mask,ref pat,ref flow,out filterIso)==0,"ISO_FC_FILTER");
    CheckDid(iso,0xA4,0x5F,0x04);
    CheckDid(iso,0xDD,0x02,0x32);
    Console.WriteLine("B3A277_NATIVE_GGD=PASS_2_OF_2_POSITIVE");
   } finally {Must(PassThruDisconnect(iso)==0,"ISO_DISCONNECT");iso=0;}
  } finally {
   if(iso!=0)PassThruDisconnect(iso);
   if(can!=0)PassThruDisconnect(can);
   if(device!=0)Must(PassThruClose(device)==0,"CLOSE");
  }
  Console.WriteLine("B3A277_NATIVE_COMBINED=PASS_13FRAME_REPLAY_AND_GGD; VIDA=NOT_TESTED");
 }
}
'@
 $code=$code.Replace('__DLL__',$dll.Replace('"','""'))
 Add-Type -TypeDefinition $code -Language CSharp -ErrorAction Stop
 [B3A277Combined]::Run()
 $report=[ordered]@{
   schema='b3a277-native-combined-v1'
   status='PASS_B9FB_13_OF_13_AND_GGD_2_OF_2'
   dll_sha256=(Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
   profile_sha256=(Get-FileHash -LiteralPath (Join-Path $dest 'virtualcar.ini') -Algorithm SHA256).Hash
   original_vida='NOT_TESTED'
   original_ecu_identification='NOT_TESTED'
 }
 $reportPath=Join-Path $dest 'B3A277-native-pass.json'
 [IO.File]::WriteAllText($reportPath,(($report|ConvertTo-Json)+"`n"),(New-Object Text.UTF8Encoding($false)))
 Write-Output 'B3A277_NATIVE_PROVENANCE=ISOLATED_X86_SYNTHETIC_AND_PRIVATE_REPLAY'
 Write-Output 'B3A277_REGISTRY=UNCHANGED; VIDA=NOT_TESTED; SQL=UNCHANGED'
}finally{
 $env:TEMP=$savedTemp;$env:TMP=$savedTmp;$env:LOCALAPPDATA=$savedLocal
}
