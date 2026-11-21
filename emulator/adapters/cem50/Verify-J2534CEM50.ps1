#Requires -Version 5.1
# Owner-local x86 native CEM50 B9FB read-only J2534 smoke.
# Uses only a copied DLL and the published profile; no registry, VIDA or physical ECU.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Fa-f0-9]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -ExpectedSha256 $ExpectedSha256 -OutputDirectory $OutputDirectory
    exit $LASTEXITCODE
}
$src = (Resolve-Path -LiteralPath $DllPath).Path
$sourceIni = Join-Path $PSScriptRoot 'virtualcar.ini'
$dir = [IO.Path]::GetFullPath($OutputDirectory)
if (-not (Test-Path -LiteralPath $sourceIni) -or
    [IO.Directory]::Exists($dir) -or
    [IO.File]::Exists($dir)) {
    throw 'Missing published INI or existing output directory'
}
# A physical J2534 driver must never be used for this isolated synthetic test.
if ([IO.Path]::GetFileName($src) -ine 'VirtualCarJ2534.dll') {
    throw 'Expected emulator source DLL by exact file name; do not use physical J2534 DLL'
}
$peBytes = [IO.File]::ReadAllBytes($src)
if ($peBytes.Length -lt 256 -or $peBytes[0] -ne 0x4D -or $peBytes[1] -ne 0x5A) {
    throw 'Expected x86 PE32 emulator DLL'
}
$offset = [BitConverter]::ToInt32($peBytes, 0x3C)
if ($offset -lt 64 -or $offset + 26 -ge $peBytes.Length -or
    $peBytes[$offset] -ne 0x50 -or $peBytes[$offset+1] -ne 0x45 -or
    [BitConverter]::ToUInt16($peBytes,$offset+4) -ne 0x014C -or
    [BitConverter]::ToUInt16($peBytes,$offset+24) -ne 0x010B) {
    throw 'Expected x86 PE32 emulator DLL'
}
$sha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
if ($sha -ine $ExpectedSha256) { throw 'x86 J2534 DLL SHA256 mismatch' }
$iniText = [IO.File]::ReadAllText($sourceIni)
if (-not $iniText.Contains('VIN = YV1CR855691511566') -or
    -not $iniText.Contains('B9FBFrameCount = 13')) {
    throw 'Unexpected CEM50 reference profile'
}
[void][IO.Directory]::CreateDirectory($dir)
$stagedDll = Join-Path $dir 'J2534CEM50.dll'
Copy-Item -LiteralPath $src -Destination $stagedDll
Copy-Item -LiteralPath $sourceIni -Destination (Join-Path $dir 'virtualcar.ini')
if ((Get-FileHash -LiteralPath $stagedDll -Algorithm SHA256).Hash -ine $sha) {
    throw 'Staged DLL SHA mismatch'
}
$savedLocal = $env:LOCALAPPDATA
$savedTemp = $env:TEMP
$savedTmp = $env:TMP
try {
    $env:LOCALAPPDATA = $dir
    $env:TEMP = $dir
    $env:TMP = $dir
    $cs = @'
using System;
using System.Runtime.InteropServices;
public static class CEM50NativeProbe {
    const string Library = @"__DLL_PATH__";
    [StructLayout(LayoutKind.Sequential)]
    public struct Msg {
        public uint ProtocolID, RxStatus, TxFlags, Timestamp, DataSize, ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray, SizeConst=4128)] public byte[] Data;
    }
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
    static void Require(bool ok, string gate) {
        if (!ok) throw new InvalidOperationException("CEM50 native probe failed: " + gate);
    }
    static readonly byte[,] Frames = new byte[13,8] {
        {0x8F,0x50,0xF9,0xFB,0x57,0x00,0x30,0x66},
        {0x09,0x70,0x28,0x30,0x30,0x35,0x0D,0x0A},
        {0x0A,0x59,0x56,0x31,0x43,0x52,0x38,0x35},
        {0x0B,0x35,0x36,0x39,0x31,0x35,0x31,0x31},
        {0x0C,0x35,0x36,0x36,0x0D,0x0A,0x32,0x35},
        {0x0D,0x31,0x35,0x36,0x38,0x39,0x35,0x32},
        {0x0E,0x0D,0x0A,0x32,0x39,0x35,0x0D,0x0A},
        {0x0F,0x35,0x31,0x31,0x35,0x36,0x36,0x0D},
        {0x08,0x0A,0x32,0x31,0x0D,0x0A,0x32,0x30},
        {0x09,0x30,0x35,0x31,0x32,0x0D,0x0A,0x30},
        {0x0A,0x30,0x30,0x30,0x34,0x33,0x33,0x38},
        {0x0B,0x36,0x30,0x34,0x30,0x38,0x32,0x32},
        {0x4F,0x30,0x36,0x39,0x33,0x31,0x0D,0x0A}
    };
    public static void Run() {
        uint device=0, channel=0;
        bool opened=false, connected=false;
        try {
            Require(PassThruOpen(IntPtr.Zero, out device)==0 && device!=0, "PassThruOpen");
            opened=true;
            Require(PassThruConnect(device,5u,0u,500000u,out channel)==0 && channel!=0, "CAN 500k Connect");
            connected=true;
            Msg request=new Msg();
            request.ProtocolID=5u; request.TxFlags=0x100u; request.DataSize=12u;
            request.Data=new byte[4128];
            byte[] id={0x00,0x0F,0xFF,0xFE};
            byte[] payload={0xCB,0x50,0xB9,0xFB,0,0,0,0};
            Array.Copy(id,0,request.Data,0,4);
            Array.Copy(payload,0,request.Data,4,8);
            uint count=1;
            Require(PassThruWriteMsgs(channel,ref request,ref count,5000)==0 && count==1,
                    "CEM50 B9FB WriteMsgs");
            IntPtr ptr=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
            try {
                for (int n=0;n<13;n++) {
                    count=1;
                    uint rc=PassThruReadMsgs(channel,ptr,ref count,1500);
                    Require(rc==0 && count==1, "ReadMsgs frame "+n);
                    Msg incoming=(Msg)Marshal.PtrToStructure(ptr,typeof(Msg));
                    Require(incoming.ProtocolID==5u && incoming.DataSize==12u &&
                            (incoming.RxStatus & 0x100u)!=0, "29-bit CAN RX shape "+n);
                    byte[] responseId={0x01,0x20,0x00,0x03};
                    for (int j=0;j<4;j++)
                        Require(incoming.Data[j]==responseId[j], "CAN response ID frame "+n);
                    for (int j=0;j<8;j++)
                        Require(incoming.Data[j+4]==Frames[n,j], "D2 data frame "+n+" byte "+j);
                }
                count=1;
                Require(PassThruReadMsgs(channel,ptr,ref count,0)==16,
                        "no unexpected extra RX");
            } finally {
                Marshal.FreeHGlobal(ptr);
            }
        } finally {
            if (connected) {
                Require(PassThruDisconnect(channel)==0, "PassThruDisconnect");
            }
            if (opened) {
                Require(PassThruClose(device)==0, "PassThruClose");
            }
        }
        Console.WriteLine("CEM50_NATIVE_PASS: 13/13 exact D2 frames");
    }
}
'@
    $cs = $cs.Replace('__DLL_PATH__', $stagedDll)
    Add-Type -TypeDefinition $cs -Language CSharp -ErrorAction Stop
    [CEM50NativeProbe]::Run()
    $report = [ordered]@{
        schema_version = 'cem50_native_x86_fixture_v1'
        status = 'CEM50_NATIVE_PASS'
        published_vin = 'YV1CR855691511566'
        actual_can_baud = 500000
        expected_response_id = '01200003'
        actual_matched_frame_count = 13
        dll_sha256 = $sha
        vida_readvin_verified = $false
        ecu_identification_verified = $false
        physical_adapter_used = $false
    }
    $json = $report | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText((Join-Path $dir 'native-check.json'),$json,[Text.Encoding]::UTF8)
    Write-Host "CEM50_NATIVE_PASS: report $dir\native-check.json"
} finally {
    $env:LOCALAPPDATA = $savedLocal
    $env:TEMP = $savedTemp
    $env:TMP = $savedTmp
}
