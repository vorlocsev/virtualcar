# Read-only two-phase Windows PowerShell 5.1 capture of ONE client run.
# Begin: verify the registered x86 J2534 DLL, snapshot private native log size
#        and SHA256. Do NOT launch the diagnostic client from this script.
# Finish: verify DLL still matches and send ONLY appended log bytes to a
#         private Python sanitizer; no raw data is written to the safe folder.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('Begin','Finish')]
    [string]$Phase,
    [Parameter(Mandatory=$true)]
    [string]$SessionDirectory,
    [string]$NativeLog = '',
    [string]$UiObservation = '',
    [switch]$IConfirmClientClosed
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$fmt = 'virtualcar-private-native-client-capture-state-v1'
$dll = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\VirtualCarJ2534.dll'))
# DLL reads the sibling virtualcar.ini at PassThruOpen.
$profile = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\virtualcar.ini'))
$stateName = 'PRIVATE-DO-NOT-SHARE'
$folder = [IO.Path]::GetFullPath($SessionDirectory)
$statePath = Join-Path (Join-Path $folder $stateName) 'state.json'
$safeFolder = Join-Path $folder 'SAFE-JSON-REPORTS'
$pythonTool = [IO.Path]::GetFullPath(
    (Join-Path $PSScriptRoot '..\tools\prepare_p2_client_run.py'))
$script:emptyHash = [Security.Cryptography.SHA256]::Create()
try {
    $script:emptyDigest = ([BitConverter]::ToString(
        $script:emptyHash.ComputeHash([byte[]]@()))).Replace('-','').ToLowerInvariant()
} finally {
    $script:emptyHash.Dispose()
}

function Get-Machine([string]$path) {
    if (-not [IO.File]::Exists($path)) { throw 'Expected J2534 DLL was not found' }
    $file = [IO.File]::Open($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,
                             [IO.FileShare]::Read)
    try {
        $reader = New-Object IO.BinaryReader($file)
        if ($reader.ReadUInt16() -ne 0x5A4D) { throw 'Invalid DLL MZ header' }
        [void]$file.Seek(0x3C,[IO.SeekOrigin]::Begin)
        $offset = $reader.ReadInt32()
        if ($offset -lt 64 -or $offset -gt ($file.Length - 6)) {
            throw 'Invalid DLL PE offset'
        }
        [void]$file.Seek($offset,[IO.SeekOrigin]::Begin)
        if ($reader.ReadUInt32() -ne 0x00004550) {
            throw 'Invalid DLL PE signature'
        }
        return $reader.ReadUInt16()
    } finally {
        $file.Dispose()
    }
}

function Assert-RegisteredDll {
    if ((Get-Machine $dll) -ne 0x014C) {
        throw 'This laboratory workflow requires the 32-bit x86 J2534 DLL'
    }
    $keyName = 'SOFTWARE\PassThruSupport.04.04\SectorV Virtual Car'
    $base = [Microsoft.Win32.RegistryKey]::OpenBaseKey(
        [Microsoft.Win32.RegistryHive]::LocalMachine,
        [Microsoft.Win32.RegistryView]::Registry32)
    try {
        $key = $base.OpenSubKey($keyName, $false)
        if ($null -eq $key) { throw 'Virtual Car J2534 not registered in Registry32' }
        try {
            $registered = [string]$key.GetValue('FunctionLibrary','')
            $version = $key.GetValue('MessageVersion',0)
            if (-not $registered) { throw 'Registered J2534 DLL path is empty' }
            $actual = [IO.Path]::GetFullPath($registered)
            if (-not [string]::Equals($actual,$dll,
                        [StringComparison]::OrdinalIgnoreCase)) {
                throw 'Registered DLL differs from the script-adjacent x86 DLL'
            }
            if ([int]$version -ne 0x0404) {
                throw 'Unexpected J2534 PassThru version'
            }
        } finally { $key.Close() }
    } finally { $base.Close() }
}

function Get-Sha256([string]$path) {
    return (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
}

function Get-ProfileDigest {
    if (-not [IO.File]::Exists($profile)) {
        throw 'DLL-side virtualcar.ini is missing; explicit lab profile required'
    }
    $bytes = (Get-Item -LiteralPath $profile).Length
    if ($bytes -lt 1 -or $bytes -gt 262144) {
        throw 'The virtualcar.ini profile must be nonempty and at most 256 KiB'
    }
    return Get-Sha256 $profile
}

function Assert-NoClientProcess {
    # A simple guard, not evidence that the user ran a particular client.
    $running = @(Get-Process -Name 'SectorV','VDASH','VDASH2' -ErrorAction SilentlyContinue)
    if ($running.Count -gt 0) {
        throw 'Close the diagnostic client before starting or finalizing the capture'
    }
}

if (-not [IO.File]::Exists($pythonTool)) {
    throw 'Python client evidence sanitizer is missing'
}
Assert-RegisteredDll
Assert-NoClientProcess

if ($Phase -eq 'Begin') {
    if (Test-Path -LiteralPath $folder) {
        throw 'Session directory already exists; select a new private directory'
    }
    if (-not $NativeLog) { $NativeLog = Join-Path $env:TEMP 'SectorVVirtualCar.log' }
    $logPath = [IO.Path]::GetFullPath($NativeLog)
    $length = [long]0
    $digest = $script:emptyDigest
    if ([IO.File]::Exists($logPath)) {
        $length = (Get-Item -LiteralPath $logPath).Length
        if ($length -gt 67108864) {
            throw 'Previous private log too large for bounded pre-client snapshot'
        }
        $digest = Get-Sha256 $logPath
    }
    # Paths and the historical-log digest remain in this PRIVATE subdirectory.
    # Share ONLY files under SAFE-JSON-REPORTS after manual review.
    [void][IO.Directory]::CreateDirectory((Join-Path $folder $stateName))
    $state = @{
        format = $fmt
        native_log_path = $logPath
        before_bytes = $length
        before_sha256 = $digest
        dll_sha256 = Get-Sha256 $dll
        profile_sha256 = Get-ProfileDigest
    }
    [IO.File]::WriteAllText($statePath,($state | ConvertTo-Json -Depth 3),
                            ([Text.UTF8Encoding]::new($false)))
    Write-Host 'PASS: registered x86 DLL and private native-log baseline verified'
    Write-Host 'Now start ONE diagnostic client manually, read only; close it afterwards.'
    Write-Host 'Then invoke this script with -Phase Finish -IConfirmClientClosed.'
    Write-Host 'Do not send the PRIVATE-DO-NOT-SHARE directory to anyone.'
    exit 0
}

if (-not $IConfirmClientClosed) {
    throw 'Finish requires -IConfirmClientClosed after the client exits'
}
if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    throw 'Private Begin state is missing'
}
if (Test-Path -LiteralPath $safeFolder) {
    throw 'Safe output already exists; refusing to overwrite'
}
$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 |
         ConvertFrom-Json
if ($state.format -ne $fmt -or
    $state.before_bytes -lt 0 -or
    $state.before_bytes -gt 67108864 -or
    $state.before_sha256 -notmatch '^[a-f0-9]{64}$' -or
    $state.dll_sha256 -notmatch '^[a-f0-9]{64}
    [string]::IsNullOrWhiteSpace([string]$state.native_log_path)) {
    throw 'Invalid private Begin state'
}
if ((Get-Sha256 $dll) -ne $state.dll_sha256) {
    throw 'Virtual J2534 DLL changed between Begin and Finish'
}
if (-not [IO.File]::Exists([string]$state.native_log_path)) {
    throw 'No appended native J2534 log exists'
}
$call = @('-3', $pythonTool, [string]$state.native_log_path,
          '--offset-bytes', [string]$state.before_bytes,
          '--prefix-sha256', [string]$state.before_sha256,
          '--output-dir', $safeFolder)
if ($UiObservation) {
    if (-not (Test-Path -LiteralPath $UiObservation -PathType Leaf)) {
        throw 'Operator UI observation JSON is missing'
    }
    $call += @('--ui', [IO.Path]::GetFullPath($UiObservation))
}
& py @call
if ($LASTEXITCODE -ne 0) {
    throw 'Client evidence capture failed closed: output not verified'
}
Write-Host 'PASS: only sanitized JSON files were created in SAFE-JSON-REPORTS.'
Write-Host 'Review safe JSON files before sharing. Client acceptance is NOT verified.'
 -or
    $state.profile_sha256 -notmatch '^[a-f0-9]{64}
    [string]::IsNullOrWhiteSpace([string]$state.native_log_path)) {
    throw 'Invalid private Begin state'
}
if ((Get-Sha256 $dll) -ne $state.dll_sha256) {
    throw 'Virtual J2534 DLL changed between Begin and Finish'
}
if (-not [IO.File]::Exists([string]$state.native_log_path)) {
    throw 'No appended native J2534 log exists'
}
$call = @('-3', $pythonTool, [string]$state.native_log_path,
          '--offset-bytes', [string]$state.before_bytes,
          '--prefix-sha256', [string]$state.before_sha256,
          '--output-dir', $safeFolder)
if ($UiObservation) {
    if (-not (Test-Path -LiteralPath $UiObservation -PathType Leaf)) {
        throw 'Operator UI observation JSON is missing'
    }
    $call += @('--ui', [IO.Path]::GetFullPath($UiObservation))
}
& py @call
if ($LASTEXITCODE -ne 0) {
    throw 'Client evidence capture failed closed: output not verified'
}
Write-Host 'PASS: only sanitized JSON files were created in SAFE-JSON-REPORTS.'
Write-Host 'Review safe JSON files before sharing. Client acceptance is NOT verified.'
 -or
    [string]::IsNullOrWhiteSpace([string]$state.native_log_path)) {
    throw 'Invalid private Begin state'
}
if ((Get-Sha256 $dll) -ne $state.dll_sha256) {
    throw 'Virtual J2534 DLL changed between Begin and Finish'
}
if ((Get-ProfileDigest) -ne $state.profile_sha256) {
    throw 'Virtual J2534 INI profile changed between Begin and Finish'
}
if (-not [IO.File]::Exists([string]$state.native_log_path)) {
    throw 'No appended native J2534 log exists'
}
$call = @('-3', $pythonTool, [string]$state.native_log_path,
          '--offset-bytes', [string]$state.before_bytes,
          '--prefix-sha256', [string]$state.before_sha256,
          '--output-dir', $safeFolder)
if ($UiObservation) {
    if (-not (Test-Path -LiteralPath $UiObservation -PathType Leaf)) {
        throw 'Operator UI observation JSON is missing'
    }
    $call += @('--ui', [IO.Path]::GetFullPath($UiObservation))
}
& py @call
if ($LASTEXITCODE -ne 0) {
    throw 'Client evidence capture failed closed: output not verified'
}
Write-Host 'PASS: only sanitized JSON files were created in SAFE-JSON-REPORTS.'
Write-Host 'Review safe JSON files before sharing. Client acceptance is NOT verified.'
