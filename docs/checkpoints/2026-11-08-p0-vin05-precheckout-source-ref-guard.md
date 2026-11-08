# P0-VIN-05 checkpoint: precheckout source-ref allowlist gate

Date: 2026-11-08
Project: Virtual Car
Branch: `ci/p0-vin05-validate-selected-source-before-checkout`
Scope: private Windows VMware CI trust boundary
Workflow implementation commit: `00f9794e850daceed64b5f1efc4f2da5365562b5`
Workflow final blob SHA-1: `9d8b814fa6f7de87ece00ef2be1a49fbca19b672`
Pinned research source under test: `3e90a0d30d63133f489b8ce12894ac9288b6d340` (Draft PR #192)

## Changes

The existing owner-only workflow `.github/workflows/vmware-development-validation.yml` now includes two safety steps:

1. `Validate owner-approved source ref before checkout` runs **before actions/checkout**. Reads `inputs.source_ref || development` via an environment variable rather than interpolating it inside PowerShell. Performs exact case-sensitive membership against the 32 explicitly approved source refs already shown under `workflow_dispatch.inputs.source_ref.options`. Rejects all other values, including API-supplied values not in the list, and prevents a `push` event from selecting any source besides `development`.
2. `Verify immutable commit matches selected SHA` runs **after checkout**, before running tools. For a 40-hex source ref it requires `git rev-parse HEAD` to equal that exact SHA.

The original steps, runner labels, job gate, workflow permissions, command invocations and original 32 selectable values remain unchanged. Any future option change must synchronize the precheckout allowlist. No new untrusted PR execution, privileged permissions or uploads.

## Verification: eight groups

Static checks performed against the fetched GitHub `main` and feature-branch workflow blobs:

1. Existing 32 workflow options unchanged, unique and complete: PASS.
2. Precheckout case-sensitive allowlist contains exactly the 32 options: PASS.
3. Only two new steps added; original 20 steps preserved and ordered: PASS.
4. Guard executes before checkout and pinned-SHA verification after checkout: PASS.
5. The untrusted ref is passed through an environment variable; no direct PowerShell string interpolation: PASS.
6. Owner identity, main-only manual dispatch, private runner labels and permissions unchanged: PASS.
7. Existing Python, Go, C/C++, .NET checks are retained; no PR-trigger or upload/release step introduced: PASS.
8. Fetched final workflow file has valid size (<50 kB), expected insertions and no accidental duplicated steps: PASS.

**11/11 individual static assertions PASS across these eight groups.** This is a source/diff review, **not** a PowerShell parser runtime test or a Windows CI run. A broken intermediate feature-branch edit was detected by these checks and replaced with a corrected full workflow before PR submission; only the final blob above is proposed for merge.

## Explicitly unverified and release state

- New workflow PowerShell execution on actual Windows runner: NOT RUN.
- Owner-only manual `workflow_dispatch` for pinned PR #192 SHA: NOT DISPATCHED (current GitHub integration does not expose a new-workflow-dispatch action).
- Actual selected original VIDA XML and same-installation T111 CSV: NOT TESTED.
- Client VIN accepted / physical J2534 / real ECU RX: NOT VERIFIED.
- Virtual Car Windows build or GitHub Release: NOT PUBLISHED.

## Next stage

After protected workflow change reaches `main`, run the existing owner-only VM workflow with the exact SHA `3e90a0d30d63133f489b8ce12894ac9288b6d340`; verify job's checked-out HEAD, full test results and any actionable failures. Only then evaluate a testable emulator build, rather than a research-only release.
