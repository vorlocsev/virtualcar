# Virtual Car: Volvo P2 diagnostic emulator research

**Status:** experimental development source. The current Windows x86 deliverable is a **J2534 tracing proxy**, not a complete vehicle emulator. Its original upstream `VirtualCarJ2534.dll` and corresponding `virtualcar.c` are **not in this repository**.

The project investigates Volvo P2 CEM / HS-CAN / LS-CAN diagnostic behavior, initially for an XC90 V8 model year 2009 (virtual J2534, Windows x86, VMware). Read-only observation, ECU identification and diagnostic protocol compatibility are the current goals. This project is **separate from Dvinholm**.

## Layout

- `proxy/` : C99 Windows x86 J2534 tracing proxy, CEM routing and vehicle state observers (current dev26 implementation).
- `cmd/oneclick/` : Windows x86 GUI to run the proxy and collect sanitized diagnostic reports.
- `trace_attribution/`, `cmd/trace_summary/`, `cmd/ignition_report/` : Go reporting tools.
- `tests/` : C integration and classification tests.
- `research/dev23/`, `research/dev24/`, `research/dev25/` : previous snapshots of CEM router, LS observer and combined vehicle core, for traceability.
- `docs/` : dev26 notes and integration limitations.
- `.github/workflows/ci.yml` : Linux CI cross-compiling Windows x86 output and running tests.

## Building

The canonical source-build is `bash build_dev26.sh` on Linux with Clang, `lld-link`, GCC, Go >=1.23, and `file`. It builds all four embedded assets from source, then the Windows x86 GUI. Do not call `go test ./...` on an unbuilt checkout until generating `cmd/oneclick/assets/` with the build script, because `go:embed` requires those files at compile time.

## Accuracy and safety

- The proxy forwards J2534 calls to the original DLL unchanged; its classification alone does not prove a valid ECU response.
- A3/B9F0 positive CEM responses are **not verified or synthesized**. B9FB is delegated to the original emulator.
- An observed ignition-key broadcast does not establish D2 reference 6660 or physical ignition ON.
- Passive VolvoCan IDs are experimental and disabled by default for the target model year.
- No real VIN, hardware identifiers, proprietary diagnostic binaries, personal logs, passwords or ECU secrets belong in the repository.
- The diagnostic application executable and the original emulator DLL must be provided separately by their authorized owners. Neither is redistributed here.

## Branches

`main` for reviewed baseline; `development` for PR integration. Do not publish a release until Windows/VMware end-to-end behavior is confirmed. See [ROADMAP](docs/ROADMAP.md).
