#Requires -Version 5.1
# B3A67: isolated x86 CAN_PS CEM40 pass-filter smoke. Synthetic lab only.
# No registration, physical hardware, original VIDA, or installed INI changes.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$LabIni,
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{64}$')][string]$ExpectedSha256,
    [Parameter(Mandatory=$true)][string]$OutputDirectory
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) {
    & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -LabIni $LabIni -ExpectedSha256 $ExpectedSha256 -OutputDirectory $OutputDirectory
    exit $LASTEXITCODE
}

$src = (Resolve-Path -LiteralPath $DllPath -ErrorAction Stop).Path
$lab = (Resolve-Path -LiteralPath $LabIni -ErrorAction Stop).Path
$out = [IO.Path]::GetFullPath($OutputDirectory)
$sourceDirectory = [IO.Path]::GetDirectoryName($src).TrimEnd('\')
if ([IO.Path]::GetFileName($src) -ine 'J2534CEM50PS.dll') { throw 'Only the named CEM50 PS lab provider can be used' }
if ([IO.Path]::GetFileName($lab) -ine 'virtualcar.ini') { throw 'Laboratory input must be named virtualcar.ini' }
if ((Test-Path -LiteralPath $out) -or
    $out.StartsWith($sourceDirectory + '\',[StringComparison]::OrdinalIgnoreCase) -or
    $out.StartsWith($env:WINDIR.TrimEnd('\') + '\',[StringComparison]::OrdinalIgnoreCase) -or
    $out.StartsWith($env:ProgramData.TrimEnd('\') + '\',[StringComparison]::OrdinalIgnoreCase) -or
    $out -ieq $sourceDirectory -or
    [IO.Path]::GetDirectoryName($lab).TrimEnd('\') -ieq $sourceDirectory) {
    throw 'Output must be new, outside the provider and system directories; input must be a separate lab INI'
}
if (-not (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($out)) -PathType Container)) {
    throw 'Output parent directory must already exist'
}
if ((Get-Item -LiteralPath $lab).Length -gt 524288) { throw 'Oversized INI' }
$sha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
if ($sha -ine $ExpectedSha256) { throw 'Pinned source DLL SHA256 mismatch' }
$peBytes = [IO.File]::ReadAllBytes($src)
if ($peBytes.Length -lt 256 -or $peBytes[0] -ne 0x4D -or $peBytes[1] -ne 0x5A) { throw 'Not PE' }
$pe = [BitConverter]::ToInt32($peBytes,0x3C)
if ($pe -lt 64 -or $pe+26 -ge $peBytes.Length -or
    $peBytes[$pe] -ne 0x50 -or $peBytes[$pe+1] -ne 0x45 -or
    [BitConverter]::ToUInt16($peBytes,$pe+4) -ne 0x014C -or
    [BitConverter]::ToUInt16($peBytes,$pe+24) -ne 0x010B) {
    throw 'Only x86 PE32 laboratory provider allowed'
}

# Parse just the synthetic INI; no bytes or VIN are printed.
$entries = @{}; $section = ''
foreach ($line in [IO.File]::ReadAllLines($lab)) {
    $item = $line.Trim()
    if (-not $item -or $item.StartsWith(';') -or $item.StartsWith('#')) { continue }
    if ($item -match '^\[([^\]]+)\]$') {
        $section = $Matches[1]
        if ($entries.ContainsKey($section)) { throw 'Duplicate INI section' }
        $entries[$section] = @{}
        continue
    }
    if ($item -match '^([^=]+?)\s*=\s*(.*?)\s*$') {
        if (-not $section) { throw 'Key outside section' }
        $key = $Matches[1].Trim(); $value = $Matches[2].Trim()
        if ($entries[$section].ContainsKey($key)) { throw 'Duplicate INI key' }
        $entries[$section][$key] = $value
    }
}
function V([string]$sectionName,[string]$keyName) {
    if (-not $entries.ContainsKey($sectionName)) { throw 'Missing synthetic lab section' }
    if (-not $entries[$sectionName].ContainsKey($keyName)) { throw 'Missing synthetic lab key' }
    return [string]$entries[$sectionName][$keyName]
}
if ((V 'P2' 'StrictRouting') -ne '1' -or
    (V 'P2' 'FixtureAuthority') -ne 'synthetic_d2_40_route_experiment_not_oem' -or
    (V 'P2' 'FixtureProvenance') -ne 'synthetic_public_2005_donor_retargeted_50_to_40_lab_only' -or
    (V 'J2534_2' 'Enabled') -ne '1' -or
    (V 'D2_40' 'ResponseId') -ne '00800003' -or
    (V 'D2_40' 'B9FBFrameCount') -ne '13' -or
    (V 'D2_50' 'B9FBFrameCount') -ne '13' -or
    (V 'D2_40_B9F0' 'FrameCount') -ne '0' -or
    (V 'D2_50_B9F0' 'FrameCount') -ne '0' -or
    (V 'D2_40_B9FC' 'FrameCount') -ne '0' -or
    (V 'D2_50_B9FC' 'FrameCount') -ne '0') {
    throw 'Input is not the isolated B3A65 synthetic profile'
}
if ($entries['D2_40'].ContainsKey('FrameCount')) { throw 'Ambiguous native FrameCount overrides B9FBFrameCount' }
$expected = New-Object 'System.String[]' 13
for ($i=0; $i -lt 13; $i++) {
    $value = V 'D2_40' ('B9FBFrame'+$i.ToString('X'))
    if ($value -notmatch '^(?:[0-9A-Fa-f]{2}\s+){7}[0-9A-Fa-f]{2}$') { throw 'Invalid lab D2 frame encoding' }
    $expected[$i] = $value
}
if ($expected[0] -notmatch '^8F\s+40\s+F9\s+FB\s+' -or
    $expected[12] -notmatch '^4F\s+') { throw 'Wrong synthetic target/sequence' }

[void][IO.Directory]::CreateDirectory($out)
$stagedDll = Join-Path $out 'J2534CEM50PS.dll'
$stagedIni = Join-Path $out 'virtualcar.ini'
Copy-Item -LiteralPath $src -Destination $stagedDll -ErrorAction Stop
Copy-Item -LiteralPath $lab -Destination $stagedIni -ErrorAction Stop
if ((Get-FileHash -LiteralPath $stagedDll -Algorithm SHA256).Hash -ine $sha) { throw 'Staged DLL mismatch' }
if ((Get-FileHash -LiteralPath $stagedIni -Algorithm SHA256).Hash -ine
    (Get-FileHash -LiteralPath $lab -Algorithm SHA256).Hash) { throw 'Staged lab INI mismatch' }

# Strict RX filters enabled on STAGED COPY only; input lab INI remains unchanged.
$cfgBefore=[IO.File]::ReadAllText($stagedIni)
if ($cfgBefore -match '(?im)^\s*\[Diagnostics\]\s*$') {
    throw 'Refusing lab INI with pre-existing Diagnostics section'
}
[IO.File]::AppendAllText($stagedIni,"`r`n[Diagnostics]`r`nStrictJ2534Filters = 1`r`n")


$wasLocal=$env:LOCALAPPDATA; $wasTemp=$env:TEMP; $wasTmp=$env:TMP
try {
    $env:LOCALAPPDATA=$out; $env:TEMP=$out; $env:TMP=$out
    $code=@'
using System;
using System.Runtime.InteropServices;
public static class B3A66CEM40Probe {
    const string Library=@"__DLL_PATH__";
    [StructLayout(LayoutKind.Sequential)]
    public struct Msg {
        public uint ProtocolID,RxStatus,TxFlags,Timestamp,DataSize,ExtraDataIndex;
        [MarshalAs(UnmanagedType.ByValArray,SizeConst=4128)] public byte[] Data;
    }
    [StructLayout(LayoutKind.Sequential)] public struct Config {public uint Parameter,Value;}
    [StructLayout(LayoutKind.Sequential)] public struct ConfigList {public uint Count;public IntPtr Ptr;}
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruOpen(IntPtr name,out uint dev);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruClose(uint dev);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruConnect(uint dev,uint protocol,uint flags,uint baud,out uint ch);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruDisconnect(uint ch);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruIoctl(uint ch,uint cmd,ref ConfigList cfg,IntPtr output);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruWriteMsgs(uint ch,ref Msg msg,ref uint count,uint timeout);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruReadMsgs(uint ch,IntPtr msg,ref uint count,uint timeout);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStartMsgFilter(uint ch,uint type,ref Msg mask,ref Msg pattern,IntPtr flow,out uint fid);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruStopMsgFilter(uint ch,uint fid);
    static void Require(bool value,string name) {
        if(!value)throw new InvalidOperationException("B3A67 failed: "+name);
    }
    static void SelectMsPins(uint channel) {
        IntPtr ptr=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Config)));
        try {
            Marshal.StructureToPtr(new Config{Parameter=0x8001u,Value=0x030Bu},ptr,false);
            ConfigList list=new ConfigList{Count=1u,Ptr=ptr};
            Require(PassThruIoctl(channel,2u,ref list,IntPtr.Zero)==0u,"J1962 SET_CONFIG");
            Marshal.StructureToPtr(new Config{Parameter=0x8001u,Value=0u},ptr,false);
            Require(PassThruIoctl(channel,1u,ref list,IntPtr.Zero)==0u,"J1962 GET_CONFIG");
            Config read=(Config)Marshal.PtrToStructure(ptr,typeof(Config));
            Require(read.Value==0x030Bu,"MS pin readback");
        } finally {Marshal.FreeHGlobal(ptr);}
    }
    static byte[] Parse(string value) {
        string[] tokens=value.Split((char[])null,StringSplitOptions.RemoveEmptyEntries);
        Require(tokens.Length==8,"expected INI frame width");
        byte[] bytes=new byte[8];
        for(int i=0;i<8;i++)bytes[i]=Convert.ToByte(tokens[i],16);
        return bytes;
    }
    static uint StartPassFilter(uint ch,uint maskId,uint matchId) {
        Msg mask=new Msg();mask.ProtocolID=0x8004u;mask.DataSize=4u;mask.Data=new byte[4128];
        Msg pattern=new Msg();pattern.ProtocolID=0x8004u;pattern.DataSize=4u;pattern.Data=new byte[4128];
        for(int i=0;i<4;i++) {
            int shift=(3-i)*8;
            mask.Data[i]=(byte)(maskId>>shift);
            pattern.Data[i]=(byte)(matchId>>shift);
        }
        uint fid=0u;
        Require(PassThruStartMsgFilter(ch,1u,ref mask,ref pattern,IntPtr.Zero,out fid)==0u && fid!=0u,
                "StartMsgFilter PASS CAN_PS");
        return fid;
    }
    public static void Run(string[] frameHex) {
        Require(frameHex!=null && frameHex.Length==13,"expected 13 frames");
        uint dev=0,ch=0;bool opened=false,connected=false;
        try {
            Require(PassThruOpen(IntPtr.Zero,out dev)==0u&&dev!=0u,"PassThruOpen");
            opened=true;
            Require(PassThruConnect(dev,0x8004u,0u,125000u,out ch)==0u&&ch!=0u,
                    "CAN_PS 125000 Connect");
            connected=true;
            SelectMsPins(ch);
            Msg tx=new Msg();
            tx.ProtocolID=0x8004u;tx.TxFlags=0x100u;tx.DataSize=12u;tx.Data=new byte[4128];
            byte[] payload={0,0x0F,0xFF,0xFE,0xCB,0x40,0xB9,0xFB,0,0,0,0};
            Array.Copy(payload,tx.Data,payload.Length);
            uint count=1u;
            uint filter=0u;
            IntPtr rx=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
            try {
                // Wrong exact 29-bit response ID must yield no RX.
                filter=StartPassFilter(ch,0xFFFFFFFFu,0x00800002u);
                Require(PassThruWriteMsgs(ch,ref tx,ref count,5000u)==0u&&count==1u,
                        "CAN_PS B9FB TX under wrong exact filter");
                count=1u;
                Require(PassThruReadMsgs(ch,rx,ref count,0u)==16u&&count==0u,
                        "wrong PASS filter blocks RX");
                Require(PassThruStopMsgFilter(ch,filter)==0u,"StopMsgFilter wrong");
                filter=0u;
                // A mask/pattern low-bit 1 candidate is documented in public VIDA work.
                // This verifies our DLL response, NOT original VIDA filter installation.
                filter=StartPassFilter(ch,0x00000001u,0x00000001u);
                count=1u;
                Require(PassThruWriteMsgs(ch,ref tx,ref count,5000u)==0u&&count==1u,
                        "CAN_PS B9FB TX under odd-ID pass filter");
                for(int i=0;i<13;i++) {
                    count=1u;
                    Require(PassThruReadMsgs(ch,rx,ref count,1500u)==0u&&count==1u,
                            "ReadMsgs frame "+i);
                    Msg got=(Msg)Marshal.PtrToStructure(rx,typeof(Msg));
                    Require(got.ProtocolID==0x8004u&&got.DataSize==12u &&
                            (got.RxStatus&0x100u)!=0u, "CAN_PS 29bit RX status "+i);
                    byte[] canId={0x00,0x80,0x00,0x03};
                    for(int j=0;j<4;j++)
                        Require(got.Data[j]==canId[j],"response ID "+i);
                    byte[] expected=Parse(frameHex[i]);
                    for(int j=0;j<8;j++)
                        Require(got.Data[4+j]==expected[j],"frame byte "+i+"/"+j);
                }
                count=1u;
                Require(PassThruReadMsgs(ch,rx,ref count,0u)==16u,
                        "no extra queued RX");
            } finally {
                if(filter!=0u)Require(PassThruStopMsgFilter(ch,filter)==0u,"StopMsgFilter odd");
                Marshal.FreeHGlobal(rx);
            }
        } finally {
            if(connected)Require(PassThruDisconnect(ch)==0u,"PassThruDisconnect");
            if(opened)Require(PassThruClose(dev)==0u,"PassThruClose");
        }
    }
}
'@
    $code=$code.Replace('__DLL_PATH__',$stagedDll)
    Add-Type -TypeDefinition $code -Language CSharp -ErrorAction Stop
    [B3A66CEM40Probe]::Run([string[]]$expected)
    $report=[ordered]@{
        schema_version='virtualcar-b3a67-cem40-filter-native-v1'
        status='CEM40_PS_FILTER_NATIVE_PASS'
        route='D2_40'
        protocol='CAN_PS'
        baud_bps=125000
        selected_pins='0x030B'
        staged_strict_j2534_filters=$true
        wrong_exact_id_filter_blocked_rx=$true
        odd_id_mask_one_filter_delivered_frames=13
        synthetic_frames_matched=13
        installed_ini_modified=$false
        j2534_rx_delivered_in_isolated_smoke=$true
        actual_vida_readvin_verified=$false
        oem_cem_verified=$false
        physical_adapter_used=$false
    }
    [IO.File]::WriteAllText((Join-Path $out 'cem40-filter-native-check.json'),
        ($report | ConvertTo-Json -Depth 4),[Text.Encoding]::UTF8)
    Write-Host 'CEM40_PS_FILTER_NATIVE_PASS: wrong filter blocks RX; odd-mask pass delivers 13/13 CAN_PS 125000'
    Write-Host 'Original VIDA filter installation / ReadVin / OEM CEM: NOT_VERIFIED'
} finally {
    $env:LOCALAPPDATA=$wasLocal; $env:TEMP=$wasTemp; $env:TMP=$wasTmp
}
