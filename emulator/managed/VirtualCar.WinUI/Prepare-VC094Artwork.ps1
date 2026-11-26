# Package only two reviewed public-domain reference photographs, not private VIN data.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$Package,
    [Parameter(Mandatory=$true)][string]$WorkDirectory,
    [string]$SourceDirectory
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$entries = @(
    @{id='xc90-v8';name='2006-2008_Volvo_XC90_(P28)_V8_wagon_01.jpg';
      url='https://upload.wikimedia.org/wikipedia/commons/1/19/2006-2008_Volvo_XC90_%28P28%29_V8_wagon_01.jpg';
      sha1='63059239d4814d5cb1a0e5a04e96f97456d28c9b';bytes=4276478;width=3726;height=2088;author='OSX';
      page='https://commons.wikimedia.org/wiki/File:2006-2008_Volvo_XC90_(P28)_V8_wagon_01.jpg'},
    @{id='p2-reference';name='Volvo_XC90_Facelift_20090321_front.jpg';
      url='https://upload.wikimedia.org/wikipedia/commons/3/38/Volvo_XC90_Facelift_20090321_front.jpg';
      sha1='6ed6cd3cb132d118839ce318bc2b2845829775e8';bytes=3452424;width=2466;height=1800;author='M 93';
      page='https://commons.wikimedia.org/wiki/File:Volvo_XC90_Facelift_20090321_front.jpg'}
)
function Assert-Directory([string]$path) {
    if ($path -notmatch '^[A-Za-z]:[\\/]') { throw 'Absolute local directory required.' }
    $dir = Get-Item -LiteralPath $path
    if ($dir -isnot [IO.DirectoryInfo] -or [IO.DriveInfo]::new($dir.Root.FullName).DriveType -ne [IO.DriveType]::Fixed) { throw 'Local fixed drive required.' }
    while ($null -ne $dir) {
        if (($dir.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Reparse directory rejected.' }
        $dir = $dir.Parent
    }
}
Assert-Directory $Package
Assert-Directory $WorkDirectory
if ($SourceDirectory) { Assert-Directory $SourceDirectory }
$target = Join-Path $Package 'artwork'
if (Test-Path -LiteralPath $target) { throw 'Artwork output already exists.' }
$stage = Join-Path $WorkDirectory 'artwork-stage'
if (Test-Path -LiteralPath $stage) { throw 'Artwork staging already exists.' }
[void](New-Item -ItemType Directory -Path $stage)
$credits = @()
foreach ($entry in $entries) {
    $source = if ($SourceDirectory) { Join-Path $SourceDirectory $entry.name } else { Join-Path $stage $entry.name }
    if (-not $SourceDirectory) {
        # Network is allowed during packaging only. The application itself never fetches artwork.
        Invoke-WebRequest -Uri $entry.url -UseBasicParsing -OutFile $source -TimeoutSec 60 -MaximumRedirection 0 -UserAgent 'VirtualCar-artwork-packaging/1.0'
    }
    $item = Get-Item -LiteralPath $source
    if ($item -isnot [IO.FileInfo] -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0 -or
        $item.Length -ne $entry.bytes -or (Get-FileHash -LiteralPath $source -Algorithm SHA1).Hash -ne $entry.sha1) {
        throw 'Reference photograph differs from reviewed Commons revision.'
    }
    $bytes = [IO.File]::ReadAllBytes($source)
    $algorithm = [Security.Cryptography.SHA1]::Create()
    try { $snapshotHash = [BitConverter]::ToString($algorithm.ComputeHash($bytes)).Replace('-','') } finally { $algorithm.Dispose() }
    if ($bytes.Length -ne $entry.bytes -or $snapshotHash -ne $entry.sha1) { throw 'Photograph changed during read.' }
    $stream = [IO.MemoryStream]::new($bytes)
    $image = $null
    $bitmap = $null
    $graphics = $null
    try {
        $image = [Drawing.Image]::FromStream($stream,$false,$true)
        if ($image.Width -ne $entry.width -or $image.Height -ne $entry.height -or
            $image.RawFormat.Guid -ne [Drawing.Imaging.ImageFormat]::Jpeg.Guid) { throw 'Unexpected image format or dimensions.' }
        $w = [Math]::Min(960,$image.Width)
        $h = [int][Math]::Round($image.Height * $w / $image.Width)
        $bitmap = [Drawing.Bitmap]::new($w,$h,[Drawing.Imaging.PixelFormat]::Format24bppRgb)
        $graphics = [Drawing.Graphics]::FromImage($bitmap)
        $graphics.InterpolationMode = [Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.DrawImage($image,0,0,$w,$h)
        $file = Join-Path $stage ($entry.id + '.jpg')
        # Re-encode into a fresh bitmap; do not copy the original EXIF/GPS metadata.
        $bitmap.Save($file,[Drawing.Imaging.ImageFormat]::Jpeg)
    } finally {
        if ($graphics) { $graphics.Dispose() }
        if ($bitmap) { $bitmap.Dispose() }
        if ($image) { $image.Dispose() }
        $stream.Dispose()
    }
    $normalized = Get-Item -LiteralPath $file
    if ($normalized.Length -le 0 -or $normalized.Length -gt 1048576) { throw 'Normalized photograph size out of bounds.' }
    $sha = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant()
    [IO.File]::WriteAllText((Join-Path $stage ($entry.id + '.sha256')),$sha,[Text.Encoding]::ASCII)
    $credits += "$($entry.id).jpg - $($entry.author); public-domain dedication by author; source $($entry.page); resized and re-encoded, metadata not copied."
}
[void](New-Item -ItemType Directory -Path $target)
foreach ($entry in $entries) {
    foreach ($extension in @('.jpg','.sha256')) {
        $name = $entry.id + $extension
        Copy-Item -LiteralPath (Join-Path $stage $name) -Destination (Join-Path $target $name)
    }
}
[IO.File]::WriteAllLines((Join-Path $target 'credits.txt'),[string[]]$credits,[Text.Encoding]::UTF8)
Write-Host 'VC094E_ARTWORK=PACKAGED_2_REFERENCE_PHOTOS'
