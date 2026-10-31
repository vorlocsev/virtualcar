#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p _build cmd/oneclick/assets
pushd _build >/dev/null
lld-link /dll /noentry /def:../proxy/kernel32.def /implib:kernel32.lib /machine:x86
clang -target i686-pc-windows-msvc -fno-builtin -fno-stack-protector -ffreestanding -Werror -Wall -Wextra -c ../proxy/j2534_trace_proxy.c -o proxy.obj
clang -target i686-pc-windows-msvc -fno-builtin -fno-stack-protector -ffreestanding -Werror -Wall -Wextra -c ../proxy/p2_message_classify.c -o classify.obj
for f in p2_cem_router p2_ls_observer p2_vehicle_core p2_j2534_bridge freestanding_memory; do
    clang -target i686-pc-windows-msvc -fno-builtin -fno-stack-protector -ffreestanding -Werror -Wall -Wextra -c "../proxy/$f.c" -o "$f.obj"
done
args=(/dll /entry:DllMain@12 /machine:x86 /nodefaultlib /opt:ref /def:../proxy/exports.def /out:../cmd/oneclick/assets/VirtualCarTrace32.dll proxy.obj classify.obj p2_cem_router.obj p2_ls_observer.obj p2_vehicle_core.obj p2_j2534_bridge.obj freestanding_memory.obj kernel32.lib)
for spec in 'LoadLibraryA:4' 'GetProcAddress:8' 'GetEnvironmentVariableA:12' 'CreateFileA:28' 'WriteFile:20' 'CloseHandle:4' 'GetTickCount:0' 'InitOnceExecuteOnce:16' 'GetTempPathA:8'; do
  name=${spec%:*}; bytes=${spec#*:}; args+=("/alternatename:__imp__${name}@${bytes}=__imp__${name}")
done
for spec in 'InitializeCriticalSection:4' 'EnterCriticalSection:4' 'LeaveCriticalSection:4'; do
  name=${spec%:*}; bytes=${spec#*:}; args+=("/alternatename:__imp__${name}@${bytes}=__imp__${name}")
done
lld-link "${args[@]}"
popd >/dev/null
for c in gcc clang; do
  "$c" -std=c99 -Werror -Wall -Wextra -pedantic -Iproxy \
  proxy/p2_cem_router.c proxy/p2_ls_observer.c proxy/p2_vehicle_core.c proxy/p2_j2534_bridge.c \
  tests/test_bridge.c -o "_build/test_bridge_$c"
  "_build/test_bridge_$c"
done
GOOS=windows GOARCH=386 CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o cmd/oneclick/assets/VirtualCarTraceAttribution-x86.exe ./trace_attribution
GOOS=windows GOARCH=386 CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o cmd/oneclick/assets/VirtualCarTraceSummary-x86.exe ./cmd/trace_summary
GOOS=windows GOARCH=386 CGO_ENABLED=0 go build -trimpath -ldflags='-s -w' -o cmd/oneclick/assets/VirtualCarIgnition-x86.exe ./cmd/ignition_report
GOOS=windows GOARCH=386 CGO_ENABLED=0 go build -trimpath -ldflags='-s -w -H windowsgui' -o SectorV-Trace-OneClick-v0.3.6.7-dev26.exe ./cmd/oneclick
for c in gcc clang; do "$c" -std=c99 -Werror -Wall -Wextra -pedantic proxy/p2_message_classify.c tests/test_power_reference.c -o "_build/test_$c"; "_build/test_$c"; done
go test ./...
go test -race ./...
go vet ./...
file SectorV-Trace-OneClick-v0.3.6.7-dev26.exe cmd/oneclick/assets/VirtualCarTrace32.dll
