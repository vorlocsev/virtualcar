# Virtual Car / original VIDA J2534 CAN-MS capability check.
# Owner-local, virtual-driver-only. Does not send frames or start VIDA.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$DllPath,
    [string]$OutputDirectory = (Join-Path $env:USERPROFILE 'VIDA-original-private')
)
$ErrorActionPreference = 'Stop'
if ([IntPtr]::Size -ne 4) { throw 'Run this script with 32-bit Windows PowerShell (SysWOW64), because the virtual J2534 DLL is x86.' }
$path = [IO.Path]::GetFullPath($DllPath)
if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw "DLL not found: $path" }
if ([IO.Path]::GetFileName($path) -cne 'VirtualCarJ2534.dll') { throw 'Only VirtualCarJ2534.dll is permitted. Never run this probe on a physical adapter DLL.' }
$stream = [IO.File]::OpenRead($path)
try {
    $reader = New-Object IO.BinaryReader($stream)
    if ($reader.ReadUInt16() -ne 0x5A4D) { throw 'Not a PE file' }
    $stream.Position = 0x3C
    $pe = $reader.ReadInt32()
    if ($pe -lt 64 -or $pe -gt ($stream.Length - 26)) { throw 'Invalid PE offset' }
    $stream.Position = $pe
    if ($reader.ReadUInt32() -ne 0x00004550) { throw 'Invalid PE signature' }
    if ($reader.ReadUInt16() -ne 0x014C) { throw 'Not PE32 x86' }
    $stream.Position = $pe + 24
    if ($reader.ReadUInt16() -ne 0x010B) { throw 'Not a PE32 optional header' }
} finally { $stream.Dispose() }

Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class VirtualCarJ2534ProbeNative {
    [DllImport("kernel32.dll", EntryPoint="LoadLibraryW", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern IntPtr LoadLibrary(string path);
    [DllImport("kernel32.dll", EntryPoint="GetProcAddress", CharSet=CharSet.Ansi, SetLastError=true)]
    public static extern IntPtr GetProcAddress(IntPtr module, string name);
    [DllImport("kernel32.dll", EntryPoint="FreeLibrary", SetLastError=true)]
    [return: MarshalAs(UnmanagedType.Bool)] public static extern bool FreeLibrary(IntPtr module);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate uint OpenDelegate(IntPtr name, out uint device);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate uint ConnectDelegate(uint device, uint protocol, uint flags, uint baud, out uint channel);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate uint DisconnectDelegate(uint channel);
    [UnmanagedFunctionPointer(CallingConvention.StdCall)]
    public delegate uint CloseDelegate(uint device);
}
'@ -ErrorAction Stop

$module = [VirtualCarJ2534ProbeNative]::LoadLibrary($path)
if ($module -eq [IntPtr]::Zero) { throw "LoadLibrary failed (Win32 $([Runtime.InteropServices.Marshal]::GetLastWin32Error()))" }
$device = [uint32]0
$opened = $false
$result = [ordered]@{
    Schema = 'virtualcar-vida-canms-j2534-probe-v1'
    CapturedAt = (Get-Date -Format o)
    OriginalDllPath = $path
    OriginalDllSha256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    ProcessArchitecture = 'x86'
    ProbeScope = 'VirtualCarJ2534.dll PassThruOpen, Connect, Disconnect, Close only'
    NoDiagnosticMessagesSent = $true
    OriginalVidaExecuted = $false
    VINAcceptedByVida = $false
    PhysicalJ2534Tested = $false
    Probes = @()
    PassThruOpenStatus = $null
    PassThruCloseStatus = $null
    Passed = $false
}
try {
    function Get-Delegate([string]$name,[type]$signature) {
        $fn = [VirtualCarJ2534ProbeNative]::GetProcAddress($module,$name)
        if ($fn -eq [IntPtr]::Zero) { throw "Missing J2534 export: $name" }
        return [Runtime.InteropServices.Marshal]::GetDelegateForFunctionPointer($fn,$signature)
    }
    $open = Get-Delegate 'PassThruOpen' ([VirtualCarJ2534ProbeNative+OpenDelegate])
    $connect = Get-Delegate 'PassThruConnect' ([VirtualCarJ2534ProbeNative+ConnectDelegate])
    $disconnect = Get-Delegate 'PassThruDisconnect' ([VirtualCarJ2534ProbeNative+DisconnectDelegate])
    $close = Get-Delegate 'PassThruClose' ([VirtualCarJ2534ProbeNative+CloseDelegate])
    $openStatus = $open.Invoke([IntPtr]::Zero,[ref]$device)
    $result.PassThruOpenStatus = [int64]$openStatus
    if ($openStatus -eq 0) {
        $opened = $true
        foreach ($spec in @(
            @{Name='CAN_PS'; Protocol=[uint32]5; Flags=[uint32]256; Baud=[uint32]125000},
            @{Name='ISO15765_PS'; Protocol=[uint32]6; Flags=[uint32]0; Baud=[uint32]125000}
        )) {
            $channel = [uint32]0
            $connectStatus = $connect.Invoke($device,$spec.Protocol,$spec.Flags,$spec.Baud,[ref]$channel)
            $disconnectStatus = $null
            if ($connectStatus -eq 0) {
                $disconnectStatus = [int64]$disconnect.Invoke($channel)
            }
            $result.Probes += [ordered]@{
                Name = $spec.Name; ProtocolID = $spec.Protocol
                Flags = $spec.Flags; Baudrate = $spec.Baud
                ConnectStatus = [int64]$connectStatus
                ChannelId = $channel
                DisconnectStatus = $disconnectStatus
                Passed = ($connectStatus -eq 0 -and $disconnectStatus -eq 0)
            }
        }
    }
} finally {
    if ($opened) {
        $result.PassThruCloseStatus = [int64]$close.Invoke($device)
    }
    [void][VirtualCarJ2534ProbeNative]::FreeLibrary($module)
}
$result.Passed = ($result.PassThruOpenStatus -eq 0 -and $result.PassThruCloseStatus -eq 0 -and
    $result.Probes.Count -eq 2 -and @($result.Probes | Where-Object { -not $_.Passed }).Count -eq 0)
[IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
$file = Join-Path $OutputDirectory ('VIDA-ReadVIN-J2534-CANMS-{0}-{1}.json' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), [guid]::NewGuid().ToString('N'))
[IO.File]::WriteAllText($file,($result | ConvertTo-Json -Depth 6),[Text.UTF8Encoding]::new($false))
Write-Host ('Proof file: ' + $file)
Write-Host ('CAN-MS J2534 connect/disconnect: ' + $(if($result.Passed){'PASS'}else{'FAIL'}))
$result.Probes | Format-Table Name,ProtocolID,Flags,Baudrate,ConnectStatus,DisconnectStatus,Passed -AutoSize
if (-not $result.Passed) { throw 'VirtualCar CAN-MS J2534 preflight failed; inspect the owner-private JSON report.' }
