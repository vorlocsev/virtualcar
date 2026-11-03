#Requires -Version 5.1
# Non-destructive inspection of the dedicated 32-bit CAN_PS A/B virtual adapter.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$registryPath = 'SOFTWARE\PassThruSupport.04.04\Virtual Car CANPS AB LAB'
$owner = 'VirtualCar-CANPS-AB-v1'

function Show-Result([string]$name, $value) {
    Write-Host ("{0}: {1}" -f $name, $value)
}

# Registry32 is used regardless of whether the calling shell is x64 or x86.
$base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
    [Microsoft.Win32.RegistryHive]::LocalMachine,
    [Microsoft.Win32.RegistryView]::Registry32
)
try {
    $key = $base.OpenSubKey($registryPath)
    if ($null -eq $key) {
        Show-Result 'REGISTRATION' 'MISSING'
        Write-Host 'Run .\Set-VirtualCarAB.ps1 -Mode CONTROL as Administrator in the extracted LAB folder.'
        return
    }
    try {
        $dll = [string]$key.GetValue('FunctionLibrary', '')
        $currentOwner = [string]$key.GetValue('LabOwner', '')
        $name = [string]$key.GetValue('Name', '')
    } finally {
        $key.Close()
    }
} finally {
    $base.Close()
}
if ($currentOwner -ne $owner) {
    Show-Result 'REGISTRATION' 'UNEXPECTED_OWNER'
    return
}
Show-Result 'REGISTRATION' 'PRESENT_32BIT'
Show-Result 'ADAPTER_NAME' $name
if ([string]::IsNullOrEmpty($dll) -or -not [IO.File]::Exists($dll)) {
    Show-Result 'DLL' 'MISSING'
    return
}
if ([IO.Path]::GetFileName($dll) -ne 'VirtualCarJ2534.dll') {
    Show-Result 'DLL' 'UNEXPECTED_FILENAME'
    return
}
$modeFolder = Split-Path -Path $dll -Parent
$root = Split-Path -Path $modeFolder -Parent
$ini = Join-Path $modeFolder 'virtualcar.ini'
$buildInfo = Join-Path $root 'BUILDINFO.json'
if (-not [IO.File]::Exists($ini)) {
    Show-Result 'INI' 'MISSING'
    return
}
if (-not [IO.File]::Exists($buildInfo)) {
    Show-Result 'BUILDINFO' 'MISSING'
    return
}
$info = Get-Content -LiteralPath $buildInfo -Raw | ConvertFrom-Json
if ($info.format -ne 'virtualcar-canps-api-only-ab-v1') {
    Show-Result 'BUILDINFO' 'UNEXPECTED_FORMAT'
    return
}
$actual = (Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne [string]$info.dll_sha256) {
    Show-Result 'DLL_SHA256' 'MISMATCH'
    return
}
Show-Result 'DLL_SHA256' 'MATCH'
$modeName = Split-Path -Path $modeFolder -Leaf
$modes = @{'CONTROL'='0'; 'A_FILTER'='1'; 'B_D8_WRITE'='2'; 'C_D8_PERIODIC'='3'}
if (!$modes.ContainsKey($modeName)) {
    Show-Result 'MODE' 'UNKNOWN_DIRECTORY'
    return
}
$iniText = Get-Content -LiteralPath $ini -Raw
if ($iniText -notmatch '(?m)^EnableCanPsConfigProbe=1\s*$' -or
    $iniText -notmatch ('(?m)^CanPsApiOutcomeMode=' + $modes[$modeName] + '\s*$')) {
    Show-Result 'PROFILE' 'MODE_MISMATCH'
    return
}
Show-Result 'PROFILE' ("MODE_" + $modeName)

if ([IntPtr]::Size -ne 4) {
    $x86 = Join-Path $env:WINDIR 'SysWOW64\WindowsPowerShell\v1.0\powershell.exe'
    if (-not [IO.File]::Exists($x86)) {
        Show-Result 'X86_POWERSHELL' 'MISSING'
        return
    }
    Write-Host 'Running read-only ABI preflight in 32-bit PowerShell...'
    & $x86 -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath
    if ($LASTEXITCODE -ne 0) { throw "x86 preflight failed ($LASTEXITCODE)" }
    return
}
Show-Result 'PROCESS_ARCH' 'X86'

# This tests the exact registered DLL using J2534, not GUI recognition.
# Only PassThruOpen/Connect/Disconnect/Close are issued. No messages are sent.
$source = @'
using System;
using System.Runtime.InteropServices;
public static class VirtualCarABPreflight {
    const string Library = @"__DLL_PATH__";
    [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true,ExactSpelling=true)]
    static extern IntPtr LoadLibraryW(string path);
    [DllImport("kernel32.dll",CharSet=CharSet.Ansi,ExactSpelling=true)]
    static extern IntPtr GetProcAddress(IntPtr handle,string name);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruOpen(IntPtr name,out uint device);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruClose(uint device);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruConnect(uint device,uint protocol,uint flags,uint baud,out uint channel);
    [DllImport(Library,CallingConvention=CallingConvention.StdCall)]
    static extern uint PassThruDisconnect(uint channel);
    public static string Run() {
        IntPtr handle=LoadLibraryW(Library);
        if(handle==IntPtr.Zero)
            return "DLL_LOAD_FAILURE_WIN32_" + Marshal.GetLastWin32Error();
        foreach(string name in new string[]{"Open","Close","Connect","Disconnect","ReadMsgs",
            "WriteMsgs","StartMsgFilter","StopMsgFilter","StartPeriodicMsg",
            "StopPeriodicMsg","SetProgrammingVoltage","ReadVersion","GetLastError","Ioctl"}) {
            if(GetProcAddress(handle,"PassThru"+name)==IntPtr.Zero)
                return "MISSING_EXPORT_PassThru"+name;
        }
        uint device=0,iso=0,ps=0;
        uint result=PassThruOpen(IntPtr.Zero,out device);
        if(result!=0)return "PASSTHRU_OPEN_STATUS_"+result;
        try {
            uint statusIso=PassThruConnect(device,6,0,500000,out iso);
            if(statusIso==0)PassThruDisconnect(iso);
            uint statusPs=PassThruConnect(device,0x8004,0x900,125000,out ps);
            if(statusPs==0)PassThruDisconnect(ps);
            return "PASSTHRU_ISO15765_STATUS_"+statusIso+
                   "_CANPS_STATUS_"+statusPs;
        } finally {
            PassThruClose(device);
        }
    }
}
'@
$source = $source.Replace('__DLL_PATH__', $dll.Replace('"', '""'))
try {
    Add-Type -TypeDefinition $source -Language CSharp -ErrorAction Stop
    Show-Result 'J2534_PREFLIGHT' ([VirtualCarABPreflight]::Run())
} catch {
    Show-Result 'J2534_PREFLIGHT' ('ERROR_' + $_.Exception.GetType().Name)
}
Write-Host 'This is a J2534 preflight only. VDASH/ECU recognition is not inferred.'
