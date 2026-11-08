# Checkpoint P0-VIN-04: immutable Windows CI source is now allowlisted on main

Date: 2026-11-08
Repository: `vorlocsev/virtualcar`
Checkpoint stage: CI policy activation, not emulator behavior
Pre-checkpoint source: merge of PR #193 into `main`
Verified merge commit: `18fdc1d9b454423f16d3ab3433abf4f9fdc93e76`
Pinned source to test: `3e90a0d30d63133f489b8ce12894ac9288b6d340` (Draft PR #192)

## Completed
- Reviewed exact PR #193 diff. Its only executable workflow change adds the reviewed immutable P0-VIN-02 SHA as a `workflow_dispatch.inputs.source_ref.options` choice.
- Marked PR #193 ready and merged it to main using a SHA-leased squash merge.
- Re-fetched the main workflow and confirmed the merged source-ref option is present.
- Confirmed the stage checkpoint from PR #193 is present on main.
- No CEM/J2534 emulator behavior, physical adapter, ECU replies, releases, or binary packaging changed.

## Eight stage verification groups

1. **GitHub merged state and immutable pinned SHA**: PR #193 reports merged, merge SHA verified; selected P0-VIN-02 source SHA is present exactly once: PASS.
2. **Source selection**: workflow_dispatch retains `type: choice`, and `actions/checkout` still uses the `source_ref` input: PASS.
3. **Owner authorization**: job retains `github.repository == 'vorlocsev/virtualcar'` and `github.actor == 'vorlocsev'`: PASS.
4. **Trusted dispatcher**: the manual job path remains restricted to `workflow_dispatch` from `refs/heads/main`: PASS.
5. **Isolated runner**: `runs-on: [self-hosted, Windows, X64, virtualcar-win]` unchanged: PASS.
6. **No untrusted PR execution**: `pull_request` and `pull_request_target` event triggers absent: PASS.
7. **Full Python suite wired**: `python -m unittest discover -s emulator/tests -p 'test_*.py' -v` remains included: PASS.
8. **No release artifact upload**: neither `actions/upload-artifact` nor `softprops/action-gh-release` was added: PASS.

All eight items are **static/repository checks**, not claims of an executed Windows job.

## CI and evidence state
- GitHub integration available in this session supports fetching runs and rerunning existing jobs, but **not dispatching a new workflow**. An owner-only `workflow_dispatch` was NOT initiated.
- No exact-SHA Windows VMware run URL or test conclusion exists from this action; leave CI as **NOT RUN**.
- The new Python analyzer had nine synthetic-only tests verified at P0-VIN-02, but no original target VIDA selected script or service catalog has been processed as part of this stage.
- Physical J2534, client VIN acceptance and real ECU response: **UNVERIFIED**.
- Build artifact: **NOT PUBLISHED**. GitHub Release: **NOT PUBLISHED**.

## Ready-to-run owner command

From an authenticated GitHub CLI session with owner access:

```powershell
gh workflow run vmware-development-validation.yml -R vorlocsev/virtualcar -r main -f source_ref=3e90a0d30d63133f489b8ce12894ac9288b6d340
```

After successful dispatch, capture the actual run ID/URL, job statuses and `git rev-parse HEAD`; do not infer the selected source from the workflow's `main` trigger SHA. Create next checkpoint **only after** observed results.

## Next
- Obtain an authorized Windows CI run for the exact source SHA.
- Analyze failures in Python / C / Go / C++ / .NET if present.
- Keep Draft PR #192 unmerged until applicable checks and source evidence gates are satisfied.
- Publish a test build only when there is genuinely testable emulator functionality and required safety checks pass.
