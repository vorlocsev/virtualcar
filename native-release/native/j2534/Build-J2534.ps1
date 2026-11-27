# Local build only. Run from x86 Visual Studio Developer PowerShell.
param([string]$Python='py.exe')
$ErrorActionPreference='Stop'
if($env:VSCMD_ARG_TGT_ARCH -ne 'x86'){throw 'Use x86 target Developer PowerShell'}
foreach($tool in @('clang-cl.exe','link.exe',$Python)){if(-not(Get-Command $tool -ErrorAction SilentlyContinue)){throw "Missing $tool"}}
function Run([string]$exe,[string[]]$argv){& $exe @argv;if($LASTEXITCODE -ne 0){throw "$exe failed: $LASTEXITCODE"}}
$src=Join-Path $PSScriptRoot 'src'
$manifest=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'summary.json') -Raw | ConvertFrom-Json
foreach($entry in $manifest.source_files.PSObject.Properties){if((Get-FileHash -LiteralPath (Join-Path $src $entry.Name) -Algorithm SHA256).Hash -ne $entry.Value){throw 'Source hash mismatch'}}
$out=Join-Path $PSScriptRoot ('build-'+[guid]::NewGuid().ToString('N'));New-Item -ItemType Directory -Path $out | Out-Null
$sources=@('virtualcar.c','p2core\p2_cem_router.c','p2core\p2_ls_observer.c','p2core\p2_vehicle_core.c','p2core\p2_j2534_bridge.c','p2core\freestanding_memory.c','vc110\rotation_windows.c')
$objects=@()
foreach($source in $sources){$o=Join-Path $out (([IO.Path]::GetFileNameWithoutExtension($source))+'.obj');$objects+=$o;Run 'clang-cl.exe' @('--target=i686-pc-windows-msvc','/nologo','/c','/O2','/GS-','/Zl','/TC','/clang:-fno-builtin','/DVC108P_SDK','/D_WIN32_WINNT=0x0A00',('/Fo'+$o),(Join-Path $src $source))}
$dll=Join-Path $out 'VirtualCarJ2534.dll'
Run 'link.exe' (@('/NOLOGO','/DLL','/MACHINE:X86','/ENTRY:DllMain@12','/NODEFAULTLIB',('/DEF:'+(Join-Path $src 'virtualcar.def')),('/OUT:'+$dll))+$objects+@('kernel32.lib'))
$pa=@();if($Python -eq 'py.exe'){$pa=@('-3')};Run $Python ($pa+@((Join-Path $PSScriptRoot 'audit_pe.py'),$dll))
$hash=(Get-FileHash -LiteralPath $dll -Algorithm SHA256).Hash
Write-Host "VC127B3_BUILD=PASS; DLL=$dll SHA256=$hash"
Write-Host ('VC127B3_RC1_BYTE_MATCH='+($hash -eq $manifest.reference_rc1_dll_sha256))
Write-Host 'VC127B3_RUNTIME=NOT_TESTED; PUBLICATION=NOT_APPROVED; registry unchanged'
