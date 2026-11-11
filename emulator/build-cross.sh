#!/usr/bin/env bash
# Cross-build on Linux with Clang/LLD for Windows 32-bit, no Windows SDK needed.
set -euo pipefail
# Git Bash/MSYS rewrites LLD's slash-prefixed options (/lib, /def, /out)
# into filesystem paths. This script uses only relative paths, so disable
# argument conversion for its Windows tool invocations.
export MSYS2_ARG_CONV_EXCL='*'
export MSYS_NO_PATHCONV=1

cd "$(dirname "$0")"
LLVM_CLANG="${LLVM_CLANG:-clang}"
LLVM_LINK="${LLVM_LINK:-lld-link}"
mkdir -p .build
"$LLVM_LINK" /lib /def:src/kernel32.def /machine:x86 /out:.build/kernel32.lib
"$LLVM_CLANG" -target i686-pc-windows-msvc -DCROSS_LLVM -c -O2 -fno-builtin \
    -fno-stack-protector -fms-extensions -Wno-microsoft \
    -o .build/virtualcar.obj src/virtualcar.c
for f in p2_cem_router p2_ls_observer p2_vehicle_core p2_j2534_bridge freestanding_memory; do
    "$LLVM_CLANG" -target i686-pc-windows-msvc -c -O2 -ffreestanding -fno-builtin \
        -fno-stack-protector -fms-extensions -Wno-microsoft \
        -o ".build/$f.obj" "src/p2core/$f.c"
done
"$LLVM_LINK" /dll /machine:x86 /entry:DllMain@12 /nodefaultlib \
    /out:VirtualCarJ2534.dll /def:src/virtualcar.def \
    /alternatename:__imp_Sleep=__imp__Sleep /alternatename:__imp_GetTickCount=__imp__GetTickCount /alternatename:__imp_QueryPerformanceCounter=__imp__QueryPerformanceCounter /alternatename:__imp_QueryPerformanceFrequency=__imp__QueryPerformanceFrequency /alternatename:__imp_GetCurrentProcessId=__imp__GetCurrentProcessId /alternatename:__imp_GetModuleFileNameA=__imp__GetModuleFileNameA /alternatename:__imp_GetPrivateProfileStringA=__imp__GetPrivateProfileStringA /alternatename:__imp_GetTempPathA=__imp__GetTempPathA /alternatename:__imp_GetEnvironmentVariableA=__imp__GetEnvironmentVariableA /alternatename:__imp_CreateDirectoryA=__imp__CreateDirectoryA /alternatename:__imp_CreateFileA=__imp__CreateFileA /alternatename:__imp_SetFilePointer=__imp__SetFilePointer /alternatename:__imp_WriteFile=__imp__WriteFile /alternatename:__imp_CloseHandle=__imp__CloseHandle /alternatename:__imp_InterlockedCompareExchange=__imp__InterlockedCompareExchange /alternatename:__imp_InterlockedExchange=__imp__InterlockedExchange /alternatename:__imp_ReadProcessMemory=__imp__ReadProcessMemory \
    .build/virtualcar.obj .build/p2_cem_router.obj .build/p2_ls_observer.obj .build/p2_vehicle_core.obj .build/p2_j2534_bridge.obj .build/freestanding_memory.obj .build/kernel32.lib
printf 'Built: VirtualCarJ2534.dll (Windows x86)\n'
