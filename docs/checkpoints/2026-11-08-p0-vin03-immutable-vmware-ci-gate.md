# Checkpoint P0-VIN-03: immutable SHA allowlist for owner-only VMware CI

Date: 2026-11-08
Repository: vorlocsev/virtualcar
Branch: ci/p0-vin02-immutable-catalog-ci-checkpoint
Base: main
Related research: Draft PR #192
Pinned source commit: `3e90a0d30d63133f489b8ce12894ac9288b6d340`
Workflow change commit: `38a03ea07aaf5dacea88bd848055ddd9e7f2f244`

## Scope
A single safe option was added to the pre-existing `workflow_dispatch.inputs.source_ref.options` list in `.github/workflows/vmware-development-validation.yml`:

```yaml
          # P0 VIN-02 static catalog tests: immutable source SHA from Draft PR #192.
          - 3e90a0d30d63133f489b8ce12894ac9288b6d340
```

No executable build steps, shell commands, job permissions, runners, filters, or trigger types were changed. The workflow is *owner-only* and *self-hosted*; manual dispatch originates on `main`, and checkout can select only explicitly approved choices. The exact SHA is immutable, unlike a moving PR branch.

## Verification / checklist (8 checks)
1. Pinned SHA equals the current approved Draft PR #192 head at inspection: PASS.
2. Workflow file matches `main` byte-for-byte except for the one intended comment+SHA entry: PASS.
3. Pinned SHA appears exactly once in the source-ref choices: PASS.
4. Owner-actor and `main` manual dispatch condition remain unchanged: PASS.
5. Self-hosted `[self-hosted, Windows, X64, virtualcar-win]` runner label unchanged: PASS.
6. No `pull_request` trigger introduced: PASS.
7. No artifact upload / release publishing step added: PASS.
8. Immutable entry is present under the existing source_ref choice allowlist: PASS.

Validation is a static, exact-source comparison. **No GitHub Actions workflow run is claimed.**

## Outstanding gates
- This change is only in its feature branch. It must be reviewed and merged to `main` before the option exists in the dispatchable workflow definition.
- The GitHub integration here does not provide an authorized workflow dispatch operation; no workflow run was started.
- Full Windows x86/x64/Go/.NET CI: NOT RUN on this SHA.
- Original private selected ReadVin XML / same-installation T111 CSV: NOT TESTED.
- Actual ECU response, VIN accepted in SectorV and physical J2534: NOT VERIFIED.
- New binary artifact / GitHub Release: NOT PUBLISHED.

## After merge
Trigger the existing owner-only workflow from `main`, choosing the exact SHA:
```powershell
gh workflow run vmware-development-validation.yml -R vorlocsev/virtualcar -r main -f source_ref=3e90a0d30d63133f489b8ce12894ac9288b6d340
```
Record the resulting run URL, conclusion, checked-out `git rev-parse HEAD`, and test/job results as **a new checkpoint**. Do not promote P0 VIN support or publish a new runtime release based on static analysis alone.
