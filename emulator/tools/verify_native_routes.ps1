# Native x86 DLL regression. Synthetic profile, no registration or physical J2534.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [switch]$IdentityReplay,
    [switch]$CanMsPreflight
)
$ErrorActionPreference = 'Stop'
if ($CanMsPreflight -and $IdentityReplay) {
    throw 'Choose one synthetic native verification mode'
}
if ([IntPtr]::Size -ne 4) {
    if ($CanMsPreflight) {
        & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -OutputDirectory $OutputDirectory -CanMsPreflight
    } elseif ($IdentityReplay) {
        & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -OutputDirectory $OutputDirectory -IdentityReplay
    } else {
        & "$env:WINDIR\SysWOW64\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath -DllPath $DllPath -OutputDirectory $OutputDirectory
    }
    exit $LASTEXITCODE
}
$dll = (Resolve-Path -LiteralPath $DllPath).Path
$directory = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $directory) { throw 'Output directory must be new; refusing to overwrite files' }
[void][IO.Directory]::CreateDirectory($directory)
$isolatedDll = Join-Path $directory 'VirtualCarJ2534.dll'
Copy-Item -LiteralPath $dll -Destination $isolatedDll
# No live ECU identity. The optional replay uses source-shaped SYNTHETIC
# bytes already covered by the in-memory C transport tests.
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
B9FBFrameCount=__FRAME_COUNT__
__IDENTITY_FRAMES__
[PassiveCAN]
Enabled=0
[PassiveTrace]
Enabled=0
[Diagnostics]
BackendTelemetryEnabled=1
'@
if ($IdentityReplay) {
    # Synthetic only: same 13-frame transport fixture as virtualcar_test.c;
    # it is NOT an XC90 V8 MY2009 or OEM CEM identity record.
    $replay = @'
B9FBFrame0=8F 50 F9 FB 57 00 30 66
B9FBFrame1=09 70 28 30 30 35 0D 0A
B9FBFrame2=0A 59 56 31 43 5A 30 30
B9FBFrame3=0B 30 32 41 30 30 30 30
B9FBFrame4=0C 30 30 31 0D 0A 32 35
B9FBFrame5=0D 31 35 36 38 39 35 32
B9FBFrame6=0E 0D 0A 32 39 35 0D 0A
B9FBFrame7=0F 31 39 38 36 32 35 0D
B9FBFrame8=08 0A 32 31 0D 0A 32 30
B9FBFrame9=09 30 35 31 32 0D 0A 30
B9FBFrameA=0A 30 30 30 34 33 33 38
B9FBFrameB=0B 36 30 34 30 38 32 32
B9FBFrameC=4F 30 36 39 33 31 0D 0A
'@
    $profile = $profile.Replace('__FRAME_COUNT__', '13').Replace('__IDENTITY_FRAMES__', $replay.Trim())
} else {
    $profile = $profile.Replace('__FRAME_COUNT__', '0').Replace('__IDENTITY_FRAMES__', '')
}
if ($profile.Contains('__FRAME_COUNT__') -or $profile.Contains('__IDENTITY_FRAMES__')) {
    throw 'Synthetic profile fixture placeholders unresolved'
}
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
    static readonly bool IdentityReplay = __IDENTITY_REPLAY__;
    static readonly bool CanMsPreflight = __CAN_MS_PREFLIGHT__;
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
    static void Check(bool condition, string gate) { if (!condition) throw new Exception(gate); }
    static void Write(uint channel, uint protocol, uint id, byte[] payload) {
        Msg msg = new Msg(); msg.ProtocolID=protocol; msg.DataSize=(uint)payload.Length+4;
        msg.TxFlags=id>0x7ff ? 0x100u : 0u; msg.Data=new byte[4128];
        msg.Data[0]=(byte)(id>>24); msg.Data[1]=(byte)(id>>16);
        msg.Data[2]=(byte)(id>>8); msg.Data[3]=(byte)id;
        Array.Copy(payload,0,msg.Data,4,payload.Length);
        uint count=1; Check(PassThruWriteMsgs(channel,ref msg,ref count,10)==0 && count==1,"TX rejected");
    }
    static void Silent(uint channel, uint protocol, uint id, byte[] payload) {
        Write(channel,protocol,id,payload);
        Empty128(channel);
    }
    static Msg ReceiveOne(uint channel, uint timeout) {
        IntPtr buffer=Marshal.AllocHGlobal(Marshal.SizeOf(typeof(Msg)));
        try {
            uint count=1;
            Check(PassThruReadMsgs(channel,buffer,ref count,timeout)==0 && count==1,
                "Native read-only response missing");
            return (Msg)Marshal.PtrToStructure(buffer,typeof(Msg));
        } finally { Marshal.FreeHGlobal(buffer); }
    }
    static void CheckSyntheticB9FB(uint hs) {
        // Independently assert every byte and J2534 field on the real 32-bit DLL.
        byte[,] expected = new byte[13,8] {
            {0x8F,0x50,0xF9,0xFB,0x57,0x00,0x30,0x66},
            {0x09,0x70,0x28,0x30,0x30,0x35,0x0D,0x0A},
            {0x0A,0x59,0x56,0x31,0x43,0x5A,0x30,0x30},
            {0x0B,0x30,0x32,0x41,0x30,0x30,0x30,0x30},
            {0x0C,0x30,0x30,0x31,0x0D,0x0A,0x32,0x35},
            {0x0D,0x31,0x35,0x36,0x38,0x39,0x35,0x32},
            {0x0E,0x0D,0x0A,0x32,0x39,0x35,0x0D,0x0A},
            {0x0F,0x31,0x39,0x38,0x36,0x32,0x35,0x0D},
            {0x08,0x0A,0x32,0x31,0x0D,0x0A,0x32,0x30},
            {0x09,0x30,0x35,0x31,0x32,0x0D,0x0A,0x30},
            {0x0A,0x30,0x30,0x30,0x34,0x33,0x33,0x38},
            {0x0B,0x36,0x30,0x34,0x30,0x38,0x32,0x32},
            {0x4F,0x30,0x36,0x39,0x33,0x31,0x0D,0x0A}
        };
        Write(hs,5,0x000ffffe,new byte[]{0xCB,0x50,0xB9,0xFB,0,0,0,0});
        uint previous=0;
        for(int i=0;i<13;i++){
            Msg m=ReceiveOne(hs,150);
            Check(m.ProtocolID==5 && m.DataSize==12 && m.ExtraDataIndex==12 &&
                  m.RxStatus==0x100u,"B9FB J2534 metadata mismatch");
            Check(m.Data[0]==1 && m.Data[1]==0x20 && m.Data[2]==0 && m.Data[3]==3,
                  "B9FB source CAN ID mismatch");
            for(int b=0;b<8;b++) Check(m.Data[4+b]==expected[i,b],"B9FB frame content/sequence mismatch");
            if(i>0) Check(m.Timestamp!=previous,"B9FB replay did not advance its timestamp");
            previous=m.Timestamp;
        }
        Empty128(hs);
    }
    static void CheckSyntheticEcmVin(uint iso) {
        // Synthetic placeholder VIN from the isolated INI, not a vehicle ID.
        Write(iso,6,0x7e0,new byte[]{0x22,0xF1,0x90});
        Msg m=ReceiveOne(iso,150);
        Check(m.ProtocolID==6 && m.DataSize==24 && m.ExtraDataIndex==24 &&
              m.RxStatus==0,"ECM F190 J2534 metadata mismatch");
        Check(m.Data[0]==0 && m.Data[1]==0 && m.Data[2]==7 && m.Data[3]==0xE8,
              "ECM F190 response CAN ID mismatch");
        Check(m.Data[4]==0x62 && m.Data[5]==0xF1 && m.Data[6]==0x90,
              "ECM F190 UDS positive prefix mismatch");
        byte[] synthetic=System.Text.Encoding.ASCII.GetBytes("YV1CZ0002A0000001");
        Check(synthetic.Length==17,"Bad synthetic VIN fixture");
        for(int i=0;i<synthetic.Length;i++)
            Check(m.Data[7+i]==synthetic[i],"ECM F190 placeholder VIN mismatch");
        Empty128(iso);
    }
    static void Empty128(uint channel) {
        int bytes=Marshal.SizeOf(typeof(Msg))*128;
        IntPtr buffer=Marshal.AllocHGlobal(bytes);
        try { uint count=128; Check(PassThruReadMsgs(channel,buffer,ref count,0)==16 && count==0,"Unexpected RX or READ128 failure"); }
        finally { Marshal.FreeHGlobal(buffer); }
    }
    static void CheckSyntheticVidaCanMsPreflight(uint device) {
        uint canMs=0,isoMs=0,hsCan=0;
        uint rejected=0xC0DEFACEu;
        try {
            // Original VIDA source-shaped numeric channel arguments only.
            // This check does not execute VIDA or transmit any diagnostic bytes.
            Check(PassThruConnect(device,5,0x100u,125000,out canMs)==0 &&
                  canMs!=0,"CAN_MS 125k/0x100 connect failed");
            Console.WriteLine("PASS B3A331 gate 3: CAN 5 / flags 0x100 / 125000");
            Check(PassThruConnect(device,6,0,125000,out isoMs)==0 &&
                  isoMs!=0 && isoMs!=canMs,"ISO15765_PS 125k connect failed");
            Console.WriteLine("PASS B3A331 gate 4: ISO15765 6 / flags 0 / 125000");
            Check(PassThruConnect(device,5,0x800u,500000,out hsCan)==0 &&
                  hsCan!=0 && hsCan!=canMs && hsCan!=isoMs,
                  "Independent 500k CAN channel rejected");
            Console.WriteLine("PASS B3A331 gate 5: simultaneous 500k channel distinct");
            Check(PassThruConnect(device,0x8004u,0,125000,out rejected)==3u &&
                  rejected==0xC0DEFACEu,
                  "Vendor 0x8004 falsely accepted");
            Check(PassThruConnect(device,0x8005u,0,125000,out rejected)==3u &&
                  rejected==0xC0DEFACEu,
                  "Vendor 0x8005 falsely accepted");
            Console.WriteLine("PASS B3A331 gate 6: vendor 0x8004/0x8005 rejected");
        } finally {
            bool released=true;
            if(hsCan!=0) released &= PassThruDisconnect(hsCan)==0;
            if(isoMs!=0) released &= PassThruDisconnect(isoMs)==0;
            if(canMs!=0) released &= PassThruDisconnect(canMs)==0;
            Check(released,"J2534 CAN-MS channel release failed");
        }
        Console.WriteLine("PASS B3A331 gate 7: all synthetic channels disconnected");
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
            if(CanMsPreflight) {
                Console.WriteLine("PASS B3A331 gate 1: x86 ABI and 14 exports");
                Console.WriteLine("PASS B3A331 gate 2: PassThruOpen");
                CheckSyntheticVidaCanMsPreflight(device);
                Check(PassThruClose(device)==0,"CAN-MS preflight Close failed");
                opened=false;
                Console.WriteLine("PASS B3A331 gate 8: PassThruClose; no WriteMsgs/ReadMsgs or original client");
                return;
            }
            Check(PassThruConnect(device,5,0x800,500000,out hs)==0,"HS connect failed");
            Check(PassThruConnect(device,5,0x800,125000,out ls)==0,"LS connect failed");
            for(int k=0;k<3;k++) Silent(hs,5,0x7e0,new byte[]{2,0x3e,0x80});
            for(int k=0;k<3;k++) Silent(ls,5,0x7e0,new byte[]{2,0x3e,0x80});
            Console.WriteLine("PASS group 2: six silent physical ECM TX, simultaneous HS/LS");
            Check(PassThruConnect(device,6,0,500000,out iso)==0,"ISO connect failed");
            Silent(iso,6,0x7e0,new byte[]{0x3e,0x80});
            Console.WriteLine("PASS group 3: ISO15765 physical suppression");
            Silent(ls,5,0x000ffffe,new byte[]{0xcb,0x40,0xb9,0xfb,0,0,0,0});
            if(IdentityReplay) {
                CheckSyntheticB9FB(hs);
                Console.WriteLine("PASS group 4: synthetic 13-frame B9FB native x86 replay");
            } else {
                Silent(hs,5,0x000ffffe,new byte[]{0xcb,0x50,0xb9,0xfb,0,0,0,0});
                Console.WriteLine("PASS group 4: B9FB missing fixtures, no RX");
            }
            Check(PassThruConnect(device,5,0x800,250000,out wrong)==0,"250 connect failed");
            Silent(wrong,5,0x000ffffe,new byte[]{0xcb,0x50,0xb9,0xfb,0,0,0,0});
            if(IdentityReplay)
                Silent(ls,5,0x000ffffe,new byte[]{0xcb,0x50,0xb9,0xfb,0,0,0,0});
            Console.WriteLine("PASS group 5: strict B9FB baud rejection");
            Silent(hs,5,0x726,new byte[]{3,0x22,0xf1,0x14,0,0,0,0});
            Silent(iso,6,0x726,new byte[]{0x22,0xf1,0x14});
            Console.WriteLine("PASS group 6: absent P3 node, CAN and ISO15765");
            Silent(iso,6,0x7df,new byte[]{0x3e,0x80});
            Console.WriteLine("PASS group 7: functional suppression, no RX");
            Empty128(hs); Empty128(ls); Empty128(iso); Empty128(wrong);
            Console.WriteLine("PASS group 8: READ128 on all empty channels");
            if(IdentityReplay) {
                CheckSyntheticEcmVin(iso);
                Console.WriteLine("PASS group 9: isolated synthetic ECM F190 native ISO15765 VIN");
            }
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
    $source = $source.Replace('__IDENTITY_REPLAY__', $(if ($IdentityReplay) { 'true' } else { 'false' }))
    $source = $source.Replace('__CAN_MS_PREFLIGHT__', $(if ($CanMsPreflight) { 'true' } else { 'false' }))
    Add-Type -TypeDefinition $source -Language CSharp
    [NativeRouteCheck]::Run()
    $backend = Join-Path $directory 'VirtualCar/dev47-backend.jsonl'
    if (-not $CanMsPreflight -and -not (Test-Path -LiteralPath $backend)) {
        throw 'Native DLL produced no backend evidence'
    }
    if ($CanMsPreflight) {
        Write-Output 'PASS B3A331: owner-independent x86 virtual CAN-MS channel lifecycle; no diagnostics, no original VIDA, no VIN/ECU acceptance.'
    } elseif ($IdentityReplay) {
        Write-Output 'Native identity replay assertions passed. The silent-route Python verifier does not support this mode.'
    } else {
        Write-Output 'Native calls passed. Verify the isolated backend with verify_native_routes.py.'
    }
} finally {
    $env:LOCALAPPDATA = $savedLocal
    $env:TEMP = $savedTemp
    $env:TMP = $savedTmp
}
