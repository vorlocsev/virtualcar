# VC090B: read-only registry checkpoints for owner-confirmed WinUI registration.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[0-9a-fA-F]{40}$')][string]$ExpectedSha,
    [Parameter(Mandatory=$true)][string]$BuildDirectory,
    [Parameter(Mandatory=$true)][string]$NativeDirectory,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [Parameter(Mandatory=$true)][ValidateSet('Baseline','InstallCancelled','Installed','RemoveCancelled','Restored')][string]$Phase
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT' -or -not [Environment]::UserInteractive) { throw 'Interactive Windows desktop required.' }
$directory = (Resolve-Path -LiteralPath $BuildDirectory).Path
$manifest = Get-Content -LiteralPath (Join-Path $directory 'build-manifest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($manifest.schema -ne 'vc075-winui-build-v1' -or $manifest.source_sha -ne $ExpectedSha -or
    $manifest.publish -ne 'pass' -or $manifest.platform -ne 'win-x64') { throw 'Build manifest mismatch.' }
$app = Join-Path $directory 'app'
# Verify complete inventory before starting the exact published application.
$actual = @(Get-ChildItem -LiteralPath $app -Recurse -File)
if ($actual.Count -ne @($manifest.files).Count) { throw 'Published inventory count mismatch.' }
$seen = @{}
foreach ($entry in $manifest.files) {
    if ($entry.path -notmatch '^[^\\/:]+(?:/[^\\/:]+)*$' -or ($entry.path.Split('/') | Where-Object { $_ -in @('.','..') })) {
        throw 'Invalid relative inventory path.'
    }
    if ($seen.ContainsKey($entry.path)) { throw 'Duplicate inventory path.' }
    $seen[$entry.path] = $true
    $file = Get-Item -LiteralPath (Join-Path $app $entry.path)
    if ($file -isnot [IO.FileInfo] -or $file.Length -ne $entry.bytes -or
        (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256) {
        throw 'Published file fingerprint mismatch.'
    }
}


$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'Exact checkout required.' }
$dirty = @(& git -C $repo status --porcelain --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Clean checkout required.' }
function Assert-LocalPath([string]$path,[bool]$exists) {
    if ($path -notmatch '^[a-zA-Z]:[\\/]') { throw 'Absolute local path required.' }
    $full = [IO.Path]::GetFullPath($path)
    if ([IO.DriveInfo]::new([IO.Path]::GetPathRoot($full)).DriveType -ne [IO.DriveType]::Fixed) { throw 'Fixed drive required.' }
    $cursor = Get-Item -LiteralPath $(if ($exists) { $full } else { Split-Path -Parent $full })
    while ($null -ne $cursor) {
        if (($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse ancestry not supported.' }
        if ($cursor -is [IO.FileInfo]) { $cursor = $cursor.Directory }
        elseif ($cursor -is [IO.DirectoryInfo]) {
            if ((Test-Path -LiteralPath (Join-Path $cursor.FullName '.git')) -or
                $cursor.FullName.TrimEnd('\') -eq $directory.TrimEnd('\')) { throw 'External directory required.' }
            $cursor = $cursor.Parent
        } else { throw 'Invalid local file type.' }
    }
    return $full
}
$native = Assert-LocalPath $NativeDirectory $true
$out = Assert-LocalPath $OutputDirectory ($Phase -ne 'Baseline')
if ($out.TrimEnd('\') -eq $native.TrimEnd('\') -or
    $out.StartsWith($native.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Separate registration directory required.' }
$nativeReport = Get-Content -LiteralPath (Join-Path $native 'vc090-native-preflight.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$gateNames = @('source_and_managed_inventory','fresh_native_build','x86_export_contract','native_silence_and_evidence','synthetic_identity_replay','can_ms_lifecycle','registry32_preflight','final_integrity')
if ($nativeReport.schema -ne 'vc090-native-preflight-v1' -or $nativeReport.source_sha -ne $ExpectedSha -or $nativeReport.status -ne 'pass' -or
    $nativeReport.native_dll_sha256 -notmatch '^[0-9a-fA-F]{64}$' -or @($nativeReport.gates.PSObject.Properties).Count -ne 8) { throw 'Exact-head VC090A preflight report required.' }
foreach ($gate in $gateNames) { if ($nativeReport.gates.$gate -ne 'pass') { throw "Native preflight gate incomplete: $gate" } }
$sourceDll = Assert-LocalPath (Join-Path $native 'source\emulator\VirtualCarJ2534.dll') $true
$hash = (Get-FileHash -LiteralPath $sourceDll -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne $nativeReport.native_dll_sha256 -or (Get-Item -LiteralPath $sourceDll).Length -ne $nativeReport.native_dll_bytes) { throw 'Native DLL fingerprint mismatch.' }
$parent = 'SOFTWARE\PassThruSupport.04.04'
$canonical = 'J2534 Lab Adapter'
$legacy = 'SectorV Virtual Car'
$helper = Join-Path $app 'driver-tools\VirtualCar.DriverTool.exe'
$provider = Join-Path $out 'provider\VirtualCarJ2534.dll'
$expected = [ordered]@{Vendor='J2534 Lab';Name='J2534 Lab Adapter';FunctionLibrary=$provider;ConfigApplication='';CAN=1;ISO15765=1;MessageVersion=1028}

# Hash deterministic registry value names, types and contents recursively. No
# registry data or other provider paths are written to disk or printed.
function Write-Key($key,[IO.BinaryWriter]$writer,[int]$depth,[bool]$excludeCanonical) {
    if ($depth -gt 32) { throw 'Registry snapshot depth exceeded.' }
    [string[]]$names = $key.GetValueNames()
    [Array]::Sort($names,[StringComparer]::Ordinal)
    $writer.Write([int]$names.Count)
    foreach ($name in $names) {
        $kind = $key.GetValueKind($name)
        $value = $key.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
        $writer.Write([string]$name)
        $writer.Write([int]$kind)
        if ($kind -eq [Microsoft.Win32.RegistryValueKind]::Binary -or $kind -eq [Microsoft.Win32.RegistryValueKind]::None) {
            if ($value -isnot [byte[]]) { throw 'Unsupported registry binary value.' }
            $writer.Write([int]$value.Length)
            $writer.Write([byte[]]$value)
        } elseif ($kind -eq [Microsoft.Win32.RegistryValueKind]::MultiString) {
            if ($value -isnot [string[]]) { throw 'Unsupported registry multi-string value.' }
            $writer.Write([int]$value.Length)
            foreach ($part in $value) { $writer.Write([string]$part) }
        } elseif ($kind -eq [Microsoft.Win32.RegistryValueKind]::DWord) {
            $writer.Write([int]$value)
        } elseif ($kind -eq [Microsoft.Win32.RegistryValueKind]::QWord) {
            $writer.Write([long]$value)
        } elseif ($kind -eq [Microsoft.Win32.RegistryValueKind]::String -or $kind -eq [Microsoft.Win32.RegistryValueKind]::ExpandString) {
            if ($value -isnot [string]) { throw 'Unsupported registry string value.' }
            $writer.Write([string]$value)
        } else { throw 'Unsupported registry value kind.' }
        if ($writer.BaseStream.Length -gt 16777216) { throw 'Registry snapshot size exceeded.' }
    }
    [string[]]$children = @($key.GetSubKeyNames() | Where-Object { -not ($excludeCanonical -and $_ -ieq $canonical) })
    [Array]::Sort($children,[StringComparer]::Ordinal)
    $writer.Write([int]$children.Count)
    foreach ($name in $children) {
        $writer.Write([string]$name)
        $child = $key.OpenSubKey($name,$false)
        if ($null -eq $child) { throw 'Registry changed while reading.' }
        try { Write-Key $child $writer ($depth+1) $false } finally { $child.Dispose() }
    }
}
function Read-View([Microsoft.Win32.RegistryView]$view,[bool]$installed) {
    $root = [Microsoft.Win32.RegistryKey]::OpenBaseKey([Microsoft.Win32.RegistryHive]::LocalMachine,$view)
    $key = $null
    $stream = [IO.MemoryStream]::new()
    $writer = [IO.BinaryWriter]::new($stream)
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        $key = $root.OpenSubKey($parent,$false)
        # Require existing parent in Registry32 so removing our child restores the
        # original parent presence. Never create/delete a parent for the test.
        if ($null -eq $key -and $view -eq [Microsoft.Win32.RegistryView]::Registry32) { throw 'Registry32 parent absent; test would leave a new parent. Stop.' }
        $writer.Write([bool]($null -ne $key))
        $count = 0
        if ($null -ne $key) {
            $current = $key.OpenSubKey($canonical,$false)
            $old = $key.OpenSubKey($legacy,$false)
            try {
                if ($view -eq [Microsoft.Win32.RegistryView]::Registry32) {
                    if ($null -ne $old) { throw 'Legacy provider exists; preserve it and stop.' }
                    if ($installed -ne ($null -ne $current)) { throw 'Unexpected canonical provider presence.' }
                    if ($installed) {
                        if ($current.SubKeyCount -ne 0 -or $current.ValueCount -ne 7) { throw 'Unexpected canonical provider shape.' }
                        foreach ($name in $expected.Keys) {
                            $kind = if ($expected[$name] -is [int]) { [Microsoft.Win32.RegistryValueKind]::DWord } else { [Microsoft.Win32.RegistryValueKind]::String }
                            $value = $current.GetValue($name,$null,[Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)
                            if ($null -eq $value -or $current.GetValueKind($name) -ne $kind -or $value -cne $expected[$name]) { throw 'Canonical provider value mismatch.' }
                        }
                    }
                } elseif ($null -ne $current) { throw 'Unexpected canonical Registry64 entry.' }
            } finally {
                if ($null -ne $current) { $current.Dispose() }
                if ($null -ne $old) { $old.Dispose() }
            }
            $count = @($key.GetSubKeyNames() | Where-Object { -not ($view -eq [Microsoft.Win32.RegistryView]::Registry32 -and $_ -ieq $canonical) }).Count
            Write-Key $key $writer 0 ($view -eq [Microsoft.Win32.RegistryView]::Registry32)
        }
        $writer.Flush()
        $stream.Position = 0
        $digest = [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','').ToLowerInvariant()
        return [pscustomobject]@{digest=$digest;other_provider_count=$count}
    } finally {
        $sha.Dispose(); $writer.Dispose(); $stream.Dispose()
        if ($null -ne $key) { $key.Dispose() }
        $root.Dispose()
    }
}
$installed = $Phase -in @('Installed','RemoveCancelled')
$view32 = Read-View ([Microsoft.Win32.RegistryView]::Registry32) $installed
$view64 = Read-View ([Microsoft.Win32.RegistryView]::Registry64) $false
$lines = @(& $helper inspect $hash)
if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 2) { throw 'DriverTool inspection failed.' }
if ($installed) {
    if ($lines[0] -cne 'VC090_REGISTRY_STATE=Registered' -or $lines[1] -cne 'VC090_REGISTERED_DLL_MATCH=exact_bytes') { throw 'Registered library not confirmed.' }
} elseif ($lines[0] -cne 'VC090_REGISTRY_STATE=Absent' -or $lines[1] -cne 'VC090_REGISTERED_DLL_MATCH=not_assessed') { throw 'Expected absent registration.' }

$phases = @('Baseline','InstallCancelled','Installed','RemoveCancelled','Restored')
$index = [Array]::IndexOf($phases,$Phase)
$target = Join-Path $out ($Phase+'.json')
if (Test-Path -LiteralPath $target) { throw 'Checkpoint already exists; do not overwrite evidence.' }
if ($Phase -eq 'Baseline') {
    if (Test-Path -LiteralPath $out) { throw 'New output directory required.' }
    [void](New-Item -ItemType Directory -Path $out)
    [void](New-Item -ItemType Directory -Path (Join-Path $out 'provider'))
    Copy-Item -LiteralPath $sourceDll -Destination $provider
} else {
    for ($i=0;$i -lt $index;$i++) {
        $previous = Get-Content -LiteralPath (Join-Path $out ($phases[$i]+'.json')) -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($previous.schema -ne 'vc090b-registration-checkpoint-v1' -or $previous.phase -ne $phases[$i] -or
            $previous.source_sha -ne $ExpectedSha -or $previous.native_sha256 -ne $hash -or
            $previous.registry32_other.digest -ne $view32.digest -or $previous.registry64.digest -ne $view64.digest) { throw 'Prior checkpoint mismatch or unrelated registry changes; stop.' }
    }
}
$provider = Assert-LocalPath $provider $true
if ((Get-FileHash -LiteralPath $provider -Algorithm SHA256).Hash -ne $hash -or
    (Get-Item -LiteralPath $provider).Length -ne $nativeReport.native_dll_bytes) { throw 'Staged provider DLL changed.' }
# Compare both registry views twice, without writing to either.
$confirm32 = Read-View ([Microsoft.Win32.RegistryView]::Registry32) $installed
$confirm64 = Read-View ([Microsoft.Win32.RegistryView]::Registry64) $false
if ($confirm32.digest -ne $view32.digest -or $confirm64.digest -ne $view64.digest) { throw 'Registry changed during checkpoint.' }
$final = @(Get-ChildItem -LiteralPath $app -Recurse -File)
if ($final.Count -ne @($manifest.files).Count) { throw 'Build inventory changed.' }
foreach ($entry in $manifest.files) {
    $file = Get-Item -LiteralPath (Join-Path $app $entry.path)
    if ($file -isnot [IO.FileInfo] -or $file.Length -ne $entry.bytes -or (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $entry.sha256) { throw 'Build fingerprint changed.' }
}
$head = (& git -C $repo rev-parse HEAD | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or $head -ne $ExpectedSha) { throw 'HEAD changed.' }
$dirty = @(& git -C $repo status --porcelain --untracked-files=all)
if ($LASTEXITCODE -ne 0 -or $dirty.Count -ne 0) { throw 'Checkout changed.' }
[ordered]@{schema='vc090b-registration-checkpoint-v1';source_sha=$ExpectedSha;phase=$Phase;native_sha256=$hash;canonical_present=$installed;registry32_other=$view32;registry64=$view64;ui_actions='owner_confirmation_required';vida='not_tested';physical_j2534='not_tested'} |
    ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $target -Encoding UTF8
Write-Host "VC090B_CHECKPOINT=PASS PHASE=$Phase SHA=$ExpectedSha"
if ($Phase -eq 'Restored') { Write-Host 'VC090B_REGISTRY_CHECKPOINTS=PASS 5/5 UI_ACTIONS=OWNER_EVIDENCE_REQUIRED' }
