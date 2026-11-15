#Requires -Version 5.1
# Explicit isolated DLL load only; no J2534 registration or physical adapter.
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$ProfilePath,
    [Parameter(Mandatory=$true)][string]$IdentityJson,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [string]$PythonExe = 'python'
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -ProfilePath $ProfilePath -IdentityJson $IdentityJson -OutputDirectory $OutputDirectory -PythonExe $PythonExe
    exit $LASTEXITCODE
}
& $PythonExe (Join-Path $PSScriptRoot 'build_b3a146_cem40_lab_profile.py') --validate-only --profile $ProfilePath --identity-json $IdentityJson
if ($LASTEXITCODE -ne 0) { throw 'Profile preflight failed' }
if (Test-Path -LiteralPath $OutputDirectory) { throw 'New isolated output directory required' }
$dir = [IO.Path]::GetFullPath($OutputDirectory)
$ancestor = [IO.DirectoryInfo]::new($dir)
while ($null -ne $ancestor) {
    if ((Test-Path -LiteralPath (Join-Path $ancestor.FullName '.git')) -or
        ($ancestor.Exists -and ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint))) {
        throw 'Private runtime output must be outside checkouts and redirected directories'
    }
    $ancestor = $ancestor.Parent
}
[void][IO.Directory]::CreateDirectory($dir)
$dll = Join-Path $dir 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $DllPath -Destination $dll
Copy-Item -LiteralPath $ProfilePath -Destination (Join-Path $dir 'virtualcar.ini')
# The preflight above establishes the exact INI contract. Retain expected
# bytes in memory only and compare every returned byte, including padding.
$expectedFrames=@{}; $section=''
foreach($line in [IO.File]::ReadAllLines((Join-Path $dir 'virtualcar.ini'))) {
    if($line -match '^\[([^\]]+)\]$') { $section=$Matches[1]; continue }
    if($line -match '^\s*(b9fbframe[0-9a-f]+|frame[0-9a-f]+)\s*=\s*(.+?)\s*$') {
        $expectedFrames[$section+'/'+$Matches[1]]=$Matches[2]
    }
}
function Frame-List([string]$Section,[string]$Prefix,[int]$Count) {
    $frames=for($i=0;$i -lt $Count;$i++) { $expectedFrames[$Section+'/'+$Prefix+$i.ToString('x')] }
    if(@($frames).Count -ne $Count -or @($frames | Where-Object { -not $_ }).Count) { throw 'Expected frames missing' }
    return $frames -join ';'
}
$f0=Frame-List 'D2_40_B9F0' 'frame' 3
$fb=Frame-List 'D2_40' 'b9fbframe' 13
$ae=Frame-List 'D2_40_AE1B' 'frame' 1
$f5=''; $f8=''
if($expectedFrames.ContainsKey('D2_40_B9F5/frame0')) {
    $f5=Frame-List 'D2_40_B9F5' 'frame' 1
    $f8=Frame-List 'D2_40_B9F8' 'frame' 1
}
$savedTemp=$env:TEMP; $savedLocal=$env:LOCALAPPDATA
try {
    $env:TEMP=$dir; $env:LOCALAPPDATA=$dir
    $source = @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
public static class CemLabRuntime {
    const string Dll = @"__DLL__";
    [StructLayout(LayoutKind.Sequential)] public struct Msg {
        public uint ProtocolID, RxStatus, TxFlags, Timestamp, DataSize, ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst=4128)] public byte[] Data;
    }
    [DllImport(Dll)] static extern uint PassThruOpen(IntPtr n,out uint d);
    [DllImport(Dll)] static extern uint PassThruClose(uint d);
    [DllImport(Dll)] static extern uint PassThruConnect(uint d,uint p,uint f,uint b,out uint c);
    [DllImport(Dll)] static extern uint PassThruDisconnect(uint c);
    [DllImport(Dll)] static extern uint PassThruStartMsgFilter(uint c,uint t,ref Msg m,ref Msg p,IntPtr flow,out uint f);
    [DllImport(Dll)] static extern uint PassThruWriteMsgs(uint c,ref Msg m,ref uint n,uint timeout);
    [DllImport(Dll)] static extern uint PassThruReadMsgs(uint c,ref Msg m,ref uint n,uint timeout);
    static void Check(bool ok) { if(!ok) throw new Exception("CEM lab native contract failed"); }
    static Msg Message() { return new Msg {ProtocolID=5,TxFlags=0x100,Data=new byte[4128]}; }
    public static void Run(string f0,string fb,string ae,string f5,string f8) {
        uint d,c,f; Check(PassThruOpen(IntPtr.Zero,out d)==0);
        try {
            Check(PassThruConnect(d,5,0x100,125000,out c)==0);
            try {
                Msg mask=Message(), pattern=Message(); mask.DataSize=pattern.DataSize=4;
                mask.Data[3]=pattern.Data[3]=1;
                Check(PassThruStartMsgFilter(c,1,ref mask,ref pattern,IntPtr.Zero,out f)==0);
                Probe(c,0xB9,0xF0,f0); Probe(c,0xB9,0xFB,fb); Probe(c,0xAE,0x1B,ae);
                if(f5.Length>0) { Probe(c,0xB9,0xF5,f5); Probe(c,0xB9,0xF8,f8); }
            } finally { PassThruDisconnect(c); }
        } finally { PassThruClose(d); }
    }
    static void Probe(uint c,byte service,byte mode,string expectedFrames) {
        string[] frames=expectedFrames.Split(';'); int expected=frames.Length;
        Msg tx=Message(); tx.DataSize=12;
        byte[] request={0,15,255,254,203,64,service,mode,0,0,0,0};
        Array.Copy(request,tx.Data,12); uint n=1;
        Stopwatch clock=Stopwatch.StartNew();
        Check(PassThruWriteMsgs(c,ref tx,ref n,100)==0 && n==1);
        double first=0,last=0,minGap=Double.MaxValue,maxGap=0;
        for(int i=0;i<expected;i++) {
            Msg rx=Message(); n=1; Check(PassThruReadMsgs(c,ref rx,ref n,1000)==0 && n==1);
            double now=clock.Elapsed.TotalMilliseconds;
            if(i==0) first=now; else { minGap=Math.Min(minGap,now-last); maxGap=Math.Max(maxGap,now-last); }
            last=now;
            Check(rx.ProtocolID==5 && rx.RxStatus==0x100 && rx.DataSize==12);
            Check(rx.Data[0]==0 && rx.Data[1]==128 && rx.Data[2]==0 && rx.Data[3]==3);
            if(i==0) Check(rx.Data[5]==64 && rx.Data[6]==service+64 && rx.Data[7]==mode);
            byte header=expected==1 ? (byte)203 : i==0 ? (byte)143 : i==expected-1 ? (byte)(mode==0xF0?76:79) : (byte)(8|(i&7));
            Check(rx.Data[4]==header);
            string[] bytes=frames[i].Split(new char[]{' '},StringSplitOptions.RemoveEmptyEntries);
            Check(bytes.Length==8);
            for(int j=0;j<8;j++) Check(rx.Data[4+j]==Convert.ToByte(bytes[j],16));
        }
        Msg empty=Message(); n=1; Check(PassThruReadMsgs(c,ref empty,ref n,0)==16 && n==0);
        Console.WriteLine("PASS {0:X2}{1:X2}: frames={2} first_ms={3:F3} last_ms={4:F3} gap_min_ms={5:F3} gap_max_ms={6:F3}",
            service,mode,expected,first,last,expected==1?0:minGap,maxGap);
    }
}
'@
    Add-Type -TypeDefinition $source.Replace('__DLL__', $dll.Replace('"','""'))
    [CemLabRuntime]::Run($f0,$fb,$ae,$f5,$f8)
    Write-Output 'PASS: every returned D2 byte equals the preflighted private profile.'
    Write-Output 'Native profile loaded and delivered; actual VIDA GUI acceptance NOT_VERIFIED.'
} finally { $env:TEMP=$savedTemp; $env:LOCALAPPDATA=$savedLocal }
