# Virtual Car contributor and agent operating rules

These rules govern work in this repository, including automated coding assistants.
Scope: **Virtual Car only**; do not apply changes to Dvinholm or other repositories.

## Autonomous PR and CI rule (owner authorization, 2026-11-08)

**Default to action, not an approval loop.** When the owner asks to continue development or has defined an unambiguous next stage:

1. Inspect the current repo, active work, and branch protections before editing.
2. Implement the next bounded, reviewable stage on a dedicated branch. Create/open a PR **yourself** whenever repository permissions and available tools allow. Do not wait for a separate "open PR" instruction.
3. Run relevant local tests, lint and static checks yourself. Trigger PR CI / the approved workflow **yourself whenever the available integration permits**. Poll or fetch the result during the current work session when possible; report the actual job URL and conclusion.
4. A PR may remain Draft when blocked by absent evidence, unrun CI, unresolved review, or incomplete work. Mark ready or merge only when applicable checks, permissions and repository protection gates are satisfied. Never claim a merge happened before GitHub confirms it; never bypass rules to force a merge.
5. The owner has authorized publishing testable Virtual Car **builds** when the stage's relevant quality gates pass. This is not permission to publish original VIDA files, proprietary binaries, real VINs, CAN traces, passwords, or to claim an emulator function is proven when it is not. Distinguish CI artifact from GitHub Release and verify the link before stating publication.
6. **Do not create routine stage checkpoints or checkpoint-only PRs.** Keep development moving. Record test results, blockers and relevant links concisely in the main development PR and a short final status report. Historical checkpoint files may remain as archive; no new checkpoint document is required.
7. If a tool, credential, physical device, licensed input or workflow trigger is unavailable, complete all feasible preparation in the current session, record the blocker, and provide the minimal exact next step. Never imply the inaccessible action was carried out and never promise asynchronous work without a scheduled task.

## Persistent Windows/VMware runner safety

- The self-hosted Windows VMware runner is owner-controlled and persistent. Do **not** execute arbitrary PR head code through `pull_request_target`, expose secrets, broaden workflow write permissions, or allow mutable, unreviewed refs.
- Existing owner-only manual dispatch from `main` may select **immutable, reviewed commit SHAs** that are deliberately allowlisted. Maintain the repository/actor/ref gates and runner restrictions; first review any workflow policy changes.
- Never create a release from failed, cancelled, missing or unverified CI, unless a separately labeled experimental source-only artifact is explicitly within the stage's defined scope.
- Diagnose and document failed runs rather than masking them.

## Research and emulator evidence boundaries

- Static VIDA XML / SQL ID matches and synthetic fixtures are **research evidence**, not proof of an actual selected script, positive ECU response, VIN acceptance or protocol implementation.
- Preserve read-only testing unless a later stage explicitly authorizes otherwise; do not fabricate target-car CEM responses or expose licensed/private donor material.
- Record separately what passed offline and what still needs real SectorV / VDASH, original selected VIDA data, VMware tests or physical J2534 verification.

## Required completion format

At the end of each active development turn, give a **brief** status: what changed, PR/commit link, tests actually run, blockers and build/release link when available. No stage checkpoint document or mandatory fixed count of tests. Prefer completing the available PR/CI steps yourself over instructing the owner to do routine tool-accessible work.
