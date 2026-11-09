# Build one real x86 Go GUI + already tested x86 C J2534 DLL locally.
# Validate a synthetic P2 VMware LAB ZIP; do not distribute, install or run it.
$ErrorActionPreference = 'Stop'
if ($env:GITHUB_REPOSITORY -cne 'vorlocsev/virtualcar') {
    throw 'Unexpected repository for trusted local LAB smoke'
}
$sourceSha = (git rev-parse HEAD).Trim()
if ($LASTEXITCODE -ne 0 -or $sourceSha.Length -ne 40) {
    throw 'Cannot establish checkout commit'
}
$dll = Join-Path $env:GITHUB_WORKSPACE 'emulator\VirtualCarJ2534.dll'
$control = Join-Path $env:GITHUB_WORKSPACE 'emulator\VirtualCarControl.exe'
$dirName = 'virtualcar-ci-local-lab-' + $env:GITHUB_RUN_ID + '-' + $env:GITHUB_RUN_ATTEMPT
$output = Join-Path $env:RUNNER_TEMP $dirName
$python = (Get-Content -LiteralPath 'E:\VirtualCar\Tools\python312.path' -Raw).Trim()
if (-not (Test-Path -LiteralPath $dll -PathType Leaf)) {
    throw 'Tested x86 J2534 DLL does not exist'
}
if ((Test-Path -LiteralPath $control) -or (Test-Path -LiteralPath $output)) {
    throw 'Refusing to overwrite previously existing LAB outputs'
}
New-Item -ItemType Directory -Path $output -ErrorAction Stop | Out-Null
$createdControl = $false
try {
    # This step targets x86, not the 64-bit self-hosted runner default.
    # Build only. Never launch VirtualCarControl or SectorV.
    Push-Location (Join-Path $env:GITHUB_WORKSPACE 'emulator\control')
    try {
        $env:GOOS = 'windows'
        $env:GOARCH = '386'
        $env:CGO_ENABLED = '0'
        $createdControl = $true
        $guiFlags = '-H windowsgui'
        & go build -trimpath -buildvcs=false -ldflags $guiFlags -o $control .
        if ($LASTEXITCODE -ne 0) { throw 'Win32 Go Control build failed' }
    } finally {
        Pop-Location
    }
    if (-not (Test-Path -LiteralPath $control -PathType Leaf)) {
        throw 'Win32 Go Control.exe not created'
    }
    $version = 'ci-' + $sourceSha.Substring(0,12)
    & $python emulator/tools/package_vmware_lab.py --root emulator --output-dir $output --source-sha $sourceSha --version $version
    if ($LASTEXITCODE -ne 0) { throw 'Failed to package real x86 lab inputs' }
    $filename = 'VirtualCar-VMware-LAB-' + $version + '-Windows-x86.zip'
    $archive = Join-Path $output $filename
    & $python emulator/tools/verify_local_vmware_lab.py --archive $archive --source-root emulator --source-sha $sourceSha
    if ($LASTEXITCODE -ne 0) { throw 'Packaged real x86 inputs did not verify' }
    Write-Host 'PASS: actual Win32 GUI and C J2534 DLL matched private LAB ZIP; no release or GUI'
} finally {
    if ($createdControl -and (Test-Path -LiteralPath $control)) {
        Remove-Item -LiteralPath $control -Force -ErrorAction Stop
    }
    if (Test-Path -LiteralPath $output) {
        Remove-Item -LiteralPath $output -Recurse -Force -ErrorAction Stop
    }
}
