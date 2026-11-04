# Isolated Windows x86 J2534 test of a synthetic B9FB -> A3 boundary.
# It is NOT a SectorV/VIDA replay, real XC90 identity, or A3/E3 authorization.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$FixtureProfile
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    $childArgs = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                   $PSCommandPath, '-DllPath', $DllPath,
                   '-OutputDirectory', $OutputDirectory)
    if ($FixtureProfile) { $childArgs += @('-FixtureProfile', $FixtureProfile) }
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" @childArgs
    exit $LASTEXITCODE
}
$dll = (Resolve-Path -LiteralPath $DllPath).Path
$directory = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $directory) { throw 'Refusing existing native B9FB audit directory' }
[void][IO.Directory]::CreateDirectory($directory)
$isolatedDll = Join-Path $directory 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $dll -Destination $isolatedDll

# Default uses an all-zero synthetic B9FB body. The optional INI is
# a separate laboratory-only donor fixture, not a verified XC90 MY2009.
# Both modes require exact J2534 RX byte equality to the configured frames.
$controls = @(0x8F, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
              0x08, 0x09, 0x0A, 0x0B, 0x4F)
$profile = New-Object Text.StringBuilder
[void]$profile.AppendLine('; SYNTHETIC D2 framing test. Not a real CEM B9FB identity.')
[void]$profile.AppendLine('[Vehicle]')
[void]$profile.AppendLine('VIN=VCARLAB0000000000')
[void]$profile.AppendLine('ECUCount=1')
[void]$profile.AppendLine('BatteryMv=12500')
[void]$profile.AppendLine('[ECU0]')
[void]$profile.AppendLine('RequestId=7E0')
[void]$profile.AppendLine('ResponseId=7E8')
[void]$profile.AppendLine('[P2]')
[void]$profile.AppendLine('StrictRouting=1')
[void]$profile.AppendLine('ReplaySpacingMs=12')
[void]$profile.AppendLine('[D2_40]')
[void]$profile.AppendLine('B9FBFrameCount=0')
[void]$profile.AppendLine('[D2_50]')
[void]$profile.AppendLine('ResponseId=01200003')
[void]$profile.AppendLine('B9FBFrameCount=13')
for ($i=0; $i -lt $controls.Count; $i++) {
    $bytes = New-Object byte[] 8
    $bytes[0] = [byte]$controls[$i]
    if ($i -eq 0) {
        $bytes[1] = 0x50; $bytes[2] = 0xF9; $bytes[3] = 0xFB
        $bytes[4] = 0x57  # Payload shape marker only, not a validated VIN schema.
    }
    $hex = ($bytes | ForEach-Object { $_.ToString('X2') }) -join ' '
    [void]$profile.AppendLine(('B9FBFrame{0:X}={1}' -f $i, $hex))
}
[void]$profile.AppendLine('[PassiveCAN]')
[void]$profile.AppendLine('Enabled=0')
[void]$profile.AppendLine('[PassiveTrace]')
[void]$profile.AppendLine('Enabled=0')
[void]$profile.AppendLine('[Diagnostics]')
[void]$profile.AppendLine('BackendTelemetryEnabled=1')
$chosen = $profile.ToString()
if ($FixtureProfile) {
    $sourcePath = (Resolve-Path -LiteralPath $FixtureProfile).Path
    $chosen = [IO.File]::ReadAllText($sourcePath, [Text.Encoding]::UTF8)
    if ($chosen -match '(?im)^\s*\[Diagnostics\]\s*$') {
        throw 'Lab fixture must not override native evidence logging'
    }
    # The repository donor INI is immutable; append telemetry only to
    # this isolated test copy to enable the backend lifecycle audit.
    $chosen += "`r`n[Diagnostics]`r`nBackendTelemetryEnabled=1`r`n"
}
if ($chosen -notmatch '(?im)^\s*StrictRouting\s*=\s*1\s*$' -or
    $chosen -notmatch '(?im)^\s*B9FBFrameCount\s*=\s*13\s*$' -or
    $chosen -notmatch '(?im)^\s*ResponseId\s*=\s*01200003\s*$') {
    throw 'Expected strict 13-frame CEM50 laboratory B9FB fixture'
}
# Build C# constants from strict 8-byte frame literals, never Vehicle.VIN.
$expectedRows = New-Object 'System.Collections.Generic.List[string]'
for ($i=0; $i -lt $controls.Count; $i++) {
    $name = 'B9FBFrame' + $i.ToString('X')
    $pattern = '(?im)^\s*' + $name + '\s*=\s*([0-9a-fA-F ]+)\s*$'
    $match = [regex]::Match($chosen, $pattern)
    if (-not $match.Success) { throw 'Missing configured B9FB frame' }
    $parts = @($match.Groups[1].Value.Trim() -split '\s+')
    if ($parts.Count -ne 8) { throw 'Invalid B9FB frame byte count' }
    $frame = New-Object byte[] 8
    for ($j=0; $j -lt 8; $j++) {
        if ($parts[$j] -notmatch '^[0-9a-fA-F]{2}$') {
            throw 'Invalid B9FB hex byte'
        }
        $frame[$j] = [Convert]::ToByte($parts[$j],16)
    }
    if ($frame[0] -ne $controls[$i]) {
        throw 'B9FB continuation sequence mismatch'
    }
    if ($i -eq 0 -and ($frame[1] -ne 0x50 -or
                      $frame[2] -ne 0xF9 -or $frame[3] -ne 0xFB)) {
        throw 'Positive B9FB echo missing'
    }
    $literals = ($frame | ForEach-Object { '0x{0:X2}' -f $_ }) -join ','
    $expectedRows.Add(('new byte[]{{{0}}}' -f $literals))
}
[IO.File]::WriteAllText((Join-Path $directory 'virtualcar.ini'),
                        $chosen, [Text.Encoding]::ASCII)
$savedLocal=$env:LOCALAPPDATA; $savedTemp=$env:TEMP; $savedTmp=$env:TMP
try {
    $env:LOCALAPPDATA=$directory; $env:TEMP=$directory; $env:TMP=$directory
    $source=@'
using System;
using System.Runtime.InteropServices;
public static class NativeB9FBA3Check {
    const string Library=@"__ISOLATED_DLL__";
    static readonly byte[][] ExpectedFrames = new byte[][] {
        __EXPECTED_FRAMES__
    };
    [StructLayout(LayoutKind.Sequential)]
    public struct Msg {
        public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray,SizeConst=4128)]
        public byte[] Data;
    }
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)]
    static extern IntPtr LoadLibraryW(string name);
    [DllImport("kernel32.dll",CharSet=CharSet.Ansi,ExactSpelling=true)]
    static extern IntPtr GetProcAddress(IntPtr library,string export);
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
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruWriteMsgs(uint channel,ref Msg message,ref uint count,uint timeout);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruReadMsgs(uint channel,IntPtr messages,ref uint count,uint timeout);

    static void Check(bool passed,string gate) {
        if(!passed) throw new InvalidOperationException(gate);
    }
    static Msg Request(byte target,byte service) {
        Msg message=new Msg();
        message.ProtocolID=5; message.TxFlags=0x100; message.DataSize=12;
        message.Data=new byte[4128];
        message.Data[0]=0x00; message.Data[1]=0x0F;
        message.Data[2]=0xFF; message.Data[3]=0xFE;
        if(service==0xB9) {
            message.Data[4]=0xCB; message.Data[5]=target;
            message.Data[6]=0xB9; message.Data[7]=0xFB;
        } else {
            message.Data[4]=0xCF; message.Data[5]=target;
            message.Data[6]=0xA3; message.Data[7]=0x02;
            message.Data[8]=0x03; message.Data[9]=0xA5;
            message.Data[10]=0xA5; message.Data[11]=0;
        }
        return message;
    }
    static void Write(uint channel,byte target,byte service) {
        Msg message=Request(target,service);
        uint count=1;
        Check(PassThruWriteMsgs(channel,ref message,ref count,2000)==0 && count==1,
              "Native J2534 WriteMsgs rejected synthetic request");
    }
    static uint NoRx(uint channel,uint timeout) {
        IntPtr buffer=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg))*128);
        try {
            uint count=128;
            uint code=PassThruReadMsgs(channel,buffer,ref count,timeout);
            Check(count==0,"Unexpected extra or cross-channel RX");
            return code;
        } finally { Marshal.FreeHGlobal(buffer); }
    }
    static Msg ReadSingle(uint channel) {
        IntPtr buffer=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try {
            uint count=1;
            uint status=PassThruReadMsgs(channel,buffer,ref count,120);
            Check(status==0 && count==1,"Missing or late D2 fragment");
            return (Msg)Marshal.PtrToStructure(buffer,typeof(Msg));
        } finally { Marshal.FreeHGlobal(buffer); }
    }
    public static void Run() {
        Check(IntPtr.Size==4 && Marshal.SizeOf(typeof(Msg))==4152,"x86 J2534 ABI");
        IntPtr module=LoadLibraryW(Library);
        Check(module!=IntPtr.Zero,"Native module LoadLibrary failed");
        uint device=0,hs=0,ls=0;bool opened=false;
        try {
            foreach(string api in new string[]{"Open","Close","Connect","Disconnect","WriteMsgs","ReadMsgs"})
                Check(GetProcAddress(module,"PassThru"+api)!=IntPtr.Zero,"Missing J2534 export");
            Console.WriteLine("PASS 1/8: x86 ABI and core J2534 exports");
            Check(PassThruOpen(IntPtr.Zero,out device)==0,"Open failed");opened=true;
            Check(PassThruConnect(device,5,0x800,500000,out hs)==0,"HS/500 connect failed");
            Check(PassThruConnect(device,5,0x800,125000,out ls)==0,"LS/125 connect failed");
            Console.WriteLine("PASS 2/8: isolated HS and LS channels");
            Write(hs,0x50,0xB9);
            Console.WriteLine("PASS 3/8: positive-response fixture requested through native WriteMsgs");
            byte[] controls=new byte[]{
                0x8F,0x09,0x0A,0x0B,0x0C,0x0D,0x0E,0x0F,0x08,0x09,0x0A,0x0B,0x4F};
            uint firstTimestamp=0, lastTimestamp=0;
            for(int i=0;i<controls.Length;i++){
                Msg response=ReadSingle(hs);
                Check(response.ProtocolID==5 && response.DataSize==12
                      && response.ExtraDataIndex==12
                      && (response.RxStatus & 0x100)==0x100
                      && (response.RxStatus & 0x0B)==0,
                      "Invalid native CAN RX metadata");
                Check(response.Data[0]==0x01 && response.Data[1]==0x20
                      && response.Data[2]==0x00 && response.Data[3]==0x03
                      && response.Data[4]==controls[i],
                      "Incorrect native D2 CAN ID or frame order");
                for(int octet=0;octet<8;octet++)
                    Check(response.Data[4+octet]==ExpectedFrames[i][octet],
                          "Native J2534 RX differs from configured B9FB frame");
                if(i==0) {
                    Check(response.Data[5]==0x50 && response.Data[6]==0xF9
                          && response.Data[7]==0xFB,"First-frame positive B9FB echo mismatch");
                    firstTimestamp=response.Timestamp;
                }
                if(i>0) Check(unchecked(response.Timestamp-lastTimestamp)<60000000u,
                              "D2 timestamp not source-local or nonmonotonic");
                lastTimestamp=response.Timestamp;
            }
            Console.WriteLine("PASS 4/8: 13 B9FB frames match lab INI byte-for-byte over J2534");
            Check(NoRx(hs,0)==16 && NoRx(ls,0)==16,"Stale or cross-bus D2 frames");
            Console.WriteLine("PASS 5/8: B9FB queue drained and LS route isolated");
            Write(hs,0x50,0xA3);
            Check(NoRx(hs,20)==9,"HS A3 unexpectedly received a CEM response");
            Console.WriteLine("PASS 6/8: subsequent HS A3 has J2534 timeout, no E3");
            Write(ls,0x40,0xA3);
            Check(NoRx(ls,20)==9,"LS A3 unexpectedly received a CEM response");
            Console.WriteLine("PASS 7/8: LS A3 has J2534 timeout, no E3");
            Write(hs,0x40,0xA3); // mismatched CAN bus, no simulated ECU response
            Check(NoRx(hs,0)==16,"Wrong-bus A3 produced a response");
            Write(ls,0x40,0xB9);
            Check(NoRx(ls,0)==16,"Unconfigured LS B9FB created an RX fixture");
            Console.WriteLine("PASS 8/8: wrong-bus A3 and missing B9FB fixture remain silent");
            Check(unchecked(lastTimestamp-firstTimestamp)<60000000u,
                  "Out-of-bounds D2 delivery timestamps");
        } finally {
            bool clean=true;
            if(ls!=0) clean &= PassThruDisconnect(ls)==0;
            if(hs!=0) clean &= PassThruDisconnect(hs)==0;
            if(opened) clean &= PassThruClose(device)==0;
            clean &= FreeLibrary(module);
            Check(clean,"Native cleanup failed");
        }
    }
}
'@
    $source=$source.Replace('__ISOLATED_DLL__',$isolatedDll.Replace('"','""'))
    $source=$source.Replace('__EXPECTED_FRAMES__',($expectedRows -join ",`n        "))
    Add-Type -TypeDefinition $source -Language CSharp
    [NativeB9FBA3Check]::Run()
    $backend=Join-Path $directory 'VirtualCar/dev47-backend.jsonl'
    if (-not (Test-Path -LiteralPath $backend)) { throw 'Synthetic B9FB/A3 native backend evidence missing' }
    Write-Output 'Native B9FB -> A3 passed. Verify the backend lifecycle separately.'
} finally {
    $env:LOCALAPPDATA=$savedLocal; $env:TEMP=$savedTemp; $env:TMP=$savedTmp
}
