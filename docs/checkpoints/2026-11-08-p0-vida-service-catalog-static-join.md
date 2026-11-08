# Virtual Car checkpoint: P0 VIDA service catalog static join

Date: 2026-11-08
Status: implementation checkpoint; evidence / CI gates remain open
PR: #192 (Draft, stacked on Draft #191)
Pre-checkpoint HEAD: ff350e3bf380393930c55338c878c601a44c4dda

## Completed this stage
- Added `emulator/tools/audit_vida_readvin_service_catalog.py`: bounded local XML ZIP + CSV static classification of ReadVin.ServiceId against carcom.T111_Service.id.
- Added `emulator/tests/test_audit_vida_readvin_service_catalog.py`: nine synthetic test cases for catalog match/missing/duplicate, XML property overrides, parser shape, privacy and CLI/output safety.
- Added `docs/research/vida-readvin-service-catalog-static-join.md` with invocation and evidence restrictions.
- Scope: research-only. No CEM emulator response, J2534 implementation or release artifacts changed.

## Verification checkpoint
- Nine synthetic tests are implemented. The previous development summary reported 9/9 locally; this checkpoint does not independently establish an exact-current-head CI run.
- CI on the exact PR #192 HEAD: NOT RUN / NOT CONFIRMED.
- Selected original owner ReadVin XML ZIP and same-installation T111_Service.csv: NOT TESTED in this stage.
- Actual GetScript selection: NOT VERIFIED.
- Exact CarCom mode/definition, VIN accepted by SectorV, ECU response, physical J2534: NOT VERIFIED.
- No release or build published at this checkpoint.

## Owner-approved build publication policy (effective 2026-11-08)
- Owner authorizes publishing Virtual Car build artifacts when a stage yields a testable runtime build.
- Create a durable checkpoint after **each completed development stage**, recording source SHA, changed files, tests executed/passed/failed/not-run, CI run link, blockers, next gate and exact release/artifact link if any.
- Prefer draft PRs/branch builds until tests and applicable Windows/VMware CI pass. Do not represent research-only static analysis as a working vehicle emulator.
- Keep original VIDA DLLs, XML, SQL database/exports, VINs, real CAN captures, passwords and private device information out of public artifacts.
- Distinguish build artifact published from GitHub Release published; do not claim either without a verified URL and success result.
- No automatic merging of incomplete Draft PRs. Record a failed or missing CI check as an explicit blocker.
- Complete 6-8 relevant checks per stage when feasible; retain negative and not-executed results rather than claiming implicit success.

## Next gate
1. Review exact implementation and execute the nine synthetic tests in the appropriate environment.
2. Run exact-head private Windows VMware CI when the authorized guarded workflow is available.
3. On owner machine, inspect the actual selected ReadVin XML ZIP and corresponding T111_Service.csv and preserve only redacted counts.
4. If the join is unique and original installation provenance independently verified, analyze CarCom service/mode/definition without inventing wire payloads.
5. Reassess whether this stage warrants a Windows diagnostic build; do not publish an unchanged emulator as a functional VIN fix.
