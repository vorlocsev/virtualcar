# Checkpoint P0-VIN-02: exact-blob static catalog unit test verification

Date: 2026-11-08
Repository: vorlocsev/virtualcar
Branch: research/p0-vida-readvin-service-catalog-static-join
PR: #192 (Draft)
Pre-checkpoint commit: f432c78b96d8625c850d48e7477a6c8d4d954c70

## Stage outcome
Verified **exact GitHub blob bytes** of the new privacy-safe VIDA ReadVin/T111 catalog classifier and its synthetic unit tests, then independently executed the actual tests in a clean isolated Python workspace.

Verified files and Git blob SHA-1:
- `emulator/tools/audit_vida_readvin_service_catalog.py`: `c87b89672e4f9b4f847b965b1d31612ef3b31311`
- `emulator/tests/test_audit_vida_readvin_service_catalog.py`: `bf1a7d76af5814de7c272f201f7ce5262c10085c`

Invocation:
```bash
python -m unittest discover -s emulator/tests -p 'test_audit_vida_readvin_service_catalog.py' -v
```

**Executed result: 9 tests, 9 PASS, 0 FAIL, 0 ERROR.** Test cases exercised:
1. Unique static catalog candidate does not imply runtime VIN success.
2. Missing catalog row does not match.
3. Duplicate catalog ID remains ambiguous.
4. Enabled/disabled `propertyhandler` setter treatment.
5. Non-Int, nonliteral, noncanonical and duplicate ServiceId declarations.
6. Invalid catalog headers/rows and XML duplicates/DTD rejected.
7. Private VIN-like tokens, numeric identifiers, row text not leaked.
8. Local CLI creates exclusive, privacy-safe report.
9. Size limits and malformed CSV fail closed.

## Existing Windows CI discovery
`.github/workflows/vmware-development-validation.yml` already runs
`python -m unittest discover -s emulator/tests -p 'test_*.py' -v`.
The new test module is therefore included **when the trusted branch gets run**.
However, the workflow's owner-only `workflow_dispatch` `source_ref` choice allowlist currently excludes this PR branch; no Windows CI run has been confirmed. Do not bypass this control or run untrusted PR code on the persistent self-hosted VM.

## Explicitly unverified
- Windows x86/x64 C++/J2534 builds, self-hosted VMware gates: **NOT RUN** for exact PR #192 HEAD.
- Private original selected ReadVin XML, same-installation `T111_Service.csv`: **NOT TESTED**.
- `GetScript` selection, service definition and actual CAN behavior: **NOT VERIFIED**.
- Actual CEM ECU response, VIN accepted by SectorV/VDASH: **NOT VERIFIED**.
- New Virtual Car build/artifact/release: **NOT PUBLISHED**, because this stage only verifies static research tooling.

## Next stage
Either perform owner-authorized read-only source audit with exact original selected VIDA XML + T111 service catalog on the same host, or prepare an owner-reviewed minimal workflow allowlist update on `main` to permit exact-sha Windows CI. Avoid replacing a missing original ECU reply with a fabricated fixture.

## Publication and checkpoint policy
The owner has authorized publishing build artifacts for Virtual Car when testable runtime changes are ready. Record a separate stage checkpoint after each completed stage with actual verification, CI, blockers and build/release link when available.
