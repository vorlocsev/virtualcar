# Native x86 DLL regression. Synthetic profile, no registration or physical J2534.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -OutputDirectory $OutputDirectory
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
            Msg msg=new Msg(); msg.ProtocolID=0x8004; msg.DataSize=12; msg.Data=new byte[4128];
            uint count=1;
            Check(PassThruWriteMsgs(channel,ref msg,ref count,0)==1 && count==0,"PS write was not blocked");
            Empty128(channel);
            Console.WriteLine("PASS native CAN_PS configuration-only opt-in/roundtrip/rebind/write/RX checks");
        } finally {
            Marshal.FreeHGlobal(entry);
            if(channel!=0) Check(PassThruDisconnect(channel)==0,"PS disconnect failed");
            Check(PassThruClose(device)==0,"PS close failed");
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
    [NativeRouteCheck]::Run()
    [NativeRouteCheck]::RunCanPsConfigProbe($false)
    [IO.File]::AppendAllText((Join-Path $directory 'virtualcar.ini'), "`r`nEnableCanPsConfigProbe=1`r`n", [Text.Encoding]::ASCII)
    [NativeRouteCheck]::RunCanPsConfigProbe($true)
    $backend = Join-Path $directory 'VirtualCar/dev47-backend.jsonl'
    if (-not (Test-Path -LiteralPath $backend)) { throw 'Native DLL produced no backend evidence' }
    Write-Output 'Native calls passed. Verify the isolated backend with verify_native_routes.py.'
} finally {
    $env:LOCALAPPDATA = $savedLocal
    $env:TEMP = $savedTemp
    $env:TMP = $savedTmp
}
