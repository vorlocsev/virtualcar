# Virtual Car: Volvo P2 diagnostic emulator research

**Status:** experimental Windows x86 J2534 emulator and diagnostic tooling. **Dvinholm is the primary product; Virtual Car is its independent development/test laboratory.** Target P2/CEM read-only identity remains evidence-gated. No successful XC90 V8 MY2009 / physical J2534 acceptance is claimed.

**Starting a new ChatGPT conversation?** Read [NEXT_CHAT.md](NEXT_CHAT.md) on the **development** branch. It contains the current checkpoint, next Issue and a copyable restart prompt.

**Current active plan:** [STATUS](docs/project/STATUS.md), [Dvinholm-first ROADMAP](docs/project/ROADMAP.md), [next task](docs/project/NEXT_CHAT.md), [Issue #60](https://github.com/vorlocsev/virtualcar/issues/60). The root NEXT_CHAT remains the first entrypoint and links these files.

## Two distinct components

- **emulator/**: source of the virtual J2534 adapter from user-provided v0.3.6.6, integrated with the observational CEM Vehicle Core and J2534 READ128 fix on the development branch. Includes its own Windows x86 cross-build, Go Control GUI, fixtures and tests.
- **proxy/**, **cmd/oneclick/**: J2534 tracing/proxy and reporting tools, based on dev26; they forward calls to an existing emulator.
- **research/**: archived experimental dev23–dev25 modules, not independent runtime versions.
- **docs/**: roadmap, research, provenance and development workflow.

## Build from a clean checkout

Emulator (Linux host, LLVM/LLD, GCC, Go 1.23, Python):

    cd emulator
    bash build-cross.sh
    gcc -std=c11 -O2 -Wall -Wextra -o /tmp/virtualcar_test tests/virtualcar_test.c src/p2core/p2_cem_router.c src/p2core/p2_ls_observer.c src/p2core/p2_vehicle_core.c src/p2core/p2_j2534_bridge.c
    /tmp/virtualcar_test
    python3 -m unittest discover -s tests -p 'test_*.py'
    (cd control && go test ./... && go vet ./... && GOOS=windows GOARCH=386 CGO_ENABLED=0 go build -o ../VirtualCarControl.exe .)

Tracing proxy/OneClick (repository root):

    bash build_dev26.sh

The OneClick Go tool uses embedded assets produced by the root build script. Building it before the assets exist will fail.

## Branches and working process

- **main**: reviewed baseline. **development**: integration branch; code must first pass a focused PR and tests.
- Open focused task PRs into development. The development-to-main release-gate PR stays open until manual VMware validation.
- See [Chat + GitHub workflow](docs/CHAT_GITHUB_WORKFLOW_RU.md), [agent instructions](AGENTS.md), and [ROADMAP](docs/ROADMAP.md).
- CI-generated artifacts are the default place for Windows x86 binaries. Historical ZIPs are not source of truth.

## Accuracy and security

- No invented CEM A3, A6, B9F0, D2 normal-mode or ignition positive replies. Reproduce only validated response frames with clear provenance.
- Preserve validated B9FB playback; distinguish synthetic fixtures and original response data.
- VolvoCan and 2002/2003 Volvo P2 broadcast CAN maps are **not** verified for XC90 V8 MY2009.
- Private VIN, ECU dumps, keys, personal J2534 traces, binary diagnostic software and donor profiles must never be committed.
- A CI pass verifies code-level behavior, **not** SectorV/VDASH end-to-end operation in VMware.

## Releases

No Stable release is claimed without explicit approval and verified Windows/VMware behavior. Lab builds remain experimental.
