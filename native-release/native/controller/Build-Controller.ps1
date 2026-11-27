# Build only; no installation, registry access or executable launch.
param([Parameter(Mandatory=$true)][string]$DllPath,[Parameter(Mandatory=$true)][string]$OutputDirectory)
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$source=Join-Path $PSScriptRoot 'VirtualCar.cpp'
if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash -cne 'CD73D6949CE2BED344508F8D7DADBC6421351ED0EF1C3D5AE814F2EFD8722B0E') {throw 'Original VC122 source hash mismatch'}
$dll=(Resolve-Path -LiteralPath $DllPath).Path
$hash=(Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
if ($hash -cnotmatch '^[A-F0-9]{64}$') {throw 'Invalid SHA256'}
$out=[IO.Path]::GetFullPath($OutputDirectory)
if(Test-Path -LiteralPath $out){throw 'Output directory exists'}
$vswhere=Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vs=& $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if($LASTEXITCODE -ne 0 -or !$vs){throw 'MSVC not found'}
Import-Module (Join-Path $vs 'Common7\Tools\Microsoft.VisualStudio.DevShell.dll')
Enter-VsDevShell -VsInstallPath $vs -SkipAutomaticLocation -DevCmdArguments '-arch=x86 -host_arch=x64'
if($env:VSCMD_ARG_TGT_ARCH -ne 'x86'){throw 'Incorrect target architecture'}
New-Item -ItemType Directory -Path $out | Out-Null
$encoding=New-Object Text.UTF8Encoding($false,$true)
$raw=[IO.File]::ReadAllText($source,$encoding)
$old='constexpr wchar_t kHash[]=L"C9792583ED670612EB430208BCE443E42B0E71C6FA9322983B63A752EE938AFF";'
$new='constexpr wchar_t kHash[]=L"'+$hash+'";'
if([regex]::Matches($raw,[regex]::Escape($old)).Count -ne 1){throw 'Pin anchor mismatch'}
$bound=$raw.Replace($old,$new)
if($bound.Replace($new,$old) -cne $raw){throw 'Unexpected source delta'}
$generated=Join-Path $out 'VirtualCar.bound.cpp'
[IO.File]::WriteAllText($generated,$bound,$encoding)
$exe=Join-Path $out 'VirtualCar.exe';$obj=Join-Path $out 'VirtualCar.obj'
& cl.exe /nologo /std:c++17 /EHsc /O1 /GL /MT /W4 /WX /utf-8 "/Fo$obj" $generated /link /LTCG /OPT:REF /OPT:ICF /SUBSYSTEM:WINDOWS /MACHINE:X86 /DYNAMICBASE /NXCOMPAT '/MANIFESTUAC:level="requireAdministrator" uiAccess="false"' "/OUT:$exe"
if($LASTEXITCODE -ne 0){throw 'Controller compilation failed'}
$pe=(& dumpbin.exe /headers /imports $exe | Out-String)
if($LASTEXITCODE -ne 0 -or $pe -notmatch '14C machine \(x86\)' -or $pe -match '(?im)^\s*(mscoree|vcruntime[^ ]*|msvcp[^ ]*|python[^ ]*|Microsoft\.UI\.Xaml)\.dll\s*$'){throw 'PE/import audit failed'}
[IO.File]::WriteAllText((Join-Path $out 'pe-audit.txt'),$pe,$encoding)
if((Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash -cne $hash){throw 'Provider changed during build'}
Write-Host 'VC127B4_CONTROLLER_BUILD=PASS x86 /W4 /WX; no launch'
