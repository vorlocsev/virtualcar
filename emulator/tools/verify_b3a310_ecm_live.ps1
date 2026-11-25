# B3A310: isolated x86 DLL test; no original VIDA, registry or physical adapter.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$Enabled,
    [switch]$Expanded,
    [ValidateSet('0','1','2','3','4','invalid')][string]$Scenario='0',
    [switch]$BatterySync,
    [switch]$RemProbe,
    [switch]$RemSync,
    [switch]$SupplyProbe,
    [switch]$SupplySync,
    [switch]$Dynamic,
    [switch]$DynamicProbe
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
BatteryMv=12345
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
if ($Expanded) { $profile += [Environment]::NewLine + "[B3A314_EcmExtendedLiveLab]" + [Environment]::NewLine + "Enabled=1" }
if ($Scenario -ne "0") { $profile += [Environment]::NewLine + "[B3A316_EcmScenarioLab]" + [Environment]::NewLine + "Enabled=1" + [Environment]::NewLine + "State=$Scenario" }
if ($BatterySync) { $profile += [Environment]::NewLine + "[B3A319_BatterySyncLab]" + [Environment]::NewLine + "Enabled=1" }
if ($RemProbe) { $profile += [Environment]::NewLine + "[B3A267_CurrentDataLab]" + [Environment]::NewLine + "Enabled=1" }
if ($RemSync) { $profile += [Environment]::NewLine + "[B3A320_RemVoltageSyncLab]" + [Environment]::NewLine + "Enabled=1" }
if ($SupplyProbe) {
    if (-not $RemProbe) { throw 'SupplyProbe requires RemProbe' }
    $profile=$profile.Replace('ECUCount=1','ECUCount=2').Replace('StrictJ2534Filters=0',"StrictJ2534Filters=0"+[Environment]::NewLine+"EnableGGDCemLab=1")
    $profile += [Environment]::NewLine + "[ECU1]" + [Environment]::NewLine + "RequestId=18DA50F1" + [Environment]::NewLine + "ResponseId=18DAF150" + [Environment]::NewLine + "ExpectedBaud=500000" + [Environment]::NewLine + "PartNumber=LAB-CEM-HW"
}
if ($SupplySync) { $profile += [Environment]::NewLine + "[B3A324_SupplyVoltageSyncLab]" + [Environment]::NewLine + "Enabled=1" }
if ($DynamicProbe -and -not ($Dynamic -and $Enabled -and $Expanded -and $BatterySync -and $RemProbe -and $RemSync -and $SupplyProbe -and $SupplySync)) { throw 'DynamicProbe requires all dynamic prerequisites' }
if ($Dynamic) { $profile += [Environment]::NewLine + "[B3A329_DynamicEcmLab]" + [Environment]::NewLine + "Enabled=1" }
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
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)] static extern uint PassThruIoctl(uint id,uint ioctl,IntPtr input,out uint output);
    static void Check(bool ok,string gate){if(!ok)throw new Exception(gate);}
    static void Send(uint ch,uint id,uint flags,byte[] payload,uint protocol=6){
        Msg m=new Msg();m.ProtocolID=protocol;m.TxFlags=flags;m.DataSize=(uint)payload.Length+4;m.Data=new byte[4128];
        m.Data[0]=(byte)(id>>24);m.Data[1]=(byte)(id>>16);m.Data[2]=(byte)(id>>8);m.Data[3]=(byte)id;
        Array.Copy(payload,0,m.Data,4,payload.Length);
        uint n=1;Check(PassThruWriteMsgs(ch,ref m,ref n,100)==0 && n==1,"write");
    }
    static void Empty(uint ch){
        IntPtr p=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try{uint n=1;Check(PassThruReadMsgs(ch,p,ref n,0)==16 && n==0,"unexpected RX");}
        finally{Marshal.FreeHGlobal(p);}
    }
    static void Expect(uint ch,byte[] payload,uint rx=Rx){
        IntPtr p=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try{
            uint n=1;Check(PassThruReadMsgs(ch,p,ref n,200)==0 && n==1,"missing RX");
            Msg m=(Msg)Marshal.PtrToStructure(p,typeof(Msg));
            Check(m.ProtocolID==6 && m.RxStatus==0x100 && m.DataSize==payload.Length+4 && m.ExtraDataIndex==m.DataSize,"RX metadata");
            uint id=((uint)m.Data[0]<<24)|((uint)m.Data[1]<<16)|((uint)m.Data[2]<<8)|m.Data[3];
            Check(id==rx,"RX CAN ID");
            for(int i=0;i<payload.Length;i++)Check(m.Data[4+i]==payload[i],"RX payload");
        }finally{Marshal.FreeHGlobal(p);}
        Empty(ch);
    }
    static void ExpectD2(uint ch,byte[] payload){
        IntPtr p=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try{
            uint n=1;Check(PassThruReadMsgs(ch,p,ref n,200)==0 && n==1,"missing D2 RX");
            Msg m=(Msg)Marshal.PtrToStructure(p,typeof(Msg));
            Check(m.ProtocolID==5 && m.DataSize==12,"D2 RX metadata");
            uint id=((uint)m.Data[0]<<24)|((uint)m.Data[1]<<16)|((uint)m.Data[2]<<8)|m.Data[3];
            Check(id==0x00800003,"D2 RX ID");
            for(int i=0;i<8;i++)Check(m.Data[4+i]==payload[i],"D2 RX payload index="+i+" expected="+BitConverter.ToString(payload)+" actual="+BitConverter.ToString(m.Data,4,8));
        }finally{Marshal.FreeHGlobal(p);}
        Empty(ch);
    }
    // B3A330: independent elapsed-time oracle, including Open and request timing uncertainty.
    [DllImport("kernel32.dll")] static extern uint GetTickCount();
    static readonly int[] Times={0,2000,4000,60000,180000};
    static readonly int[] Volts={12500,10500,14200,14000,14000};
    static readonly int[] Rpm={0,200,1100,900,700};
    static readonly int[] Coolant={20,20,20,60,90};
    static readonly int[] Maf={0,200,900,700,550};
    static readonly int[] Load={0,150,250,200,180};
    static int Interpolate(int[] points,int t){
        int i=0;
        while(i<3 && t>=Times[i+1])i++;
        int pos=Math.Min(t,Times[i+1])-Times[i];
        return points[i]+(points[i+1]-points[i])*pos/(Times[i+1]-Times[i]);
    }
    static uint FloatBits(float value){return BitConverter.ToUInt32(BitConverter.GetBytes(value),0);}
    static uint ExpectedRaw(int kind,int t){
        int mv=Interpolate(Volts,t),rpm=Interpolate(Rpm,t);
        switch(kind){
            case 0:return (uint)mv;
            case 1:return (uint)(rpm*4);
            case 2:return FloatBits(rpm);
            case 3:return (uint)((mv*65536+10000)/20000);
            case 4:return (uint)((mv+62)/125);
            case 5:return (uint)((mv*65535+12500)/25000);
            case 6:return (uint)((mv*64+500)/1000);
            case 7:return (uint)((mv+125)/250);
            case 8:return (uint)((Interpolate(Coolant,t)+40)*8+2)/5;
            case 9:return FloatBits((float)(Interpolate(Maf,t)/100.0));
            case 10:return (uint)((Interpolate(Load,t)*255+500)/1000);
            default:throw new Exception("unknown timeline kind");
        }
    }
    static int Elapsed(uint now,uint epoch){return (int)Math.Min(180000u,unchecked(now-epoch));}
    static void AssertTimeline(int kind,uint raw,uint openBefore,uint openAfter,uint txBefore,uint rxAfter){
        int lo=Elapsed(txBefore,openAfter),hi=Elapsed(rxAfter,openBefore);
        Check(lo<=hi,"timeline clock range");
        uint min=UInt32.MaxValue,max=0;
        for(int t=lo;t<=hi;t++){
            uint expected=ExpectedRaw(kind,t);
            min=Math.Min(min,expected);max=Math.Max(max,expected);
        }
        Check(raw>=min && raw<=max,"timeline kind="+kind+" raw="+raw+" expected="+min+".."+max+" ms="+lo+".."+hi);
    }
    static uint DynamicRead(uint ch,uint tx,uint rx,uint protocol,byte[] request,byte[] header,int length,int tail,int kind,uint openBefore,uint openAfter){
        uint before=GetTickCount();
        Send(ch,tx,0x140,request,protocol);
        IntPtr ptr=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        uint raw=0,after;
        try{
            uint count=1;
            Check(PassThruReadMsgs(ch,ptr,ref count,200)==0 && count==1,"dynamic missing RX");
            after=GetTickCount();
            Msg m=(Msg)Marshal.PtrToStructure(ptr,typeof(Msg));
            uint id=((uint)m.Data[0]<<24)|((uint)m.Data[1]<<16)|((uint)m.Data[2]<<8)|m.Data[3];
            Check(m.ProtocolID==protocol && id==rx && m.DataSize==4+header.Length+length+tail,"dynamic RX metadata");
            if(protocol==6)Check(m.RxStatus==0x100 && m.ExtraDataIndex==m.DataSize,"dynamic ISO metadata");
            for(int i=0;i<header.Length;i++)Check(m.Data[4+i]==header[i],"dynamic RX header");
            for(int i=0;i<length;i++)raw=(raw<<8)|m.Data[4+header.Length+i];
            for(int i=0;i<tail;i++)Check(m.Data[4+header.Length+length+i]==0,"dynamic D2 padding");
        }finally{Marshal.FreeHGlobal(ptr);}
        AssertTimeline(kind,raw,openBefore,openAfter,before,after);Empty(ch);
        return raw;
    }
    static uint DynamicVoltage(uint ch,uint openBefore,uint openAfter){
        uint raw,before=GetTickCount();
        Check(PassThruIoctl(ch,3,IntPtr.Zero,out raw)==0,"dynamic READ_VBATT");
        AssertTimeline(0,raw,openBefore,openAfter,before,GetTickCount());return raw;
    }
    static uint DynamicDid(uint ch,uint tx,uint rx,byte a,byte b,int len,int kind,uint openBefore,uint openAfter){
        return DynamicRead(ch,tx,rx,6,new byte[]{0x22,a,b},new byte[]{0x62,a,b},len,0,kind,openBefore,openAfter);
    }
    static uint DynamicD2(uint ch,byte target,byte a,byte b,int len,int kind,uint openBefore,uint openAfter){
        // D2 exact request uses 0x100; ISO15765_FRAME_PAD is not a CAN flag.
        uint before=GetTickCount();
        Send(ch,0x000FFFFE,0x100,new byte[]{0xCD,target,0xA6,a,b,1,0,0},5);
        IntPtr ptr=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        uint raw=0,after;
        try{
            uint count=1;Check(PassThruReadMsgs(ch,ptr,ref count,200)==0&&count==1,"dynamic D2 missing RX");after=GetTickCount();
            Msg m=(Msg)Marshal.PtrToStructure(ptr,typeof(Msg));
            Check(m.ProtocolID==5&&m.DataSize==12&&m.Data[0]==0&&m.Data[1]==0x80&&m.Data[2]==0&&m.Data[3]==3,"dynamic D2 metadata");
            Check(m.Data[4]==0xCC+len&&m.Data[5]==target&&m.Data[6]==0xE6&&m.Data[7]==a&&m.Data[8]==b,"dynamic D2 header");
            for(int i=0;i<len;i++)raw=(raw<<8)|m.Data[9+i];
            for(int i=9+len;i<12;i++)Check(m.Data[i]==0,"dynamic D2 padding");
        }finally{Marshal.FreeHGlobal(ptr);}
        AssertTimeline(kind,raw,openBefore,openAfter,before,after);Empty(ch);return raw;
    }
    static void WaitPhase(uint epoch,uint target){
        while(unchecked(GetTickCount()-epoch)<target)System.Threading.Thread.Sleep(10);
    }
    public static void RunDynamic(){
        Check(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,"dynamic x86 ABI");
        for(int session=0;session<2;session++){
            uint dev=0,hs=0,ls=0,can=0;bool opened=false;
            uint openBefore=GetTickCount(),openAfter;
            try{
                Check(PassThruOpen(IntPtr.Zero,out dev)==0,"dynamic open");opened=true;openAfter=GetTickCount();
                Check(PassThruConnect(dev,6,0x100,500000,out hs)==0,"dynamic HS connect");
                Check(PassThruConnect(dev,6,0x100,125000,out ls)==0 && ls!=hs,"dynamic LS connect");
                Check(PassThruConnect(dev,5,0x100,125000,out can)==0 && can!=hs && can!=ls,"dynamic CAN connect");
                uint[] phases=session==0?new uint[]{750,2000,5000,60000,180000,181000}:new uint[]{750};
                foreach(uint phase in phases){
                    WaitPhase(openAfter,phase);
                    uint v=DynamicVoltage(hs,openBefore,openAfter);DynamicVoltage(ls,openBefore,openAfter);
                    uint rpm=DynamicDid(hs,Tx,Rx,0xF4,0x0C,2,1,openBefore,openAfter);
                    DynamicDid(hs,Tx,Rx,0xDA,0x48,4,2,openBefore,openAfter);
                    DynamicDid(hs,Tx,Rx,0x12,0x0D,2,3,openBefore,openAfter);
                    DynamicD2(can,0x46,0xD0,0xD4,1,4,openBefore,openAfter);
                    DynamicD2(can,0x46,0x1A,0x02,2,5,openBefore,openAfter);
                    DynamicD2(can,0x29,0x00,0x80,2,6,openBefore,openAfter);
                    DynamicDid(hs,0x18DA50F1,0x18DAF150,0xDD,0x02,1,7,openBefore,openAfter);
                    DynamicDid(hs,Tx,Rx,0xD9,0x9B,1,8,openBefore,openAfter);
                    DynamicDid(hs,Tx,Rx,0xD9,0x94,4,9,openBefore,openAfter);
                    DynamicDid(hs,Tx,Rx,0xF4,0x43,2,10,openBefore,openAfter);
                    if(phase==750)Check(v>11000 && v<12500 && rpm<800,"initial/reopened phase");
                    if(phase==2000)Check(v<11500,"crank voltage dip");
                    if(phase==5000)Check(v>13500 && rpm>3600,"post-start phase");
                    if(phase>=180000)Check(v==14000 && rpm==2800,"terminal latch");
                    Send(hs,0x18DA50F1,0x140,new byte[]{0x22,0xA4,0x5F});
                    Expect(hs,new byte[]{0x62,0xA4,0x5F,0x04},0x18DAF150);
                    Send(ls,Tx,0x140,new byte[]{0x22,0x12,0x0D});Empty(ls);Empty(hs);
                    Send(hs,Tx,0x140,new byte[]{0x22,0x12,0x0E});Expect(hs,new byte[]{0x7F,0x22,0x31});
                    Console.WriteLine("B3A330_NATIVE_PHASE_PASS session="+session+" ms="+phase+" voltage="+v+" rpm="+rpm/4.0);
                }
            }finally{
                bool clean=true;
                if(can!=0)clean &= PassThruDisconnect(can)==0;
                if(ls!=0)clean &= PassThruDisconnect(ls)==0;
                if(hs!=0)clean &= PassThruDisconnect(hs)==0;
                if(opened)clean &= PassThruClose(dev)==0;
                Check(clean,"dynamic cleanup");
            }
        }
        Console.WriteLine("B3A330_NATIVE_DYNAMIC_PASS");
    }
    static void ApplyScenario(byte[][] replies,uint[] values,int offset){
        for(int i=0;i<replies.Length;i++){
            byte[] reply=replies[i];
            uint raw=values[offset+i];
            for(int j=3;j<reply.Length;j++)reply[j]=(byte)(raw>>(8*(reply.Length-1-j)));
        }
    }
    public static void Run(bool enabled,bool expanded,int scenario,bool batterySync,bool remProbe,bool remSync,bool supplyProbe,bool supplySync){
        uint[][] states={
            new uint[]{0xa000,0x60,0x60,0x0,0x0,0x0,0x3c,0x0,0x0,0x60,0x0,0x3c,0x0,0x64,0x0,0x0,0x64,0xc8,0x3333},
            new uint[]{0x8666,0x60,0x60,0x43480000,0x320,0x0,0x3c,0x0,0x0,0x60,0x26,0x3c,0xc8,0x64,0x0,0x0,0x5a,0xc8,0x2e14},
            new uint[]{0xb5c3,0x60,0x60,0x44898000,0x1130,0x0,0x3c,0x0,0x0,0x68,0x40,0x3c,0x384,0x64,0x0,0x0,0x2d,0xc8,0x170a},
            new uint[]{0xb333,0x68,0xa0,0x44610000,0xe10,0x0,0x41,0x0,0x0,0x78,0x33,0x64,0x2bc,0x64,0x0,0x0,0x26,0xc8,0x1375},
            new uint[]{0xb333,0x70,0xd0,0x442f0000,0xaf0,0x0,0x46,0x0,0x0,0x88,0x2e,0x82,0x226,0x64,0x0,0x0,0x23,0xc8,0x11ec}
        };
        Check(scenario>=0 && scenario<states.Length,"scenario index");
        Check(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,"x86 ABI");
        uint dev=0,hs=0,ls=0,can=0;bool opened=false;
        try{
            Check(PassThruOpen(IntPtr.Zero,out dev)==0,"open");opened=true;
            Check(PassThruConnect(dev,6,0x100,500000,out hs)==0,"HS connect");
            Check(PassThruConnect(dev,6,0x100,125000,out ls)==0 && ls!=hs,"LS connect");
            uint[] batteryMv={12500,10500,14200,14000,14000};
            uint expectedMv=batterySync&&enabled?batteryMv[scenario]:12345u;
            uint measured;
            Check(PassThruIoctl(hs,3,IntPtr.Zero,out measured)==0 && measured==expectedMv,"HS READ_VBATT");
            Check(PassThruIoctl(ls,3,IntPtr.Zero,out measured)==0 && measured==expectedMv,"LS READ_VBATT");
            Console.WriteLine("B3A319_READ_VBATT_PASS state="+scenario+" sync="+batterySync+" baseline="+enabled+" mV="+expectedMv);
            if(remProbe){
                Check(PassThruConnect(dev,5,0x100,125000,out can)==0 && can!=hs && can!=ls,"REM CAN connect");
                byte[] values={0x64,0x54,0x72,0x70,0x70};
                byte expected=remSync&&batterySync&&enabled?values[scenario]:(byte)0x64;
                Send(can,0x000FFFFE,0x100,new byte[]{0xCD,0x46,0xA6,0xD0,0xD4,1,0,0},5);
                ExpectD2(can,new byte[]{0xCD,0x46,0xE6,0xD0,0xD4,expected,0,0});
                Send(can,0x000FFFFE,0x100,new byte[]{0xCD,0x40,0xA6,0x1A,0x04,1,0,0},5);
                ExpectD2(can,new byte[]{0xCD,0x40,0xE6,0x1A,0x04,6,0,0});
                Console.WriteLine("B3A320_NATIVE_REM_PASS state="+scenario+" raw="+expected+" remSync="+remSync+" batterySync="+batterySync+" baseline="+enabled);
                if(supplyProbe){
                    int state=supplySync&&batterySync&&enabled?scenario:0;
                    uint[] rem={0x8000,0x6B85,0x9168,0x8F5C,0x8F5C};
                    uint[] ccm={0x0320,0x02A0,0x038D,0x0380,0x0380};
                    byte[] cem={0x32,0x2A,0x39,0x38,0x38};
                    Send(can,0x000FFFFE,0x100,new byte[]{0xCD,0x46,0xA6,0x1A,0x02,1,0,0},5);
                    ExpectD2(can,new byte[]{0xCE,0x46,0xE6,0x1A,0x02,(byte)(rem[state]>>8),(byte)rem[state],0});
                    Send(can,0x000FFFFE,0x100,new byte[]{0xCD,0x29,0xA6,0x00,0x80,1,0,0},5);
                    ExpectD2(can,new byte[]{0xCE,0x29,0xE6,0x00,0x80,(byte)(ccm[state]>>8),(byte)ccm[state],0});
                    foreach(uint flags in new uint[]{0x100,0x140}){
                        Send(hs,0x18DA50F1,flags,new byte[]{0x22,0xDD,0x02});
                        Expect(hs,new byte[]{0x62,0xDD,0x02,cem[state]},0x18DAF150);
                        Send(hs,0x18DA50F1,flags,new byte[]{0x22,0xA4,0x5F});
                        Expect(hs,new byte[]{0x62,0xA4,0x5F,0x04},0x18DAF150);
                    }
                    Send(ls,0x18DA50F1,0x140,new byte[]{0x22,0xDD,0x02});Empty(ls);Empty(hs);
                    Send(hs,0x18DA50F1,0x140,new byte[]{0x22,0xDD,0x03});Empty(hs);
                    Console.WriteLine("B3A324_NATIVE_SUPPLY_PASS state="+scenario+" effective="+state);
                }
            }
            byte[][] replies={
                new byte[]{0x62,0x12,0x0D,0xA0,0},
                new byte[]{0x62,0xD9,0x98,0x60},
                new byte[]{0x62,0xD9,0x9B,0x60},
                new byte[]{0x62,0xDA,0x48,0,0,0,0},
                new byte[]{0x62,0xF4,0x0C,0,0},
                new byte[]{0x62,0xF4,0x0D,0},
                new byte[]{0x62,0xF4,0x0F,0x3C}
            };
            ApplyScenario(replies,states[scenario],0);
            byte[] nrc={0x7F,0x22,0x31};
            foreach(uint flags in new uint[]{0x100,0x140}){
                foreach(byte[] reply in replies){
                    Send(hs,Tx,flags,new byte[]{0x22,reply[1],reply[2]});
                    Expect(hs,enabled?reply:nrc);
                }
            }
            Console.WriteLine("B3A310_DID_14_EXCHANGES_PASS enabled="+enabled);
            byte[][] extra={
                new byte[]{0x62,0xD9,0xAC,0x00,0x00},
                new byte[]{0x62,0xD9,0xAD,0x00,0x00},
                new byte[]{0x62,0xD9,0xB8,0x60},
                new byte[]{0x62,0xF4,0x04,0x00},
                new byte[]{0x62,0xF4,0x05,0x3C},
                new byte[]{0x62,0xF4,0x10,0x00,0x00},
                new byte[]{0x62,0xF4,0x33,0x64},
                new byte[]{0x62,0xF4,0x49,0x00},
                new byte[]{0x62,0xF4,0x4A,0x00},
                new byte[]{0x62,0xF4,0x0B,0x64},
                new byte[]{0x62,0xD9,0xA4,0xC8},
                new byte[]{0x62,0xDA,0x47,0x33,0x33}
            };
            ApplyScenario(extra,states[scenario],7);
            foreach(uint flags in new uint[]{0x100,0x140}){
                foreach(byte[] reply in extra){
                    Send(hs,Tx,flags,new byte[]{0x22,reply[1],reply[2]});
                    Expect(hs,expanded?reply:nrc);
                }
            }
            Send(hs,Tx,0x140,new byte[]{0x22,0xD9,0xAE});Expect(hs,nrc);
            Send(ls,Tx,0x140,new byte[]{0x22,0xD9,0xAC});Empty(ls);Empty(hs);
            Send(hs,0x18DA11F1,0x140,new byte[]{0x22,0xD9,0xAC});Empty(hs);
            Console.WriteLine("B3A314_DID_24_EXCHANGES_PASS expanded="+expanded+" baseline="+enabled);
            uint[][] observedValues={new uint[]{0,0},new uint[]{38,0x40000000},new uint[]{64,0x41100000},new uint[]{51,0x40E00000},new uint[]{46,0x40B00000}};
            byte[][] observedReplies={new byte[]{0x62,0xF4,0x43,0,0},new byte[]{0x62,0xD9,0x94,0,0,0,0}};
            ApplyScenario(observedReplies,observedValues[scenario],0);
            foreach(uint flags in new uint[]{0x100,0x140}){
                foreach(byte[] reply in observedReplies){
                    Send(hs,Tx,flags,new byte[]{0x22,reply[1],reply[2]});
                    Expect(hs,expanded?reply:nrc);
                }
            }
            Console.WriteLine("B3A318_DID_4_EXCHANGES_PASS expanded="+expanded+" state="+scenario);
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
            if(can!=0)clean &= PassThruDisconnect(can)==0;
            if(ls!=0)clean &= PassThruDisconnect(ls)==0;
            if(hs!=0)clean &= PassThruDisconnect(hs)==0;
            if(opened)clean &= PassThruClose(dev)==0;
            Check(clean,"cleanup");
        }
        Console.WriteLine("B3A316_NATIVE_SCENARIO_PASS state="+scenario+" baseline="+enabled+" expanded="+expanded);
        Console.WriteLine("B3A310_NATIVE_PASS enabled="+enabled);
    }
}
'@
    $source=$source.Replace('__DLL__',$isolated.Replace('"','""'))
    Add-Type -TypeDefinition $source -Language CSharp
    $expectedState=0
    if ($Scenario -ne 'invalid') { $expectedState=[int]$Scenario }
    if ($DynamicProbe) { [EcmLiveNative]::RunDynamic() }
    else { [EcmLiveNative]::Run([bool]$Enabled,[bool]$Expanded,$expectedState,[bool]$BatterySync,[bool]$RemProbe,[bool]$RemSync,[bool]$SupplyProbe,[bool]$SupplySync) }
} finally {
    $env:LOCALAPPDATA=$savedLocal
    $env:TEMP=$savedTemp
    $env:TMP=$savedTmp
}
