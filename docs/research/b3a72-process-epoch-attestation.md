# B3A72 — exact process-creation epoch correlation

## Purpose

B3A63 correlated the D2 B9FB request, a live PS DLL module snapshot and the native Active INI marker using the text PID. A PID can be reused after a process exits, so this was deliberately classified as `CORRELATED_SAME_TEXT_PID_EPOCH_NOT_ATTESTED`.

B3A72 adds a Windows process-creation FILETIME marker to the native log and captures the live process creation FILETIME in the read-only Toolhelp snapshot. The auditor compares the two exact 64-bit values in memory. Neither the PID nor the FILETIME is emitted in the categorical report.

## Native marker

During the native `PassThruOpen` configuration initialization (`load_config()`), `GetProcessTimes(GetCurrentProcess(), ...)` reads the host process creation FILETIME. The DLL writes the value as eight big-endian bytes in the private native log under:

`Process creation FILETIME (BE)`

The marker is written before the `Active INI` marker and the fixture metadata. It is diagnostic metadata only; it is not a CAN frame, J2534 payload, ECU identity or protocol response.

## Live process snapshot

The existing read-only Toolhelp process/module snapshot uses `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` and `GetProcessTimes` both before and after the PID-based module snapshot. It accepts the process creation FILETIME only when both reads are available and exactly equal, rejecting PID reuse during enumeration. The numeric value stays in memory and is not serialized.

## Acceptance logic

The B3A72 audit:

1. Locates the D2 B9FB request in the B3A45 append window.
2. Selects the latest process-epoch marker for that host/PID before the request.
3. Requires an Active INI marker after that epoch marker and before the request.
4. Requires the exact PS DLL module path in the live process snapshot.
5. Compares the logged and live process-creation FILETIME values exactly.
6. Keeps fixture metadata classification and disk SHA as separate evidence.
7. Emits only categorical booleans/counts/statuses; no PID, FILETIME, paths, VIN or raw frames.

Statuses distinguish missing/malformed marker, unavailable live process time, epoch mismatch (including PID reuse), and exact epoch match.

## Limits

An exact process-epoch match links the historical native log records to the same currently live process instance. It does **not** prove the exact INI bytes read by Windows, the contents of the in-memory DLL, which J2534 entry point VIDA called, ECU RX delivery, VIN acceptance, OEM authenticity, T111/T122, or physical J2534 behavior.

The old B3A45 log has no process-epoch marker and cannot be retroactively attested. A fresh native DLL build and a new process initialization are required. Any deployment to the installed provider, Registry32, INI or VIDA requires separate owner approval. This PR is source-only: no installed files, provider settings, registry, VIDA, VMware, CI jobs or physical hardware are changed or exercised.
