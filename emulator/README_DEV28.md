# Virtual Car dev28: v0.3.6.6 base + Vehicle Core + READ128

This source snapshot uses the **user-supplied v0.3.6.6** codebase, not the older dev27 v0.3.6.1 source.

## Changes
- Integrated observational `p2_j2534_bridge` without changing CEM diagnostic response behavior.
- Fixed `PassThruReadMsgs`: accepts `NumMsgs`=128 even though the internal queue has only 64 slots. `NumMsgs`=0 remains an error.
- Restored synthetic test fixtures absent from the supplied 0.3.6.6 source ZIP so the full Go and Python suites run.
- Preserved 0.3.6.6 features: configurable ECU nodes, optional passive recorded traces, F106 multi-frame DID handling, B9FB and B9FC fixtures.

## Build & tests (Linux cross compilation)
```sh
cd emulator
bash build-cross.sh
cc -std=c11 -O2 -Wall -Wextra -o /tmp/virtualcar_test tests/virtualcar_test.c src/p2core/p2_cem_router.c src/p2core/p2_ls_observer.c src/p2core/p2_vehicle_core.c src/p2core/p2_j2534_bridge.c
/tmp/virtualcar_test
python3 -m unittest discover -s tests -p 'test_*.py'
(cd control && go test ./... && go test -race ./... && go vet ./...)
```

## Evidence and boundaries
- This is a read-only **laboratory** emulator and contains **no private vehicle donor VIN**.
- Test INI files and reference D2 frames are synthetic, public redacted, or explicitly labeled laboratory examples.
- The A3 `E3 02` response remains **unimplemented** (no known-good fixture).
- B9F0 only replays exact configured fixtures. The shipped default sets zero frames.
- Working `B9FB` replay logic is unchanged; tests include a synthetic 13-frame sequence.
- Do not replace the installed 0.3.6.6 DLL without a separate Windows/VMware check.
- The user-provided **PRIVATE** hotfix archive contains a donor VIN and is intentionally excluded from source control and redistributable packages.
- dev27 and dev26 tooling remain historically available in the repository.
