# Isolated x86 native VIDA CAN-MS preflight. Synthetic only; no registry/VIDA access.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$ExpectedSha256 = ''
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    $args32 = @('-NoProfile','-ExecutionPolicy','Bypass','-File',$PSCommandPath,
        '-DllPath',$DllPath,'-OutputDirectory',$OutputDirectory)
    if ($ExpectedSha256) { $args32 += @('-ExpectedSha256',$ExpectedSha256) }
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" @args32
    if ($LASTEXITCODE -ne 0) { throw "x86 PS native VIDA CAN-MS gate FAILED: $LASTEXITCODE" }
    exit 0
}
$sourceDll = (Resolve-Path -LiteralPath $DllPath -ErrorAction Stop).Path
$actual = (Get-FileHash -LiteralPath $sourceDll -Algorithm SHA256).Hash
if ($ExpectedSha256 -and ($actual -cne $ExpectedSha256.ToUpperInvariant())) {
    throw "DLL SHA256 mismatch: expected $ExpectedSha256, got $actual"
}
$directory = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $directory) { throw "Refusing to overwrite $directory" }
[void][IO.Directory]::CreateDirectory($directory)
$isolatedDll = Join-Path $directory 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $sourceDll -Destination $isolatedDll
if ((Get-FileHash -LiteralPath $isolatedDll -Algorithm SHA256).Hash -cne $actual) { throw 'Isolated DLL copy SHA256 mismatch' }
$profilePath = Join-Path $directory 'virtualcar.ini'
$profile = @'
; VIDA J2534-2 synthetic native lab only, NOT original VIDA data.
[Vehicle]
VIN=YV1CZ0002A0000001
BatteryMv=12500
ECUCount=1
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
EnableVidaCanPsLab=0
StrictJ2534Filters=1
BackendTelemetryEnabled=0
'@
[IO.File]::WriteAllText($profilePath,$profile,[Text.Encoding]::ASCII)
$savedLocal = $env:LOCALAPPDATA
$savedTemp = $env:TEMP
$savedTmp = $env:TMP
try {
    $env:LOCALAPPDATA = $directory
    $env:TEMP = $directory
    $env:TMP = $directory
    $code = @'
using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
public static class NativeVidaPsLab {
    const string Library=@"__DLL__";
    const string Profile=@"__PROFILE__";
    const uint PS_CAN=0x8004u, PS_ISO=0x8005u, PINS=0x8001u;
    [StructLayout(LayoutKind.Sequential)]
    public struct Msg {
        public uint ProtocolID, RxStatus, TxFlags, Timestamp, DataSize, ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst=4128)] public byte[] Data;
    }
    [StructLayout(LayoutKind.Sequential)]
    public struct ConfigList { public uint NumOfParams; public IntPtr ConfigPtr; }
    [DllImport("kernel32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
    static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32.dll", CharSet=CharSet.Ansi, ExactSpelling=true)]
    static extern IntPtr GetProcAddress(IntPtr module,string name);
    [DllImport("kernel32.dll")] static extern bool FreeLibrary(IntPtr module);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruOpen(IntPtr name,out uint device);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruClose(uint device);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruConnect(uint device,uint protocol,uint flags,uint baud,out uint channel);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruDisconnect(uint channel);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruIoctl(uint channel,uint ioctl,ref ConfigList input,IntPtr output);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruWriteMsgs(uint channel,ref Msg msg,ref uint count,uint timeout);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruReadMsgs(uint channel,IntPtr msg,ref uint count,uint timeout);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall, EntryPoint="PassThruStartMsgFilter")]
    static extern uint StartRawFilter(uint channel,uint type,ref Msg mask,ref Msg pattern,IntPtr flow,out uint filter);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall, EntryPoint="PassThruStartMsgFilter")]
    static extern uint StartIsoFilter(uint channel,uint type,ref Msg mask,ref Msg pattern,ref Msg flow,out uint filter);
    [DllImport(Library, CallingConvention=CallingConvention.StdCall, EntryPoint="PassThruStopMsgFilter")]
    static extern uint StopFilter(uint channel,uint filter);
    static void Require(bool condition,string label) {
        if(!condition) throw new InvalidOperationException(label);
    }
    static void Status(uint result,uint expected,string label) {
        Require(result==expected,label+" (expected "+expected+", got "+result+")");
    }
    static Msg Frame(uint protocol,uint id,byte[] data) {
        Msg m=new Msg();m.ProtocolID=protocol;m.TxFlags=id>0x7FF?0x100u:0u;
        m.DataSize=(uint)data.Length+4u;m.Data=new byte[4128];
        m.Data[0]=(byte)(id>>24);m.Data[1]=(byte)(id>>16);
        m.Data[2]=(byte)(id>>8);m.Data[3]=(byte)id;
        Array.Copy(data,0,m.Data,4,data.Length);return m;
    }
    static Msg Id(uint proto,uint id) {return Frame(proto,id,new byte[0]);}
    static uint SetConfig(uint channel,uint param,uint value) {
        IntPtr pair=Marshal.AllocHGlobal(8);
        try {
            Marshal.WriteInt32(pair,0,unchecked((int)param));
            Marshal.WriteInt32(pair,4,unchecked((int)value));
            ConfigList list=new ConfigList();list.NumOfParams=1;list.ConfigPtr=pair;
            return PassThruIoctl(channel,2,ref list,IntPtr.Zero);
        } finally {Marshal.FreeHGlobal(pair);}
    }
    static uint GetConfig(uint channel,uint param) {
        IntPtr pair=Marshal.AllocHGlobal(8);
        try {
            Marshal.WriteInt32(pair,0,unchecked((int)param));Marshal.WriteInt32(pair,4,0);
            ConfigList list=new ConfigList();list.NumOfParams=1;list.ConfigPtr=pair;
            Status(PassThruIoctl(channel,1,ref list,IntPtr.Zero),0,"GET_CONFIG");
            return unchecked((uint)Marshal.ReadInt32(pair,4));
        } finally {Marshal.FreeHGlobal(pair);}
    }
    static Msg Read(uint channel) {
        IntPtr p=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try {
            uint n=1;Status(PassThruReadMsgs(channel,p,ref n,0),0,"ReadMsgs");
            Require(n==1,"ReadMsgs expected exactly one response");
            return (Msg)Marshal.PtrToStructure(p,typeof(Msg));
        } finally {Marshal.FreeHGlobal(p);}
    }
    static uint Write(uint channel,Msg msg,out uint count) {
        count=1;return PassThruWriteMsgs(channel,ref msg,ref count,10);
    }
    public static void Run() {
        Require(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,"x86 ABI");
        IntPtr module=LoadLibraryW(Library);Require(module!=IntPtr.Zero,"LoadLibraryW x86 DLL");
        uint dev=0,can=0,iso=0,tmp=0,fcan=0,fiso=0;
        bool opened=false;
        try {
            foreach(string api in new string[]{"Open","Close","Connect","Disconnect","ReadMsgs","WriteMsgs",
                "StartPeriodicMsg","StopPeriodicMsg","StartMsgFilter","StopMsgFilter",
                "SetProgrammingVoltage","ReadVersion","GetLastError","Ioctl"})
                Require(GetProcAddress(module,"PassThru"+api)!=IntPtr.Zero,"Missing export "+api);
            Console.WriteLine("PASS PS native 1: 14 exports and exact x86 ABI");
            Status(PassThruOpen(IntPtr.Zero,out dev),0,"Open default-off");opened=true;
            Status(PassThruConnect(dev,PS_CAN,0x100,125000,out tmp),3,"CAN_PS default-off");
            Status(PassThruConnect(dev,PS_ISO,0,125000,out tmp),3,"ISO15765_PS default-off");
            Require(tmp==0,"Default-off created channel");
            Status(PassThruClose(dev),0,"Close default-off");opened=false;
            Console.WriteLine("PASS PS native 2: both protocols rejected by default");
            string p=File.ReadAllText(Profile,Encoding.ASCII);
            Require(p.Contains("EnableVidaCanPsLab=0"),"Profile default-off marker missing");
            File.WriteAllText(Profile,p.Replace("EnableVidaCanPsLab=0","EnableVidaCanPsLab=1"),Encoding.ASCII);
            Status(PassThruOpen(IntPtr.Zero,out dev),0,"Open opt-in");opened=true;
            Status(PassThruConnect(dev,PS_CAN,0x100,500000,out tmp),25,"Reject wrong PS speed");
            Status(PassThruConnect(dev,PS_ISO,0x800,125000,out tmp),6,"Reject wrong PS flags");
            Status(PassThruConnect(dev,0x10000001u,0,125000,out tmp),3,"Reject vendor protocol");
            Status(PassThruConnect(dev,PS_CAN,0x100,125000,out can),0,"Connect CAN_PS");
            Require(can!=0,"CAN_PS ID zero");
            Status(PassThruConnect(dev,PS_ISO,0,125000,out iso),0,"Connect ISO15765_PS");
            Require(iso!=0 && iso!=can,"PS channels not distinct");
            Console.WriteLine("PASS PS native 3: both native PS Connect calls and error boundaries");
            uint n;
            Msg raw=Frame(PS_CAN,0x7E0,new byte[]{3,0x22,0xF1,0x90,0,0,0,0});
            Status(Write(can,raw,out n),19,"Reject CAN_PS write without pins");
            Require(n==0,"PS invalid write count");
            Status(SetConfig(can,PINS,0x060E),19,"Reject unsupported pins");
            Require(GetConfig(can,PINS)==0,"Unsupported pin setting leaked into state");
            Status(SetConfig(can,PINS,0x030B),0,"Set CAN_PS pins3/11");
            Status(SetConfig(can,1,125000),0,"Set CAN_PS data rate");
            Status(SetConfig(can,3,0),0,"Set CAN_PS LOOPBACK");
            Status(SetConfig(can,23,68),0,"Set CAN_PS sample point");
            Require(GetConfig(can,PINS)==0x030B && GetConfig(can,1)==125000,"CAN_PS readback");
            Status(SetConfig(iso,PINS,0x030B),0,"Set ISO_PS pins3/11");
            Status(SetConfig(iso,1,125000),0,"Set ISO_PS data rate");
            Status(SetConfig(iso,3,0),0,"Set ISO_PS LOOPBACK");
            Require(GetConfig(iso,PINS)==0x030B,"ISO_PS pin readback");
            Console.WriteLine("PASS PS native 4: per-channel J1962 pins and config");
            Msg mask=Id(PS_CAN,0xFFFFFFFF),pat=Id(PS_CAN,0x7E8);
            Status(StartRawFilter(can,1,ref mask,ref pat,IntPtr.Zero,out fcan),0,"CAN_PS PASS_FILTER");
            Require(fcan!=0,"CAN_PS filter ID zero");
            Status(Write(can,raw,out n),0,"CAN_PS raw VIN TX");Require(n==1,"CAN_PS write count");
            Msg rx=Read(can);
            Require(rx.ProtocolID==PS_CAN && rx.DataSize==12 && rx.Data[4]==0x10,
                "CAN_PS RX frame or wire ProtocolID mismatch");
            Status(StopFilter(can,fcan),0,"Stop CAN_PS filter");fcan=0;
            Console.WriteLine("PASS PS native 5: CAN_PS actual synthetic TX/RX and strict filter");
            Msg imask=Id(PS_ISO,0xFFFFFFFF),ipat=Id(PS_ISO,0x7E8),flow=Id(PS_ISO,0x7E0);
            Status(StartIsoFilter(iso,3,ref imask,ref ipat,ref flow,out fiso),0,"ISO_PS FC filter");
            Require(fiso!=0,"ISO_PS FC filter ID zero");
            Msg req=Frame(PS_ISO,0x7E0,new byte[]{0x22,0xF1,0x90});
            Status(Write(iso,req,out n),0,"ISO_PS VIN TX");Require(n==1,"ISO_PS write count");
            rx=Read(iso);
            Require(rx.ProtocolID==PS_ISO && rx.DataSize==24 &&
                rx.Data[4]==0x62 && rx.Data[5]==0xF1 && rx.Data[6]==0x90,
                "ISO15765_PS RX payload or ProtocolID mismatch");
            req=Frame(PS_ISO,0x7E0,new byte[]{0x2E,0xF1,0x90,0});
            Status(Write(iso,req,out n),0,"Protected service TX");
            rx=Read(iso);
            Require(rx.ProtocolID==PS_ISO && rx.DataSize==7 &&
                rx.Data[4]==0x7F && rx.Data[5]==0x2E && rx.Data[6]==0x33,
                "Protected UDS operation not denied");
            Status(StopFilter(iso,fiso),0,"Stop ISO_PS filter");fiso=0;
            Console.WriteLine("PASS PS native 6: ISO15765_PS FC filter, synthetic VIN and protected UDS");
            Status(PassThruDisconnect(iso),0,"Disconnect ISO_PS");iso=0;
            Status(PassThruDisconnect(can),0,"Disconnect CAN_PS");can=0;
            Status(PassThruConnect(dev,PS_CAN,0,125000,out tmp),0,"Reconnect CAN_PS");
            Require(GetConfig(tmp,PINS)==0,"Pin state leaked across channel reopen");
            Status(PassThruDisconnect(tmp),0,"Disconnect reopened PS");tmp=0;
            Console.WriteLine("PASS PS native 7: isolation and channel pin-state reset");
            Status(PassThruClose(dev),0,"Close opt-in");opened=false;
            Console.WriteLine("PASS PS native 8: clean device lifecycle");
        } finally {
            if(iso!=0) PassThruDisconnect(iso);
            if(can!=0) PassThruDisconnect(can);
            if(tmp!=0) PassThruDisconnect(tmp);
            if(opened) PassThruClose(dev);
            FreeLibrary(module);
        }
    }
}
'@
    $code = $code.Replace('__DLL__',$isolatedDll.Replace('"','""'))
    $code = $code.Replace('__PROFILE__',$profilePath.Replace('"','""'))
    Add-Type -TypeDefinition $code -Language CSharp -ErrorAction Stop
    [NativeVidaPsLab]::Run()
    Write-Output "PASS: isolated native x86 VIDA CAN_MS PS protocol gate. DLL SHA256=$actual"
    Write-Output "Evidence directory: $directory"
    Write-Output 'No original VIDA, J2534 registry, physical adapters or client GUI used.'
} finally {
    $env:LOCALAPPDATA = $savedLocal
    $env:TEMP = $savedTemp
    $env:TMP = $savedTmp
}
