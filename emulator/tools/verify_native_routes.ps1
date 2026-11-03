# Native x86 DLL regression. Synthetic profile, no registration or physical J2534.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$ApiOutcomeRegression
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    $forward = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath,'-DllPath',$DllPath,'-OutputDirectory',$OutputDirectory)
    if ($ApiOutcomeRegression) { $forward += '-ApiOutcomeRegression' }
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" @forward
    exit $LASTEXITCODE
}
$dll = (Resolve-Path -LiteralPath $DllPath).Path
$directory = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $directory) { throw 'Output directory must be new; refusing to overwrite files' }
[void][IO.Directory]::CreateDirectory($directory)
$isolatedDll = Join-Path $directory 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $dll -Destination $isolatedDll
# Deliberately no CEM node or positive CEM fixture.
$profile = @'
; SYNTHETIC native route regression, not vehicle evidence.
[Vehicle]
VIN=YV1CZ0002A0000001
ECUCount=1
BatteryMv=12500
[ECU0]
RequestId=7E0
ResponseId=7E8
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
BackendTelemetryEnabled=1
'@
[IO.File]::WriteAllText((Join-Path $directory 'virtualcar.ini'), $profile, [Text.Encoding]::ASCII)
$savedLocal = $env:LOCALAPPDATA
$savedTemp = $env:TEMP
$savedTmp = $env:TMP
try {
    # The DLL uses process environment variables for both logs. Do not touch
    # the user's backend log, installed profile, registry, or adapter selection.
    $env:LOCALAPPDATA = $directory
    $env:TEMP = $directory
    $env:TMP = $directory
    $source = @'
using System;
using System.Runtime.InteropServices;
public static class NativeRouteCheck {
    const string Library = @"__ISOLATED_DLL__";
    [StructLayout(LayoutKind.Sequential)] public struct Msg {
        public uint ProtocolID, RxStatus, TxFlags, Timestamp, DataSize, ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst=4128)] public byte[] Data;
    }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi, ExactSpelling=true)]
    static extern IntPtr GetProcAddress(IntPtr module, string name);
    [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr module);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruOpen(IntPtr name, out uint device);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruClose(uint device);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruConnect(uint device, uint protocol, uint flags, uint baud, out uint channel);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruDisconnect(uint channel);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruWriteMsgs(uint channel, ref Msg msg, ref uint count, uint timeout);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruReadMsgs(uint channel, IntPtr msg, ref uint count, uint timeout);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStartMsgFilter(uint channel, uint type, ref Msg mask, ref Msg pattern, IntPtr flow, ref uint filter);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStartPeriodicMsg(uint channel, ref Msg msg, ref uint period, uint interval);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStopMsgFilter(uint channel, uint filter);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStopPeriodicMsg(uint channel, uint period);
    [StructLayout(LayoutKind.Sequential)] struct ConfigList { public uint Count; public IntPtr Entries; }
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruIoctl(uint channel, uint ioctl, ref ConfigList config, IntPtr output);
    static void Check(bool condition, string gate) { if (!condition) throw new Exception(gate); }
    static void Silent(uint channel, uint protocol, uint id, byte[] payload) {
        Msg msg = new Msg(); msg.ProtocolID=protocol; msg.DataSize=(uint)payload.Length+4;
        msg.TxFlags=id>0x7ff ? 0x100u : 0u; msg.Data=new byte[4128];
        msg.Data[0]=(byte)(id>>24); msg.Data[1]=(byte)(id>>16);
        msg.Data[2]=(byte)(id>>8); msg.Data[3]=(byte)id;
        Array.Copy(payload,0,msg.Data,4,payload.Length);
        uint count=1; Check(PassThruWriteMsgs(channel,ref msg,ref count,10)==0 && count==1,"TX rejected");
        Empty128(channel);
    }
    static void Empty128(uint channel) {
        int bytes=Marshal.SizeOf(typeof(Msg))*128;
        IntPtr buffer=Marshal.AllocHGlobal(bytes);
        try { uint count=128; Check(PassThruReadMsgs(channel,buffer,ref count,0)==16 && count==0,"Unexpected RX or READ128 failure"); }
        finally { Marshal.FreeHGlobal(buffer); }
    }
    public static void RunCanPsConfigProbe(bool enabled) {
        uint device=0,channel=0;
        Check(PassThruOpen(IntPtr.Zero,out device)==0,"PS Open failed");
        IntPtr entry=Marshal.AllocHGlobal(8);
        try {
            uint status=PassThruConnect(device,0x8004,0x900,125000,out channel);
            Check(status==(enabled ? 0u : 3u),"PS opt-in not respected");
            if(!enabled) return;
            ConfigList list=new ConfigList(); list.Count=1; list.Entries=entry;
            Marshal.WriteInt32(entry,0,0x8001); Marshal.WriteInt32(entry,4,0);
            Check(PassThruIoctl(channel,1,ref list,IntPtr.Zero)==0 && Marshal.ReadInt32(entry,4)==0,"PS initial hint wrong");
            Marshal.WriteInt32(entry,4,0x030b);
            Check(PassThruIoctl(channel,2,ref list,IntPtr.Zero)==0,"PS SET hint failed");
            Marshal.WriteInt32(entry,4,0);
            Check(PassThruIoctl(channel,1,ref list,IntPtr.Zero)==0 && Marshal.ReadInt32(entry,4)==0x030b,"PS GET hint failed");
            Marshal.WriteInt32(entry,4,0x060e);
            Check(PassThruIoctl(channel,2,ref list,IntPtr.Zero)==1,"PS rebind not rejected");
            Check(PassThruIoctl(channel,1,ref list,IntPtr.Zero)==0 && Marshal.ReadInt32(entry,4)==0x030b,"PS rebind changed hint");
            // SYNTHETIC B9FB envelope: classified before rejection, never transmitted.
            Msg msg=new Msg(); msg.ProtocolID=0x8004; msg.DataSize=12; msg.TxFlags=0x100; msg.Data=new byte[4128];
            Array.Copy(new byte[]{0,0x0f,0xff,0xfe,0xcb,0x40,0xb9,0xfb,0,0,0,0},msg.Data,12);
            uint count=1;
            Check(PassThruWriteMsgs(channel,ref msg,ref count,0)==1 && count==0,"PS write was not blocked");
            Msg mask=new Msg(); mask.ProtocolID=0x8004; mask.DataSize=4; mask.TxFlags=0x100; mask.Data=new byte[4128];
            Array.Copy(new byte[]{0x1f,0xff,0xff,0xff},mask.Data,4);
            Msg pattern=new Msg(); pattern.ProtocolID=0x8004; pattern.DataSize=4; pattern.TxFlags=0x100; pattern.Data=new byte[4128];
            Array.Copy(new byte[]{0,0x80,0,3},pattern.Data,4);
            uint filter=0xc0deface;
            Check(PassThruStartMsgFilter(channel,1,ref mask,ref pattern,IntPtr.Zero,ref filter)==1 && filter==0xc0deface,"PS filter was not blocked");
            Array.Copy(new byte[]{0,0x0f,0xff,0xfe,0xd8,0,0,0,0,0,0,0},msg.Data,12);
            uint period=0xc0deface;
            Check(PassThruStartPeriodicMsg(channel,ref msg,ref period,4000)==1 && period==0xc0deface,"PS periodic was not blocked");
            Empty128(channel);
            Console.WriteLine("PASS native CAN_PS configuration-only opt-in/roundtrip/rebind/write/RX checks");
        } finally {
            Marshal.FreeHGlobal(entry);
            if(channel!=0) Check(PassThruDisconnect(channel)==0,"PS disconnect failed");
            Check(PassThruClose(device)==0,"PS close failed");
        }
    }
    // SYNTHETIC local API outcomes only: no CAN delivery or ECU acknowledgement.
    public static void RunCanPsApiOutcome(uint mode, bool enabled) {
        uint device=0,channel=0;
        Check(PassThruOpen(IntPtr.Zero,out device)==0,"Outcome Open failed");
        IntPtr entry=Marshal.AllocHGlobal(8);
        try {
            Check(PassThruConnect(device,0x8004,0x900,125000,out channel)==(enabled?0u:3u),"Outcome master switch failed");
            if(!enabled) return;
            ConfigList list=new ConfigList(); list.Count=1; list.Entries=entry;
            Marshal.WriteInt32(entry,0,0x8001); Marshal.WriteInt32(entry,4,0x030b);
            Check(PassThruIoctl(channel,2,ref list,IntPtr.Zero)==0,"Outcome pins failed");
            Msg mask=new Msg(); mask.ProtocolID=0x8004; mask.DataSize=4; mask.Data=new byte[4128];
            Array.Copy(new byte[]{0xff,0xff,0xff,0xff},mask.Data,4);
            Msg pattern=new Msg(); pattern.ProtocolID=0x8004; pattern.DataSize=4; pattern.Data=new byte[4128];
            Array.Copy(new byte[]{0,0,7,0xe8},pattern.Data,4);
            uint filter=0xc0deface;
            Check(PassThruStartMsgFilter(channel,1,ref mask,ref pattern,IntPtr.Zero,ref filter)==((mode&1)!=0?0u:1u),"Outcome filter bit failed");
            Check((mode&1)!=0 ? filter>0 && filter<0x80000000 : filter==0xc0deface,"Outcome filter output failed");
            Msg msg=new Msg(); msg.ProtocolID=0x8004; msg.TxFlags=0x100; msg.DataSize=12; msg.Data=new byte[4128];
            Array.Copy(new byte[]{0,0x0f,0xff,0xfe,0xd8,0,0,0,0,0,0,0},msg.Data,12);
            uint count=1;
            Check(PassThruWriteMsgs(channel,ref msg,ref count,0)==((mode&2)!=0?0u:1u) && count==((mode&2)!=0?1u:0u),"Outcome write bit failed");
            uint period=0xc0deface;
            Check(PassThruStartPeriodicMsg(channel,ref msg,ref period,1000)==((mode&4)!=0?0u:1u),"Outcome periodic bit failed");
            Check((mode&4)!=0 ? period>0 && period<0x80000000 : period==0xc0deface,"Outcome periodic output failed");
            Empty128(channel);
            if(mode==7) {
                Array.Copy(new byte[]{0,0x0f,0xff,0xfe,0xcb,0x40,0xb9,0xfb,0,0,0,0},msg.Data,12);
                count=1;
                Check(PassThruWriteMsgs(channel,ref msg,ref count,0)==1 && count==0,"Outcome allowed a general diagnostic write");
                Empty128(channel);
            }
            // Cleanup must work after a DATA_RATE change, without enabling a transport.
            Marshal.WriteInt32(entry,0,1); Marshal.WriteInt32(entry,4,500000);
            Check(PassThruIoctl(channel,2,ref list,IntPtr.Zero)==0,"Outcome baud update failed");
            if((mode&1)!=0) {
                Check(PassThruStopMsgFilter(channel,filter)==0,"Outcome StopFilter failed");
                Check(PassThruStopMsgFilter(channel,filter)==22,"Outcome stale filter handle accepted");
            }
            if((mode&4)!=0) {
                Check(PassThruStopPeriodicMsg(channel,period)==0,"Outcome StopPeriodic failed");
                Check(PassThruStopPeriodicMsg(channel,period)==13,"Outcome stale periodic handle accepted");
            }
            Check(PassThruIoctl(channel,10,ref list,IntPtr.Zero)==0,"Outcome ClearFilter failed");
            Check(PassThruIoctl(channel,9,ref list,IntPtr.Zero)==0,"Outcome ClearPeriodic failed");
            Empty128(channel);
            Console.WriteLine("PASS native API-outcome mask="+mode+"; local resources only, no transport");
        } finally {
            Marshal.FreeHGlobal(entry);
            if(channel!=0) Check(PassThruDisconnect(channel)==0,"Outcome disconnect failed");
            Check(PassThruClose(device)==0,"Outcome close failed");
        }
    }
    public static void Run() {
        Check(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,"x86 ABI mismatch");
        IntPtr module=LoadLibraryW(Library); Check(module!=IntPtr.Zero,"LoadLibrary failed");
        uint device=0,hs=0,ls=0,iso=0,wrong=0; bool opened=false;
        try {
            foreach(string api in new string[]{"Open","Close","Connect","Disconnect","ReadMsgs","WriteMsgs","StartPeriodicMsg","StopPeriodicMsg","StartMsgFilter","StopMsgFilter","SetProgrammingVoltage","ReadVersion","GetLastError","Ioctl"})
                Check(GetProcAddress(module,"PassThru"+api)!=IntPtr.Zero,"Missing PassThru export");
            Console.WriteLine("PASS group 1: native x86 ABI and 14 exports");
            Check(PassThruOpen(IntPtr.Zero,out device)==0,"Open failed"); opened=true;
            Check(PassThruConnect(device,5,0x800,500000,out hs)==0,"HS connect failed");
            Check(PassThruConnect(device,5,0x800,125000,out ls)==0,"LS connect failed");
            for(int k=0;k<3;k++) Silent(hs,5,0x7e0,new byte[]{2,0x3e,0x80});
            for(int k=0;k<3;k++) Silent(ls,5,0x7e0,new byte[]{2,0x3e,0x80});
            Console.WriteLine("PASS group 2: six silent physical ECM TX, simultaneous HS/LS");
            Check(PassThruConnect(device,6,0,500000,out iso)==0,"ISO connect failed");
            Silent(iso,6,0x7e0,new byte[]{0x3e,0x80});
            Console.WriteLine("PASS group 3: ISO15765 physical suppression");
            Silent(ls,5,0x000ffffe,new byte[]{0xcb,0x40,0xb9,0xfb,0,0,0,0});
            Silent(hs,5,0x000ffffe,new byte[]{0xcb,0x50,0xb9,0xfb,0,0,0,0});
            Console.WriteLine("PASS group 4: B9FB missing fixtures, no RX");
            Check(PassThruConnect(device,5,0x800,250000,out wrong)==0,"250 connect failed");
            Silent(wrong,5,0x000ffffe,new byte[]{0xcb,0x50,0xb9,0xfb,0,0,0,0});
            Console.WriteLine("PASS group 5: strict B9FB baud rejection");
            Silent(hs,5,0x726,new byte[]{3,0x22,0xf1,0x14,0,0,0,0});
            Silent(iso,6,0x726,new byte[]{0x22,0xf1,0x14});
            Console.WriteLine("PASS group 6: absent P3 node, CAN and ISO15765");
            Silent(iso,6,0x7df,new byte[]{0x3e,0x80});
            Console.WriteLine("PASS group 7: functional suppression, no RX");
            Empty128(hs); Empty128(ls); Empty128(iso); Empty128(wrong);
            Console.WriteLine("PASS group 8: READ128 on all empty channels");
        } finally {
            bool clean=true;
            if(wrong!=0) clean &= PassThruDisconnect(wrong)==0;
            if(iso!=0) clean &= PassThruDisconnect(iso)==0;
            if(ls!=0) clean &= PassThruDisconnect(ls)==0;
            if(hs!=0) clean &= PassThruDisconnect(hs)==0;
            if(opened) clean &= PassThruClose(device)==0;
            clean &= FreeLibrary(module);
            Check(clean,"Native resource cleanup failed");
        }
    }
}
'@
    $source = $source.Replace('__ISOLATED_DLL__', $isolatedDll.Replace('"', '""'))
    Add-Type -TypeDefinition $source -Language CSharp
    $backend = Join-Path $directory 'VirtualCar/dev47-backend.jsonl'
    if ($ApiOutcomeRegression) {
        $ini = Join-Path $directory 'virtualcar.ini'
        [IO.File]::WriteAllText($ini,$profile+"`r`nEnableCanPsConfigProbe=0`r`nCanPsApiOutcomeMask=7`r`n",[Text.Encoding]::ASCII)
        [NativeRouteCheck]::RunCanPsApiOutcome(0,$false)
        foreach ($mode in 0..7) {
            [IO.File]::WriteAllText($ini,$profile+"`r`nEnableCanPsConfigProbe=1`r`nCanPsApiOutcomeMask=$mode`r`n",[Text.Encoding]::ASCII)
            [NativeRouteCheck]::RunCanPsApiOutcome($mode,$true)
        }
        [IO.File]::WriteAllText($ini,$profile+"`r`nEnableCanPsConfigProbe=1`r`nCanPsApiOutcomeMask=0x7`r`n",[Text.Encoding]::ASCII)
        [NativeRouteCheck]::RunCanPsApiOutcome(0,$true)
        if ((Test-Path -LiteralPath $backend) -and (Get-Item -LiteralPath $backend).Length -ne 0) { throw 'API-outcome regression produced backend traffic' }
        Write-Output 'All eight native API-outcome masks passed; no backend requests.'
    } else {
        [NativeRouteCheck]::Run()
        [NativeRouteCheck]::RunCanPsConfigProbe($false)
        [IO.File]::AppendAllText((Join-Path $directory 'virtualcar.ini'), "`r`nEnableCanPsConfigProbe=1`r`n", [Text.Encoding]::ASCII)
        [NativeRouteCheck]::RunCanPsConfigProbe($true)
        if (-not (Test-Path -LiteralPath $backend)) { throw 'Native DLL produced no backend evidence' }
        Write-Output 'Native calls passed. Verify the isolated backend with verify_native_routes.py.'
    }
} finally {
    $env:LOCALAPPDATA = $savedLocal
    $env:TEMP = $savedTemp
    $env:TMP = $savedTmp
}
