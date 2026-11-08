# Virtual Car development instructions

These instructions apply to coding agents working in this repository. **For a new chat/session, read [NEXT_CHAT.md](NEXT_CHAT.md) first** and confirm its checkpoint against the live GitHub refs/Issues/PRs/Actions. See docs/CHAT_GITHUB_WORKFLOW_RU.md for the operational process.

## Source of truth
- Use GitHub source and CI results as the authority. The uploaded ZIPs from historical stages are archival, not the live source of truth.
- main is the reviewed baseline; development integrates verified branches. For a task, branch from development and open one focused PR into development. The existing development-to-main PR is a separate release gate.
- Treat emulator/ as the actual v0.3.6.6-derived J2534 emulator source on development; proxy/ is the tracing proxy. Do not confuse them.

## Changes
- Work in meaningful increments, normally 1 issue, 1 focused PR, 6-8 groups of relevant checks. Avoid iterative empty documentation-only PRs or hundreds of tiny regressions.
- Verify existing implementation and CI before writing code. Reuse the actual source files; do not regenerate complete repositories from ZIPs.
- Preserve existing B9FB replay. CEM A3, A6, B9F0 and other incomplete diagnostics must not receive invented positive responses.
- Keep read-only lab behavior. Do not add programming, security-access or immobilizer-bypass functionality.
- Every code change needs tests covering behavior, failure modes and regressions; mark hardware/VMware checks as not performed until evidence exists.

## Automatic VMware CI is mandatory
- The authoritative self-hosted workflow is `.github/workflows/vmware-development-validation.yml`. **Every push to the trusted `development` branch automatically starts CI**, including workflow, code, test, and documentation-only changes. Do not add `paths` or `paths-ignore` filters that silently skip development commits.
- Normal agent workflow: implement on a focused branch; run available local checks and review the diff; merge the approved change into `development`; then **look up the GitHub Actions run for the exact resulting development commit SHA**. Inspect its conclusion, failing steps and logs. A run on an earlier SHA, a queued run, or an absence of a run is never a green result.
- If CI fails, diagnose the real failure, fix via a focused reviewed PR and allow the next `development` push to trigger a fresh run. Do not repeatedly rerun unchanged failures, bypass tests, or claim an incomplete stage as verified.
- Do not ask the user to execute `gh workflow run` or routine PowerShell commands. Use automatic development-push CI and connected GitHub tools within available permissions. If an exceptional manual action is impossible, report the limitation precisely instead of claiming it was performed.
- Preserve the existing runner safety boundary: owner-actor requirement, trusted development push, manual dispatch only from main with allowlisted source refs, no PR code execution on a persistent self-hosted runner, read-only token and no automatic release publishing.
- A successful CI proves only the checks that actually ran. Distinguish root tracing-proxy object compilation, legacy emulator DLL linking, offline diagnostics, and physical J2534/SectorV/VIDA VIN acceptance.

## Privacy and attribution
- Never commit donor VINs, private INI profiles, raw J2534 logs, credentials, proprietary binaries or ECU dumps.
- Synthetic fixtures must be labeled synthetic. Redaction must not be represented as a real vehicle-identification response.
- Keep externally researched CAN IDs model-year-specific; early P2 250 kbit/s HS mapping is not evidence for XC90 V8 2009 500 kbit/s.
- Third-party GPL code must not be copied without a license review; link and summarize external research independently.

## Session handoff
- After a significant task PR is merged into development, update NEXT_CHAT.md with the new verified state and exact next actionable Issue.
- New sessions start with the development branch, not default main; do not rely on previous chat messages or versioned ZIPs.

## Chat response contract
- On 'далее', check issue/PR/CI status, continue the current highest-priority unblocked issue and produce a real repository change when justified.
- Report only: what changed, commit/PR, verified checks, unverified blockers, next step. Keep it concise and in Russian.
- No new downloadable ZIP unless needed for Windows/VMware manual testing or explicitly requested. Prefer versioned CI artifacts.
- Do not claim a build, PR merge, GitHub upload, test or VMware run without confirming it from the relevant tool output. For merged changes, include the exact automatic VMware CI run and its conclusion.
