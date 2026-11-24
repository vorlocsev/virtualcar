# B3A310: isolated x86 DLL test; no original VIDA, registry or physical adapter.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$Enabled
)
$ErrorActionPreference='Stop'
if ([IntPtr]::Size -ne 4) { throw 'Use 32-bit Windows PowerShell' }
$dll=(Resolve-Path -LiteralPath $DllPath).Path
$dir=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $dir) { throw 'Output directory must not exist' }
[void][IO.Directory]::CreateDirectory($dir)
$isolated=Join-Path $dir 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $dll -Destination $isolated
if ((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -ne (Get-FileHash -LiteralPath $isolated -Algorithm SHA256).Hash) { throw 'DLL copy mismatch' }
# Omit the new section entirely for the disabled/default control.
$profile=@'
[Vehicle]
ECUCount=1
EmitIsoRxStart=0
[ECU0]
RequestId=18DA10F1
ResponseId=18DAF110
ExpectedBaud=500000
PartNumber=LAB-ECM-HW
[P2]
StrictRouting=1
[PassiveCAN]
Enabled=0
[PassiveTrace]
Enabled=0
[Diagnostics]
StrictJ2534Filters=0
BackendTelemetryEnabled=0
'@
if ($Enabled) { $profile += [Environment]::NewLine + "[B3A309_EcmLiveDataLab]" + [Environment]::NewLine + "Enabled=1" }
[IO.File]::WriteAllText((Join-Path $dir 'virtualcar.ini'),$profile,[Text.Encoding]::ASCII)
$savedLocal=$env:LOCALAPPDATA
$savedTemp=$env:TEMP
$savedTmp=$env:TMP
try {
    $env:LOCALAPPDATA=$dir
    $env:TEMP=$dir
    $env:TMP=$dir
    $source=@'
using System;
using System.Runtime.InteropServices;
public static class EcmLiveNative {
    const string Library=@"__DLL__";
    const uint Tx=0x18DA10F1, Rx=0x18DAF110;
    [StructLayout(LayoutKind.Sequential)] public struct Msg {
        public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray,SizeConst=4128)] public byte[] Data;
    }
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruOpen(IntPtr name,out uint dev);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruClose(uint dev);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruConnect(uint dev,uint protocol,uint flags,uint baud,out uint ch);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruDisconnect(uint ch);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruWriteMsgs(uint ch,ref Msg msg,ref uint count,uint timeout);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruReadMsgs(uint ch,IntPtr buffer,ref uint count,uint timeout);
    static void Check(bool ok,string gate){if(!ok)throw new Exception(gate);}
    static void Send(uint ch,uint id,uint flags,byte[] payload){
        Msg m=new Msg();m.ProtocolID=6;m.TxFlags=flags;m.DataSize=(uint)payload.Length+4;m.Data=new byte[4128];
        m.Data[0]=(byte)(id>>24);m.Data[1]=(byte)(id>>16);m.Data[2]=(byte)(id>>8);m.Data[3]=(byte)id;
        Array.Copy(payload,0,m.Data,4,payload.Length);
        uint n=1;Check(PassThruWriteMsgs(ch,ref m,ref n,100)==0 && n==1,"write");
    }
    static void Empty(uint ch){
        IntPtr p=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try{uint n=1;Check(PassThruReadMsgs(ch,p,ref n,0)==16 && n==0,"unexpected RX");}
        finally{Marshal.FreeHGlobal(p);}
    }
    static void Expect(uint ch,byte[] payload){
        IntPtr p=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try{
            uint n=1;Check(PassThruReadMsgs(ch,p,ref n,200)==0 && n==1,"missing RX");
            Msg m=(Msg)Marshal.PtrToStructure(p,typeof(Msg));
            Check(m.ProtocolID==6 && m.RxStatus==0x100 && m.DataSize==payload.Length+4 && m.ExtraDataIndex==m.DataSize,"RX metadata");
            uint id=((uint)m.Data[0]<<24)|((uint)m.Data[1]<<16)|((uint)m.Data[2]<<8)|m.Data[3];
            Check(id==Rx,"RX CAN ID");
            for(int i=0;i<payload.Length;i++)Check(m.Data[4+i]==payload[i],"RX payload");
        }finally{Marshal.FreeHGlobal(p);}
        Empty(ch);
    }
    public static void Run(bool enabled){
        Check(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,"x86 ABI");
        uint dev=0,hs=0,ls=0;bool opened=false;
        try{
            Check(PassThruOpen(IntPtr.Zero,out dev)==0,"open");opened=true;
            Check(PassThruConnect(dev,6,0x100,500000,out hs)==0,"HS connect");
            Check(PassThruConnect(dev,6,0x100,125000,out ls)==0 && ls!=hs,"LS connect");
            byte[][] replies={
                new byte[]{0x62,0x12,0x0D,0xA0,0},
                new byte[]{0x62,0xD9,0x98,0x60},
                new byte[]{0x62,0xD9,0x9B,0x60},
                new byte[]{0x62,0xDA,0x48,0,0,0,0},
                new byte[]{0x62,0xF4,0x0C,0,0},
                new byte[]{0x62,0xF4,0x0D,0},
                new byte[]{0x62,0xF4,0x0F,0x3C}
            };
            byte[] nrc={0x7F,0x22,0x31};
            foreach(uint flags in new uint[]{0x100,0x140}){
                foreach(byte[] reply in replies){
                    Send(hs,Tx,flags,new byte[]{0x22,reply[1],reply[2]});
                    Expect(hs,enabled?reply:nrc);
                }
            }
            Console.WriteLine("B3A310_DID_14_EXCHANGES_PASS enabled="+enabled);
            Send(hs,Tx,0x140,new byte[]{0x22,0x12,0x0E});Expect(hs,nrc);
            Console.WriteLine("B3A310_UNKNOWN_DID_PASS");
            Send(ls,Tx,0x140,new byte[]{0x22,0x12,0x0D});Empty(ls);Empty(hs);
            Send(hs,0x18DA11F1,0x140,new byte[]{0x22,0x12,0x0D});Empty(hs);
            Console.WriteLine("B3A310_WRONG_BUS_AND_ID_PASS");
            byte[] part=System.Text.Encoding.ASCII.GetBytes("LAB-ECM-HW");
            byte[] idReply=new byte[3+part.Length];idReply[0]=0x62;idReply[1]=0xF1;idReply[2]=0x87;
            Array.Copy(part,0,idReply,3,part.Length);
            Send(hs,Tx,0x140,new byte[]{0x22,0xF1,0x87});Expect(hs,idReply);
            Console.WriteLine("B3A310_EXISTING_F187_PASS");
            Empty(hs);Empty(ls);
        }finally{
            bool clean=true;
            if(ls!=0)clean &= PassThruDisconnect(ls)==0;
            if(hs!=0)clean &= PassThruDisconnect(hs)==0;
            if(opened)clean &= PassThruClose(dev)==0;
            Check(clean,"cleanup");
        }
        Console.WriteLine("B3A310_NATIVE_PASS enabled="+enabled);
    }
}
'@
    $source=$source.Replace('__DLL__',$isolated.Replace('"','""'))
    Add-Type -TypeDefinition $source -Language CSharp
    [EcmLiveNative]::Run([bool]$Enabled)
} finally {
    $env:LOCALAPPDATA=$savedLocal
    $env:TEMP=$savedTemp
    $env:TMP=$savedTmp
}
