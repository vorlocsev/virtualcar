# Synthetic Windows x86 J2534 API outcome regression. No real adapter, no registration.
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
if (Test-Path -LiteralPath $directory) { throw 'Refusing to overwrite outcome regression directory' }
[void][IO.Directory]::CreateDirectory($directory)
$isolatedDll = Join-Path $directory 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $dll -Destination $isolatedDll
$savedLocal = $env:LOCALAPPDATA
$savedTemp = $env:TEMP
$savedTmp = $env:TMP
try {
    $env:LOCALAPPDATA = $directory
    $env:TEMP = $directory
    $env:TMP = $directory
    $source = @'
using System;
using System.Runtime.InteropServices;
using System.Threading;
public static class CanPsOutcomeCheck {
    const string Library = @"__ISOLATED_DLL__";
    [StructLayout(LayoutKind.Sequential)] public struct Msg {
        public uint ProtocolID, RxStatus, TxFlags, Timestamp, DataSize, ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst=4128)] public byte[] Data;
    }
    [StructLayout(LayoutKind.Sequential)] struct ConfigList {
        public uint Count; public IntPtr Entries;
    }
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruOpen(IntPtr name, out uint device);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruClose(uint device);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruConnect(uint device,uint protocol,uint flags,uint baud,out uint channel);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruDisconnect(uint channel);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruIoctl(uint channel,uint op,ref ConfigList config,IntPtr output);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruWriteMsgs(uint channel,ref Msg msg,ref uint count,uint timeout);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruReadMsgs(uint channel,IntPtr buffer,ref uint count,uint timeout);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStartMsgFilter(uint channel,uint type,ref Msg mask,ref Msg pattern,IntPtr flow,ref uint filterId);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStopMsgFilter(uint channel,uint filterId);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStartPeriodicMsg(uint channel,ref Msg msg,ref uint periodicId,uint interval);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStopPeriodicMsg(uint channel,uint periodicId);

    static void Check(bool valid,string description) {
        if(!valid)throw new Exception(description);
    }
    static Msg Build(uint id, byte[] data, uint flags) {
        Msg msg = new Msg(); msg.ProtocolID=0x8004; msg.TxFlags=flags;
        msg.DataSize=(uint)data.Length+4; msg.Data=new byte[4128];
        msg.Data[0]=(byte)(id>>24);msg.Data[1]=(byte)(id>>16);
        msg.Data[2]=(byte)(id>>8);msg.Data[3]=(byte)id;
        if(data.Length!=0)Array.Copy(data,0,msg.Data,4,data.Length);
        return msg;
    }
    static void NoRx(uint channel) {
        IntPtr buffer=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try {
            uint count=1;
            Check(PassThruReadMsgs(channel,buffer,ref count,0)==16 && count==0,"Unexpected CAN_PS RX");
        } finally { Marshal.FreeHGlobal(buffer); }
    }
    public static void Run(uint mode) {
        Check(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,"x86 ABI mismatch");
        uint device=0,channel=0;
        Check(PassThruOpen(IntPtr.Zero,out device)==0,"Open failed");
        try {
            Check(PassThruConnect(device,0x8004,0x900,125000,out channel)==0,"CAN_PS connect failed");
            IntPtr config=Marshal.AllocHGlobal(8);
            try {
                Marshal.WriteInt32(config,0,0x8001);
                Marshal.WriteInt32(config,4,0x030b);
                ConfigList list=new ConfigList(); list.Count=1;list.Entries=config;
                Check(PassThruIoctl(channel,2,ref list,IntPtr.Zero)==0,"J1962_PINS setup failed");
            } finally { Marshal.FreeHGlobal(config); }

            Msg mask=Build(0x1fffffffu,new byte[0],0x100);
            Msg pattern=Build(0x00800003u,new byte[0],0x100);
            uint filterId=0xc0deface;
            uint filterRc=PassThruStartMsgFilter(channel,1,ref mask,ref pattern,IntPtr.Zero,ref filterId);
            if(mode==1) {
                Check(filterRc==0 && filterId!=0xc0deface,"Filter mode not accepted");
                Check(PassThruStopMsgFilter(channel,filterId)==0,"Filter stop failed");
            } else Check(filterRc==1 && filterId==0xc0deface,"Filter unexpectedly accepted");

            Msg d8=Build(0x000ffffeu,new byte[]{0xd8,0,0,0,0,0,0,0},0x100);
            uint count=1;
            uint writeRc=PassThruWriteMsgs(channel,ref d8,ref count,0);
            if(mode==2) {
                Check(writeRc==0 && count==1,"Exact D8 write outcome failed");
                d8.Data[5]=1;
                count=1;
                Check(PassThruWriteMsgs(channel,ref d8,ref count,0)==1 && count==0,
                    "Modified D8 was not rejected");
                d8.Data[5]=0;
            } else Check(writeRc==1 && count==0,"D8 write unexpectedly accepted");

            uint periodicId=0xc0deface;
            uint periodicRc=PassThruStartPeriodicMsg(channel,ref d8,ref periodicId,1000);
            if(mode==3) {
                Check(periodicRc==0 && periodicId!=0xc0deface,"Periodic mode not accepted");
                Thread.Sleep(1100); NoRx(channel);
                Check(PassThruStopPeriodicMsg(channel,periodicId)==0,"Periodic stop failed");
                periodicId=0xc0deface;
                Check(PassThruStartPeriodicMsg(channel,ref d8,ref periodicId,4000)==1 &&
                      periodicId==0xc0deface,"Unexpected periodic interval accepted");
            } else Check(periodicRc==1 && periodicId==0xc0deface,
                         "Periodic unexpectedly accepted");
            NoRx(channel);
            Console.WriteLine("PASS native CAN_PS mode " + mode + " API-only");
        } finally {
            if(channel!=0)Check(PassThruDisconnect(channel)==0,"Disconnect failed");
            Check(PassThruClose(device)==0,"Close failed");
        }
    }
}
'@
    $source = $source.Replace('__ISOLATED_DLL__', $isolatedDll.Replace('"', '""'))
    Add-Type -TypeDefinition $source -Language CSharp
    foreach ($mode in 0..3) {
        $profile = @"
; Synthetic CAN_PS API-only regression, not vehicle evidence
[Vehicle]
VIN=YV1CZ0002A0000001
ECUCount=1
[PassiveCAN]
Enabled=0
[PassiveTrace]
Enabled=0
[Diagnostics]
BackendTelemetryEnabled=1
EnableCanPsConfigProbe=1
CanPsApiOutcomeMode=$mode
"@
        [IO.File]::WriteAllText((Join-Path $directory 'virtualcar.ini'), $profile, [Text.Encoding]::ASCII)
        [CanPsOutcomeCheck]::Run([uint32]$mode)
    }
    $nativeLog = Join-Path $directory 'SectorVVirtualCar.log'
    if (!(Test-Path -LiteralPath $nativeLog)) { throw 'Native log was not written' }
    $log = [IO.File]::ReadAllText($nativeLog)
    foreach ($forbidden in @('TX context channel/protocol', 'RX context channel/protocol',
                             'PassThruReadMsgs -> delivered', 'J2534 periodic TX')) {
        if ($log.Contains($forbidden)) { throw "Unexpected CAN_PS wire activity: $forbidden" }
    }
    $marker = 'J2534 CAN_PS API-only outcome mode/operation/status (BE)'
    if (([regex]::Matches($log,[regex]::Escape($marker))).Count -ne 3) {
        throw 'Expected exactly three successful experiment metadata records'
    }
    if (Test-Path -LiteralPath (Join-Path $directory 'VirtualCar\dev47-backend.jsonl')) {
        throw 'Experimental CAN_PS generated backend route events'
    }
    Write-Output 'PASS: native x86 CAN_PS CONTROL/A/B/C, no TX/RX/backend'
} finally {
    $env:LOCALAPPDATA=$savedLocal
    $env:TEMP=$savedTemp
    $env:TMP=$savedTmp
}
