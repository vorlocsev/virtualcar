@echo off
setlocal
if not defined VC_PYTHON set "VC_PYTHON=python"
cd /d "%~dp0.."
set "VC_VS_PATH="
for /f "usebackq tokens=*" %%I in (`"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VC_VS_PATH=%%I"
if not defined VC_VS_PATH exit /b 1
call "%VC_VS_PATH%\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 exit /b 1
if not exist _build\native mkdir _build\native
cl /nologo /std:c11 /W4 /WX /GS- /Zl /Oi- /c proxy\j2534_trace_proxy.c proxy\j2534_observer.c proxy\p2_message_classify.c proxy\p2_cem_router.c proxy\p2_ls_observer.c proxy\p2_vehicle_core.c proxy\p2_j2534_bridge.c proxy\freestanding_memory.c /Fo:_build\native\
if errorlevel 1 exit /b 1
link /nologo /dll /entry:DllMain@12 /machine:x86 /nodefaultlib /def:proxy\exports.def /out:_build\native\VirtualCarTrace32.dll _build\native\j2534_trace_proxy.obj _build\native\j2534_observer.obj _build\native\p2_message_classify.obj _build\native\p2_cem_router.obj _build\native\p2_ls_observer.obj _build\native\p2_vehicle_core.obj _build\native\p2_j2534_bridge.obj _build\native\freestanding_memory.obj kernel32.lib
if errorlevel 1 exit /b 1
cl /nologo /std:c11 /W4 /WX /GS- /Zl /Oi- /c tests\native_fixture.c /Fo:_build\native\native_fixture.obj
if errorlevel 1 exit /b 1
link /nologo /dll /entry:DllMain@12 /machine:x86 /nodefaultlib /def:tests\native_fixture.def /out:_build\native\SyntheticJ2534.dll _build\native\native_fixture.obj _build\native\freestanding_memory.obj
if errorlevel 1 exit /b 1
cl /nologo /std:c11 /W4 /WX tests\test_proxy_native.c /Fe:_build\native\test_proxy_native.exe /Fo:_build\native\test_proxy_native.obj
if errorlevel 1 exit /b 1
set "VC_NATIVE_LOG=_build\native\synthetic-%RANDOM%-%RANDOM%.jsonl"
_build\native\test_proxy_native.exe _build\native\VirtualCarTrace32.dll _build\native\SyntheticJ2534.dll "%VC_NATIVE_LOG%"
if errorlevel 1 exit /b 1
"%VC_PYTHON%" tests\test_proxy_log.py "%VC_NATIVE_LOG%"
if errorlevel 1 exit /b 1
for %%M in (self relative missing) do (
    _build\native\test_proxy_native.exe _build\native\VirtualCarTrace32.dll _build\native\missing.dll "_build\native\rejected-%%M-%RANDOM%.jsonl" %%M
    if errorlevel 1 exit /b 1
)
if "%~1"=="" exit /b 0
set "VC_NATIVE_LOG=_build\native\cross-synthetic-%RANDOM%-%RANDOM%.jsonl"
_build\native\test_proxy_native.exe "%~1" _build\native\SyntheticJ2534.dll "%VC_NATIVE_LOG%"
if errorlevel 1 exit /b 1
"%VC_PYTHON%" tests\test_proxy_log.py "%VC_NATIVE_LOG%"
if errorlevel 1 exit /b 1
for %%M in (self relative missing) do (
    _build\native\test_proxy_native.exe "%~1" _build\native\missing.dll "_build\native\cross-rejected-%%M-%RANDOM%.jsonl" %%M
    if errorlevel 1 exit /b 1
)
exit /b %errorlevel%
