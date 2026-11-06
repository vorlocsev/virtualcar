# M3 | Native C++20 J2534 v04.04 ABI DLL, x86 and x64

**Scope:** implementation-stage ABI binary ONLY, not a usable J2534 adapter.
Dvinholm is the primary product. Virtual Car is a private read-only lab.

## Implementation

- `emulator/native-cpp/src/j2534_fail_closed.cpp` implements 14 actual
  Windows-native exported entrypoints with `extern "C"` and the precise
  32-bit `__stdcall` / 64-bit Windows calling convention.
- Independent .DEF files map x86 decorated internal symbols to
  **undecorated public PassThru names**, while x64 exports are plain C names.
- CMake Visual Studio 2022 builds two distinct binaries, Win32 PE32 and
  x64 PE32+. Filename `VirtualCarJ2534Cpp.dll` is intentionally separate
  from the existing `VirtualCarJ2534.dll` legacy x86 simulator.
- J2534 DWORDs are 32-bit; PASSTHRU_MSG is 4152 bytes with 4128-byte Data.
  Client functions use the exact J2534 v04.04 argument counts/types.
- There is no service connectivity in M3; `PassThruOpen` returns
  `ERR_DEVICE_NOT_CONNECTED` and sets the handle to zero. All functions
  fail closed with bounded outputs and no CAN I/O, fake VIN, source-data
  leakage or implied hardware/firmware claims.
- `PassThruWriteMsgs`, periodic TX, voltage and IOCTL refuse operations
  with `ERR_NOT_SUPPORTED`. Read returns no messages. `GetLastError`
  writes a short non-identifying per-thread status into the J2534-mandated
  caller buffer (80 bytes minimum).
- The separate `src/virtualcar.c` legacy x86 simulator and its current
  regression workflow remain completely unchanged.
- Neither CMake nor the new GitHub Actions job uploads/publishes the M3 DLL.
  Do **not** add PassThruSupport registry entries or launch it as a working
  adapter. No vehicle communication has been implemented.

## Verification

CI workflow `.github/workflows/managed-migration.yml` runs M3 on Windows
2022 in **two separately compiled target architectures**: Win32 and x64.
For each target, standard-library PE parsing checks IMAGE_FILE_MACHINE,
PE32/PE32+, DLL characteristics and the exact undecorated 14-export set.

The matching-bitness C++ smoke runner executes eight groups:
1. Windows LoadLibrary/GetProcAddress for all 14 exact function names.
2. Device Open returns disconnected and zero handle; null guards.
3. Channel Connect/Disconnect/Close refuse state and clear handle.
4. ReadMsgs returns no messages, clears count and preserves caller data.
5. WriteMsgs refuses even write-like UDS bytes, never reports TX.
6. Filter and periodic-TX functions refuse activation and zero IDs.
7. Voltage, IOCTL and version refuse unsupported capabilities.
8. GetLastError is bounded, generic and isolated between threads.

These gates prove **binary ABI/load/error behavior only**. No actual
CAN/ISO-TP/J2534 sessions, VIDA or SectorV vehicle recognition, Dvinholm
end-to-end test, VMware guest execution or physical DiCE testing are claimed.

## Next gates

- M4: C++ transport/ISO-TP/filters/queue and timing parity with the known
  existing C implementation, independent x86 and x64 tests.
- M5: authenticate local Windows Named Pipes to a separate C# .NET10 service,
  connection retry and cancellation; no SQLite access per CAN frame.
- M7: load the functional x64 C++ DLL from Dvinholm's J2534 path and run
  deterministic read-only synthetic ECU tests before any real-car claim.

Persistent state lives in `docs/progress/CURRENT.md` and
`NEXT_CHAT.md`. Exact cross-chat continuation phrase: **virtual car**.
