# Checkpoint: autonomous PR and CI execution policy

Date: 2026-11-08
Project: Virtual Car
Branch: `docs/autonomous-pr-ci-checkpoint-policy`
Stage: governance / development workflow
Policy commit: `8cf181030f49c485411d2a01a34e19122ddd6bae`
Policy file: `AGENTS.md`
Policy Git blob SHA-1: `d8d55debd312a921776a81ab2c2de8acae824511`

## Owner instruction incorporated

The owner requests that the assistant create and launch PRs on its own whenever possible, and has already authorized build publication and per-stage checkpoints. The new rule tells contributors/agents to open PRs, run available checks, and when tool access permits trigger approved CI, without requesting routine approvals. It does **not** waive branch protections, allow untrusted code to run on the persistent VMware runner, or claim offline tests establish vehicle identity.

## Stage checks

The exact committed AGENTS.md was fetched from GitHub and evaluated by eight static source assertions:

1. Autonomous PR creation directive: PASS.
2. Autonomous available CI triggering directive: PASS.
3. Checkpoint after every completed stage: PASS.
4. 6-8 applicable verification items recorded: PASS.
5. Explicit ban on executing arbitrary PR code on persistent VMware runner: PASS.
6. Conditional build publication authorization: PASS.
7. No false success claims when tools are unavailable: PASS.
8. Static VIDA evidence does not establish real VIN acceptance: PASS.

Total: **8/8 PASS**. These are documentation invariant checks, not Windows CI, which is not relevant to policy-only changes and has not run.

## Changes and impact

- Added `AGENTS.md` at the repo root; this is documentation/policy only.
- Added this checkpoint.
- No binaries, protocol handlers, emulator responses, test fixtures, runner workflow or release files touched.
- No new Virtual Car build published.
- Project-wide operational effect will apply once this policy PR is merged into `main`; do not claim before confirmation.

## Next

Apply policy via a reviewed PR. For the ongoing P0-VIN research work, prefer autonomous PR creation and CI execution when the GitHub integration exposes the required action. Preserve exact-SHA owner-only VMware workflow safeguards and record any unavailable dispatch in the relevant checkpoint.
