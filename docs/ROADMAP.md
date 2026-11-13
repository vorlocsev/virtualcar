# Virtual Car roadmap (updated after dev30)

## Baseline available in development
- User-supplied VirtualCarJ2534 source v0.3.6.6 under emulator/, with observation-only P2 Vehicle Core integration.
- J2534 READ128 compatibility fix and offline regression checks.
- Configurable emulator ECU profiles, B9FB/B9FC frame replay and 142-byte F106 fixture support.
- Passive 11/29-bit CAN observation tools, early P2 source research, and read-only SavvyCAN CSV statistics.
- Privately supplied donor profile **is not** part of the repository.

## Verified migration checkpoint (2026-11-07)

- M5A-M5D-2eB local C# Host and C++20 read-only synthetic IPC migration:
  Windows VMware feature and post-merge validation SUCCESS.
  See [PR #125](https://github.com/vorlocsev/virtualcar/pull/125),
  [PR #128](https://github.com/vorlocsev/virtualcar/pull/128),
  [post-merge VMware #42375477826](https://github.com/vorlocsev/virtualcar/actions/runs/42375477826).
- Test boundary: 8/8 native CTest for x86 and x64; C# Host 17/17;
  Python 252; three Host failures/cancellation and recovery using only
  sealed synthetic fixtures. Fail-closed C++ J2534 DLL remains unlinked.
- This is NOT proof that SectorV/VDASH/VIDA detects XC90 V8 MY2009
  and not evidence of real CAN traffic, DiCE compatibility or OEM responses.

## Development priorities
1. P0: Verified CEM identification for XC90 V8 MY2009. Investigate A3, A6, B9F0 and P3/29-bit routes using trusted response captures. Preserve existing B9FB replay.
2. P0: Correct J2534 transport boundaries, channel/filter identity, read/write semantics, and READ128 real-world validation.
3. P1: Read-only ECU identification including VIN and ECU topology, with per-model profiles and provenance for each DID.
4. P1: Offline CAN-state model (Off/Sleepy/Awake/Active) using *synthetic* signals and explicit model-year gates; do not interpret status frames as D2 normal-mode confirmation.
5. P1: VMware end-to-end tests with a separate adapter installation; compare J2534 diagnostics to the previously verified DLL.
6. P2: Physical J2534 testing only after emulator-only milestones, with no programming/security operations.

## PR and release gates
- Every task: one focused feature/fix branch -> PR to development; normally 6–8 meaningful checks.
- GitHub Actions must pass on the PR HEAD SHA; distinguish unit tests from real VMware/device testing.
- development -> main PR #2 currently stays in draft until end-to-end evidence is provided.
- No Stable release or merge based solely on source compilation, synthetic VIN, lab fixtures, or assumed CEM positive responses.

See [workflow](CHAT_GITHUB_WORKFLOW_RU.md) and [provenance](PROVENANCE.md).

## External protocol-source integration gate (2026-11-13)
- See [volvo-vida-diagnostics applicability review](research/volvo-vida-diagnostics-applicability.md) and `emulator/tests/test_vida_transport_boundaries.py`.
- Retain separate Volvo P2 D2 and standard ISO-TP framing; verify J2534 ABI/flags against independent references, not against the Python client wrapper as a vendor/DiCE implementation.
- Do not import V40 2017/V60 2015 DBC data into the XC90 V8 MY2009 emulator or treat generic UDS settings as VIDA timings.
- Research and synthetic framing regression are not an original VIDA ReadVin PASS; unchanged acceptance gates remain in force.

## VIDA 2014D CarCom source cross-check (2026-11-13)
- Review [spnda/volvo_vida_db](research/spnda-volvo-vida-db-applicability.md) for VIDA `T161` / `T160` profile → `T100/T121` ECU/config → `T122/T123` protocol/bus → `T111` service chain. Treat default ECU rows as *candidate topology*, not diagnosed ECUs.
- The B9FB shape auditor now reports a conditional `vida2014d_d2_rx_filter_candidate` based on the documented odd-29-bit-response-ID J2534 mask. Actual 29-bit flags, channel/baud, filter and client acceptance stay unverified.
- Keep original VIDA service/route selection and opt-in synthetic B9FB playback as next owner-VMware gates. Do not enable D2 keep-alive, populate A3/A6/B9F0 responses, or import SQL credentials from external code.
