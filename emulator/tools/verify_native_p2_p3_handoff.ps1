# One-process Windows x86 J2534 read-only laboratory handoff:
# synthetic B9FB -> synthetic B9F0 -> synthetic P3 F114 DID response.
# This is not a SectorV/VDASH acceptance run or a genuine Volvo CEM identity.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$CompositeLocked,
    [switch]$PayloadFilterProbe
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    $forward = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                 $PSCommandPath, '-DllPath', $DllPath,
                 '-OutputDirectory', $OutputDirectory)
    if ($CompositeLocked) { $forward += '-CompositeLocked' }
    if ($PayloadFilterProbe) { $forward += '-PayloadFilterProbe' }
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" @forward
    if ($LASTEXITCODE -ne 0) { throw 'Isolated x86 handoff process failed' }
    exit 0
}
$dll = (Resolve-Path -LiteralPath $DllPath).Path
$directory = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $directory) { throw 'Refusing existing handoff output directory' }
[void][IO.Directory]::CreateDirectory($directory)
$isolatedDll = Join-Path $directory 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $dll -Destination $isolatedDll

# All three positive replies are deliberately synthetic. No historical donor
# hardware part number, customer VIN, E3 authorization or real ECU is included.
$profile = New-Object Text.StringBuilder
foreach ($line in @(
    '; SYNTHETIC P2/P3 one-process native lab, not original XC90 identity',
    '[Vehicle]', 'VIN=VCARLAB0000000000', 'ECUCount=1',
    'EmitIsoRxStart=0', 'BatteryMv=12500',
    '[ECU0]', 'RequestId=726', 'ResponseId=72E',
    'PartNumber=LAB-ONLY', 'Software=LAB-ONLY',
    '[P2]', 'StrictRouting=1', 'ReplaySpacingMs=1',
    '[D2_40]', 'B9FBFrameCount=0',
    '[D2_50]', 'ResponseId=01200003', 'B9FBFrameCount=13'
)) {
    if ($CompositeLocked -and $line -eq '[D2_40]') {
        [void]$profile.AppendLine('FixtureProvenance=local_composite_unverified_trace_import')
        [void]$profile.AppendLine('AllowCompositeReplay=0')
    }
    [void]$profile.AppendLine($line)
}
$controls = @('8F','09','0A','0B','0C','0D','0E','0F','08','09','0A','0B','4F')
for ($i=0; $i -lt $controls.Count; $i++) {
    $octets = if ($i -eq 0) { '8F 50 F9 FB 57 00 00 00' }
              else { $controls[$i] + ' 00 00 00 00 00 00 00' }
    [void]$profile.AppendLine(('B9FBFrame{0:X}={1}' -f $i,$octets))
}
foreach ($line in @(
    '[D2_50_B9F0]', 'ResponseId=01000003', 'FrameCount=3',
    'Frame0=8F 50 F9 F0 00 00 00 00',
    'Frame1=09 00 00 00 00 00 00 00',
    'Frame2=4C 00 00 00 00 00 00 00',
    '[PassiveCAN]', 'Enabled=0',
    '[PassiveTrace]', 'Enabled=0',
    '[Diagnostics]', 'BackendTelemetryEnabled=1'
)) { [void]$profile.AppendLine($line) }
[IO.File]::WriteAllText((Join-Path $directory 'virtualcar.ini'),
                        $profile.ToString(), [Text.Encoding]::ASCII)
$savedLocal=$env:LOCALAPPDATA; $savedTemp=$env:TEMP; $savedTmp=$env:TMP
try {
    $env:LOCALAPPDATA=$directory; $env:TEMP=$directory; $env:TMP=$directory
    $source=@'
using System;
using System.Runtime.InteropServices;
public static class NativeP2P3Handoff {
    const string Library=@"__ISOLATED_DLL__";
    static readonly bool CompositeLocked=__COMPOSITE_LOCKED__;
    static readonly bool PayloadFilterProbe=__PAYLOAD_FILTER_PROBE__;
    [StructLayout(LayoutKind.Sequential)]
    public struct Msg {
        public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray,SizeConst=4128)]
        public byte[] Data;
    }
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32.dll",CharSet=CharSet.Ansi,ExactSpelling=true)]
    static extern IntPtr GetProcAddress(IntPtr module,string name);
    [DllImport("kernel32.dll")]
    static extern bool FreeLibrary(IntPtr module);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruOpen(IntPtr name,out uint device);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruClose(uint device);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruConnect(uint device,uint protocol,uint flags,uint baud,out uint channel);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruDisconnect(uint channel);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruWriteMsgs(uint channel,ref Msg msg,ref uint count,uint timeout);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruReadMsgs(uint channel,IntPtr buffer,ref uint count,uint timeout);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStartMsgFilter(uint channel,uint type,
       ref Msg mask,ref Msg pattern,IntPtr flow,out uint filterId);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStopMsgFilter(uint channel,uint filterId);

    static void Check(bool pass,string gate) {
        if(!pass)throw new InvalidOperationException(gate);
    }
    static Msg Request(uint protocol,uint canid,byte[] body) {
        Msg msg=new Msg();
        msg.ProtocolID=protocol;
        msg.TxFlags=canid>0x7FF ? 0x100u : 0u;
        msg.DataSize=(uint)(4+body.Length);
        msg.Data=new byte[4128];
        msg.Data[0]=(byte)(canid>>24);
        msg.Data[1]=(byte)(canid>>16);
        msg.Data[2]=(byte)(canid>>8);
        msg.Data[3]=(byte)canid;
        Array.Copy(body,0,msg.Data,4,body.Length);
        return msg;
    }
    static void Write(uint channel,uint protocol,uint id,byte[] body) {
        Msg m=Request(protocol,id,body);
        uint count=1;
        Check(PassThruWriteMsgs(channel,ref m,ref count,2000)==0 && count==1,
              "Native PassThruWriteMsgs failed");
    }
    static Msg Read(uint channel,uint expectedProtocol,uint expectedId,int timeout) {
        IntPtr mem=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try {
            uint count=1;
            uint code=PassThruReadMsgs(channel,mem,ref count,(uint)timeout);
            Check(code==0 && count==1,"Missing native RX in full P2/P3 chain");
            Msg msg=(Msg)Marshal.PtrToStructure(mem,typeof(Msg));
            Check(msg.ProtocolID==expectedProtocol,"Native RX protocol mismatch");
            uint id=((uint)msg.Data[0]<<24)|((uint)msg.Data[1]<<16)|
                    ((uint)msg.Data[2]<<8)|msg.Data[3];
            Check(id==expectedId,"Wrong CAN response route in full handoff");
            Check((msg.RxStatus & 0x0B)==0,"TX or start indication is not ECU data");
            return msg;
        } finally {Marshal.FreeHGlobal(mem);}
    }
    static void CheckNoRx(uint channel,string source) {
        IntPtr mem=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try {
            uint count=1;
            uint result=PassThruReadMsgs(channel,mem,ref count,0);
            Check(result==16 && count==0,
                  "Unapproved composite replay emitted "+source);
        } finally {Marshal.FreeHGlobal(mem);}
    }
    static void VerifyPayloadFilters(uint can) {
        byte[] request=new byte[]{0xCB,0x50,0xB9,0xF0,0,0,0,0};
        Msg mask=Request(5,0xFFFFFFFFu,new byte[]{0xFF});
        Msg pat=Request(5,0x01000003u,new byte[]{0x8F});
        uint fid=0;
        Check(PassThruStartMsgFilter(can,1,ref mask,ref pat,
                                     IntPtr.Zero,out fid)==0,
              "Native five-byte PASS filter install failed");
        try {
            Write(can,5,0x000FFFFEu,request);
            Msg first=Read(can,5,0x01000003u,300);
            Check(first.Data[4]==0x8F && first.Data[5]==0x50 &&
                  first.Data[6]==0xF9 && first.Data[7]==0xF0,
                  "Native five-byte PASS filter missed B9F0 first frame");
            IntPtr buf=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
            try {
                uint count=1;
                uint status=PassThruReadMsgs(can,buf,ref count,240);
                Check(status==9 && count==0,
                      "Native PASS filter leaked second/third same-ID B9F0 frame");
            } finally { Marshal.FreeHGlobal(buf); }
        } finally {
            Check(PassThruStopMsgFilter(can,fid)==0,
                  "Native PASS filter removal failed");
        }
        Check(PassThruStartMsgFilter(can,2,ref mask,ref pat,
                                     IntPtr.Zero,out fid)==0,
              "Native five-byte BLOCK filter install failed");
        try {
            Write(can,5,0x000FFFFEu,request);
            Msg second=Read(can,5,0x01000003u,300);
            Msg third=Read(can,5,0x01000003u,300);
            Check(second.Data[4]==0x09 && third.Data[4]==0x4C,
                  "Native BLOCK filter rejected wrong same-ID frames");
        } finally {
            Check(PassThruStopMsgFilter(can,fid)==0,
                  "Native BLOCK filter removal failed");
        }
        Console.WriteLine("PASS: native x86 J2534 5-byte CAN PASS/BLOCK ID-and-payload filters");
    }
    public static void Run() {
        Check(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,
              "Native x86 J2534 ABI mismatch");
        IntPtr lib=LoadLibraryW(Library);
        Check(lib!=IntPtr.Zero,"Cannot load isolated virtual DLL");
        uint device=0, d2=0, p3=0;
        bool opened=false;
        try {
            foreach(string api in new string[]{"Open","Close","Connect","Disconnect",
                                              "WriteMsgs","ReadMsgs"})
                Check(GetProcAddress(lib,"PassThru"+api)!=IntPtr.Zero,
                      "Missing J2534 export");
            Console.WriteLine("PASS 1/8: isolated Windows x86 J2534 exports");
            Check(PassThruOpen(IntPtr.Zero,out device)==0,"Open failed");
            opened=true;
            Check(PassThruConnect(device,5,0x800,500000,out d2)==0,
                  "CAN 500 kbit/s connect failed");
            Check(PassThruConnect(device,6,0,500000,out p3)==0,
                  "ISO15765 connect failed");
            Console.WriteLine("PASS 2/8: same-process D2 CAN and P3 ISO channels");
            if(PayloadFilterProbe) {
                VerifyPayloadFilters(d2);
                return;
            }
            Write(d2,5,0x000FFFFE,new byte[]{0xCB,0x50,0xB9,0xFB,0,0,0,0});
            Console.WriteLine("PASS 3/8: B9FB request accepted by native DLL");
            byte[] controls=new byte[]{0x8F,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,
                                         0x0F,0x08,0x09,0x0A,0x0B,0x4F};
            if(CompositeLocked) {
                CheckNoRx(d2,"B9FB");
            } else for(int i=0;i<controls.Length;i++) {
                Msg result=Read(d2,5,0x01200003,300);
                Check(result.DataSize==12 && result.ExtraDataIndex==12 &&
                      (result.RxStatus & 0x100)!=0 &&
                      result.Data[4]==controls[i],
                      "Wrong B9FB native transport");
                if(i==0)
                    Check(result.Data[5]==0x50 && result.Data[6]==0xF9 &&
                          result.Data[7]==0xFB, "Wrong B9FB echo");
            }
            Console.WriteLine(CompositeLocked
                ? "PASS 4/8: imported mixed-origin B9FB safely suppressed"
                : "PASS 4/8: 13 synthetic B9FB frames delivered");
            Write(d2,5,0x000FFFFE,new byte[]{0xCB,0x50,0xB9,0xF0,0,0,0,0});
            byte[] b9f0=new byte[]{0x8F,0x09,0x4C};
            if(CompositeLocked) {
                CheckNoRx(d2,"B9F0");
            } else for(int i=0;i<3;i++) {
                Msg result=Read(d2,5,0x01000003,300);
                Check(result.DataSize==12 && result.ExtraDataIndex==12 &&
                      result.Data[4]==b9f0[i], "Wrong B9F0 frame");
                if(i==0)
                    Check(result.Data[5]==0x50 && result.Data[6]==0xF9 &&
                          result.Data[7]==0xF0, "Wrong B9F0 echo");
            }
            Console.WriteLine(CompositeLocked
                ? "PASS 5/8: imported mixed-origin B9F0 safely suppressed"
                : "PASS 5/8: 3 synthetic B9F0 frames delivered");
            Write(p3,6,0x726,new byte[]{0x22,0xF1,0x14});
            Console.WriteLine("PASS 6/8: later P3 F114 read on same native process");
            Msg uds=Read(p3,6,0x72E,300);
            Check(uds.DataSize==24 && uds.ExtraDataIndex==24 &&
                  uds.Data[4]==0x62 && uds.Data[5]==0xF1 &&
                  uds.Data[6]==0x14,
                  "Wrong P3 DID response header/length");
            byte[] lab=System.Text.Encoding.ASCII.GetBytes("VCARLAB0000000000");
            Check(lab.Length==17,"Synthetic lab VIN is not 17 bytes");
            for(int i=0;i<17;i++)
                Check(uds.Data[7+i]==lab[i],
                      "Unexpected synthetic P3 DID data");
            Console.WriteLine("PASS 7/8: positive synthetic P3 62 F1 14 via ISO15765");
            Check(PassThruDisconnect(p3)==0,"P3 disconnect failed");p3=0;
            Check(PassThruDisconnect(d2)==0,"D2 disconnect failed");d2=0;
            Console.WriteLine("PASS 8/8: both native channels closed");
        } finally {
            bool clean=true;
            if(p3!=0)clean &= PassThruDisconnect(p3)==0;
            if(d2!=0)clean &= PassThruDisconnect(d2)==0;
            if(opened)clean &= PassThruClose(device)==0;
            clean &= FreeLibrary(lib);
            Check(clean,"Native cleanup failed");
        }
    }
}
'@
    $source=$source.Replace('__ISOLATED_DLL__',$isolatedDll.Replace('"','""'))
    $source=$source.Replace('__COMPOSITE_LOCKED__',
                            $(if ($CompositeLocked) { 'true' } else { 'false' }))
    $source=$source.Replace('__PAYLOAD_FILTER_PROBE__',
                            $(if ($PayloadFilterProbe) { 'true' } else { 'false' }))
    Add-Type -TypeDefinition $source -Language CSharp
    [NativeP2P3Handoff]::Run()
    $nativeLog=Join-Path $directory 'SectorVVirtualCar.log'
    if (-not (Test-Path -LiteralPath $nativeLog)) {
        throw 'Isolated same-process native J2534 log not created'
    }
    if ($PayloadFilterProbe) {
        Write-Output 'PASS: isolated compiled x86 J2534 CAN PASS/BLOCK payload mask probe'
    } elseif ($CompositeLocked) {
        Write-Output 'PASS: unapproved mixed-origin x86 D2 silent; independent synthetic P3 read remains available'
    } else {
        Write-Output 'PASS: one-process x86 B9FB/B9F0/P3 native lab, no real diagnostic client'
    }
} finally {
    $env:LOCALAPPDATA=$savedLocal; $env:TEMP=$savedTemp; $env:TMP=$savedTmp
}
