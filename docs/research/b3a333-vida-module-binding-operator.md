# B3A333 — VIDA process → virtual J2534 module binding

Scope: read-only, owner-selected process-module observation. The checker
does not start VIDA, load a J2534 DLL, modify the registry, transmit CAN,
open a process by PID, read XML contents or print private path/hash/VIN data.

## Source basis and changes

Reuse the existing SectorV process binding checker
emulator/tools/audit_vmware_sectorv_process.ps1 instead of duplicating
its Windows Toolhelp module snapshot, 32-bit J2534 registration lookup,
reference byte-equivalence and PE32 architecture checks.

The original VIDA process name is not determined by a synthetic CI test.
Only on explicit operator request, -OperatorSession with
-VidaProcessName accepts the closed candidates iexplore, java,
VidaMonitor, w3wp. These are name matches, not confirmed authentic
original VIDA executable identities. A reference x86 virtual
VirtualCarJ2534.dll path must be supplied using -ReferenceDll.

Example, on an operator's own isolated Windows guest, only when the
original authorized client is already open (the name is an EXAMPLE):

    $script = '.\emulator\tools\audit_vmware_sectorv_process.ps1'
    $virtualDll = 'REPLACE_WITH_OWNER_VERIFIED_PRIVATE_X86_DLL_PATH'
    & "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File $script -OperatorSession -VidaProcessName iexplore -ReferenceDll $virtualDll

No directory scan or guessed DLL path is performed. The operator must
choose the right process name after independently observing the VM.
Do not execute the script against a live physical interface as a way
to test ECU communication; it is only a passive module inspection.

## Strict evidence boundary

A module path matching the canonical registered Virtual Car x86 J2534
DLL means a module with that path appeared in one name-matched process
snapshot. It is not evidence the name-matched process is original VIDA,
or that the loaded binary's memory bytes match its disk file.
Byte-equivalence is only the two readable disk file snapshots.
Multiple same-name processes, unreadable or incomplete module lists,
and absent registered libraries are distinct outcomes, not proof of
failure by an original VIDA process elsewhere.

The new report schema is virtualcar-vida-process-binding-operator-v1.
It contains only bounded categories, never PID/path/hash/CAN/VIN or raw
process title. It always refuses to assert:
- authenticated original VIDA executable;
- active diagnostic.config.xml loaded by that process;
- effective DiagnosticConnection runtime setting;
- original ReadVin GetScript selection;
- J2534 TX/RX or authentic CEM provenance;
- GUI VIN acceptance and ECU identification.

If a name-matched module and reference disk bytes are both verified,
the next gate is STILL independent effective configuration-source
observation and ReadVin script progression. B3A332's static XML
candidate mode is not promoted into a runtime setting.

## Checks and non-changes

Existing automatic VMware process-binding selftest is extended with
eight synthetic VIDA report classifications, closed-output privacy and
invalid process name rejection. CI never executes the original VIDA GUI
or chooses an actual operator process.

Prior B3A332 PR #409 exact development SHA
c1f80c6c4827d2302e7d244f45d22ab3aca2a26c
VMware #44661167473 SUCCESS 36/36, Python 1035 pass / 4 skipped.

No change to the emulator DLL, B9FB/CEM synthetic fixture, VIDA
configuration, native registry, physical J2534, main branch or release.
