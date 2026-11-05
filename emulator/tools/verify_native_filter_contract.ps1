# Stage 40. Compiled x86 J2534 DLL contract, isolated laboratory run.
# No ECU TX, VIN, EEPROM, registry changes, hardware, or releases.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [ValidateSet('legacy','strict')][string]$Mode='legacy'
)
$ErrorActionPreference='Stop'
if ([IntPtr]::Size -ne 4) {
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -OutputDirectory $OutputDirectory -Mode $Mode
    exit $LASTEXITCODE
}
$dll=(Resolve-Path -LiteralPath $DllPath).Path
$directory=[IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $directory) { throw 'OutputDirectory must not already exist' }
[void][IO.Directory]::CreateDirectory($directory)
$isolatedDll=Join-Path $directory 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $dll -Destination $isolatedDll
# Private vehicle identities and any positive ECU reply are intentionally absent.
$profile=@'
; Synthetic stage 40 J2534-only fixture. Never connect a physical vehicle.
[Vehicle]
ECUCount=1
BatteryMv=12500
[ECU0]
RequestId=7E0
ResponseId=7E8
[PassiveCAN]
Enabled=0
[PassiveTrace]
Enabled=0
[P2]
StrictRouting=1
[Diagnostics]
BackendTelemetryEnabled=0
'@
# Mode is an opt-in INI setting read by PassThruOpen, not a test-only switch.
$profile += "`r`nStrictJ2534Filters=$([int]($Mode -eq 'strict'))`r`n"
[IO.File]::WriteAllText((Join-Path $directory 'virtualcar.ini'),$profile,[Text.Encoding]::ASCII)
$savedLocal=$env:LOCALAPPDATA
$savedTemp=$env:TEMP
$savedTmp=$env:TMP
try {
    $env:LOCALAPPDATA=$directory
    $env:TEMP=$directory
    $env:TMP=$directory
    $source=@'
using System;
using System.Runtime.InteropServices;
public static class Stage40NativeFilter {
    const string Library=@"__ISOLATED_DLL__";
    const uint CAN=5, ISO=6, PASS=1, FC=3;
    const uint OK=0, INVALID_CHANNEL=2, NULL_PARAM=4;
    const uint INVALID_FILTER=22, NO_FLOW_CONTROL=23;
    static int checks=0;
    [StructLayout(LayoutKind.Sequential)]
    public struct Msg {
        public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst=4128)] public byte[] Data;
    }
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32.dll",CharSet=CharSet.Ansi,ExactSpelling=true)]
    static extern IntPtr GetProcAddress(IntPtr library,string symbol);
    [DllImport("kernel32.dll")]
    static extern bool FreeLibrary(IntPtr library);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruOpen(IntPtr name,out uint device);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruClose(uint device);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruConnect(uint device,uint protocol,uint flags,uint baud,out uint channel);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruDisconnect(uint channel);
    [DllImport(Library,EntryPoint="PassThruStartMsgFilter",CallingConvention=CallingConvention.StdCall)]
    static extern uint FilterWithFlow(uint channel,uint type,ref Msg mask,ref Msg pattern,ref Msg flow,out uint filter);
    [DllImport(Library,EntryPoint="PassThruStartMsgFilter",CallingConvention=CallingConvention.StdCall)]
    static extern uint FilterNoFlow(uint channel,uint type,ref Msg mask,ref Msg pattern,IntPtr noFlow,out uint filter);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStopMsgFilter(uint channel,uint filter);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruWriteMsgs(uint channel,ref Msg msg,ref uint count,uint timeout);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruReadMsgs(uint channel,IntPtr buffer,ref uint count,uint timeout);
    static uint Receive(uint channel,out Msg received) {
        received=new Msg();IntPtr buffer=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try {
            uint count=1;
            uint rc=PassThruReadMsgs(channel,buffer,ref count,0);
            if(rc==OK&&count==1)received=(Msg)Marshal.PtrToStructure(buffer,typeof(Msg));
            return rc;
        } finally {Marshal.FreeHGlobal(buffer);}
    }
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruIoctl(uint channel,uint code,IntPtr input,IntPtr output);
    static void Check(string name,bool condition,uint actual) {
        Console.WriteLine((condition?"PASS ":"FAIL ")+name+" actual="+actual);
        if(!condition) throw new Exception("Stage40 failed: "+name);
        checks++;
    }
    static Msg Id(uint protocol,uint id) {
        Msg m=new Msg();m.ProtocolID=protocol;m.DataSize=4;m.Data=new byte[4128];
        m.Data[0]=(byte)(id>>24);m.Data[1]=(byte)(id>>16);
        m.Data[2]=(byte)(id>>8);m.Data[3]=(byte)id;return m;
    }
    public static void Run(bool strict) {
        Check("ABI_4152",IntPtr.Size==4&&Marshal.SizeOf(typeof(Msg))==4152,
              (uint)Marshal.SizeOf(typeof(Msg)));
        IntPtr module=LoadLibraryW(Library);
        Check("LoadLibrary_x86",module!=IntPtr.Zero,(uint)(module!=IntPtr.Zero?1:0));
        uint device=0,can=0,iso=0,filter=0,old=0;
        bool opened=false;
        try {
            string[] names={"Open","Close","Connect","Disconnect","ReadMsgs","WriteMsgs",
                "StartPeriodicMsg","StopPeriodicMsg","StartMsgFilter","StopMsgFilter",
                "SetProgrammingVoltage","ReadVersion","GetLastError","Ioctl"};
            int count=0;foreach(string name in names)
                if(GetProcAddress(module,"PassThru"+name)!=IntPtr.Zero) count++;
            Check("J2534_14_exports",count==14,(uint)count);
            uint rc=PassThruOpen(IntPtr.Zero,out device);
            Check("Open",rc==OK&&device!=0,rc);opened=true;
            rc=PassThruConnect(device,CAN,0,500000,out can);
            Check("CAN_connect",rc==OK&&can!=0,rc);
            rc=PassThruConnect(device,ISO,0,500000,out iso);
            Check("ISO_connect",rc==OK&&iso!=0,rc);
            Msg canMask=Id(CAN,0xffffffff),canPattern=Id(CAN,0x7e8),canFlow=Id(CAN,0x7e0);
            Msg mask=Id(ISO,0xffffffff),pattern=Id(ISO,0x7e8),flow=Id(ISO,0x7e0);
            rc=FilterWithFlow(can,FC,ref canMask,ref canPattern,ref canFlow,out filter);
            Check("CAN_FC_policy",strict?rc==NO_FLOW_CONTROL:rc==OK,rc);
            if(rc==OK) Check("CAN_FC_cleanup",PassThruStopMsgFilter(can,filter)==OK,filter);
            rc=FilterNoFlow(iso,FC,ref mask,ref pattern,IntPtr.Zero,out filter);
            Check("ISO_null_flow_policy",strict?rc==NULL_PARAM:rc==OK,rc);
            if(rc==OK) Check("ISO_null_flow_cleanup",PassThruStopMsgFilter(iso,filter)==OK,filter);
            rc=FilterNoFlow(iso,PASS,ref mask,ref pattern,IntPtr.Zero,out filter);
            Check("ISO_PASS_policy",strict?rc!=OK:rc==OK,rc);
            if(rc==OK) Check("ISO_PASS_cleanup",PassThruStopMsgFilter(iso,filter)==OK,filter);
            rc=FilterWithFlow(iso,FC,ref mask,ref pattern,ref flow,out filter);
            Check("ISO_valid_FC",rc==OK&&filter!=0,rc);
            old=filter;
            Check("Filter_stop",PassThruStopMsgFilter(iso,filter)==OK,filter);
            rc=PassThruStopMsgFilter(iso,filter);
            Check("Filter_repeat_invalid",rc==INVALID_FILTER,rc);
            rc=FilterWithFlow(iso,FC,ref mask,ref pattern,ref flow,out filter);
            Check("FC_reinstall",rc==OK&&filter!=0,rc);
            rc=PassThruIoctl(iso,10,IntPtr.Zero,IntPtr.Zero);
            Check("Clear_filters",rc==OK,rc);
            rc=PassThruStopMsgFilter(iso,filter);
            Check("Cleared_FilterID_invalid",rc==INVALID_FILTER,rc);
            uint disconnectedChannel=iso;
            rc=PassThruDisconnect(iso);
            Check("Disconnect_ISO",rc==OK,rc);iso=0;
            rc=PassThruStopMsgFilter(disconnectedChannel,old);
            Check("Disconnected_channel_invalid",rc==INVALID_CHANNEL,rc);
            rc=PassThruConnect(device,ISO,0,500000,out iso);
            Check("Reconnect_ISO",rc==OK&&iso!=0,rc);
            rc=PassThruStopMsgFilter(iso,old);
            Check("Old_ID_after_reconnect",rc==INVALID_FILTER,rc);
            if(strict) {
                /* Real Windows x86 DLL, synthetic ECU only. No VIN is printed. */
                Msg request=Id(ISO,0x7e0u);
                request.Data[4]=0x22;request.Data[5]=0xF1;request.Data[6]=0x90;
                request.DataSize=7;
                uint n=1;
                rc=PassThruWriteMsgs(iso,ref request,ref n,10);
                Check("Strict_no_filter_TX",rc==OK&&n==1,rc);
                Msg received;
                rc=Receive(iso,out received);
                Check("Strict_no_filter_RX",rc==16,rc);
                rc=FilterWithFlow(iso,FC,ref mask,ref pattern,ref flow,out filter);
                Check("Strict_add_valid_FC",rc==OK,rc);
                n=1;rc=PassThruWriteMsgs(iso,ref request,ref n,10);
                Check("Strict_FC_TX",rc==OK&&n==1,rc);
                rc=Receive(iso,out received);
                Check("Strict_FC_reassembled_VIN",rc==OK&&received.ProtocolID==ISO
                      &&received.DataSize==24&&received.ExtraDataIndex==24
                      &&received.Data[4]==0x62&&received.Data[5]==0xF1
                      &&received.Data[6]==0x90,rc);
                rc=PassThruStopMsgFilter(iso,filter);
                Check("Strict_stop_FC",rc==OK,rc);
                n=1;rc=PassThruWriteMsgs(iso,ref request,ref n,10);
                Check("Strict_after_stop_TX",rc==OK&&n==1,rc);
                rc=Receive(iso,out received);
                Check("Strict_after_stop_RX",rc==16,rc);
            }
            Console.WriteLine("STAGE40 SUMMARY "+checks+" checks, mode="+(strict?"strict":"legacy"));
        } finally {
            if(iso!=0) PassThruDisconnect(iso);
            if(can!=0) PassThruDisconnect(can);
            if(opened) PassThruClose(device);
            FreeLibrary(module);
        }
    }
}
'@
    $source=$source.Replace('__ISOLATED_DLL__',$isolatedDll.Replace('"','""'))
    Add-Type -TypeDefinition $source -Language CSharp
    [Stage40NativeFilter]::Run($Mode -eq 'strict')
} finally {
    $env:LOCALAPPDATA=$savedLocal
    $env:TEMP=$savedTemp
    $env:TMP=$savedTmp
}
